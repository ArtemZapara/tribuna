from __future__ import annotations

import pytest

from pydantic import ValidationError

from tribuna.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url == "sqlite:///./data/tribuna.db"
    assert settings.object_store == "filesystem"
    assert str(settings.object_root) == "data"
    assert str(settings.web_origin) == "http://localhost:5173/"
    assert settings.log_level == "INFO"


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIBUNA_ENV", "test")
    monkeypatch.setenv("TRIBUNA_DATABASE_URL", "postgresql://db/tribuna")
    monkeypatch.setenv("TRIBUNA_OBJECT_STORE", "s3")
    monkeypatch.setenv("TRIBUNA_OBJECT_ROOT", "/var/lib/tribuna")
    monkeypatch.setenv("TRIBUNA_WEB_ORIGIN", "https://tribuna.example")
    monkeypatch.setenv("TRIBUNA_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.database_url == "postgresql://db/tribuna"
    assert settings.object_store == "s3"
    assert str(settings.object_root) == "/var/lib/tribuna"
    assert str(settings.web_origin) == "https://tribuna.example/"
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TRIBUNA_ENV", "staging"),
        ("TRIBUNA_DATABASE_URL", "not-a-url"),
        ("TRIBUNA_OBJECT_STORE", "memory"),
        ("TRIBUNA_WEB_ORIGIN", "localhost:5173"),
        ("TRIBUNA_LOG_LEVEL", "verbose"),
    ],
)
def test_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
