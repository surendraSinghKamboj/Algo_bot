Front-end Handoff
==================
This document explains how to use the backend APIs and model shapes to build a production-grade front-end.

Backend server
--------------
- Default dev base URL: http://localhost:8000
- Swagger UI (OpenAPI): http://localhost:8000/docs

Authentication flow
-------------------
- Upstox OAuth start: GET /auth/upstox/login (server responds with a redirect to Upstox)
- Upstox OAuth callback: GET /auth/upstox/callback?code=<code>&state=<state>
  - The server marks the OAuth state consumed and returns a suggestion to store UPSTOX_ACCESS_TOKEN locally.

CORS
----
- Development allowed origins include http://localhost:3000 and http://localhost:5173. If the front-end runs on another origin, add it to app/main.py CORSMiddleware allow_origins.

API endpoints mapping to dashboard widgets
-----------------------------------------
- Main dashboard widget -> GET /dashboard/state
- Positions screen -> GET /portfolio/positions (not yet implemented; use /dashboard/state positions key as temporary source)
- Signals screen -> GET /signals/current (not yet implemented; use /dashboard/state.signal)
- Options screen -> GET /options/chain?underlying=...&expiry=... (not yet implemented; OptionChainAdapter exists)
- Risk screen -> GET /risk/portfolio (not yet implemented; use /dashboard/state.risk temporarily)
- Backtest screen -> POST /backtest/run (not yet implemented)
- System screen -> GET /health and GET /system/status (system routes may be added)

Polling vs Streaming
--------------------
- Polling: Safe default for development: poll /dashboard/state every 2–3 seconds.
- Streaming: For production, use WebSocket to subscribe to tick updates, signals and order events. See docs/WEBSOCKET.md for the design.

Response format
---------------
- All API responses use an envelope: {success, data, error, timestamp, request_id}.
- Frontend should check `success` and handle `error` object consistently.

Error codes
-----------
- See docs/ERROR_CODES.md for a canonical list. Frontend should map codes to user-friendly messages and appropriate UI states (e.g., LIVE_MODE_NOT_CONFIRMED -> show big live warning and disable live order buttons).

Rate limits and caching
-----------------------
- Add local caching on expensive endpoints (option chain, historical candles). The backend will provide cache headers in the future.
- For market tick-level data prefer streaming.

Best practices
--------------
- Distinguish PAPER vs LIVE visually and hide or disable live order flows unless the backend configuration explicitly allows them.
- Use HTTPS in production and secure storage for access tokens.
- Polling interval suggestions:
  - Dashboard: 2-3s
  - Positions: 3-5s
  - Risk: 5-10s
  - Option chain: on-demand (when user opens options screen)

Building the UI
---------------
- Main dashboard: GET /dashboard/state -> map values to cards (market, regime, P&L, positions, risk)
- Positions: derive from /dashboard/state.positions until /portfolio endpoints are implemented
- Signals: GET /signals/current when implemented; otherwise show last known signal from /dashboard/state
- Options: call /options endpoints for chain data; show Greeks and payoff chart using client-side payoff calculator (backend will also provide payoff endpoint)

Contact points for missing APIs
-------------------------------
- If an endpoint needed by the UI is missing, open an issue or add a route under the appropriate namespace: /market, /options, /signals, /portfolio.

This file is intended to quickly allow another AI or front-end team to build a UI without reading implementation code. For more detailed models and schemas, see docs/DATA_MODELS.md and docs/API.md.
