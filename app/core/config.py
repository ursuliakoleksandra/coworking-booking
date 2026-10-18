import os
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

ENV_FILE = f".env.{os.getenv('APP_ENV', 'sandbox')}"
_PLACEHOLDER = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["sandbox", "production", "test"] = "sandbox"
    app_name: str = "Coworking & Conference Room Booking API"

    debug: bool = False
    enable_docs: bool = True

    secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    database_url: str | None = None
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    postgres_db: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str
    booking_lock_ttl_seconds: int = 10

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            for prefix in ("postgres://", "postgresql://"):
                if self.database_url.startswith(prefix):
                    return "postgresql+asyncpg://" + self.database_url[len(prefix) :]
            return self.database_url
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value() if self.postgres_password else None,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def database_name(self) -> str:
        if self.database_url:
            return make_url(self.async_database_url).database or ""
        return self.postgres_db or ""

    @model_validator(mode="after")
    def _check_environment_rules(self) -> "Settings":
        if not self.database_url and not (
            self.postgres_user and self.postgres_password and self.postgres_db
        ):
            raise ValueError(
                "Задайте DATABASE_URL або всі три змінні: "
                "POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB"
            )

        secret = self.secret_key.get_secret_value()
        db_name = self.database_name.lower()

        if self.app_env != "test" and len(secret) < 32:
            raise ValueError("SECRET_KEY має містити щонайменше 32 символи")

        if self.app_env == "production":
            if self.debug:
                raise ValueError("У production DEBUG має бути false")
            if _PLACEHOLDER in secret.lower():
                raise ValueError("У production SECRET_KEY не може бути значенням-заглушкою")
            password = self.postgres_password.get_secret_value() if self.postgres_password else ""
            if _PLACEHOLDER in password.lower():
                raise ValueError("У production POSTGRES_PASSWORD не може бути заглушкою")
            if "sandbox" in db_name or "test" in db_name:
                raise ValueError("Production не може використовувати sandbox/test базу даних")

        if self.app_env == "sandbox" and "prod" in db_name:
            raise ValueError("Sandbox не може використовувати production базу даних")

        return self


settings = Settings()
