from __future__ import annotations

import os
from typing import Optional

from app.config.settings import get_settings


def get_database_url() -> str:
    """Return the database URL to use. Priority:
    - DATABASE_URL environment variable
    - settings.database_url
    - sqlite fallback for local development
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    try:
        settings_url = get_settings().database_url
        if settings_url and not settings_url.startswith("******"):
            return settings_url
    except Exception:
        pass
    # Fallback to a local sqlite file
    return "sqlite:///./data/dev.db"
