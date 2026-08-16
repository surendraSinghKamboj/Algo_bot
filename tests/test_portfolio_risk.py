from app.portfolio.ledger import PositionLedger
from app.portfolio.risk import PortfolioRiskAggregator, AutomatedHedgeJob


def test_portfolio_risk_aggregation():
    ledger = PositionLedger(starting_cash=100000.0)
    ledger.apply_fill(instrument_key="A", quantity=10, price=100.0, side="BUY")
    ledger.apply_fill(instrument_key="B", quantity=5, price=200.0, side="BUY")

    prices = {"A": 110.0, "B": 190.0}
    greeks = {"A": 0.5, "B": -0.2}

    agg = PortfolioRiskAggregator()
    summary = agg.assess(ledger, prices, greeks)

    assert summary.cash < ledger.starting_cash
    assert summary.unrealized_pnl != 0
    assert summary.total_delta == 10 * 0.5 + 5 * -0.2


def test_automated_hedge_job():
    job = AutomatedHedgeJob()
    qty = job.propose_hedge(exposure_delta=100.0, hedge_instrument_delta=-0.5, lot_size=1)
    assert qty == 200
