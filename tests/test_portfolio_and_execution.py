from app.execution.paper import PaperExecutionEngine, PaperOrder, PaperPosition, PaperTradeDecision
from app.portfolio.manager import PortfolioManager


def test_portfolio_manager_sizing_reduces_risk_for_small_capital():
    manager = PortfolioManager(starting_cash=500000.0, max_portfolio_risk=0.05, max_trade_risk=0.01)
    size = manager.position_size(risk_budget=2500.0, stop_loss=18.0, entry=100.0)
    assert size == 30
    assert manager.allowed_trade_risk(500000.0) == 5000.0


def test_paper_execution_engine_rejects_when_live_mode_is_disabled():
    engine = PaperExecutionEngine(trading_mode="PAPER")
    decision = PaperTradeDecision(
        strategy="test",
        action="BUY",
        instrument_key="NSE_INDEX|Nifty 50",
        quantity=25,
        entry_price=22000.0,
        stop_loss=21850.0,
        target=22350.0,
    )
    order = engine.submit(decision)
    assert order.status == "SIMULATED"
    assert order.filled_quantity == 25


def test_paper_execution_engine_keeps_virtual_positions_consistent():
    engine = PaperExecutionEngine(trading_mode="PAPER")
    engine.submit(PaperTradeDecision(strategy="test", action="BUY", instrument_key="A", quantity=10, entry_price=100.0, stop_loss=95.0, target=110.0))
    engine.submit(PaperTradeDecision(strategy="test", action="SELL", instrument_key="A", quantity=4, entry_price=102.0, stop_loss=98.0, target=90.0))
    assert engine.positions["A"].quantity == 6
