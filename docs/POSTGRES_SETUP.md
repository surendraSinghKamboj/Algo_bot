PostgreSQL setup and operational integration

This document describes how to initialize and run the database for local development and CI.

1) Environment

- The application reads the connection URL from the Settings (DATABASE_URL / config.get_settings().database_url).
- Default development URL (in code) is postgresql+psycopg2://postgres:postgres@localhost:5432/algo_bot. Override using environment variables in production.

2) Local setup (macOS / Linux / Windows using WSL or Docker)

- Install PostgreSQL or run with Docker:

  docker run --name algo-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=algo_bot -p 5432:5432 -d postgres:15

- Verify connectivity: psql -h localhost -U postgres -d algo_bot

3) Run migrations

- Ensure alembic and sqlalchemy are installed in the Python environment.
- Use the bundled script to wait for DB and apply migrations:

  python -m app.init_db

- The script will read the configured database URL and apply Alembic upgrades programmatically.

4) Troubleshooting

- If migrations fail because alembic is not installed, install with `pip install alembic`.
- If the application cannot connect, verify firewall / port forwarding and that the database is accepting connections.

5) Notes for CI

- CI pipelines should set DATABASE_URL to a reachable Postgres instance (could be service container) and run `python -m app.init_db` before running test suites requiring the DB.
