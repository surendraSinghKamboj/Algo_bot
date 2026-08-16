from app.execution.reconciliation import BrokerState, ReconciliationEngine, ReconciliationMismatch
from app.portfolio.ledger import PositionLedger


def test_position_ledger_tracks_pnl_and_positions():
    ledger = PositionLedger(starting_cash=500000.0)
    ledger.apply_fill(instrument_key="NSE_INDEX|Nifty 50", quantity=25, price=22000.0, side="BUY")
    ledger.apply_fill(instrument_key="NSE_INDEX|Nifty 50", quantity=10, price=22200.0, side="SELL")
    assert ledger.positions["NSE_INDEX|Nifty 50"].quantity == 15
    assert ledger.portfolio_value() > 0


def test_reconciliation_engine_detects_local_broker_mismatch():
    local = PositionLedger(starting_cash=500000.0)
    local.apply_fill(instrument_key="A", quantity=10, price=100.0, side="BUY")
    broker = BrokerState(positions={"A": 8}, cash=500000.0)
    engine = ReconciliationEngine()
    mismatch = engine.compare(local, broker)
    assert mismatch is not None
    assert isinstance(mismatch, ReconciliationMismatch)
    assert mismatch.instrument_key == "A"


def test_reconciliation_engine_allows_matching_state():
    local = PositionLedger(starting_cash=500000.0)
    local.apply_fill(instrument_key="B", quantity=6, price=50.0, side="BUY")
    broker = BrokerState(positions={"B": 6}, cash=500000.0)
    engine = ReconciliationEngine()
    assert engine.compare(local, broker) is None
