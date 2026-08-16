from datetime import UTC, datetime
from decimal import Decimal
from app.data.models import MarketTick
from app.data.ohlcv import OHLCVAggregator


def tick(minute: int, price: str) -> MarketTick:
    return MarketTick("NSE_INDEX|Nifty 50", datetime(2026, 8, 17, 4, minute, tzinfo=UTC), Decimal(price), volume=10)


def test_aggregates_ticks_and_emits_finished_candle():
    aggregator = OHLCVAggregator(5)
    assert aggregator.ingest(tick(30, "100")) is None
    assert aggregator.ingest(tick(32, "104")) is None
    candle = aggregator.ingest(tick(35, "101"))
    assert candle is not None
    assert (candle.open, candle.high, candle.low, candle.close, candle.volume) == (Decimal("100"), Decimal("104"), Decimal("100"), Decimal("104"), 20)
