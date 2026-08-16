from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.config.settings import Settings
from app.data.models import MarketTick
from app.market.state import MarketState

DEFAULT_PAPER_INSTRUMENT_KEYS: tuple[str, ...] = (
    'NSE_INDEX|Nifty 50',
    'NSE_INDEX|Bank Nifty',
    'NSE_INDEX|India VIX',
    'MCX|GOLD',
    'MCX|SILVER',
    'MCX|CRUDE',
    'NSE_CURRENCY|USDINR',
)


@dataclass(frozen=True)
class RuntimeFeedConfig:
    token: str | None
    mode: str
    instrument_keys: tuple[str, ...]
    token_present: bool


def build_runtime_feed_config(settings: Settings) -> RuntimeFeedConfig:
    """Return the effective feed configuration derived from the environment and settings."""
    try:
        token = settings.upstox_access_token.get_secret_value() if settings.upstox_access_token else None
    except Exception:
        token = None
    mode = 'PAPER' if str(settings.trading_mode).upper() == 'PAPER' else 'LIVE'
    return RuntimeFeedConfig(
        token=token,
        mode=mode,
        instrument_keys=tuple(dict.fromkeys(DEFAULT_PAPER_INSTRUMENT_KEYS)),
        token_present=bool(token),
    )


def route_tick_to_market_state(state: MarketState, tick: MarketTick) -> str:
    """Apply a tick to the market state and return the resolved symbol name."""
    state.update_tick(tick)
    symbol = state._symbol_for_key(tick.instrument_key)
    return symbol


def route_ticks_to_market_state(state: MarketState, ticks: Iterable[MarketTick]) -> dict[str, float]:
    for tick in ticks:
        route_tick_to_market_state(state, tick)
    return state.get_snapshot()
