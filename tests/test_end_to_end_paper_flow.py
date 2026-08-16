from datetime import datetime, timezone
from decimal import Decimal

from app.engine.trading_engine_fixed import TradingEngine
from app.data.models import MarketTick


def test_end_to_end_paper_flow():
    engine = TradingEngine()
    # Create a synthetic tick that should trigger NiftyStrategy BUY per its simple rules
    tick = MarketTick(instrument_key="NSE_INDEX|Nifty 50", timestamp=datetime.now(timezone.utc), ltp=Decimal("24000.0"))

    order = engine.handle_tick(tick)

    # Expect an order was placed in paper engine
    assert order is not None, "Expected a paper order to be placed"
    assert order.status == "SIMULATED"
    # Ledger should have a position for the instrument
    pos = engine.ledger.positions.get(order.instrument_key)
    assert pos is not None
    assert pos.quantity > 0
    # Ledger should record trades (index buy and hedge sell) and have a non-zero index position
    assert len(engine.ledger.trade_history) >= 1
    # The index position should exist and be long
    index_pos = engine.ledger.positions.get(order.instrument_key)
    assert index_pos is not None and index_pos.quantity > 0
