import argparse
import csv
import json
import signal
import subprocess
import time
from pathlib import Path

import psutil

running = True


def _stop(*_args) -> None:
    global running
    running = False


def _to_mib(text: str) -> float:
    text = text.strip()
    units = {
        "KiB": 1 / 1024,
        "MiB": 1,
        "GiB": 1024,
        "kB": 1 / 1024,
        "MB": 1,
        "GB": 1024,
        "B": 1 / 1048576,
    }
    for unit in sorted(units, key=len, reverse=True):
        if text.endswith(unit):
            return float(text[: -len(unit)]) * units[unit]
    return 0.0


def sample_docker(containers: list[str]) -> list[tuple[str, float, float]]:
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", *containers],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        item = json.loads(line)
        rows.append(
            (
                item["Name"],
                float(item["CPUPerc"].rstrip("%")),
                _to_mib(item["MemUsage"].split("/")[0]),
            )
        )
    return rows


_SELF_MARKERS = ("monitor.py", "run_loadtest.py", "locust", "make_report.py")
_tracked: dict[int, psutil.Process] = {}


def sample_processes(patterns: list[str]) -> list[tuple[str, float, float]]:
    """Сумарні CPU/RAM процесів, у командному рядку яких є шаблон (крім самих інструментів тесту)."""
    totals = {p: [0.0, 0.0] for p in patterns}
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            label = " ".join(proc.info["cmdline"] or [proc.info["name"] or ""])
            if any(marker in label for marker in _SELF_MARKERS):
                continue
            for p in patterns:
                if p in label:
                    tracked = _tracked.setdefault(proc.pid, proc)  # той самий об'єкт між вимірами
                    totals[p][0] += tracked.cpu_percent(interval=None)
                    totals[p][1] += tracked.memory_info().rss / 1048576
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return [(p, cpu, mem) for p, (cpu, mem) in totals.items()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--containers", nargs="*", default=[])
    parser.add_argument("--match", action="append", default=[])
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--out", default="loadtests/results/resources.csv")
    args = parser.parse_args()
    if not args.containers and not args.match:
        parser.error("вкажіть --containers або --match")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if args.match:
        sample_processes(args.match)  # «прогрів» лічильників CPU

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "name", "cpu_percent", "mem_mib"])
        while running:
            started = time.time()
            try:
                rows = (
                    sample_docker(args.containers)
                    if args.containers
                    else sample_processes(args.match)
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as err:
                print(f"[monitor] помилка збору: {err}")
                rows = []
            for name, cpu, mem in rows:
                writer.writerow([f"{started:.1f}", name, f"{cpu:.1f}", f"{mem:.1f}"])
            fh.flush()
            time.sleep(max(0.0, args.interval - (time.time() - started)))


if __name__ == "__main__":
    main()
