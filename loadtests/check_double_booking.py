"""Перевірка цілісності даних після тесту: чи немає подвійних бронювань.

Читає всі бронювання через /admin/bookings і шукає активні бронювання одного
залу з перетином за часом. Результат — JSON для звіту.

    LOADTEST_ADMIN_EMAIL=... LOADTEST_ADMIN_PASSWORD=... python loadtests/check_double_booking.py --host http://localhost:8000
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def find_overlaps(bookings: list[dict]) -> dict:
    active = [b for b in bookings if b["status"] != "cancelled"]
    by_room: dict[str, list[dict]] = {}
    for b in active:
        by_room.setdefault(b["room_id"], []).append(b)

    pairs = []
    for room_id, items in by_room.items():
        items.sort(key=lambda b: datetime.fromisoformat(b["start_time"]))
        for i, a in enumerate(items):
            a_end = datetime.fromisoformat(a["end_time"])
            for b in items[i + 1 :]:
                if datetime.fromisoformat(b["start_time"]) >= a_end:
                    break
                pairs.append((room_id, a, b))
    return {
        "active_bookings": len(active),
        "overlapping_pairs": len(pairs),
        "rooms_affected": len({p[0] for p in pairs}),
        "examples": [
            {
                "room": p[1]["room_name"],
                "start": p[1]["start_time"],
                "users": [p[1]["user_email"], p[2]["user_email"]],
            }
            for p in pairs[:3]
        ],
    }


def main() -> None:
    import requests

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--out", default="loadtests/results/double_booking.json")
    args = parser.parse_args()

    token = requests.post(
        f"{args.host}/auth/login",
        data={
            "username": os.environ["LOADTEST_ADMIN_EMAIL"],
            "password": os.environ["LOADTEST_ADMIN_PASSWORD"],
        },
        timeout=30,
    ).json()["access_token"]
    bookings = requests.get(
        f"{args.host}/admin/bookings", headers={"Authorization": f"Bearer {token}"}, timeout=120
    ).json()
    result = find_overlaps(bookings)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[check] активних бронювань: {result['active_bookings']}, пар з перетином: {result['overlapping_pairs']}"
    )


if __name__ == "__main__":
    main()
