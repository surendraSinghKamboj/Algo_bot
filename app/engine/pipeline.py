from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.execution.order_plan import OrderPlanner
from app.execution.paper import PaperExecutionEngine, PaperOrder, PaperTradeDecision
from app.portfolio.manager import PortfolioManager
from app.strategies.scoring import StrategyScorer


@dataclass(frozen=True)
class DecisionOutcome:
    action: str
    score: float
    order: PaperOrder | None
    reason: str


class TradePipeline:
    """End-to-end decision pipeline for scoring, position sizing, and paper execution."""

    def __init__(
        self,
        *,
        scorer: StrategyScorer | None = None,
        manager: PortfolioManager | None = None,
        paper_engine: PaperExecutionEngine | None = None,
        planner: OrderPlanner | None = None,
    ):
        self.scorer = scorer or StrategyScorer()
        self.manager = manager or PortfolioManager(starting_cash=500000.0, max_portfolio_risk=0.05, max_trade_risk=0.01)
        self.paper_engine = paper_engine or PaperExecutionEngine(trading_mode="PAPER")
        self.planner = planner or OrderPlanner(max_open_risk=0.05, max_trade_risk=0.01)

    def evaluate(
        self,
        *,
        instrument_key: str,
        signal_score: float,
        regime_score: float,
        volatility_score: float,
        cross_asset_score: float,
        liquidity_score: float,
        risk_reward_score: float,
        proposed_risk: float,
        current_portfolio_risk: float,
        daily_loss: float,
        weekly_loss: float,
        drawdown: float,
        correlated_exposure: float,
        entry_price: float,
        stop_loss: float,
        target: float,
        strategy: str = "regime_multi_factor",
    ) -> DecisionOutcome:
        score = self.scorer.score(
            signal_score=signal_score,
            regime_score=regime_score,
            volatility_score=volatility_score,
            cross_asset_score=cross_asset_score,
            liquidity_score=liquidity_score,
            risk_reward_score=risk_reward_score,
        )

        if score.action == "NO TRADE":
            return DecisionOutcome(action="NO TRADE", score=score.final_score, order=None, reason="trade rejected by score threshold")

        quantity = self.manager.position_size(risk_budget=proposed_risk * 500000.0, stop_loss=stop_loss, entry=entry_price)
        order_plan = self.planner.plan(
            signal_action=score.action,
            instrument_key=instrument_key,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            proposed_risk=proposed_risk,
            current_portfolio_risk=current_portfolio_risk,
            daily_loss=daily_loss,
            weekly_loss=weekly_loss,
            drawdown=drawdown,
            correlated_exposure=correlated_exposure,
            strategy=strategy,
        )

        if order_plan is None:
            return DecisionOutcome(action=score.action, score=score.final_score, order=None, reason="risk controls rejected the plan")

        paper_decision = PaperTradeDecision(
            strategy=order_plan.strategy,
            action=order_plan.action,
            instrument_key=order_plan.instrument_key,
            quantity=order_plan.quantity,
            entry_price=order_plan.entry_price,
            stop_loss=order_plan.stop_loss,
            target=order_plan.target,
        )
        order = self.paper_engine.submit(paper_decision)
        return DecisionOutcome(action=score.action, score=score.final_score, order=order, reason=order_plan.notes)
