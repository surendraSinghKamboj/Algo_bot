from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import upstox_client

from app.data.models import MarketTick
from app.data.streaming import TickGate


class Streamer(Protocol):
    def on(self, event: str, listener: Callable[..., None]) -> None: ...
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def auto_reconnect(self, enable: bool, interval: int = 1, retry_count: int = 5) -> None: ...


@dataclass
class FeedStatus:
    connected: bool = False
    received_messages: int = 0
    accepted_ticks: int = 0
    rejected_ticks: int = 0
    last_error: str | None = None


def ticks_from_v3_message(message: dict[str, Any]) -> list[MarketTick]:
    """Normalize the dictionary emitted by the official SDK's V3 protobuf decoder."""
    if message.get("type") not in {"initialFeed", "liveFeed"}:
        return []
    fallback_timestamp = _timestamp(message.get("currentTs"))
    ticks: list[MarketTick] = []
    for instrument_key, feed in message.get("feeds", {}).items():
        ltpc, metadata = _ltpc_and_metadata(feed)
        if not ltpc or "ltp" not in ltpc:
            continue
        timestamp = _timestamp(ltpc.get("ltt")) or fallback_timestamp
        if timestamp is None:
            continue
        ticks.append(MarketTick(instrument_key=instrument_key, timestamp=timestamp, ltp=Decimal(str(ltpc["ltp"])), volume=_integer(ltpc.get("ltq")), open_interest=_integer(metadata.get("oi")) if metadata else None))
    return ticks


class UpstoxMarketFeed:
    """Market-data-only adapter around Upstox's official SDK V3 decoder/streamer."""
    def __init__(self, access_token: str, instrument_keys: list[str], mode: str, on_tick: Callable[[MarketTick], None], on_event: Callable[[str, str], None] | None = None, stale_after: timedelta = timedelta(seconds=10), streamer_factory: Callable[[Any, list[str], str], Streamer] | None = None):
        if not access_token:
            raise ValueError("A market-data access token is required")
        if not instrument_keys:
            raise ValueError("At least one instrument key is required")
        self._access_token, self._instrument_keys, self._mode = access_token, list(dict.fromkeys(instrument_keys)), mode
        self._on_tick, self._on_event = on_tick, on_event or (lambda *_: None)
        self._gate = TickGate(stale_after=stale_after)
        self.status = FeedStatus()
        self._streamer_factory = streamer_factory or self._official_streamer
        self._streamer: Streamer | None = None

    def start(self) -> None:
        self._streamer = self._streamer_factory(self._access_token, self._instrument_keys, self._mode)
        self._streamer.on("open", self._on_open)
        self._streamer.on("message", self._on_message)
        self._streamer.on("error", self._on_error)
        self._streamer.on("close", self._on_close)
        self._streamer.on("reconnecting", lambda message: self._on_event("reconnecting", str(message)))
        self._streamer.on("autoReconnectStopped", lambda message: self._on_event("reconnect_stopped", str(message)))
        self._streamer.auto_reconnect(True, interval=2, retry_count=5)
        self._streamer.connect()

    def stop(self) -> None:
        if self._streamer:
            self._streamer.disconnect()
        self.status.connected = False

    def _on_open(self, *_: object) -> None:
        self.status.connected = True
        self._on_event("connected", f"Subscribed to {len(self._instrument_keys)} instruments in {self._mode} mode")

    def _on_message(self, message: dict[str, Any]) -> None:
        self.status.received_messages += 1
        for tick in ticks_from_v3_message(message):
            if self._gate.accept(tick):
                self.status.accepted_ticks += 1
                self._on_tick(tick)
            else:
                self.status.rejected_ticks += 1

    def _on_error(self, error: object) -> None:
        self.status.last_error = str(error)[:500]
        self._on_event("error", self.status.last_error)

    def _on_close(self, *_: object) -> None:
        self.status.connected = False
        self._on_event("disconnected", "Upstox market data feed closed")

    @staticmethod
    def _official_streamer(access_token: str, instrument_keys: list[str], mode: str) -> Streamer:
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        return upstox_client.MarketDataStreamerV3(upstox_client.ApiClient(configuration), instrument_keys, mode)


def _ltpc_and_metadata(feed: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if "ltpc" in feed:
        return feed["ltpc"], None
    if "firstLevelWithGreeks" in feed:
        value = feed["firstLevelWithGreeks"]
        return value.get("ltpc"), value
    full = feed.get("fullFeed", {})
    for key in ("marketFF", "indexFF"):
        if key in full:
            value = full[key]
            return value.get("ltpc"), value
    return None, None


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    except (TypeError, ValueError, OSError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
