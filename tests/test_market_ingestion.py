from app.market.providers import MockMarketDataProvider
from app.market.ingestion import MarketIngestor


def test_ingestor_calls_upsert(monkeypatch):
    base = {"NIFTY": 10000.0, "India VIX": 12.0}
    provider = MockMarketDataProvider(base_values=base)
    mapping = {"NIFTY": "NSE_INDEX|Nifty 50", "India VIX": "INDIA_VIX|India VIX"}
    ingestor = MarketIngestor(provider, source="mock")

    recorded = {}

    def fake_upsert(session, ticks):
        recorded['called'] = True
        recorded['count'] = len(ticks)
        # return number accepted
        return len(ticks)

    monkeypatch.setattr('app.market.ingestion.storage.upsert_ticks', fake_upsert)

    result = ingestor.ingest_snapshot(session=None, mapping=mapping)
    assert recorded.get('called') is True
    assert recorded.get('count') == 2
    assert result == 2
