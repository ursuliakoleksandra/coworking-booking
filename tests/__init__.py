import os

os.environ.update(
    {
        "APP_ENV": "test",
        "DEBUG": "false",
        "SECRET_KEY": "test-secret-key-only-for-pytest-runs-0123456789",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_pass",
        "POSTGRES_DB": "booking_test",
        "REDIS_URL": "redis://localhost:6379/15",
    }
)
