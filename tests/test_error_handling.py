"""Безпечна обробка помилок 500: користувач не бачить внутрішні деталі (ЛР №3)."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

SECRET_DETAIL = "internal-detail-/app/app/secret_module.py"


def make_client(debug: bool) -> TestClient:
    cfg = Settings(
        _env_file=None,
        app_env="sandbox" if debug else "production",
        debug=debug,
        secret_key="x" * 40,
        redis_url="redis://localhost:6379/0",
        postgres_user="u",
        postgres_password="p",
        postgres_db="booking_sandbox" if debug else "booking_production",
    )
    app = create_app(cfg)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError(SECRET_DETAIL)

    return TestClient(app, raise_server_exceptions=False)


def test_production_hides_internal_details_on_500() -> None:
    response = make_client(debug=False).get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Внутрішня помилка сервера. Спробуйте пізніше."
    assert len(body["error_id"]) == 8
    assert SECRET_DETAIL not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_sandbox_debug_shows_traceback_for_developers() -> None:
    response = make_client(debug=True).get("/boom")
    assert response.status_code == 500
    assert "RuntimeError" in response.text


def test_docs_can_be_disabled_in_production() -> None:
    cfg = Settings(
        _env_file=None,
        app_env="production",
        enable_docs=False,
        secret_key="x" * 40,
        redis_url="redis://localhost:6379/0",
        postgres_user="u",
        postgres_password="p",
        postgres_db="booking_production",
    )
    client = TestClient(create_app(cfg))
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
