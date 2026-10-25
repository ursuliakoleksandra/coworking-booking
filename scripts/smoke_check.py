"""Перевірка розгорнутої системи (ЛР №5) — лише стандартна бібліотека Python.

    python scripts/smoke_check.py check                # доступність API + запити до БД
    python scripts/smoke_check.py write                # записати контрольні дані в БД
    python scripts/smoke_check.py read                 # перевірити, що дані пережили перезапуск

Адреса за замовчуванням http://localhost:8000 (змінюється параметром --host).
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

MARKER_EMAIL = "persistence-check@example.com"
MARKER_PASSWORD = "persistence-check-123"


def call(host: str, method: str, path: str, *, body=None, form=None, token=None):
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(host + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw)
        except ValueError:
            return err.code, None


def step(ok: bool, text: str) -> bool:
    print(f"[{'OK' if ok else 'FAIL'}] {text}")
    return ok


def check(host: str) -> bool:
    results = []
    status, data = call(host, "GET", "/health")
    results.append(
        step(
            status == 200 and data and data.get("status") == "ok", f"GET /health -> {status} {data}"
        )
    )
    status, data = call(host, "GET", "/rooms/")
    results.append(
        step(status == 200, f"GET /rooms/ (запит до БД) -> {status}, залів: {len(data or [])}")
    )

    email = f"smoke_{uuid.uuid4().hex[:10]}@example.com"
    status, _ = call(
        host,
        "POST",
        "/auth/register",
        body={"email": email, "full_name": "Smoke Test", "password": "smoke-pass-123"},
    )
    results.append(step(status == 201, f"POST /auth/register (запис у БД) -> {status}"))
    status, data = call(
        host, "POST", "/auth/login", form={"username": email, "password": "smoke-pass-123"}
    )
    token = data.get("access_token") if data else None
    results.append(
        step(status == 200 and bool(token), f"POST /auth/login (читання з БД) -> {status}")
    )
    status, data = call(host, "GET", "/auth/me", token=token)
    results.append(step(status == 200 and data.get("email") == email, f"GET /auth/me -> {status}"))
    return all(results)


def write(host: str) -> bool:
    status, _ = call(
        host,
        "POST",
        "/auth/register",
        body={"email": MARKER_EMAIL, "full_name": "Persistence Check", "password": MARKER_PASSWORD},
    )
    return step(status in (201, 409), f"контрольного користувача записано в БД (статус {status})")


def read(host: str) -> bool:
    status, data = call(
        host, "POST", "/auth/login", form={"username": MARKER_EMAIL, "password": MARKER_PASSWORD}
    )
    return step(
        status == 200 and bool(data), f"контрольні дані знайдено в БД (статус входу {status})"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "write", "read"))
    parser.add_argument("--host", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        ok = {"check": check, "write": write, "read": read}[args.command](args.host.rstrip("/"))
    except urllib.error.URLError as err:
        ok = step(False, f"сервер недоступний: {err.reason}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
