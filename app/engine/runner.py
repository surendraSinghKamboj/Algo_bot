from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from app.broker.runtime import build_runtime_feed_config
from app.broker.upstox_feed import MarketTick, UpstoxMarketFeed
from app.config.settings import get_settings
from app.engine.trading_engine import TradingEngine

log = logging.getLogger(__name__)


class MockStreamer:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False

    def on(self, event: str, listener: Callable[..., None]) -> None:
        self._handlers.setdefault(event, []).append(listener)

    def connect(self) -> None:
        self._running = True
        for h in self._handlers.get('open', []):
            try:
                h()
            except Exception:
                pass

    def disconnect(self) -> None:
        self._running = False
        for h in self._handlers.get('close', []):
            try:
                h()
            except Exception:
                pass

    def auto_reconnect(self, enable: bool, interval: int = 1, retry_count: int = 5) -> None:
        return None

    def emit_message(self, message: dict) -> None:
        for h in self._handlers.get('message', []):
            try:
                h(message)
            except Exception:
                log.exception('MockStreamer message handler error')


class Runner:
    """Small in-process runner that subscribes to Upstox feed and forwards ticks to TradingEngine."""

    def __init__(self, engine: TradingEngine, streamer_factory: Optional[Callable] = None):
        self.settings = get_settings()
        self.engine = engine
        self._feed: Optional[UpstoxMarketFeed] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._streamer_factory = streamer_factory

    def start(self) -> None:
        runtime_config = build_runtime_feed_config(self.settings)
        token = runtime_config.token
        instruments = list(runtime_config.instrument_keys)
        mode = runtime_config.mode

        if token:
            log.info('Starting UpstoxMarketFeed in %s mode for %s instruments', mode, len(instruments))
            self._feed = UpstoxMarketFeed(token, instruments, mode, on_tick=self._on_tick, on_event=self._on_event)
        else:
            log.info('No Upstox access token configured; using MockStreamer for feed')
            mock_streamer = self._streamer_factory() if self._streamer_factory else MockStreamer()

            class _MockFeed:
                def __init__(self, streamer, keys, mode, on_tick, on_event):
                    self._streamer = streamer
                    self._on_tick = on_tick
                    self._on_event = on_event
                    self.status = type('s', (), {'connected': False})()
                    self._streamer.on('open', self._on_open)
                    self._streamer.on('message', self._on_message)
                    self._streamer.on('close', self._on_close)

                def start(self):
                    self._streamer.connect()

                def stop(self):
                    self._streamer.disconnect()

                def _on_open(self, *args):
                    self.status.connected = True
                    self._on_event('connected', 'mock connected')

                def _on_message(self, message):
                    from app.broker.upstox_feed import ticks_from_v3_message
                    for tick in ticks_from_v3_message(message):
                        self._on_tick(tick)

                def _on_close(self, *args):
                    self.status.connected = False
                    self._on_event('disconnected', 'mock disconnected')

            self._feed = _MockFeed(mock_streamer, instruments, mode, on_tick=self._on_tick, on_event=self._on_event)

        self._last_tick_time = time.time()
        self._thread = threading.Thread(target=self._run_feed_loop, name='runner-feed', daemon=True)
        self._thread.start()

    def _run_feed_loop(self) -> None:
        try:
            if self._feed is None:
                raise RuntimeError('Feed is not initialized')
            self._feed.start()
            while not self._stop_event.is_set():
                time.sleep(0.5)
                elapsed = time.time() - getattr(self, '_last_tick_time', 0)
                if elapsed > 30:
                    log.warning('No ticks received for %.1f seconds; reconnect attempt', elapsed)
                    try:
                        self._feed.stop()
                    except Exception:
                        log.exception('Error stopping feed during reconnect')
                    time.sleep(1)
                    try:
                        self._feed.start()
                    except Exception:
                        log.exception('Error reconnecting feed')
        except Exception:
            log.exception('runner feed loop failed')

    def stop(self) -> None:
        self._stop_event.set()
        if self._feed is not None:
            try:
                self._feed.stop()
            except Exception:
                log.exception('Failed to stop feed')

    def _on_tick(self, tick: MarketTick) -> None:
        self._last_tick_time = time.time()
        self.engine.handle_tick(tick)

    def _on_event(self, event: str, message: str) -> None:
        log.info('Feed event %s: %s', event, message)
