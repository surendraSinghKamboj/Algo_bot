import pytest
from datetime import date

from app.market.option_adapter import OptionChainAdapter


class FakeClient:
    def __init__(self, payload):
        self._payload = payload
    async def option_chain(self, underlying_key, expiry_date):
        return self._payload


@pytest.mark.asyncio
async def test_fetch_option_chain_returns_payload():
    payload = {"calls": [], "puts": []}
    client = FakeClient(payload)
    adapter = OptionChainAdapter(client)
    result = await adapter.fetch_option_chain("NSE_INDEX|Nifty 50", date(2026, 8, 20))
    assert result is payload


@pytest.mark.asyncio
async def test_fetch_option_chain_validates_inputs():
    client = FakeClient({})
    adapter = OptionChainAdapter(client)
    with pytest.raises(ValueError):
        await adapter.fetch_option_chain("", date(2026, 8, 20))
    with pytest.raises(ValueError):
        await adapter.fetch_option_chain("NSE_INDEX|Nifty 50", None)
