import argparse
import getpass
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import psutil
import requests

HERE = Path(__file__).parent
PROFILES = {
    "smoke": {
        "title": "Smoke (контрольний, 5 VU)",
        "users": 5,
        "rate": 1,
        "time": "30s",
        "file": "locustfile.py",
    },
    "baseline": {
        "title": "Baseline (початковий, 20 VU)",
        "users": 20,
        "rate": 2,
        "time": "3m",
        "file": "locustfile.py",
    },
    "peak": {
        "title": "Peak (30 VU б'ються за спільні слоти)",
        "users": 30,
        "rate": 10,
        "time": "60s",
        "file": "locustfile.py",
        "classes": ["PeakUser"],
    },
    "stress": {
        "title": "Stress (ступінчасте, до 200 VU)",
        "users": 200,
        "rate": 10,
        "time": None,
        "file": "locustfile_step.py",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, default="baseline")
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--results", default=str(HERE / "results"))
    parser.add_argument(
        "--containers",
        nargs="*",
        default=["coworking-sandbox-app-1", "coworking-sandbox-db-1"],
        help="імена контейнерів для docker stats",
    )
    parser.add_argument(
        "--match",
        action="append",
        default=[],
        help="замість Docker: збирати CPU/RAM процесів, у назві яких є рядок",
    )
    parser.add_argument(
        "--log-file", help="файл логу сервера (якщо застосунок запущено без Docker)"
    )
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    results = Path(args.results)
    results.mkdir(parents=True, exist_ok=True)
    for old in results.glob("*"):
        old.unlink()

    health = requests.get(f"{args.host}/health", timeout=10).json()
    if health.get("environment") == "production":
        sys.exit("ВІДМОВА: це production. Навантажувальні тести — лише для sandbox.")
    if not os.environ.get("LOADTEST_ADMIN_EMAIL"):
        os.environ["LOADTEST_ADMIN_EMAIL"] = input("Email адміністратора sandbox: ").strip()
    if not os.environ.get("LOADTEST_ADMIN_PASSWORD"):
        os.environ["LOADTEST_ADMIN_PASSWORD"] = getpass.getpass("Пароль адміністратора: ")

    monitor_cmd = [
        sys.executable,
        str(HERE / "monitor.py"),
        "--out",
        str(results / "resources.csv"),
    ]
    if args.match:
        monitor_cmd += [x for m in args.match for x in ("--match", m)]
        monitor_mode = "psutil (процеси: " + ", ".join(args.match) + ")"
    else:
        monitor_cmd += ["--containers", *args.containers]
        monitor_mode = "docker stats (" + ", ".join(args.containers) + ")"

    locust_cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(HERE / profile["file"]),
        "--headless",
        "--host",
        args.host,
        "--csv",
        str(results / "run"),
        "--csv-full-history",
        "--html",
        str(results / "run.html"),
        "--only-summary",
    ]
    if profile["time"]:
        locust_cmd += [
            "-u",
            str(profile["users"]),
            "-r",
            str(profile["rate"]),
            "-t",
            profile["time"],
        ]
    # для ступінчастого профілю кількість VU і швидкість задає LoadTestShape
    locust_cmd += profile.get("classes", [])

    started = datetime.now()
    print(f"[run] профіль: {profile['title']}\n[run] середовище: {health.get('environment')}")
    monitor = subprocess.Popen(monitor_cmd)
    time.sleep(3)  # кілька вимірів «в спокої» до початку навантаження
    try:
        subprocess.run(locust_cmd, check=False)
    finally:
        time.sleep(3)
        monitor.terminate()
        monitor.wait(timeout=15)

    log_text = ""
    if args.log_file:
        log_text = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
    elif not args.match:
        out = subprocess.run(
            ["docker", "logs", "--since", started.astimezone().isoformat(), args.containers[0]],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        log_text = out.stdout + out.stderr
    server_log = {
        "pool_exhausted": len(
            re.findall(r"(?m)^sqlalchemy\.exc\.TimeoutError: QueuePool limit", log_text)
        ),
        "unhandled_errors": log_text.count("Unhandled error"),
    }
    (results / "server_log.json").write_text(json.dumps(server_log), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(HERE / "check_double_booking.py"),
            "--host",
            args.host,
            "--out",
            str(results / "double_booking.json"),
        ],
        check=False,
    )

    ramp = (
        f"{profile['users']} VU зі швидкістю {profile['rate']} VU/с (≈{profile['users'] / profile['rate']:.0f} с)"
        if profile["time"]
        else f"ступінчасте: 25 → 50 → 100 → 150 → 200 VU, +{profile['rate']} VU/с, кожен етап 60 с"
    )
    meta = {
        "profile": args.profile,
        "profile_title": profile["title"],
        "host": args.host,
        "app_environment": health.get("environment"),
        "started": started.strftime("%d.%m.%Y %H:%M"),
        "ramp_text": ramp,
        "monitor_mode": monitor_mode,
        "locust_version": version("locust"),
        "machine": {
            "os": platform.platform(),
            "cpus": os.cpu_count(),
            "ram_gib": round(psutil.virtual_memory().total / 1024**3, 1),
            "python": platform.python_version(),
        },
    }
    (results / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, str(HERE / "make_report.py"), "--results", str(results)], check=False
    )


if __name__ == "__main__":
    main()
