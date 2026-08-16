from app.engine.pipeline import DecisionOutcome, TradePipeline
from app.execution.paper import PaperExecutionEngine, PaperTradeDecision
from app.portfolio.manager import PortfolioManager
from app.strategies.scoring import StrategyScorer


def test_trade_pipeline_rejects_weak_or_risky_setup():
    pipeline = TradePipeline(
        scorer=StrategyScorer(min_trade_score=0.6),
        manager=PortfolioManager(starting_cash=500000.0, max_portfolio_risk=0.05, max_trade_risk=0.01),
        paper_engine=PaperExecutionEngine(trading_mode="PAPER"),
    )
    outcome = pipeline.evaluate(
        instrument_key="NSE_INDEX|Nifty 50",
        signal_score=0.20,
        regime_score=0.40,
        volatility_score=0.20,
        cross_asset_score=0.30,
        liquidity_score=0.25,
        risk_reward_score=0.10,
        proposed_risk=0.02,
        current_portfolio_risk=0.02,
        daily_loss=-0.02,
        weekly_loss=-0.01,
        drawdown=0.09,
        correlated_exposure=0.12,
        entry_price=22000.0,
        stop_loss=21850.0,
        target=22400.0,
    )
    assert outcome.action == "NO TRADE"
    assert outcome.order is None


def test_trade_pipeline_accepts_safe_trade_and_simulates_execution():
    pipeline = TradePipeline(
        scorer=StrategyScorer(min_trade_score=0.6),
        manager=PortfolioManager(starting_cash=500000.0, max_portfolio_risk=0.05, max_trade_risk=0.01),
        paper_engine=PaperExecutionEngine(trading_mode="PAPER"),
    )
    outcome = pipeline.evaluate(
        instrument_key="NSE_INDEX|Nifty 50",
        signal_score=0.85,
        regime_score=0.80,
        volatility_score=0.70,
        cross_asset_score=0.75,
        liquidity_score=0.90,
        risk_reward_score=0.88,
        proposed_risk=0.006,
        current_portfolio_risk=0.015,
        daily_loss=-0.01,
        weekly_loss=-0.02,
        drawdown=0.08,
        correlated_exposure=0.10,
        entry_price=22000.0,
        stop_loss=21880.0,
        target=22450.0,
    )
    assert outcome.action in {"BUY", "BUY_HEDGE"}
    assert outcome.order is not None
    assert outcome.order.status == "SIMULATED"
    assert outcome.order.filled_quantity > 0
