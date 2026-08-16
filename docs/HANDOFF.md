# Continuation handoff

Last updated: 2026-08-16. This file is the working context for the next engineer/AI.

## Current state

Repository was empty at start. Phases 1–2 and the Phase 3–4 data/feature foundation are implemented. The code is intentionally not a trading bot yet: there is no order-placement, paper-fill, strategy, or dashboard code.

`TRADING_MODE` defaults to `PAPER`. Even when configured `LIVE`, no real broker order can currently be sent. `.env.example` contains placeholders only. Never log, return, or persist `UPSTOX_API_SECRET` or access tokens.

## File map

- `app/config/settings.py`: Pydantic Settings and live-mode guard.
- `app/database/models.py`: foundation SQLAlchemy schema.
- `alembic/versions/20260816_0001_phase_one_schema.py`: initial PostgreSQL migration.
- `app/broker/upstox.py`: OAuth URL/code exchange, BOD master download, V3 historical candles.
- `app/data/instruments.py`: normalization/PostgreSQL upsert of BOD master.
- `app/data/models.py`, `app/data/candles.py`, `app/data/ohlcv.py`: canonical market objects, historical payload normalization, IST-aligned aggregation.
- `app/data/streaming.py`: Feed V3 binary subscription envelope and stale/duplicate gate.
- `app/broker/upstox_feed.py`: market-data-only wrapper around official Upstox SDK V3 protobuf decoder; parses `ltpc`, full-feed and first-level-with-Greeks messages into canonical ticks with bounded reconnect behavior.
- `app/data/storage.py`: idempotent PostgreSQL OHLCV upsert.
- `app/features/market_features.py`: causal rolling trend/momentum/realized-volatility, VIX and cross-asset features.
- `app/api/routes.py`: health, OAuth login/callback, manual master sync.
- `docs/upstox-api-notes.md`: verified API details/known gaps.
- `docs/architecture.md`, `docs/risk-controls.md`: target system contract.

## How it was validated

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
# 15 passed
```

The local system had no `python`, `docker`, or `psql` command installed. Bundled Python 3.12.13 created `.venv`. Dependencies in `requirements.txt` are installed there. No PostgreSQL instance was available, so Alembic has not been applied; after Docker is available, run `docker compose up -d postgres` then `alembic upgrade head`.

## Important OAuth adjustment

The supplied Upstox app was reported as configured with `http://localhost:4000`. The code uses a specific callback: `http://localhost:4000/auth/upstox/callback`. Upstox requires exact redirect-URI matching. Either update the developer app to that precise value (recommended) or change `UPSTOX_REDIRECT_URI` and routes together before testing login.

## Next implementation slice: close remaining data foundation

1. Configure a token and perform a non-trading live market-data smoke test (subscribe only to `NSE_INDEX|Nifty 50`), then verify received ticks and shutdown. Do not put tokens in the repo.
2. Add raw-tick, option-chain snapshot, feature, regime, signal and audit-decision migrations. Partition raw tick data before using it in production.
3. Add historical-loader pagination based on documented V3 retrieval windows and persist normalized candle batches with source metadata.
4. Add lag scan/covariance and tests; validate actual historical coverage before pair/option research.

## Later slices

- Phase 5: interpretable regime rules and stored decision output.
- Phase 6–7: NIFTY defined-risk debit spreads/hedges plus dynamic hedge ratio and deterministic risk gates.
- Phase 8: event-driven cost-aware backtester, then walk-forward/stress testing.
- Phase 9–10: paper executor, reconciliation, dashboard/alerts.
- Phase 11–12: operational stress tests and a separately authorized live executor.

## Non-negotiables

- Never hardcode contract symbols, lot sizes, secrets, risk settings, or trading decisions.
- No claimed backtest/performance until actual historical data is downloaded, an artifact exists, and costs are modelled.
- Keep real broker execution in a separate adapter and never call it from feature/strategy code.
- Persist explanatory rejection reasons; `NO TRADE` is a normal expected output.
