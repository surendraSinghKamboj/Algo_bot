from datetime import UTC, datetime
from app.utils.market_time import MarketSession, candle_bucket, market_session


def test_market_session_uses_india_time():
    assert market_session(datetime(2026, 8, 17, 4, 30, tzinfo=UTC)) is MarketSession.NORMAL
    assert market_session(datetime(2026, 8, 16, 4, 30, tzinfo=UTC)) is MarketSession.CLOSED


def test_candle_bucket_is_ist_aligned():
    value = candle_bucket(datetime(2026, 8, 17, 4, 37, 49, tzinfo=UTC), 15)
    assert (value.hour, value.minute) == (10, 0)
