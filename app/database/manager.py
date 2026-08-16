from __future__ import annotations

import logging
import os
import time
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import Engine

from app.config.db import get_database_url
from app.config.settings import get_settings

log = logging.getLogger(__name__)


def create_db_engine(url: Optional[str] = None, **kwargs) -> Engine:
    """Create and return a SQLAlchemy engine using configured database URL.

    Args:
        url: optional override for the database URL. If None, uses settings.database_url.
    """
    if url is None:
        url = get_database_url()
    engine = create_engine(url, pool_pre_ping=True, future=True, **kwargs)
    return engine


def wait_for_db(url: Optional[str] = None, timeout: int = 30, interval: float = 1.0) -> bool:
    """Wait for the database to become reachable.

    Returns True if DB became available within timeout, False otherwise.
    """
    engine = create_db_engine(url)
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            log.info("Database reachable at %s", url or get_settings().database_url)
            return True
        except OperationalError as exc:
            log.debug("Database not ready, retrying: %s", exc)
            time.sleep(interval)
    log.error("Timed out waiting for database at %s", url or get_settings().database_url)
    return False


def run_alembic_upgrade_head(alembic_ini_path: Optional[str] = None) -> None:
    """Run alembic upgrade head programmatically.

    alembic_ini_path: path to alembic.ini; if None, will attempt to use project root alembic.ini
    """
    try:
        from alembic.config import Config
        from alembic import command
    except Exception as exc:  # pragma: no cover - optional dependency
        log.error("Alembic is not installed or cannot be imported: %s", exc)
        raise

    if alembic_ini_path is None:
        current_dir = os.path.dirname(os.path.dirname(__file__))
        alembic_ini_path = os.path.join(current_dir, os.pardir, "alembic.ini")
        alembic_ini_path = os.path.abspath(alembic_ini_path)

    cfg = Config(alembic_ini_path)
    # Ensure sqlalchemy.url is set from settings in runtime as well
    cfg.set_main_option("sqlalchemy.url", get_database_url())
    log.info("Running alembic upgrade head using %s", alembic_ini_path)
    command.upgrade(cfg, "head")
