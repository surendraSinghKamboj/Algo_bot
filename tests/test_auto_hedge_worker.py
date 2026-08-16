from app.portfolio.ledger import PositionLedger
from app.engine.auto_hedge_worker import AutoHedgeWorker


def test_auto_hedge_worker_proposes_hedge():
    ledger = PositionLedger(starting_cash=100000.0)
    ledger.apply_fill(instrument_key="A", quantity=10, price=100.0, side="BUY")
    # greeks: A has delta 0.5 -> total delta 5.0
    greeks = {"A": 0.5}
    prices = {"A": 110.0}
    worker = AutoHedgeWorker(ledger, hedge_candidates={"HEDGE1": -0.5})
    proposals = worker.run_once(prices, greeks)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.instrument_key == "HEDGE1"
    assert p.hedge_quantity != 0
