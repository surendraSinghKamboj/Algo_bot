from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from app.features.market_features import build_market_features
from app.regimes.engine import RegimeEngine
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
    confidence: float | None = None


class NiftyStrategy:
    """Research-driven NIFTY strategy using stateful market features and a regime classifier."""

    def __init__(self, scorer: StrategyScorer | None = None):
        self.scorer = scorer or StrategyScorer(min_trade_score=0.5)
        self.regime_engine = RegimeEngine()

    def _get_value(self, snapshot: Dict[str, Any], *keys: str) -> float:
        for key in keys:
            if key in snapshot:
                return float(snapshot[key])
            lowered = key.lower().replace(" ", "_")
            if lowered in snapshot:
                return float(snapshot[lowered])
        return 0.0

    def _decision_from_features(self, features: Dict[str, Any]) -> tuple[str, str, str, dict]:
        vix = float(features.get("vix_level", 0.0))
        trend_score = float(features.get("trend_score", 0.0))
        momentum = float(features.get("momentum", 0.0))
        bank_confirmation = float(features.get("bank_confirmation", 0.0))
        cross_asset_score = float(features.get("cross_asset_score", 0.0))
        corr_value = float(features.get("correlation", 0.0))

        if vix >= 28.0 or features.get("vix_zscore", 0.0) > 2.0:
            return "SELL", "VOL_SHOCK", "volatility shock; hedge and preserve capital", {"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        if trend_score > 0.015 and momentum > 0.002 and bank_confirmation > 0.55 and cross_asset_score > 0.5 and vix < 25 and corr_value > 0.4:
            return "BUY", "BULL_TREND", "trend + momentum + banknifty confirmation", {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        if trend_score < -0.015 and momentum < -0.002 and bank_confirmation > 0.55 and cross_asset_score > 0.5 and vix < 25 and corr_value < -0.4:
            return "SELL", "BEAR_TREND", "downtrend + negative momentum + banknifty confirmation", {"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        if vix >= 18 and vix < 28 and cross_asset_score < 0.45:
            return "HEDGE", "RISK_OFF", "cross-asset divergence and rising volatility", {"option_structure": True, "structure": "PROTECTIVE_PUT", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        if vix < 18:
            return "BUY", "TREND_UP", "directional continuation with manageable volatility", {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        return "NO TRADE", "SIDEWAYS", "wait for quality trend and volatility confirmation", {}

    def generate_signal(self, snapshot: Dict[str, Any]) -> Signal:
        availability = snapshot.get("availability") or {}
        nifty = self._get_value(snapshot, "NIFTY", "nifty")
        vix = self._get_value(snapshot, "India VIX", "INDIA_VIX", "india_vix")
        banknifty = self._get_value(snapshot, "BANKNIFTY", "banknifty")

        required = {
            "NIFTY": availability.get("NIFTY", False),
            "BANKNIFTY": availability.get("BANKNIFTY", False),
            "INDIA_VIX": availability.get("INDIA_VIX", False),
        }

        if nifty <= 0 or vix <= 0:
            return Signal(action="NO TRADE", score=0.0, reasons={"reason": "insufficient market data", "nifty": nifty, "vix": vix, "banknifty": banknifty}, payload={}, regime="DATA_UNAVAILABLE", edge="insufficient required inputs", risk_reward=0.0, confidence=0.0)

        features = build_market_features(snapshot)
        if not features.get("has_required_inputs", False):
            if vix >= 28.0:
                return Signal(action="SELL", score=0.82, reasons={"reason": "fallback vix shock", "nifty": nifty, "vix": vix, "banknifty": banknifty, "features": features}, payload={"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}, regime="VOL_SHOCK", edge="volatility shock; hedge and preserve capital", risk_reward=0.6, confidence=0.82)
            if vix < 18.0:
                return Signal(action="BUY", score=0.78, reasons={"reason": "fallback low-vix bullish bias", "nifty": nifty, "vix": vix, "banknifty": banknifty, "features": features}, payload={"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}, regime="TREND_UP", edge="directional continuation with manageable volatility", risk_reward=0.7, confidence=0.78)
            return Signal(action="NO TRADE", score=0.35, reasons={"reason": "insufficient market history", "nifty": nifty, "vix": vix, "banknifty": banknifty, "features": features}, payload={}, regime="DATA_UNAVAILABLE", edge="wait for more confirmation", risk_reward=0.5, confidence=0.35)

        regime_decision = self.regime_engine.classify(features)
        action, regime, edge, payload = self._decision_from_features(features)

        if action == "NO TRADE":
            score = 0.35
            confidence = 0.35
        elif action == "BUY":
            score = 0.8
            confidence = 0.8
        elif action == "SELL":
            score = 0.82
            confidence = 0.82
        elif action == "HEDGE":
            score = 0.68
            confidence = 0.68
        else:
            score = 0.45
            confidence = 0.45

        reasons = {
            "nifty": nifty,
            "vix": vix,
            "banknifty": banknifty,
            "regime": regime,
            "features": features,
            "regime_decision": regime_decision.state.value,
        }
        return Signal(
            action=action,
            score=score,
            reasons=reasons,
            payload=payload,
            regime=regime,
            edge=edge,
            risk_reward=float(features.get("risk_reward_score", 0.6)),
            confidence=float(confidence),
        )
