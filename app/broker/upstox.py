from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import gzip
import json
from typing import Any
from urllib.parse import quote, urlencode
import httpx


class UpstoxAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    raw: dict[str, Any]


class UpstoxClient:
    """Documented API client. Order placement is intentionally out of scope for Phase 2."""
    auth_base = "https://api.upstox.com/v2"
    api_base = "https://api.upstox.com/v3"
    instruments_url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

    def __init__(self, api_key: str | None, api_secret: str | None, redirect_uri: str, access_token: str | None = None, client: httpx.AsyncClient | None = None):
        self.api_key, self.api_secret, self.redirect_uri, self.access_token = api_key, api_secret, redirect_uri, access_token
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers={"Accept": "application/json"})
        self._owns_client = client is None

    def authorization_url(self, state: str) -> str:
        if not self.api_key:
            raise UpstoxAPIError("UPSTOX_API_KEY is not configured")
        return f"{self.auth_base}/login/authorization/dialog?" + urlencode({"response_type": "code", "client_id": self.api_key, "redirect_uri": self.redirect_uri, "state": state})

    async def exchange_code(self, code: str) -> TokenResponse:
        if not self.api_key or not self.api_secret:
            raise UpstoxAPIError("UPSTOX_API_KEY and UPSTOX_API_SECRET are required")
        response = await self._client.post(f"{self.auth_base}/login/authorization/token", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"code": code, "client_id": self.api_key, "client_secret": self.api_secret, "redirect_uri": self.redirect_uri, "grant_type": "authorization_code"})
        self._raise_for_status(response)
        payload = response.json()
        return TokenResponse(access_token=payload["access_token"], raw=payload)

    async def download_instruments(self) -> list[dict[str, Any]]:
        response = await self._client.get(self.instruments_url)
        self._raise_for_status(response)
        try:
            # The documented .json.gz URL currently returns application/gzip without
            # a Content-Encoding header, so HTTP clients do not decode it for us.
            body = gzip.decompress(response.content) if response.content[:2] == b"\x1f\x8b" else response.content
            payload = json.loads(body)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpstoxAPIError("Instrument master could not be decoded as JSON") from exc
        if not isinstance(payload, list):
            raise UpstoxAPIError("Instrument master response is not a JSON list")
        return payload

    async def historical_candles(self, instrument_key: str, unit: str, interval: int, to_date: date, from_date: date | None = None) -> dict[str, Any]:
        path = f"/historical-candle/{quote(instrument_key, safe='')}/{unit}/{interval}/{to_date.isoformat()}"
        if from_date:
            path += f"/{from_date.isoformat()}"
        response = await self._client.get(self.api_base + path, headers=self._auth_headers())
        self._raise_for_status(response)
        return response.json()

    async def market_data_authorize_url(self) -> str:
        """Obtain the documented V3 authorized websocket endpoint."""
        response = await self._client.get(f"{self.api_base}/feed/market-data-feed/authorize", headers=self._auth_headers())
        self._raise_for_status(response)
        try:
            return response.json()["data"]["authorized_redirect_uri"]
        except (KeyError, TypeError) as exc:
            raise UpstoxAPIError("Market-data authorization response lacked websocket URL") from exc

    async def option_chain(self, underlying_key: str, expiry_date: date) -> dict[str, Any]:
        response = await self._client.get(f"{self.auth_base}/option/chain", params={"instrument_key": underlying_key, "expiry_date": expiry_date.isoformat()}, headers=self._auth_headers())
        self._raise_for_status(response)
        return response.json()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            raise UpstoxAPIError("An Upstox access token is required")
        return {"Authorization": f"Bearer {self.access_token}"}

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_error:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise UpstoxAPIError(f"Upstox API request failed ({response.status_code}): {detail}")
