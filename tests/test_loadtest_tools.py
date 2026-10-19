import pytest

from loadtests.check_double_booking import find_overlaps


def booking(
    room: str, start: str, end: str, status: str = "confirmed", user: str = "u@example.com"
) -> dict:
    return {
        "room_id": room,
        "room_name": f"Зал {room}",
        "user_email": user,
        "status": status,
        "start_time": f"2030-01-01T{start}:00+00:00",
        "end_time": f"2030-01-01T{end}:00+00:00",
    }


def test_no_overlap_when_slots_are_adjacent() -> None:
    result = find_overlaps([booking("a", "10:00", "11:00"), booking("a", "11:00", "12:00")])
    assert result["overlapping_pairs"] == 0


def test_overlap_in_same_room_is_detected() -> None:
    result = find_overlaps([booking("a", "10:00", "11:00"), booking("a", "10:30", "11:30")])
    assert result["overlapping_pairs"] == 1
    assert result["rooms_affected"] == 1
    assert result["examples"][0]["room"] == "Зал a"


def test_same_time_in_different_rooms_is_fine() -> None:
    result = find_overlaps([booking("a", "10:00", "11:00"), booking("b", "10:00", "11:00")])
    assert result["overlapping_pairs"] == 0


def test_cancelled_bookings_are_ignored() -> None:
    result = find_overlaps(
        [booking("a", "10:00", "11:00"), booking("a", "10:00", "11:00", status="cancelled")]
    )
    assert result["active_bookings"] == 1
    assert result["overlapping_pairs"] == 0


def point(t: float, users: int, p95: float) -> dict:
    return {"t": t, "users": users, "rps": 50.0, "fails": 0.0, "p50": 10.0, "p95": p95}


def test_knee_is_found_when_p95_jumps_and_stays_high() -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("docx")
    from loadtests.make_report import find_knee

    history = [point(i, 25, 50.0) for i in range(20)] + [
        point(20 + i, 100, 2000.0) for i in range(10)
    ]
    knee = find_knee(history)
    assert knee is not None
    assert knee["stage"]["users"] == 100
    assert knee["previous"]["users"] == 25


def test_no_knee_for_flat_latency() -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("docx")
    from loadtests.make_report import find_knee

    assert find_knee([point(i, 25, 50.0) for i in range(30)]) is None


def test_report_reads_cp1251_csv_written_by_locust_on_windows(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("docx")
    from loadtests.make_report import read_csv

    path = tmp_path / "run_failures.csv"
    path.write_bytes(
        "Method,Name,Error,Occurrences\nPOST,POST /bookings/,неочікуваний статус 0,2\n".encode(
            "cp1251"
        )
    )
    rows = read_csv(path)
    assert rows[0]["Error"] == "неочікуваний статус 0"
