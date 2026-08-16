from __future__ import annotations

from dataclasses import dataclass

from app.market.state import MarketState


@dataclass(frozen=True)
class MarketSnapshot:
    NIFTY: float
    BANKNIFTY: float
    india_vix: float
    Gold: float
    Silver: float
    Crude: float
    USDINR: float
    trading_mode: str


class MarketDataService:
    """Local market snapshot service for dashboard display and research flows."""

    def __init__(self, trading_mode: str = "PAPER", provider=None):
        self.trading_mode = trading_mode
        self.provider = provider
        self.market_state = MarketState()

    def snapshot(self) -> dict:
        if self.provider is not None:
            values = dict(self.provider.latest_snapshot())
        else:
            values = self.market_state.get_snapshot()
        values["India VIX"] = values.get("India VIX", values.get("INDIA_VIX", 0.0))
        values["trading_mode"] = self.trading_mode
        return values
