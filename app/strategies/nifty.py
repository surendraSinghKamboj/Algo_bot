from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from app.strategies.scoring import StrategyScorer


@dataclass
class Signal:
    action: str
    score: float
    reasons: Dict[str, Any]
    payload: Dict[str, Any] | None = None
    regime: str | None = None
    edge: str | None = None
    risk_reward: float | None = None


class NiftyStrategy:
    """Research-driven NIFTY strategy using VIX, trend, momentum and cross-asset checks."""

    def __init__(self, scorer: StrategyScorer | None = None):
        self.scorer = scorer or StrategyScorer(min_trade_score=0.5)

    def _get_value(self, snapshot: Dict[str, Any], *keys: str) -> float:
        for key in keys:
            if key in snapshot:
                return float(snapshot[key])
            lowered = key.lower().replace(" ", "_")
            if lowered in snapshot:
                return float(snapshot[lowered])
        return 0.0

    def generate_signal(self, snapshot: Dict[str, Any]) -> Signal:
        nifty = self._get_value(snapshot, "NIFTY", "nifty")
        vix = self._get_value(snapshot, "India VIX", "INDIA_VIX", "india_vix")
        banknifty = self._get_value(snapshot, "BANKNIFTY", "banknifty")
        gold = self._get_value(snapshot, "Gold", "gold")
        silver = self._get_value(snapshot, "Silver", "silver")
        crude = self._get_value(snapshot, "Crude", "crude")
        usd_inr = self._get_value(snapshot, "USDINR", "usd_inr")

        trend = 1.0 if nifty > 22000 else 0.0
        momentum = 1.0 if nifty > 0 else 0.0
        vix_regime = "LOW" if vix < 18 else "NORMAL" if vix < 25 else "HIGH"
        cross_asset = 0.6
        if banknifty > 0 and nifty > 0:
            ratio = banknifty / max(nifty, 1.0)
            cross_asset = max(0.0, min(1.0, 1.0 - abs(ratio - 2.0) / 2.0))
        cross_asset = max(0.0, min(1.0, cross_asset))

        regime_score = 0.8 if vix_regime == "LOW" else 0.6 if vix_regime == "NORMAL" else 0.35
        signal_score = 0.7 if trend and momentum else 0.45
        volatility_score = max(0.0, 1.0 - (vix / 100.0))
        liquidity_score = 0.8
        risk_reward_score = 0.72 if vix_regime == "LOW" else 0.55 if vix_regime == "NORMAL" else 0.4

        breakdown = self.scorer.score(
            signal_score=signal_score,
            regime_score=regime_score,
            volatility_score=volatility_score,
            cross_asset_score=cross_asset,
            liquidity_score=liquidity_score,
            risk_reward_score=risk_reward_score,
        )

        payload = {}
        if vix >= 25:
            action = "SELL"
            regime = "VOLATILITY_SPIKE"
            edge = "short-bias"
            if nifty > 0:
                payload = {"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        elif vix < 18 and trend and cross_asset > 0.75:
            action = "BUY"
            regime = "TREND_UP"
            edge = "momentum + low-vol"
            if nifty > 0:
                payload = {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        elif 18 <= vix < 25 and cross_asset > 0.7:
            action = "HEDGE"
            regime = "RISK_OFF"
            edge = "volatility control"
            if nifty > 0:
                payload = {"option_structure": True, "structure": "PROTECTIVE_PUT", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        else:
            action = "BUY" if trend and nifty > 0 else "NO TRADE"
            regime = "TREND_UP" if action == "BUY" else "SIDEWAYS"
            edge = "momentum carry" if action == "BUY" else "wait for better risk/reward"

        reasons = {
            "vix": vix,
            "nifty": nifty,
            "banknifty": banknifty,
            "gold": gold,
            "silver": silver,
            "crude": crude,
            "usd_inr": usd_inr,
            "cross_asset": cross_asset,
            "regime": regime,
            "score": breakdown.final_score,
        }
        return Signal(action=action, score=float(breakdown.final_score), reasons=reasons, payload=payload, regime=regime, edge=edge, risk_reward=risk_reward_score)
