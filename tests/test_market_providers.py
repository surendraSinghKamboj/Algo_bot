from datetime import datetime, timedelta

from app.market.providers import MockMarketDataProvider


def test_mock_provider_latest_snapshot_is_copy():
    base = {"NIFTY": 10000.0, "India VIX": 12.0}
    provider = MockMarketDataProvider(base_values=base, step=0.5)
    snap = provider.latest_snapshot()
    assert snap == base
    # mutate returned dict and ensure provider internal not affected
    snap["NIFTY"] = 9999.0
    assert provider.latest_snapshot()["NIFTY"] == 10000.0


def test_mock_provider_historical_series_deterministic():
    base = {"NIFTY": 10000.0}
    provider = MockMarketDataProvider(base_values=base, step=2.0)
    start = datetime(2020, 1, 1, 9, 15)
    end = start + timedelta(minutes=4)
    series = provider.historical_series("NIFTY", start, end)
    assert len(series) == 5
    assert series[0]["price"] == 10000.0
    assert series[1]["price"] == 10002.0
    assert series[-1]["time"] == end


def test_provider_integrates_with_service_snapshot():
    from app.market.service import MarketDataService

    base = {"NIFTY": 20000.0, "India VIX": 14.2}
    provider = MockMarketDataProvider(base_values=base)
    svc = MarketDataService(provider=provider)
    snap = svc.snapshot()
    assert snap["NIFTY"] == 20000.0
    assert snap["India VIX"] == 14.2
    assert snap["trading_mode"] == "PAPER"
