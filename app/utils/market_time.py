from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class MarketSession(StrEnum):
    CLOSED = "CLOSED"
    PRE_OPEN = "PRE_OPEN"
    NORMAL = "NORMAL"
    POST_CLOSE = "POST_CLOSE"


def to_ist(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    return timestamp.astimezone(IST)


def market_session(timestamp: datetime) -> MarketSession:
    local = to_ist(timestamp)
    if local.weekday() >= 5:
        return MarketSession.CLOSED
    current = local.timetz().replace(tzinfo=None)
    if time(9, 0) <= current < time(9, 15):
        return MarketSession.PRE_OPEN
    if time(9, 15) <= current <= time(15, 30):
        return MarketSession.NORMAL
    if time(15, 30) < current <= time(16, 0):
        return MarketSession.POST_CLOSE
    return MarketSession.CLOSED


def candle_bucket(timestamp: datetime, minutes: int) -> datetime:
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    local = to_ist(timestamp)
    minute = (local.minute // minutes) * minutes
    return local.replace(minute=minute, second=0, microsecond=0)
