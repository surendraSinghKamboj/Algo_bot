from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def _returns(values: list[float]) -> list[float]:
    returns: list[float] = []
    for idx in range(1, len(values)):
        prev = values[idx - 1]
        if prev == 0:
            returns.append(0.0)
        else:
            returns.append((values[idx] - prev) / prev)
    return returns


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def _pearson_corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    x_mean = _mean(xs)
    y_mean = _mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return numerator / (den_x * den_y)


def _rolling_beta(asset_returns: list[float], hedge_returns: list[float]) -> float:
    if len(asset_returns) < 2 or len(hedge_returns) < 2 or len(asset_returns) != len(hedge_returns):
        return 0.0
    hedging_var = _stddev(hedge_returns) ** 2
    if hedging_var == 0.0:
        return 0.0
    cov = sum((a - _mean(asset_returns)) * (h - _mean(hedge_returns)) for a, h in zip(asset_returns, hedge_returns)) / (len(asset_returns) - 1)
    return cov / hedging_var


def price_features(candles: pd.DataFrame, short_window: int = 20, long_window: int = 50, momentum_window: int = 20, vol_window: int = 20) -> pd.DataFrame:
    if "close" not in candles:
        raise ValueError("candles must include a close column")
    if min(short_window, long_window, momentum_window, vol_window) < 2:
        raise ValueError("all feature windows must be at least 2")
    frame = candles.copy().sort_index()
    frame["return_1"] = frame["close"].pct_change()
    frame["sma_short"] = frame["close"].rolling(short_window, min_periods=short_window).mean()
    frame["sma_long"] = frame["close"].rolling(long_window, min_periods=long_window).mean()
    frame["trend_score"] = frame["sma_short"] / frame["sma_long"] - 1
    frame["momentum"] = frame["close"].pct_change(momentum_window)
    frame["realized_volatility"] = frame["return_1"].rolling(vol_window, min_periods=vol_window).std(ddof=1) * np.sqrt(252)
    return frame


def vix_features(vix: pd.Series, window: int = 60) -> pd.DataFrame:
    if window < 2:
        raise ValueError("window must be at least 2")
    result = pd.DataFrame({"vix": vix}).sort_index()
    result["vix_change"] = result["vix"].pct_change()
    result["vix_zscore"] = (result["vix"] - result["vix"].rolling(window, min_periods=window).mean()) / result["vix"].rolling(window, min_periods=window).std(ddof=1)
    result["vix_percentile"] = result["vix"].rolling(window, min_periods=window).rank(pct=True)
    result["vix_momentum"] = result["vix"].pct_change(min(20, window - 1))
    return result


def cross_asset_features(asset: pd.Series, hedge: pd.Series, window: int = 60) -> pd.DataFrame:
    if window < 3:
        raise ValueError("window must be at least 3")
    frame = pd.concat([asset.rename("asset"), hedge.rename("hedge")], axis=1).dropna().sort_index()
    returns = frame.pct_change()
    result = pd.DataFrame(index=frame.index)
    result["pearson_correlation"] = returns["asset"].rolling(window, min_periods=window).corr(returns["hedge"])
    result["spearman_correlation"] = pd.Series([np.nan if end < window else returns["asset"].iloc[end - window:end].corr(returns["hedge"].iloc[end - window:end], method="spearman") for end in range(len(returns))], index=returns.index)
    covariance = returns["asset"].rolling(window, min_periods=window).cov(returns["hedge"])
    result["rolling_beta"] = covariance / returns["hedge"].rolling(window, min_periods=window).var()
    return result


def build_market_features(snapshot: dict) -> dict:
    history = snapshot.get("history") or {}
    def get_series(label: str, *aliases: str) -> list[float]:
        for key in (label, *aliases):
            values = history.get(key)
            if values is None:
                values = history.get(key.lower())
            if values is None:
                values = history.get(key.lower().replace(" ", "_"))
            if values is not None:
                return [float(v) for v in values]
        direct = snapshot.get(label)
        for alias in aliases:
            if direct is None:
                direct = snapshot.get(alias)
        if direct is None:
            return []
        return [float(direct)]

    nifty = float(snapshot.get("NIFTY", snapshot.get("nifty", 0.0)))
    vix = float(snapshot.get("India VIX", snapshot.get("INDIA_VIX", snapshot.get("india_vix", 0.0))))
    banknifty = float(snapshot.get("BANKNIFTY", snapshot.get("banknifty", 0.0)))
    gold = float(snapshot.get("Gold", snapshot.get("gold", 0.0)))
    silver = float(snapshot.get("Silver", snapshot.get("silver", 0.0)))
    crude = float(snapshot.get("Crude", snapshot.get("crude", 0.0)))
    usd_inr = float(snapshot.get("USDINR", snapshot.get("usd_inr", 0.0)))

    nifty_series = get_series("NIFTY", "nifty")
    bank_series = get_series("BANKNIFTY", "banknifty")
    vix_series = get_series("INDIA_VIX", "india_vix", "India VIX")
    gold_series = get_series("GOLD", "gold")
    silver_series = get_series("SILVER", "silver")
    crude_series = get_series("CRUDE", "crude")
    usd_series = get_series("USDINR", "usd_inr")

    if nifty > 0 and nifty_series:
        short_window = nifty_series[-20:] if len(nifty_series) >= 20 else nifty_series
        trend_score = (nifty - _mean(short_window)) / max(_mean(short_window), 1.0)
    else:
        trend_score = 0.0

    if len(nifty_series) >= 2:
        momentum = (nifty_series[-1] - nifty_series[-2]) / max(abs(nifty_series[-2]), 1.0)
    else:
        momentum = 0.0

    nifty_returns = _returns(nifty_series)
    bank_returns = _returns(bank_series)
    realized_volatility = _stddev(nifty_returns[-20:]) * math.sqrt(252) if len(nifty_returns) >= 20 else _stddev(nifty_returns) * math.sqrt(252) if nifty_returns else 0.0

    vix_window = vix_series[-10:] if len(vix_series) >= 10 else vix_series
    vix_mean = _mean(vix_window)
    vix_std = _stddev(vix_window)
    vix_zscore = (vix - vix_mean) / vix_std if vix_std else 0.0
    vix_change = 0.0 if len(vix_series) < 2 else (vix - vix_series[-2]) / max(abs(vix_series[-2]), 1.0)

    bank_confirmation = max(0.0, 1.0 - abs((banknifty / max(nifty, 1.0)) - 2.0) / 2.0) if banknifty > 0 and nifty > 0 else 0.0
    corr_value = _pearson_corr(nifty_returns[-30:], bank_returns[-30:]) if len(nifty_returns) >= 30 and len(bank_returns) >= 30 else 0.0
    beta_value = _rolling_beta(nifty_returns[-30:], bank_returns[-30:]) if len(nifty_returns) >= 30 and len(bank_returns) >= 30 else 0.0

    commodity_confirmations: list[float] = []
    for current, series in ((gold, gold_series), (silver, silver_series), (crude, crude_series), (usd_inr, usd_series)):
        if current <= 0 or len(series) < 2:
            continue
        prev = series[-2] if len(series) >= 2 else series[-1]
        if prev == 0:
            continue
        commodity_return = (current - prev) / abs(prev)
        commodity_confirmations.append(max(0.0, 1.0 - abs(commodity_return - momentum) / max(abs(momentum), 0.01)))
    cross_asset_score = bank_confirmation
    if commodity_confirmations:
        cross_asset_score = (cross_asset_score + sum(commodity_confirmations) / len(commodity_confirmations)) / 2.0
    cross_asset_score = max(0.0, min(1.0, cross_asset_score))

    breadth_score = max(0.0, min(1.0, 0.5 * (cross_asset_score + max(0.0, corr_value))))
    if vix < 18:
        volatility_regime = "low"
    elif vix < 25:
        volatility_regime = "moderate"
    else:
        volatility_regime = "high"

    return {
        "nifty": nifty,
        "banknifty": banknifty,
        "vix_level": vix,
        "vix_zscore": vix_zscore,
        "vix_change": vix_change,
        "trend_score": trend_score,
        "momentum": momentum,
        "realized_volatility": realized_volatility,
        "bank_confirmation": bank_confirmation,
        "cross_asset_score": cross_asset_score,
        "breadth_score": breadth_score,
        "correlation": corr_value,
        "beta": beta_value,
        "volatility_regime": volatility_regime,
        "correlation_regime": "stable" if abs(corr_value) >= 0.4 else "unstable",
        "risk_reward_score": 0.75 if vix < 18 else 0.64 if vix < 25 else 0.45,
        "liquidity_score": 0.8 if vix < 28 and realized_volatility <= 0.30 else 0.55,
        "has_required_inputs": nifty > 0 and vix > 0 and banknifty > 0,
    }
