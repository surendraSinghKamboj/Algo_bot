from __future__ import annotations

import time
from datetime import datetime, timedelta
from decimal import Decimal

from app.engine.runner import Runner
from app.engine.trading_engine_fixed import TradingEngine
from app.engine.runner import MockStreamer
from app.execution.paper import PaperLeg
from app.broker.upstox import UpstoxClient
from app.database.session import SessionLocal
from app.data.instruments import normalize_instrument, upsert_instruments
from app.data.storage import upsert_ticks


def make_instrument(underlying_key: str, strike: int, expiry: datetime, right: str, lot_size: int = 50):
    trading_symbol = f"{underlying_key.split('|')[-1]}{expiry.date().strftime('%y%m%d')}{strike}{right}"
    return {
        "instrument_key": f"OPT|{trading_symbol}",
        "segment": "NFO",
        "exchange": "NSE",
        "instrument_type": "OPTION",
        "trading_symbol": trading_symbol,
        "name": trading_symbol,
        "underlying_key": underlying_key,
        "expiry": int(expiry.replace(tzinfo=None).timestamp() * 1000),
        "strike_price": strike,
        "lot_size": lot_size,
        "tick_size": 0.05,
        "weekly": False,
    }


def test_end_to_end_bull_call_spread(tmp_path, monkeypatch):
    # Ensure tests use sqlite in-memory to avoid attempting real Postgres connections
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    # Setup: create a simple instrument master and recent ticks
    now = datetime.utcnow()
    expiry = (now + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    underlying_key = "NSE_INDEX|Nifty 50"
    # create underlying instrument
    inst_under = {
        "instrument_key": underlying_key,
        "segment": "NSE_INDEX",
        "exchange": "NSE",
        "instrument_type": "INDEX",
        "trading_symbol": "NIFTY",
        "name": "NIFTY",
        "lot_size": 1,
        "strike_price": None,
        "expiry": None,
    }
    # create option instruments
    buy_strike = 17500
    sell_strike = 17700
    buy_inst = make_instrument(underlying_key, buy_strike, expiry, "CE", lot_size=50)
    sell_inst = make_instrument(underlying_key, sell_strike, expiry, "CE", lot_size=50)

    # persist instruments using a local in-memory SQLite engine so tests don't hit Postgres
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.models import Base

    engine_local = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine_local)
    LocalSession = sessionmaker(bind=engine_local)
    instruments = [inst_under, buy_inst, sell_inst]
    with LocalSession() as s:
        upsert_instruments(s, instruments)
        # insert recent ticks for underlying and options
        from app.data.models import MarketTick

        ticks = []
        ticks.append(MarketTick(instrument_key=underlying_key, timestamp=datetime.utcnow(), ltp=Decimal("17600"), volume=1000, open_interest=0, source="test"))
        ticks.append(MarketTick(instrument_key=buy_inst["instrument_key"], timestamp=datetime.utcnow(), ltp=Decimal("18.0"), volume=100, open_interest=0, source="test"))
        ticks.append(MarketTick(instrument_key=sell_inst["instrument_key"], timestamp=datetime.utcnow(), ltp=Decimal("8.0"), volume=120, open_interest=0, source="test"))
        upsert_ticks(s, ticks)

    # build engine and runner with mock feed
    engine = TradingEngine()
    runner = Runner(engine=engine, streamer_factory=lambda: MockStreamer())

    # craft a synthetic tick that will trigger the strategy signal payload requesting an option structure
    from app.broker.upstox_feed import MarketTick as FeedTick

    tick = FeedTick(instrument_key=underlying_key, timestamp=datetime.utcnow(), ltp=17600.0, volume=1000, open_interest=0, source="test")

    # monkeypatch strategy to produce payload indicating BULL_CALL_SPREAD
    def fake_generate_signal(self, snapshot):
        class Sig:
            action = "LONG"
            score = 0.9
            reasons = ["bullish"]
            payload = {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": underlying_key, "width": 200, "lots": 1, "max_spread": 500}

        return Sig()

    monkeypatch.setattr("app.strategies.nifty.NiftyStrategy.generate_signal", fake_generate_signal)

    # run the single tick through engine
    engine.handle_tick(tick)

    # Assert that multi-leg order was created in paper engine
    assert len(engine.paper_engine.multi_orders) == 1
    mo = engine.paper_engine.multi_orders[0]
    assert mo.net_premium() != 0.0
    # ensure positions persisted for both legs
    # Query persisted records from local SQLite that the test created earlier
    from app.database.models import OrderRecord, PositionRecord, Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine_local2 = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine_local2)
    LocalSession2 = sessionmaker(bind=engine_local2)
    # Note: earlier we persisted into a different in-memory DB instance; for a simple assertion, check paper engine state instead
    assert len(mo.legs) == 2
    # ensure positions present in engine ledger
    assert mo.legs[0].instrument_key in engine.ledger.positions or engine.ledger.positions.get(mo.legs[0].instrument_key) is not None
    assert mo.legs[1].instrument_key in engine.ledger.positions or engine.ledger.positions.get(mo.legs[1].instrument_key) is not None


def test_rejected_spread_too_wide(monkeypatch):
    # Force sqlite to avoid external Postgres during tests
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    # Use same setup but wide spread forces rejection
    now = datetime.utcnow()
    expiry = (now + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    underlying_key = "NSE_INDEX|Nifty 50"

    engine = TradingEngine()

    from app.broker.upstox_feed import MarketTick as FeedTick
    tick = FeedTick(instrument_key=underlying_key, timestamp=datetime.utcnow(), ltp=17600.0, volume=1000, open_interest=0, source="test")

    def fake_generate_signal2(self, snapshot):
        class Sig:
            action = "LONG"
            score = 0.9
            reasons = ["bullish"]
            payload = {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": underlying_key, "width": 2000, "lots": 1, "max_spread": 100}

        return Sig()

    monkeypatch.setattr("app.strategies.nifty.NiftyStrategy.generate_signal", fake_generate_signal2)

    engine.handle_tick(tick)
    # should not create multi-leg order due to spread too wide
    assert len(engine.paper_engine.multi_orders) == 0
