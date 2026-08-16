from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.strategies.scoring import StrategyScorer


@dataclass
class Signal:
    action: str
    score: float
    reasons: Dict[str, float]


class NiftyStrategy:
    """Simple NIFTY strategy engine that produces a signal from a market snapshot.

    Logic (deterministic and conservative):
    - If India VIX < 18 and NIFTY > recent_threshold -> BUY
    - If India VIX >= 25 -> SELL
    - Otherwise NO TRADE

    The engine uses StrategyScorer to compute a final_score used as a sanity check.
    """

    def __init__(self, scorer: StrategyScorer | None = None):
        self.scorer = scorer or StrategyScorer(min_trade_score=0.5)

    def generate_signal(self, snapshot: Dict[str, float]) -> Signal:
        nifty = float(snapshot.get("NIFTY", 0.0))
        vix = float(snapshot.get("India VIX", snapshot.get("india_vix", 0.0)))

        # primitive momentum proxy: compare to an encoded threshold (e.g., rounded tens)
        threshold = (int(nifty) // 100) * 100
        signal_score = 0.5
        regime_score = 0.6 if vix < 20 else 0.4
        volatility_score = max(0.0, 1.0 - (vix / 100.0))
        cross_asset_score = 0.5
        liquidity_score = 0.8
        risk_reward_score = 0.6

        breakdown = self.scorer.score(
            signal_score=signal_score,
            regime_score=regime_score,
            volatility_score=volatility_score,
            cross_asset_score=cross_asset_score,
            liquidity_score=liquidity_score,
            risk_reward_score=risk_reward_score,
        )

        # Now decide action based on simple rules
        if vix >= 25:
            action = "SELL"
        elif vix < 18 and nifty > threshold:
            action = breakdown.action if breakdown.action != "NO TRADE" else "BUY"
        else:
            action = "NO TRADE"

        return Signal(action=action, score=breakdown.final_score, reasons={"vix": vix, "nifty": nifty})
