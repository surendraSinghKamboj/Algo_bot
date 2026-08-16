from __future__ import annotations

from datetime import date
from typing import Any


class OptionChainAdapter:
    """Simple adapter to fetch option chain payloads from an async Upstox-like client.

    The adapter intentionally does not persist data; callers can pass the result to the
    data.storage layer. This keeps the adapter testable and side-effect free.
    """

    def __init__(self, client: Any):
        self.client = client

    async def fetch_option_chain(self, underlying_key: str, expiry: date) -> dict:
        if not underlying_key:
            raise ValueError("underlying_key is required")
        if not expiry:
            raise ValueError("expiry date is required")
        payload = await self.client.option_chain(underlying_key, expiry)
        if not isinstance(payload, dict):
            raise RuntimeError("unexpected option chain payload type")
        return payload

    async def fetch_and_store(self, session, underlying_key: str, expiry: date) -> int:
        """Fetch option chain from client and persist via data.storage.store_option_chain_snapshot.

        Returns the created snapshot id.
        """
        from datetime import datetime
        from app.data import storage

        payload = await self.fetch_option_chain(underlying_key, expiry)
        # convert expiry date to a datetime at UTC midnight for storage
        if hasattr(expiry, "isoformat"):
            # expiry may be date or datetime
            expiry_dt = datetime.combine(expiry, datetime.min.time()) if expiry.__class__.__name__ == 'date' else expiry
        else:
            expiry_dt = expiry
        return storage.store_option_chain_snapshot(session, underlying_key, expiry_dt, payload)
