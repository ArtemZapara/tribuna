"""Validated application configuration."""

from __future__ import annotations

import re

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
ObjectStoreKind = Literal["filesystem", "s3"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DATABASE_URL_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


class InvalidDatabaseURLError(ValueError):
    """Raised when the configured database URL has no valid scheme."""

    def __init__(self) -> None:
        super().__init__("database URL must include a valid scheme")


class Settings(BaseSettings):
    """Tribuna settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Environment = Field(
        default="development", validation_alias="TRIBUNA_ENV"
    )
    database_url: str = Field(
        default="sqlite:///./data/tribuna.db",
        validation_alias="TRIBUNA_DATABASE_URL",
    )
    object_store: ObjectStoreKind = Field(
        default="filesystem", validation_alias="TRIBUNA_OBJECT_STORE"
    )
    object_root: Path = Field(
        default=Path("./data"), validation_alias="TRIBUNA_OBJECT_ROOT"
    )
    web_origin: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:5173"),
        validation_alias="TRIBUNA_WEB_ORIGIN",
    )
    log_level: LogLevel = Field(default="INFO", validation_alias="TRIBUNA_LOG_LEVEL")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Reject empty or non-URL database configuration early."""
        if not DATABASE_URL_PATTERN.match(value):
            raise InvalidDatabaseURLError
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings singleton."""
    return Settings()
