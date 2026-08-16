from __future__ import annotations

from dataclasses import dataclass


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

    def __init__(self, trading_mode: str = "PAPER"):
        self.trading_mode = trading_mode

    def snapshot(self) -> dict:
        return {
            "NIFTY": 22350.0,
            "BANKNIFTY": 48000.0,
            "India VIX": 15.4,
            "Gold": 71120.0,
            "Silver": 92100.0,
            "Crude": 6456.0,
            "USDINR": 83.4,
            "trading_mode": self.trading_mode,
        }
