"""Інтеграційні тести авторизації та контролю доступу.

Покриває всі чотири сценарії з методички лабораторної роботи №2:
1. Анонімний доступ -> 401
2. Успішна автентифікація + помилки входу -> 200 / 401
3. Вертикальне розмежування ролей (user -> admin-панель) -> 403
4. Горизонтальне розмежування прав / IDOR (чуже бронювання) -> 403
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.room import Room, RoomType
from app.models.user import UserRole

# ---------------------------------------------------------------------------
# 1. Анонімний доступ
# ---------------------------------------------------------------------------


async def test_anonymous_access_to_user_home_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/home/user")
    assert response.status_code == 401


async def test_anonymous_access_to_bookings_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/bookings/my")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2. Успішна автентифікація та помилки входу
# ---------------------------------------------------------------------------


async def test_register_then_login_succeeds(client: AsyncClient) -> None:
    register_response = await client.post(
        "/auth/register",
        json={
            "email": "newbie@example.com",
            "full_name": "Newbie User",
            "password": "correct-password-1",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["role"] == UserRole.USER.value

    login_response = await client.post(
        "/auth/login",
        data={"username": "newbie@example.com", "password": "correct-password-1"},
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_with_wrong_password_is_rejected(client: AsyncClient, make_user) -> None:
    await make_user("bob@example.com", "correct-password-1")

    response = await client.post(
        "/auth/login",
        data={"username": "bob@example.com", "password": "totally-wrong-password"},
    )
    assert response.status_code == 401


async def test_login_with_unknown_email_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        data={"username": "ghost@example.com", "password": "does-not-matter"},
    )
    assert response.status_code == 401


async def test_authenticated_user_can_read_own_profile(
    client: AsyncClient, make_user, auth_headers
) -> None:
    await make_user("alice@example.com", "alice-password-1")
    headers = await auth_headers("alice@example.com", "alice-password-1")

    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


# ---------------------------------------------------------------------------
# 3. Вертикальне розмежування ролей
# ---------------------------------------------------------------------------


async def test_regular_user_cannot_access_admin_home(
    client: AsyncClient, make_user, auth_headers
) -> None:
    await make_user("regular@example.com", "regular-password-1", role=UserRole.USER)
    headers = await auth_headers("regular@example.com", "regular-password-1")

    response = await client.get("/home/admin", headers=headers)
    assert response.status_code == 403


async def test_admin_can_access_admin_home(client: AsyncClient, make_user, auth_headers) -> None:
    await make_user("boss@example.com", "boss-password-1", role=UserRole.ADMIN)
    headers = await auth_headers("boss@example.com", "boss-password-1")

    response = await client.get("/home/admin", headers=headers)
    assert response.status_code == 200


async def test_regular_user_can_access_own_home(
    client: AsyncClient, make_user, auth_headers
) -> None:
    await make_user("regular2@example.com", "regular-password-2", role=UserRole.USER)
    headers = await auth_headers("regular2@example.com", "regular-password-2")

    response = await client.get("/home/user", headers=headers)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4. Горизонтальне розмежування прав (IDOR)
# ---------------------------------------------------------------------------


async def _create_room(db_session) -> Room:
    room = Room(
        name="Переговорна №1",
        room_type=RoomType.CONFERENCE_ROOM,
        capacity=6,
        location="2-й поверх",
    )
    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)
    return room


async def test_user_cannot_view_or_cancel_someone_elses_booking(
    client: AsyncClient, make_user, auth_headers, db_session
) -> None:
    await make_user("owner@example.com", "owner-password-1", role=UserRole.USER)
    await make_user("intruder@example.com", "intruder-password-1", role=UserRole.USER)
    room = await _create_room(db_session)

    owner_headers = await auth_headers("owner@example.com", "owner-password-1")
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=1)

    create_response = await client.post(
        "/bookings/",
        json={
            "room_id": str(room.id),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=owner_headers,
    )
    assert create_response.status_code == 201
    booking_id = create_response.json()["id"]

    intruder_headers = await auth_headers("intruder@example.com", "intruder-password-1")

    read_response = await client.get(f"/bookings/{booking_id}", headers=intruder_headers)
    assert read_response.status_code == 403

    delete_response = await client.delete(f"/bookings/{booking_id}", headers=intruder_headers)
    assert delete_response.status_code == 403


async def test_owner_can_view_and_cancel_own_booking(
    client: AsyncClient, make_user, auth_headers, db_session
) -> None:
    await make_user("owner2@example.com", "owner-password-2", role=UserRole.USER)
    room = await _create_room(db_session)
    headers = await auth_headers("owner2@example.com", "owner-password-2")

    start = datetime.now(UTC) + timedelta(days=2)
    end = start + timedelta(hours=1)
    create_response = await client.post(
        "/bookings/",
        json={
            "room_id": str(room.id),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=headers,
    )
    booking_id = create_response.json()["id"]

    read_response = await client.get(f"/bookings/{booking_id}", headers=headers)
    assert read_response.status_code == 200

    delete_response = await client.delete(f"/bookings/{booking_id}", headers=headers)
    assert delete_response.status_code == 204


async def test_admin_can_view_and_cancel_any_booking(
    client: AsyncClient, make_user, auth_headers, db_session
) -> None:
    await make_user("owner3@example.com", "owner-password-3", role=UserRole.USER)
    await make_user("admin2@example.com", "admin-password-2", role=UserRole.ADMIN)
    room = await _create_room(db_session)

    owner_headers = await auth_headers("owner3@example.com", "owner-password-3")
    start = datetime.now(UTC) + timedelta(days=3)
    end = start + timedelta(hours=1)
    create_response = await client.post(
        "/bookings/",
        json={
            "room_id": str(room.id),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=owner_headers,
    )
    booking_id = create_response.json()["id"]

    admin_headers = await auth_headers("admin2@example.com", "admin-password-2")

    read_response = await client.get(f"/bookings/{booking_id}", headers=admin_headers)
    assert read_response.status_code == 200

    delete_response = await client.delete(f"/bookings/{booking_id}", headers=admin_headers)
    assert delete_response.status_code == 204
