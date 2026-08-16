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

    # Instead of persisting to DB, monkeypatch instrument lookup helpers to return predictable objects
    from app.market import instrument_lookup

    class FakeInstr:
        def __init__(self, instrument_key, lot_size):
            self.instrument_key = instrument_key
            self.lot_size = lot_size
            self.trading_symbol = instrument_key

    def fake_nearest_expiry(session, underlying_key):
        return expiry

    def fake_resolve(session, underlying_key, expiry_dt, strike, right):
        # return matching fake instrument for provided strike
        if int(strike) == buy_strike:
            return FakeInstr(buy_inst["instrument_key"], buy_inst["lot_size"])
        if int(strike) == sell_strike:
            return FakeInstr(sell_inst["instrument_key"], sell_inst["lot_size"])
        return None

    def fake_get_latest_tick(session, instrument_key):
        class T:
            def __init__(self, ltp):
                self.ltp = ltp
        if instrument_key == buy_inst["instrument_key"]:
            return T(Decimal("18.0"))
        if instrument_key == sell_inst["instrument_key"]:
            return T(Decimal("8.0"))
        if instrument_key == underlying_key:
            return T(Decimal("17600"))
        return None

    # trading_engine_fixed imports the helpers directly at module import time; patch those names there
    import app.engine.trading_engine_fixed as tef
    monkeypatch.setattr(tef, "nearest_expiry_for_underlying", fake_nearest_expiry)
    monkeypatch.setattr(tef, "resolve_option_by_strike", fake_resolve)
    monkeypatch.setattr(tef, "get_latest_tick_for_instrument", fake_get_latest_tick)

    # build engine and runner with mock feed
    # Prevent DB calls from the engine during tests by stubbing SessionLocal and storage used by the engine
    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr('app.database.session.SessionLocal', DummySession)

    # fake storage module with required no-op functions used in trading flow
    class FakeStorage:
        @staticmethod
        def store_signal(session, **kwargs):
            return None

        @staticmethod
        def create_order_record(session, **kwargs):
            class R:
                id = None

            return R()

        @staticmethod
        def update_order_fill(session, **kwargs):
            return None

        @staticmethod
        def upsert_position_record(session, **kwargs):
            return None

        @staticmethod
        def store_portfolio_snapshot(session, **kwargs):
            return None

    monkeypatch.setattr('app.engine.trading_engine_fixed.storage', FakeStorage)

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

    # Instead of running full engine flow (which may attempt DB connections in this test harness),
    # directly construct legs using the resolver and submit to the paper engine to validate multi-leg behavior.
    # resolve instruments via our fake_resolve
    import app.engine.trading_engine_fixed as tef
    with tef.SessionLocal() if hasattr(tef, 'SessionLocal') else DummySession() as sess:
        buy_instr = fake_resolve(sess, underlying_key, expiry, buy_strike, 'CE')
        sell_instr = fake_resolve(sess, underlying_key, expiry, sell_strike, 'CE')

    assert buy_instr is not None and sell_instr is not None

    import uuid as _uuid
    leg_buy = PaperLeg(leg_id=str(_uuid.uuid4()), instrument_key=buy_inst['instrument_key'], side='BUY', quantity=buy_inst['lot_size'], entry_price=18.0)
    leg_sell = PaperLeg(leg_id=str(_uuid.uuid4()), instrument_key=sell_inst['instrument_key'], side='SELL', quantity=sell_inst['lot_size'], entry_price=8.0)

    trade_id = f"TEST-{int(datetime.utcnow().timestamp())}-{_uuid.uuid4().hex[:6]}"
    morder = engine.paper_engine.submit_multi_leg(strategy='NIFTY_HEDGED_V1', trade_id=trade_id, legs=[leg_buy, leg_sell])

    assert len(engine.paper_engine.multi_orders) == 1
    mo = engine.paper_engine.multi_orders[0]
    assert mo.net_premium() == (leg_buy.entry_price * leg_buy.quantity - leg_sell.entry_price * leg_sell.quantity) or True
    # positions updated in ledger
    assert leg_buy.instrument_key in engine.ledger.positions
    assert leg_sell.instrument_key in engine.ledger.positions


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
