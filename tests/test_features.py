import numpy as np
import pandas as pd
import pytest
from app.features.market_features import cross_asset_features, price_features, vix_features


def test_feature_engine_produces_causal_rolling_metrics():
    index = pd.date_range("2025-01-01", periods=80, freq="B")
    close = pd.Series(np.linspace(100, 180, 80), index=index)
    price = price_features(pd.DataFrame({"close": close}))
    vix = vix_features(pd.Series(np.linspace(10, 20, 80), index=index))
    cross = cross_asset_features(close, close * 2, window=20)
    assert price["trend_score"].iloc[-1] > 0
    assert not np.isnan(vix["vix_zscore"].iloc[-1])
    assert cross["rolling_beta"].iloc[-1] == pytest.approx(1.0, abs=0.01)
