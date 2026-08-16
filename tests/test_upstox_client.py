import httpx
import pytest
import gzip
import json
from app.broker.upstox import UpstoxClient


@pytest.mark.asyncio
async def test_authorization_url_contains_oauth_parameters():
    client = UpstoxClient("key", "secret", "http://localhost:4000/auth/upstox/callback")
    assert "response_type=code" in client.authorization_url("state-value")
    await client.aclose()


@pytest.mark.asyncio
async def test_exchange_code_uses_form_post():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v2/login/authorization/token"
        assert b"grant_type=authorization_code" in request.content
        return httpx.Response(200, json={"access_token": "test-token"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = UpstoxClient("key", "secret", "http://localhost:4000/callback", client=http)
        assert (await client.exchange_code("one-time-code")).access_token == "test-token"


@pytest.mark.asyncio
async def test_download_instruments_decodes_raw_gzip_master():
    compressed = gzip.compress(json.dumps([{"instrument_key": "NSE_INDEX|Nifty 50"}]).encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=compressed, headers={"Content-Type": "application/gzip"}))) as http:
        client = UpstoxClient(None, None, "http://localhost:4000/callback", client=http)
        assert (await client.download_instruments())[0]["instrument_key"] == "NSE_INDEX|Nifty 50"
