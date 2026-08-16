from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBreakdown:
    signal_score: float
    regime_score: float
    volatility_score: float
    cross_asset_score: float
    liquidity_score: float
    risk_reward_score: float
    final_score: float
    action: str


class StrategyScorer:
    """Deterministic score model for a regime-aware trade decision."""

    def __init__(self, min_trade_score: float = 0.6):
        self.min_trade_score = min_trade_score

    def score(
        self,
        *,
        signal_score: float,
        regime_score: float,
        volatility_score: float,
        cross_asset_score: float,
        liquidity_score: float,
        risk_reward_score: float,
    ) -> ScoreBreakdown:
        weights = {
            "signal": 0.25,
            "regime": 0.2,
            "volatility": 0.15,
            "cross_asset": 0.15,
            "liquidity": 0.15,
            "risk_reward": 0.10,
        }
        final_score = (
            signal_score * weights["signal"]
            + regime_score * weights["regime"]
            + volatility_score * weights["volatility"]
            + cross_asset_score * weights["cross_asset"]
            + liquidity_score * weights["liquidity"]
            + risk_reward_score * weights["risk_reward"]
        )

        if final_score < self.min_trade_score:
            return ScoreBreakdown(
                signal_score=signal_score,
                regime_score=regime_score,
                volatility_score=volatility_score,
                cross_asset_score=cross_asset_score,
                liquidity_score=liquidity_score,
                risk_reward_score=risk_reward_score,
                final_score=final_score,
                action="NO TRADE",
            )

        if signal_score >= 0.75 and regime_score >= 0.7 and risk_reward_score >= 0.7:
            action = "BUY"
        elif signal_score <= 0.25 and regime_score >= 0.7 and risk_reward_score >= 0.7:
            action = "SELL"
        elif volatility_score < 0.4 or liquidity_score < 0.5:
            action = "HEDGE"
        else:
            action = "BUY_HEDGE"

        return ScoreBreakdown(
            signal_score=signal_score,
            regime_score=regime_score,
            volatility_score=volatility_score,
            cross_asset_score=cross_asset_score,
            liquidity_score=liquidity_score,
            risk_reward_score=risk_reward_score,
            final_score=final_score,
            action=action,
        )
