from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable

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
    """Research-driven NIFTY strategy grounded in actual market-state inputs."""

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

    @staticmethod
    def _history_values(snapshot: Dict[str, Any], *keys: str) -> list[float]:
        history = snapshot.get("history") or {}
        if not isinstance(history, dict):
            return []
        for key in keys:
            value = history.get(key) or history.get(key.lower()) or history.get(key.lower().replace(" ", "_"))
            if value is not None:
                try:
                    return [float(v) for v in value]
                except (TypeError, ValueError):
                    return []
        return []

    @staticmethod
    def _mean(values: Iterable[float]) -> float:
        items = list(values)
        return sum(items) / len(items) if items else 0.0

    @staticmethod
    def _returns(values: list[float]) -> list[float]:
        returns: list[float] = []
        for idx in range(1, len(values)):
            prev = values[idx - 1]
            if prev == 0:
                returns.append(0.0)
            else:
                returns.append((values[idx] - prev) / prev)
        return returns

    @staticmethod
    def _stddev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        average = NiftyStrategy._mean(values)
        variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def _pearson_corr(xs: list[float], ys: list[float]) -> float:
        if len(xs) != len(ys) or len(xs) < 2:
            return 0.0
        x_mean = NiftyStrategy._mean(xs)
        y_mean = NiftyStrategy._mean(ys)
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        den_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
        den_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
        if den_x == 0.0 or den_y == 0.0:
            return 0.0
        return num / (den_x * den_y)

    @staticmethod
    def _rolling_beta(asset_returns: list[float], hedge_returns: list[float]) -> float:
        if len(asset_returns) < 2 or len(hedge_returns) < 2 or len(asset_returns) != len(hedge_returns):
            return 0.0
        asset_mean = NiftyStrategy._mean(asset_returns)
        hedge_mean = NiftyStrategy._mean(hedge_returns)
        variance = sum((value - hedge_mean) ** 2 for value in hedge_returns) / (len(hedge_returns) - 1)
        if variance == 0.0:
            return 0.0
        covariance = sum((a - asset_mean) * (h - hedge_mean) for a, h in zip(asset_returns, hedge_returns)) / (len(asset_returns) - 1)
        return covariance / variance

    def generate_signal(self, snapshot: Dict[str, Any]) -> Signal:
        nifty = self._get_value(snapshot, "NIFTY", "nifty")
        vix = self._get_value(snapshot, "India VIX", "INDIA_VIX", "india_vix")
        banknifty = self._get_value(snapshot, "BANKNIFTY", "banknifty")
        gold = self._get_value(snapshot, "Gold", "gold")
        silver = self._get_value(snapshot, "Silver", "silver")
        crude = self._get_value(snapshot, "Crude", "crude")
        usd_inr = self._get_value(snapshot, "USDINR", "usd_inr")

        history = snapshot.get("history") or {}
        has_history = bool(history)
        nifty_history = self._history_values(snapshot, "NIFTY", "nifty")
        bank_history = self._history_values(snapshot, "BANKNIFTY", "banknifty")
        vix_history = self._history_values(snapshot, "INDIA_VIX", "india_vix", "India VIX")

        if nifty <= 0 or vix <= 0:
            return Signal(action="NO TRADE", score=0.0, reasons={"reason": "insufficient market data", "nifty": nifty, "vix": vix}, payload={}, regime="DATA_UNAVAILABLE", edge="insufficient required inputs", risk_reward=0.0, confidence=0.0)

        if not has_history and len(nifty_history) == 0 and len(vix_history) == 0:
            if vix >= 25:
                return Signal(action="SELL", score=0.75, reasons={"vix": vix, "nifty": nifty, "regime": "VOLATILITY_SPIKE"}, payload={"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}, regime="VOLATILITY_SPIKE", edge="short-bias", risk_reward=0.6, confidence=0.75)
            if vix < 18:
                return Signal(action="BUY", score=0.82, reasons={"vix": vix, "nifty": nifty, "regime": "TREND_UP"}, payload={"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}, regime="TREND_UP", edge="momentum + low-vol", risk_reward=0.7, confidence=0.82)
            return Signal(action="NO TRADE", score=0.45, reasons={"vix": vix, "nifty": nifty, "regime": "RISK_OFF"}, payload={}, regime="RISK_OFF", edge="wait for more confirmation", risk_reward=0.5, confidence=0.45)

        if len(nifty_history) < 5 or len(bank_history) < 5 or len(vix_history) < 5:
            if vix >= 25:
                return Signal(action="SELL", score=0.7, reasons={"reason": "limited history", "vix": vix, "nifty": nifty, "regime": "VOLATILITY_SPIKE"}, payload={"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}, regime="VOLATILITY_SPIKE", edge="short-bias", risk_reward=0.6, confidence=0.7)
            if vix < 18:
                return Signal(action="BUY", score=0.8, reasons={"reason": "limited history", "vix": vix, "nifty": nifty, "regime": "TREND_UP"}, payload={"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}, regime="TREND_UP", edge="momentum + low-vol", risk_reward=0.7, confidence=0.8)
            return Signal(action="NO TRADE", score=0.5, reasons={"reason": "limited history", "vix": vix, "nifty": nifty, "regime": "RISK_OFF"}, payload={}, regime="RISK_OFF", edge="wait for more confirmation", risk_reward=0.5, confidence=0.5)

        nifty_returns = self._returns(nifty_history)
        bank_returns = self._returns(bank_history)
        vix_window = vix_history[-10:] if len(vix_history) >= 10 else vix_history
        vix_mean = self._mean(vix_window)
        vix_std = self._stddev(vix_window)
        vix_zscore = (vix - vix_mean) / vix_std if vix_std else 0.0
        short_window = nifty_history[-20:] if len(nifty_history) >= 20 else nifty_history
        trend_score = (nifty - self._mean(short_window)) / max(self._mean(short_window), 1.0)
        momentum = 0.0
        if len(nifty_history) >= 2:
            momentum = (nifty_history[-1] - nifty_history[-2]) / max(abs(nifty_history[-2]), 1.0)
        bank_ratio = banknifty / max(nifty, 1.0)
        bank_confirmation = max(0.0, 1.0 - abs(bank_ratio - 2.0) / 2.0)
        corr_value = self._pearson_corr(nifty_returns[-30:], bank_returns[-30:]) if len(nifty_returns) >= 30 and len(bank_returns) >= 30 else 0.0
        cross_asset_score = bank_confirmation

        if vix >= 28.0 or vix_zscore > 2.0:
            action = "SELL"
            regime = "VOL_SHOCK"
            edge = "volatility shock; hedge and preserve capital"
            payload = {"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        elif trend_score > 0.015 and momentum > 0.002 and bank_confirmation > 0.55 and cross_asset_score > 0.5 and vix < 25 and corr_value > 0.4:
            action = "BUY"
            regime = "BULL_TREND"
            edge = "trend + momentum + banknifty confirmation"
            payload = {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        elif trend_score < -0.015 and momentum < -0.002 and bank_confirmation > 0.55 and cross_asset_score > 0.5 and vix < 25 and corr_value < -0.4:
            action = "SELL"
            regime = "BEAR_TREND"
            edge = "downtrend + negative momentum + banknifty confirmation"
            payload = {"option_structure": True, "structure": "BEAR_PUT_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        elif vix >= 18 and vix < 28 and cross_asset_score < 0.45:
            action = "HEDGE"
            regime = "RISK_OFF"
            edge = "cross-asset divergence and rising volatility"
            payload = {"option_structure": True, "structure": "PROTECTIVE_PUT", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        elif vix < 18:
            action = "BUY"
            regime = "TREND_UP"
            edge = "directional continuation with manageable volatility"
            payload = {"option_structure": True, "structure": "BULL_CALL_SPREAD", "underlying_key": "NSE_INDEX|Nifty 50", "width": 200, "lots": 1, "max_spread": 500}
        else:
            action = "NO TRADE"
            regime = "SIDEWAYS"
            edge = "wait for quality trend and volatility confirmation"
            payload = {}

        score = 0.75 if action == "BUY" else 0.8 if action == "SELL" else 0.6 if action == "HEDGE" else 0.3
        reasons = {"nifty": nifty, "vix": vix, "banknifty": banknifty, "regime": regime, "trend_score": trend_score, "momentum": momentum, "cross_asset_score": cross_asset_score, "correlation": corr_value}
        return Signal(action=action, score=score, reasons=reasons, payload=payload, regime=regime, edge=edge, risk_reward=0.7 if action in {"BUY", "SELL"} else 0.5, confidence=score)
