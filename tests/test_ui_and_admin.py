"""Інтерфейс, адмін-API, зали та доступність слотів."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.user import UserRole

ROOM = {
    "name": "Переговорна «Дніпро»",
    "room_type": "conference_room",
    "capacity": 8,
    "location": "3 поверх",
}


async def test_ui_page_and_assets_are_served(client: AsyncClient) -> None:
    page = await client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert (await client.get("/static/app.js")).status_code == 200
    assert (await client.get("/static/style.css")).status_code == 200


async def test_security_headers_are_set(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


async def test_only_admin_can_create_rooms(client: AsyncClient, make_user, auth_headers) -> None:
    await make_user("u@example.com", "user-password-1", role=UserRole.USER)
    await make_user("a@example.com", "admin-password-1", role=UserRole.ADMIN)

    assert (await client.post("/rooms/", json=ROOM)).status_code == 401

    user_headers = await auth_headers("u@example.com", "user-password-1")
    assert (await client.post("/rooms/", json=ROOM, headers=user_headers)).status_code == 403

    admin_headers = await auth_headers("a@example.com", "admin-password-1")
    created = await client.post("/rooms/", json=ROOM, headers=admin_headers)
    assert created.status_code == 201
    assert created.json()["room_type"] == "conference_room"

    listed = await client.get("/rooms/")
    assert [r["name"] for r in listed.json()] == [ROOM["name"]]


async def test_admin_lists_are_protected(client: AsyncClient, make_user, auth_headers) -> None:
    await make_user("u2@example.com", "user-password-2", role=UserRole.USER)
    await make_user("a2@example.com", "admin-password-2", role=UserRole.ADMIN)

    for path in ("/admin/users", "/admin/bookings"):
        assert (await client.get(path)).status_code == 401
        user_headers = await auth_headers("u2@example.com", "user-password-2")
        assert (await client.get(path, headers=user_headers)).status_code == 403
        admin_headers = await auth_headers("a2@example.com", "admin-password-2")
        assert (await client.get(path, headers=admin_headers)).status_code == 200


async def _setup_room_and_booking(client, make_user, auth_headers, when: datetime):
    await make_user("a3@example.com", "admin-password-3", role=UserRole.ADMIN)
    await make_user("u3@example.com", "user-password-3", role=UserRole.USER)
    admin_headers = await auth_headers("a3@example.com", "admin-password-3")
    user_headers = await auth_headers("u3@example.com", "user-password-3")
    room = (await client.post("/rooms/", json=ROOM, headers=admin_headers)).json()
    response = await client.post(
        "/bookings/",
        json={
            "room_id": room["id"],
            "start_time": when.isoformat(),
            "end_time": (when + timedelta(hours=1)).isoformat(),
        },
        headers=user_headers,
    )
    return room, admin_headers, user_headers, response


async def test_availability_shows_busy_slots_and_admin_sees_booking_owner(
    client: AsyncClient, make_user, auth_headers
) -> None:
    when = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    room, admin_headers, user_headers, created = await _setup_room_and_booking(
        client, make_user, auth_headers, when
    )
    assert created.status_code == 201

    day_start = when.replace(hour=0)
    params = {"start": day_start.isoformat(), "end": (day_start + timedelta(days=1)).isoformat()}
    busy = await client.get(
        f"/rooms/{room['id']}/availability", params=params, headers=user_headers
    )
    assert busy.status_code == 200
    assert len(busy.json()) == 1
    assert "user_id" not in busy.json()[0]  # інтервали не розкривають, хто забронював

    assert (await client.get(f"/rooms/{room['id']}/availability", params=params)).status_code == 401

    overview = await client.get("/admin/bookings", headers=admin_headers)
    assert overview.json()[0]["user_email"] == "u3@example.com"
    assert overview.json()[0]["room_name"] == ROOM["name"]


async def test_overlapping_booking_is_rejected_with_409(
    client: AsyncClient, make_user, auth_headers
) -> None:
    when = (datetime.now(UTC) + timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    room, _admin, user_headers, first = await _setup_room_and_booking(
        client, make_user, auth_headers, when
    )
    assert first.status_code == 201
    overlap = await client.post(
        "/bookings/",
        json={
            "room_id": room["id"],
            "start_time": (when + timedelta(minutes=30)).isoformat(),
            "end_time": (when + timedelta(minutes=90)).isoformat(),
        },
        headers=user_headers,
    )
    assert overlap.status_code == 409


async def test_booking_in_the_past_is_rejected(
    client: AsyncClient, make_user, auth_headers
) -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    _room, _admin, _user, response = await _setup_room_and_booking(
        client, make_user, auth_headers, past
    )
    assert response.status_code == 400
