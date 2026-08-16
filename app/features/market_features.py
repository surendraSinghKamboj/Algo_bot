from __future__ import annotations

import numpy as np
import pandas as pd


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
