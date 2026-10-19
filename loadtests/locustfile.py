import os
import random
import time
import uuid
from datetime import UTC, datetime, timedelta

import gevent
from locust import HttpUser, between, events, task

ROOMS_NEEDED = int(os.getenv("LOADTEST_ROOMS", "5"))
PASSWORD = "loadtest-pass-123"


@events.test_start.add_listener
def prepare_environment(environment, **_kwargs) -> None:
    """Перед стартом: захист від запуску на production і підготовка залів."""
    import requests

    host = environment.host.rstrip("/")
    health = requests.get(f"{host}/health", timeout=10).json()
    if health.get("environment") == "production":
        environment.process_exit_code = 2
        raise SystemExit("ВІДМОВА: навантажувальні тести не можна запускати на production!")

    email = os.environ.get("LOADTEST_ADMIN_EMAIL")
    password = os.environ.get("LOADTEST_ADMIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Задайте LOADTEST_ADMIN_EMAIL і LOADTEST_ADMIN_PASSWORD")

    token = requests.post(
        f"{host}/auth/login", data={"username": email, "password": password}, timeout=30
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    existing = requests.get(f"{host}/rooms/", timeout=10).json()
    for i in range(len(existing), ROOMS_NEEDED):
        requests.post(
            f"{host}/rooms/",
            headers=headers,
            timeout=10,
            json={
                "name": f"Load-зал {i + 1}",
                "room_type": "conference_room" if i % 2 == 0 else "coworking_desk",
                "capacity": 6,
                "location": f"{i + 1} поверх",
            },
        ).raise_for_status()
    print(f"[loadtest] середовище: {health.get('environment')}, залів у базі: {ROOMS_NEEDED}")


class CoworkingUser(HttpUser):
    """Типовий користувач: переглядає багато, бронює рідше."""

    wait_time = between(1, 3)  # «час на роздуми» між діями
    weight = 9

    def on_start(self) -> None:
        self.email = f"load_{uuid.uuid4().hex[:12]}@example.com"
        self.client.post(
            "/auth/register",
            name="POST /auth/register",
            json={"email": self.email, "full_name": "Load User", "password": PASSWORD},
        )
        with self.client.post(
            "/auth/login",
            name="POST /auth/login",
            data={"username": self.email, "password": PASSWORD},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"login {resp.status_code}")
                self.stop()
                return
            self.client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        self.rooms = self.client.get("/rooms/", name="GET /rooms/").json()
        self.my_booking_ids: list[str] = []

    def _random_slot(self) -> tuple[str, str]:
        day = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(
            days=random.randint(1, 14)
        )
        start = day.replace(hour=random.randint(8, 18))
        return start.isoformat(), (start + timedelta(hours=1)).isoformat()

    def _book(self, room_id: str, start: str, end: str) -> None:
        with self.client.post(
            "/bookings/",
            name="POST /bookings/",
            json={"room_id": room_id, "start_time": start, "end_time": end},
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self.my_booking_ids.append(resp.json()["id"])
                resp.success()
            elif resp.status_code == 409:
                resp.success()  # слот уже зайнятий — нормальний бізнес-результат, не збій системи
            else:
                resp.failure(
                    "немає відповіді від сервера (збій з'єднання або таймаут)"
                    if resp.status_code == 0
                    else f"неочікуваний статус {resp.status_code}"
                )

    @task(1)
    def open_ui(self) -> None:
        self.client.get("/", name="GET /")

    @task(6)
    def browse_rooms(self) -> None:
        self.client.get("/rooms/", name="GET /rooms/")

    @task(5)
    def check_availability(self) -> None:
        room = random.choice(self.rooms)
        day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=random.randint(0, 7)
        )
        self.client.get(
            f"/rooms/{room['id']}/availability",
            name="GET /rooms/{id}/availability",
            params={"start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat()},
        )

    @task(3)
    def my_bookings(self) -> None:
        self.client.get("/bookings/my", name="GET /bookings/my")

    @task(2)
    def book_random_slot(self) -> None:
        start, end = self._random_slot()
        self._book(random.choice(self.rooms)["id"], start, end)

    @task(1)
    def cancel_booking(self) -> None:
        if self.my_booking_ids:
            booking_id = self.my_booking_ids.pop()
            self.client.delete(f"/bookings/{booking_id}", name="DELETE /bookings/{id}")


class PeakUser(CoworkingUser):
    """«Пікова» поведінка (початок тижня): усі натискають «Забронювати» одночасно.

    Кожні 10 секунд усі такі користувачі чекають спільного моменту і разом
    намагаються забронювати той самий НОВИЙ слот. Це перевіряє головний ризик
    предметної області — подвійне бронювання при конкурентному доступі.
    """

    weight = 1

    @task(8)
    def book_hot_slot(self) -> None:
        gevent.sleep(10 - time.time() % 10)  # синхронізація: старт у «круглу» десяту секунду
        bucket = int(time.time() // 10)
        day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        start = day + timedelta(hours=bucket % 4000)  # свіжий слот на кожне десятисекундне вікно
        room = self.rooms[bucket % len(self.rooms)]
        self._book(room["id"], start.isoformat(), (start + timedelta(hours=1)).isoformat())
