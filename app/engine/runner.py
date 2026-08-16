from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from app.broker.upstox_feed import UpstoxMarketFeed, MarketTick
from app.engine.trading_engine_fixed import TradingEngine
from app.config.settings import get_settings

log = logging.getLogger(__name__)


class MockStreamer:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False

    def on(self, event: str, listener: Callable[..., None]) -> None:
        self._handlers.setdefault(event, []).append(listener)

    def connect(self) -> None:
        self._running = True
        for h in self._handlers.get("open", []):
            try:
                h()
            except Exception:
                pass
        # do not auto-send messages here; runner will call emit_message

    def disconnect(self) -> None:
        self._running = False
        for h in self._handlers.get("close", []):
            try:
                h()
            except Exception:
                pass

    def auto_reconnect(self, enable: bool, interval: int = 1, retry_count: int = 5) -> None:
        # noop for mock
        return None

    def emit_message(self, message: dict) -> None:
        for h in self._handlers.get("message", []):
            try:
                h(message)
            except Exception:
                log.exception("MockStreamer message handler error")


class Runner:
    """Small in-process runner that subscribes to Upstox feed and forwards ticks to TradingEngine.

    Uses real UpstoxMarketFeed when an access token is configured; otherwise uses a MockStreamer for testing.
    """

    def __init__(self, engine: TradingEngine, streamer_factory: Optional[Callable] = None):
        self.settings = get_settings()
        self.engine = engine
        self._feed: Optional[UpstoxMarketFeed] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._streamer_factory = streamer_factory

    def start(self) -> None:
        # Determine access token availability
        token = None
        try:
            token = self.settings.upstox_access_token.get_secret_value() if self.settings.upstox_access_token else None
        except Exception:
            token = None

        # Instruments to subscribe: minimal set for NIFTY strategy
        instruments = ["NSE_INDEX|Nifty 50", "NSE_INDEX|India VIX"]
        mode = "PAPER" if str(self.settings.trading_mode).upper() == "PAPER" else "LIVE"

        # If a streamer_factory override is provided, pass it to UpstoxMarketFeed; otherwise default
        streamer_factory = None
        if self._streamer_factory:
            # Wrap to match UpstoxMarketFeed._official_streamer signature
            streamer_factory = lambda access_token, keys, m: self._streamer_factory()

        if token:
            log.info("Starting UpstoxMarketFeed in %s mode", mode)
            # If possible, download instrument master and persist to DB for resolving option contracts
            try:
                from app.broker.upstox import UpstoxClient
                from app.database.session import SessionLocal
                from app.data.instruments import upsert_instruments

                client = UpstoxClient(self.settings.upstox_api_key, self.settings.upstox_api_secret.get_secret_value() if self.settings.upstox_api_secret else None, self.settings.upstox_redirect_uri, token)
                # download instruments and persist
                try:
                    instruments = client._client.get(self.settings.upstox_api_key or "")  # noop to keep static analyzers happy
                except Exception:
                    pass
                # Use the client's async method in a sync context by running an event loop call
                import asyncio

                async def _download_and_persist():
                    try:
                        payload = await client.download_instruments()
                        # persist to db if DB available
                        try:
                            with SessionLocal() as session:
                                upsert_instruments(session, payload)
                                log.info("Instrument master synced (%d items)", len(payload))
                        except Exception:
                            log.exception("Failed to persist instrument master; continuing without DB persistence")
                    finally:
                        await client.aclose()

                asyncio.run(_download_and_persist())
            except Exception:
                log.exception("Instrument master sync failed; continuing")

            self._feed = UpstoxMarketFeed(token, instruments, mode, on_tick=self._on_tick, on_event=self._on_event, streamer_factory=streamer_factory)
        else:
            log.info("No Upstox access token configured; using MockStreamer for feed")
            # Build a lightweight UpstoxMarketFeed-like wrapper using MockStreamer to reuse tick normalization
            mock_streamer = (self._streamer_factory() if self._streamer_factory else MockStreamer())
            # create a small adapter that mimics UpstoxMarketFeed but uses our MockStreamer
            class _MockFeed:
                def __init__(self, streamer, keys, mode, on_tick, on_event):
                    self._streamer = streamer
                    self._on_tick = on_tick
                    self._on_event = on_event
                    self.status = type("s", (), {"connected": False})()
                    self._streamer.on("open", self._on_open)
                    self._streamer.on("message", self._on_message)
                    self._streamer.on("close", self._on_close)

                def start(self):
                    self._streamer.connect()

                def stop(self):
                    self._streamer.disconnect()

                def _on_open(self, *args):
                    self.status.connected = True
                    self._on_event("connected", "mock connected")

                def _on_message(self, message):
                    # Expect message to be normalized v3 style; reuse ticks_from_v3_message if needed
                    from app.broker.upstox_feed import ticks_from_v3_message

                    for tick in ticks_from_v3_message(message):
                        self._on_tick(tick)

                def _on_close(self, *args):
                    self.status.connected = False
                    self._on_event("disconnected", "mock disconnected")

            self._feed = _MockFeed(mock_streamer, instruments, mode, on_tick=self._on_tick, on_event=self._on_event)

        # Start feed in a background thread to keep main thread responsive and allow graceful shutdown
        self._last_tick_time = time.time()
        self._thread = threading.Thread(target=self._run_feed_loop, name="runner-feed", daemon=True)
        self._thread.start()

    def _run_feed_loop(self) -> None:
        try:
            if self._feed is None:
                raise RuntimeError("Feed is not initialized")
            self._feed.start()
            log.info("Feed started; entering main loop")
            # Keep running until stop requested
            stale_seconds = 30
            backoff = 1
            while not self._stop_event.is_set():
                time.sleep(0.5)
                # Watchdog: if no ticks received for stale_seconds, attempt a reconnect
                try:
                    elapsed = time.time() - getattr(self, "_last_tick_time", 0)
                    if elapsed > stale_seconds:
                        log.warning("No ticks received for %.1f seconds; attempting to reconnect feed", elapsed)
                        try:
                            self._feed.stop()
                        except Exception:
                            log.exception("Error stopping feed during reconnect")
                        time.sleep(backoff)
                        try:
                            self._feed.start()
                            log.info("Feed restarted")
                            backoff = 1
                            self._last_tick_time = time.time()
                        except Exception:
                            log.exception("Feed restart failed; increasing backoff")
                            backoff = min(backoff * 2, 60)
                except Exception:
                    log.exception("Error in watchdog loop")
        except Exception:
            log.exception("Runner encountered an error")
        finally:
            try:
                if self._feed:
                    self._feed.stop()
            except Exception:
                log.exception("Error stopping feed")

    def _on_tick(self, tick: MarketTick) -> None:
        log.debug("Received tick: %s %s", tick.instrument_key, getattr(tick, "ltp", None))
        # Update watchdog timestamp
        try:
            self._last_tick_time = time.time()
        except Exception:
            pass
        # Forward tick to engine synchronously
        self.engine.handle_tick(tick)

    def _on_event(self, name: str, message: str) -> None:
        log.info("Feed event: %s %s", name, message)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
