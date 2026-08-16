import pytest
from datetime import date

from app.market.option_adapter import OptionChainAdapter


class FakeClient:
    def __init__(self, payload):
        self._payload = payload
    async def option_chain(self, underlying_key, expiry_date):
        return self._payload


@pytest.mark.asyncio
async def test_fetch_and_store_calls_storage(monkeypatch):
    payload = {"calls": [], "puts": []}
    client = FakeClient(payload)
    adapter = OptionChainAdapter(client)

    recorded = {}

    async def fake_fetch_option_chain(self, underlying_key, expiry_date):
        return payload

    def fake_store(session, underlying_key, expiry_at, payload_in):
        recorded['called'] = True
        recorded['underlying'] = underlying_key
        recorded['payload'] = payload_in
        return 123

    monkeypatch.setattr('app.market.option_adapter.OptionChainAdapter.fetch_option_chain', fake_fetch_option_chain)
    monkeypatch.setattr('app.data.storage.store_option_chain_snapshot', fake_store)

    sid = await adapter.fetch_and_store(session=None, underlying_key="NSE_INDEX|Nifty 50", expiry=date(2026,8,20))
    assert sid == 123
    assert recorded.get('called') is True
    assert recorded.get('underlying') == "NSE_INDEX|Nifty 50"
    assert recorded.get('payload') == payload
