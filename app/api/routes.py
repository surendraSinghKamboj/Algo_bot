from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.broker.upstox import UpstoxAPIError, UpstoxClient
from app.config.settings import Settings, get_settings
from app.data.instruments import upsert_instruments
from app.database.models import OAuthState
from app.database.session import get_db

router = APIRouter()


def client_from_settings(settings: Settings) -> UpstoxClient:
    return UpstoxClient(settings.upstox_api_key, settings.upstox_api_secret.get_secret_value() if settings.upstox_api_secret else None, settings.upstox_redirect_uri, settings.upstox_access_token.get_secret_value() if settings.upstox_access_token else None)


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "trading_mode": settings.trading_mode}


@router.get("/auth/upstox/login")
def login(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    state = secrets.token_urlsafe(32)
    db.add(OAuthState(state=state, expires_at=datetime.now(UTC) + timedelta(seconds=settings.oauth_state_ttl_seconds)))
    db.commit()
    try:
        return RedirectResponse(client_from_settings(settings).authorization_url(state))
    except UpstoxAPIError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/auth/upstox/callback")
async def callback(code: str, state: str, settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> dict:
    record = db.get(OAuthState, state)
    if record is None or record.consumed_at or record.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")
    client = client_from_settings(settings)
    try:
        token = await client.exchange_code(code)
    except UpstoxAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstox token exchange failed") from exc
    finally:
        await client.aclose()
    record.consumed_at = datetime.now(UTC)
    db.commit()
    return {"status": "authorized", "token_received": bool(token.access_token), "next_step": "Set UPSTOX_ACCESS_TOKEN in local secret storage for this session."}


@router.post("/instruments/sync")
async def sync_instruments(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> dict:
    client = client_from_settings(settings)
    try:
        payload = await client.download_instruments()
        return {"synced": upsert_instruments(db, payload)}
    except UpstoxAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Instrument sync failed") from exc
    finally:
        await client.aclose()
