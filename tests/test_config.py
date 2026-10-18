"""Тести розділення конфігурацій: sandbox / production (ЛР №3)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SECRET = "x" * 40
DB = {"postgres_user": "u", "postgres_password": "p", "postgres_db": "booking_db"}


def make(**overrides) -> Settings:
    values = {"secret_key": SECRET, "redis_url": "redis://localhost:6379/0", **DB, **overrides}
    return Settings(_env_file=None, **values)


def test_debug_is_off_by_default() -> None:
    assert make(app_env="production", postgres_db="booking_production").debug is False


def test_production_rejects_debug_true() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        make(app_env="production", postgres_db="booking_production", debug=True)


def test_production_rejects_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        make(
            app_env="production",
            postgres_db="booking_production",
            secret_key="CHANGE-ME-" + "x" * 40,
        )


def test_short_secret_is_rejected_outside_tests() -> None:
    with pytest.raises(ValidationError, match="32"):
        make(app_env="sandbox", postgres_db="booking_sandbox", secret_key="short")


def test_production_cannot_use_sandbox_database() -> None:
    with pytest.raises(ValidationError, match="sandbox"):
        make(app_env="production", postgres_db="booking_sandbox")


def test_sandbox_cannot_use_production_database() -> None:
    with pytest.raises(ValidationError, match="production"):
        make(app_env="sandbox", postgres_db="booking_production")


def test_database_url_is_built_from_parts_and_escapes_password() -> None:
    cfg = make(
        app_env="sandbox",
        postgres_db="booking_sandbox",
        postgres_user="user",
        postgres_password="p@ss/word",
        postgres_host="db",
        postgres_port=5432,
    )
    assert (
        cfg.async_database_url == "postgresql+asyncpg://user:p%40ss%2Fword@db:5432/booking_sandbox"
    )


def test_hosting_style_database_url_is_normalized_to_asyncpg() -> None:
    cfg = Settings(
        _env_file=None,
        app_env="sandbox",
        secret_key=SECRET,
        redis_url="redis://localhost:6379/0",
        database_url="postgres://u:p@host:5432/booking_sandbox",
    )
    assert cfg.async_database_url.startswith("postgresql+asyncpg://")


def test_missing_secret_key_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(ValidationError, match="secret_key"):
        Settings(_env_file=None, redis_url="redis://localhost:6379/0", **DB)


def test_values_are_read_from_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SECRET_KEY",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "APP_ENV",
        "DEBUG",
        "REDIS_URL",
    ):
        monkeypatch.delenv(name)
    env_file = tmp_path / ".env.sandbox"
    env_file.write_text(
        "APP_ENV=sandbox\n"
        f"SECRET_KEY={SECRET}\n"
        "POSTGRES_USER=sandbox_user\n"
        "POSTGRES_PASSWORD=sandbox_pass\n"
        "POSTGRES_DB=booking_sandbox\n"
        "REDIS_URL=redis://localhost:6379/0\n"
        "DEBUG=true\n"
    )
    cfg = Settings(_env_file=env_file)
    assert cfg.app_env == "sandbox"
    assert cfg.debug is True
    assert cfg.postgres_db == "booking_sandbox"


def test_real_environment_variables_override_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Змінні, задані системою (Docker, хостинг), сильніші за значення з файлу."""
    env_file = tmp_path / ".env.sandbox"
    env_file.write_text("APP_ENV=sandbox\nDEBUG=true\nPOSTGRES_DB=booking_sandbox\n")
    monkeypatch.setenv("DEBUG", "false")
    cfg = Settings(_env_file=env_file)
    assert cfg.debug is False
