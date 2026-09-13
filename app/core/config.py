from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Централізовані налаштування застосунку.

    Значення підтягуються зі змінних середовища або файлу .env.
    """

    app_name: str = "Coworking & Conference Room Booking API"
    environment: str = "development"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://booking_user:booking_pass@localhost:5432/booking_db"

    # Redis (кеш + блокування ресурсів при конкурентному бронюванні)
    redis_url: str = "redis://localhost:6379/0"

    # Захист від подвійного бронювання одного й того ж слоту
    booking_lock_ttl_seconds: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
