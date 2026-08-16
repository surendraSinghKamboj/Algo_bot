from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RegimeState(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    RANGE = "RANGE"
    HIGH_VOL_TREND = "HIGH_VOL_TREND"
    VOL_SHOCK = "VOL_SHOCK"
    CRISIS = "CRISIS"


@dataclass(frozen=True)
class RegimeDecision:
    state: RegimeState
    confidence: float
    reasons: list[str]


class RegimeEngine:
    """Explainable regime detector based on trend, volatility, breadth, and cross-asset stability."""

    def classify(self, features: dict) -> RegimeDecision:
        trend_score = float(features.get("trend_score", 0.0))
        momentum = float(features.get("momentum", 0.0))
        realized_vol = float(features.get("realized_volatility", 0.0))
        vix_level = float(features.get("vix_level", 0.0))
        vix_z = float(features.get("vix_zscore", 0.0))
        vix_change = float(features.get("vix_change", 0.0))
        breadth = float(features.get("breadth_score", 0.0))
        cross_asset = float(features.get("cross_asset_score", 0.0))
        correlation_regime = str(features.get("correlation_regime", "stable")).lower()

        reasons: list[str] = []

        if vix_level >= 28.0 or vix_z >= 2.0 or vix_change >= 0.12:
            if realized_vol >= 0.30 or breadth <= -0.15 or correlation_regime == "unstable":
                reasons.append("volatility shock and unstable risk backdrop")
                confidence = 0.86
                return RegimeDecision(RegimeState.CRISIS if vix_level >= 35.0 or vix_z >= 3.0 else RegimeState.VOL_SHOCK, confidence, reasons)
            reasons.append("elevated volatility regime")
            confidence = 0.7
            return RegimeDecision(RegimeState.HIGH_VOL_TREND, confidence, reasons)

        if trend_score > 0.02 and momentum > 0.015 and breadth > 0.25 and cross_asset > 0.2 and correlation_regime != "unstable":
            reasons.append("persistent uptrend with healthy breadth and stable cross-asset relationships")
            return RegimeDecision(RegimeState.BULL_TREND, 0.8, reasons)

        if trend_score < -0.02 and momentum < -0.015 and breadth < -0.25 and cross_asset < -0.2 and correlation_regime != "unstable":
            reasons.append("persistent downtrend with weak breadth and adverse cross-asset confirmation")
            return RegimeDecision(RegimeState.BEAR_TREND, 0.8, reasons)

        if realized_vol > 0.18 and (vix_z > 1.0 or vix_change > 0.06):
            reasons.append("range conditions with elevated volatility")
            return RegimeDecision(RegimeState.HIGH_VOL_TREND, 0.68, reasons)

        reasons.append("directional bias weak; market is range-like or neutral")
        return RegimeDecision(RegimeState.RANGE, 0.62, reasons)
