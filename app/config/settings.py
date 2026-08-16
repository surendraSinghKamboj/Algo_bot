from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_confirmation: SecretStr | None = None
    database_url: str = "postgresql+psycopg://algo:algo@localhost:5432/algo_bot"
    log_level: str = "INFO"
    upstox_api_key: str | None = None
    upstox_api_secret: SecretStr | None = None
    upstox_redirect_uri: str = "http://localhost:4000/auth/upstox/callback"
    upstox_access_token: SecretStr | None = None
    upstox_analytics_token: SecretStr | None = None
    oauth_state_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    @field_validator("live_trading_confirmation")
    @classmethod
    def require_explicit_live_confirmation(cls, value: SecretStr | None, info):
        if info.data.get("trading_mode") == TradingMode.LIVE and (value is None or value.get_secret_value() != "I_UNDERSTAND_LIVE_TRADING"):
            raise ValueError("LIVE requires LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
