# Algo Bot

PAPER-first, explainable Indian-market algorithmic trading and research system. It is designed to reject weak or unsafe trades; it does not promise returns and must not be treated as investment advice.

## Implemented: Phase 1 and Phase 2

- Python 3.12 FastAPI service with `PAPER` as the immutable default.
- Live mode validation: it additionally requires `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING`. No live order endpoint exists yet.
- PostgreSQL schema and Alembic migration for instrument master, OAuth anti-CSRF state, and system audit events.
- Upstox OAuth 2.0 authorization-code URL and server-side code exchange. Tokens are neither returned nor persisted to PostgreSQL.
- Current Upstox BOD instrument-master downloader and PostgreSQL upsert. It stores `instrument_key`, expiry, option attributes, lot/tick size, and raw source payload—contract symbols are not hardcoded.
- Historical candle V3 normalizer, idempotent OHLCV storage migration, IST session clock, 1m/5m/15m/1h-capable in-memory aggregator, and causal trend/VIX/cross-asset features.
- Feed V3 decoder and reconnecting market-data adapter through the current official Upstox Python SDK; normalized LTPC/full/options ticks are protected by stale/duplicate gates. It never places orders.

## Quick start (Windows PowerShell)

```powershell
Copy-Item .env.example .env
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d postgres
& .\.venv\Scripts\alembic.exe upgrade head
& .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 4000
```

Set `UPSTOX_REDIRECT_URI` in `.env` to the exact redirect URL registered in the Upstox developer app. The supplied app setting is `http://localhost:4000`; this implementation uses the more specific callback `http://localhost:4000/auth/upstox/callback`, so update the registered URL to match before OAuth login.

Then visit `http://localhost:4000/docs`, open `GET /auth/upstox/login`, and after authorization place the short-lived access token only in local secret storage / `.env` for the current session. Run `POST /instruments/sync` after the database migration to load the BOD master.

## Verification

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

At this checkpoint: `15 passed`. PostgreSQL migration was not executed because Docker and PostgreSQL are absent on this machine.

## Documentation

- [Architecture and delivery roadmap](docs/architecture.md)
- [Upstox integration findings](docs/upstox-api-notes.md)
- [Handoff / continuation log](docs/HANDOFF.md)
- [Risk-control design](docs/risk-controls.md)
