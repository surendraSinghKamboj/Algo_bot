Overview
========

This document describes the HTTP API surface exposed by the Algo Bot backend (FastAPI).
The live OpenAPI/Swagger is available at: /docs (default server: http://localhost:8000/docs)

Base URL
--------
- Default (development): http://localhost:8000

Response envelope
-----------------
All successful responses follow this structure unless otherwise noted:

{
  "success": true,
  "data": {...},
  "error": null,
  "timestamp": "2026-08-16T14:20:03.508Z",
  "request_id": "..."
}

Error responses follow this structure:

{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {...}
  },
  "timestamp": "...",
  "request_id": "..."
}

Implemented REST endpoints (current repository)
----------------------------------------------

1) Health
---------
- Method: GET
- URL: /health
- Purpose: Basic liveness and trading mode check
- Authentication: none
- Request: none
- Response schema:
  {
    "status": "ok",
    "trading_mode": "PAPER"
  }
- Example curl: curl http://localhost:8000/health
- PAPER vs LIVE: returns the configured trading_mode from settings
- Read-only: yes

2) Dashboard state
------------------
- Method: GET
- URL: /dashboard/state
- Purpose: Return a snapshot used by monitoring UIs. Includes market values, regime, signal, positions, orders and risk summaries.
- Authentication: none (development). For production, protect or require API auth.
- Response schema (example):
  {
    "trading_mode": "PAPER",
    "broker_connected": false,
    "market": {"NIFTY": 22350.0, "BANKNIFTY": 48000.0, "India VIX": 15.4, "Gold": 71120.0, "Silver": 92100.0, "Crude": 6456.0, "USDINR": 83.4},
    "regime": "BULL_TREND",
    "signal": "NO TRADE",
    "risk": 0.018,
    "drawdown": 0.09,
    "margin_utilization": 0.23,
    "positions": [{"instrument":"NSE_INDEX|Nifty 50","qty":0,"pnl":0.0}],
    "orders": [{"status":"SIMULATED","qty":0}],
    "kill_switch_state": "OK",
    "no_trade_reason": "No trade; awaiting a risk-adjusted setup."
  }
- Read-only: yes

3) Upstox login (OAuth start)
-----------------------------
- Method: GET
- URL: /auth/upstox/login
- Purpose: Start the OAuth flow with Upstox. Stores an OAuth state in DB and redirects the user to Upstox auth dialog.
- Authentication: none (used for browser-based OAuth flows)
- Request params: none
- Response: HTTP Redirect to Upstox authorization URL (307)
- Errors: 503 if Upstox client not configured or Unavailable
- PAPER vs LIVE: this controls broker integration; no live orders are placed by this route.
- Note: This route is stateful (writes a transient OAuthState to DB) and thus state-changing.

4) Upstox OAuth callback
------------------------
- Method: GET
- URL: /auth/upstox/callback?code=...&state=...
- Purpose: Exchange authorization code for access token and mark the OAuth state consumed.
- Authentication: none (callback)
- Request params: code (query), state (query)
- Response: JSON indicating token_received boolean and next steps.
- Errors: 400 if state invalid/expired, 502 if token exchange fails
- State-changing: yes (updates the OAuthState record as consumed)

5) Instrument sync
------------------
- Method: POST
- URL: /instruments/sync
- Purpose: Download instrument master from Upstox and upsert into the local instruments table.
- Authentication: Upstox credentials in settings required; for testing the client may be stubbed.
- Request body: none
- Response: {"synced": <int>} number of instruments upserted
- Errors: 502 if Upstox API fails
- State-changing: yes (mutates instrument master table)

Additional endpoints
--------------------
The backend contains other modules (market ingestion, option adapter, strategy engines, risk engines). Where API endpoints are not yet implemented, prefer exposing them with REST endpoints under logical prefixes:
- /market/* (market snapshots, instrument search, historical candles)
- /options/* (option chain, expiries, option details)
- /signals/* (current signal, history)
- /portfolio/* (positions, orders, account state)
- /risk/* (risk snapshots, metrics)
- /trading/* (paper order endpoints, live order endpoints behind safety gate)
- /backtest/* (run backtests, query results)

Each of these endpoints should follow the standard response envelope and be documented in docs/DATA_MODELS.md and docs/FRONTEND_HANDOFF.md.

OpenAPI and Swagger
-------------------
- OpenAPI JSON: /openapi.json
- Swagger UI: /docs
- ReDoc: /redoc

Authentication
--------------
Currently the system uses OAuth for Upstox broker integration. API-level auth (JWT/API key) is not implemented by default; if required add an authentication dependency to routes.

Notes for frontend developers
----------------------------
- The dashboard endpoints are read-only and safe to poll frequently (e.g., 1-3s) for development. For production, prefer WebSocket streaming.
- The Upstox OAuth flow requires setting UPSTOX_API_KEY and UPSTOX_API_SECRET in environment or .env and a reachable UPSTOX_REDIRECT_URI.

Change log
----------
- 2026-08-16: Initial API.md covering implemented endpoints and usage examples.
