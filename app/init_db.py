"""Utility script to wait for DB and apply Alembic migrations.

Run: python -m app.init_db
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.database.manager import run_alembic_upgrade_head, wait_for_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def main() -> int:
    # Wait for DB
    if not wait_for_db(timeout=30, interval=1.0):
        log.error("Database not available; aborting migrations")
        return 2
    try:
        run_alembic_upgrade_head()
    except Exception as exc:
        log.exception("Failed to run alembic migrations: %s", exc)
        return 1
    log.info("Migrations applied successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
