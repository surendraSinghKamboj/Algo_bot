from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MarketInstrumentState:
    instrument_key: str
    symbol: str
    timestamp: datetime | None = None
    ltp: float = 0.0
    volume: int | None = None
    open_interest: int | None = None
    source: str = "unknown"
    stale_seconds: float | None = None

    @property
    def is_stale(self) -> bool:
        if self.timestamp is None:
            return True
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return age > 30


class MarketState:
    """Centralized market-state cache for the paper trading runtime."""

    DEFAULTS = {
        'NIFTY': 22350.0,
        'BANKNIFTY': 48000.0,
        'INDIA_VIX': 15.4,
        'GOLD': 71120.0,
        'SILVER': 92100.0,
        'CRUDE': 6456.0,
        'USDINR': 83.4,
    }

    INSTRUMENT_KEYS = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Bank Nifty",
        "INDIA_VIX": "NSE_INDEX|India VIX",
        "GOLD": "MCX|GOLD",
        "SILVER": "MCX|SILVER",
        "CRUDE": "MCX|CRUDE",
        "USDINR": "NSE_CURRENCY|USDINR",
    }

    def __init__(self):
        self._instruments: dict[str, MarketInstrumentState] = {}
        self._history: dict[str, list[float]] = {}
        self._availability: dict[str, bool] = {}
        self._freshness: dict[str, float] = {}

    def update_tick(self, tick: Any) -> MarketInstrumentState:
        if isinstance(tick, dict):
            instrument_key = tick.get('instrument_key')
            ltp = tick.get('ltp', 0.0)
            volume = tick.get('volume')
            oi = tick.get('open_interest')
            timestamp = tick.get('timestamp')
            source = tick.get('source', 'upstox_feed')
        else:
            instrument_key = getattr(tick, 'instrument_key', None)
            ltp = getattr(tick, 'ltp', 0.0)
            volume = getattr(tick, 'volume', None)
            oi = getattr(tick, 'open_interest', None)
            timestamp = getattr(tick, 'timestamp', None)
            source = getattr(tick, 'source', 'upstox_feed')
        if not instrument_key:
            raise ValueError('tick is missing instrument_key')
        ltp = float(ltp)
        symbol = self._symbol_for_key(instrument_key)
        state = MarketInstrumentState(
            instrument_key=instrument_key,
            symbol=symbol,
            timestamp=timestamp,
            ltp=ltp,
            volume=volume,
            open_interest=oi,
            source=source,
            stale_seconds=None,
        )
        if state.timestamp is not None:
            if state.timestamp.tzinfo is None:
                state.timestamp = state.timestamp.replace(tzinfo=timezone.utc)
            state.stale_seconds = (datetime.now(timezone.utc) - state.timestamp).total_seconds()
        self._instruments[instrument_key] = state
        self._availability[symbol] = True
        self._freshness[symbol] = state.stale_seconds if state.stale_seconds is not None else 9999.0
        series = self._history.setdefault(symbol, [])
        if not series or abs(series[-1] - ltp) > 1e-9:
            series.append(ltp)
        if len(series) > 200:
            series = series[-200:]
        self._history[symbol] = series
        return state

    def _symbol_for_key(self, instrument_key: str) -> str:
        current = {v: k for k, v in self.INSTRUMENT_KEYS.items()}
        return current.get(instrument_key, instrument_key)

    def get_instrument(self, instrument_key: str) -> MarketInstrumentState | None:
        return self._instruments.get(instrument_key)

    def get_series(self, symbol: str) -> list[float]:
        return list(self._history.get(symbol, []))

    def get_history_map(self) -> dict[str, list[float]]:
        return {symbol: list(values) for symbol, values in self._history.items()}

    def get_snapshot(self, use_defaults: bool = True) -> dict[str, float]:
        snapshot: dict[str, float] = {**self.DEFAULTS} if use_defaults else {}
        freshness: dict[str, float] = {}
        availability: dict[str, bool] = {}
        for key, instrument_key in self.INSTRUMENT_KEYS.items():
            state = self._instruments.get(instrument_key)
            if state is not None:
                snapshot[key] = float(state.ltp)
                availability[key] = True
                freshness[key] = float(state.stale_seconds if state.stale_seconds is not None else 0.0)
            else:
                snapshot[key] = self.DEFAULTS.get(key, 0.0) if use_defaults else 0.0
                availability[key] = False
                freshness[key] = 9999.0

        snapshot["NIFTY"] = float(snapshot.get("NIFTY", self.DEFAULTS['NIFTY']))
        snapshot["BANKNIFTY"] = float(snapshot.get("BANKNIFTY", self.DEFAULTS['BANKNIFTY']))
        snapshot["India VIX"] = float(snapshot.get("INDIA_VIX", self.DEFAULTS['INDIA_VIX']))
        snapshot["india_vix"] = float(snapshot.get("INDIA_VIX", self.DEFAULTS['INDIA_VIX']))
        snapshot["Gold"] = float(snapshot.get("GOLD", self.DEFAULTS['GOLD']))
        snapshot["Silver"] = float(snapshot.get("SILVER", self.DEFAULTS['SILVER']))
        snapshot["Crude"] = float(snapshot.get("CRUDE", self.DEFAULTS['CRUDE']))
        snapshot["USDINR"] = float(snapshot.get("USDINR", self.DEFAULTS['USDINR']))
        snapshot["history"] = self.get_history_map()
        snapshot["freshness"] = freshness
        snapshot["availability"] = availability
        snapshot["trading_mode"] = "PAPER"
        return snapshot

    def snapshot(self) -> dict[str, float]:
        return self.get_snapshot(use_defaults=True)
