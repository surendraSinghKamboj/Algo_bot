Configuration Reference
=======================

This file lists important environment variables and their purpose. Do NOT store real credentials in source control.

Environment variables
---------------------
- DATABASE_URL: SQLAlchemy-compatible database URL (postgres recommended)
  - Example: postgresql+psycopg://user:password@localhost:5432/algo_bot
  - In development the app falls back to sqlite:///./data/dev.db
- UPSTOX_API_KEY: Upstox API key (public)
- UPSTOX_API_SECRET: Upstox API secret (sensitive)
- UPSTOX_REDIRECT_URI: OAuth redirect URI for Upstox
- UPSTOX_ACCESS_TOKEN: Access token (sensitive). Prefer storing in secure secret storage.
- TRADING_MODE: PAPER or LIVE (default PAPER)
- LIVE_TRADING_CONFIRMATION: string required to enable LIVE mode. Must be set to I_UNDERSTAND_LIVE_TRADING to enable LIVE.
- LOG_LEVEL: DEBUG/INFO/WARNING/ERROR

Security notes
--------------
- Never expose UPSTOX_API_SECRET or access tokens in API responses, logs, or OpenAPI examples.
- Use a secret manager for production storage; .env is acceptable for development.

Database recommendations
------------------------
- Use PostgreSQL 12+ for production and enable SSL on remote connections.
- Use a dedicated user with minimal privileges.
- Do not hardcode credentials into code. Use DATABASE_URL environment variable.

Local development
-----------------
- The app will fall back to a local sqlite database file at ./data/dev.db when DATABASE_URL is not set.
- To run migrations against a real Postgres instance, set DATABASE_URL and run: python -m app.init_db

Runtime commands
----------------
- Start backend (development): .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
- Apply migrations: .venv\Scripts\python.exe -m app.init_db

This file does not include secrets. Add secrets via environment or secure vault.
