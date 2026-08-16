from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List


class MarketDataProvider:
    """Abstract provider interface for market data ingestion.

    Implementations should provide deterministic, testable outputs for latest_snapshot
    and historical_series. This is intentionally minimal so providers can adapt to
    external feeds (Upstox, files, mock streams).
    """

    def latest_snapshot(self) -> Dict[str, float]:
        raise NotImplementedError

    def historical_series(self, symbol: str, start: datetime, end: datetime) -> List[Dict[str, object]]:
        raise NotImplementedError


@dataclass
class MockMarketDataProvider(MarketDataProvider):
    """Deterministic mock provider used for tests and offline runs.

    Parameters:
        base_values: mapping of symbol -> float base price
        step: incremental change per minute for deterministic series
    """

    base_values: Dict[str, float]
    step: float = 1.0

    def latest_snapshot(self) -> Dict[str, float]:
        # Return a shallow copy so callers can't mutate internal state
        return dict(self.base_values)

    def historical_series(self, symbol: str, start: datetime, end: datetime) -> List[Dict[str, object]]:
        if symbol not in self.base_values:
            raise KeyError(symbol)
        results: List[Dict[str, object]] = []
        # Generate one-point-per-minute deterministic series
        current = start
        idx = 0
        while current <= end:
            price = float(self.base_values[symbol]) + idx * float(self.step)
            results.append({"time": current, "price": price})
            current = current + timedelta(minutes=1)
            idx += 1
        return results
