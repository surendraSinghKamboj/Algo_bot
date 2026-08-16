from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict

from app.data.models import MarketTick
from app.data import storage


class MarketIngestor:
    """Ingest market snapshots from a provider and persist ticks via data.storage.upsert_ticks.

    This component is intentionally small: it normalizes provider latest_snapshot outputs to
    MarketTick dataclasses and delegates persistence to the storage layer. Persistence is
    pluggable for testing (mock the storage.upsert_ticks function).
    """

    def __init__(self, provider, source: str = "provider"):
        self.provider = provider
        self.source = source

    def ingest_snapshot(self, session, mapping: Dict[str, str]) -> int:
        """Fetch latest snapshot from provider, map keys to instrument_keys and persist ticks.

        mapping: dict mapping provider snapshot keys (e.g., "NIFTY") -> instrument_key (e.g., "NSE_INDEX|Nifty 50")
        Returns the number of ticks persisted (as returned by storage.upsert_ticks).
        """
        snap = self.provider.latest_snapshot()
        now = datetime.now(timezone.utc)
        ticks = []
        for key, instrument_key in mapping.items():
            if key not in snap:
                continue
            price = snap[key]
            try:
                ltp = Decimal(str(price))
            except Exception:
                continue
            ticks.append(MarketTick(instrument_key=instrument_key, timestamp=now, ltp=ltp, volume=None, open_interest=None, source=self.source))
        if not ticks:
            return 0
        return storage.upsert_ticks(session, ticks)
