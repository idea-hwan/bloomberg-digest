#!/usr/bin/env python3
"""
블룸버그 메일 수집 — 터미널을 켜둔 채로 계속 실행해두는 방식.

실행:
    cd /Users/kyunghwan/projects/bloomberg-digest
    source .venv/bin/activate
    caffeinate -i python automation/scheduler_ingest.py

매일 KST 08:00, 20:00에 최근 3일 메일을 저장한다.
아침 5가지는 07:30, Markets Daily는 18:28–19:50에 온다.
Ctrl+C로 종료.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "automation" / "logs" / "scheduler.log"
KST = ZoneInfo("Asia/Seoul")
RUN_HOURS = (8, 20)
CHECK_INTERVAL_SEC = 20


def log(message: str) -> None:
    line = f"[{datetime.now(KST).isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def due(now: datetime, last_run: tuple[object, int] | None) -> bool:
    if now.hour not in RUN_HOURS or now.minute != 0:
        return False
    return last_run != (now.date(), now.hour)


def run_ingest() -> None:
    log("수집 시작")
    try:
        subprocess.run([sys.executable, "-m", "app", "ingest"], cwd=ROOT, check=True)
        log("수집 완료")
    except subprocess.CalledProcessError as exc:
        log(f"수집 실패 (exit {exc.returncode})")


def main() -> None:
    log("스케줄러 시작 — 매일 KST 08:00, 20:00. Ctrl+C로 종료.")
    last_run: tuple[object, int] | None = None
    try:
        while True:
            now = datetime.now(KST)
            if due(now, last_run):
                last_run = (now.date(), now.hour)
                run_ingest()
            time.sleep(CHECK_INTERVAL_SEC)
    except KeyboardInterrupt:
        log("스케줄러 종료 (Ctrl+C)")
        sys.exit(0)


if __name__ == "__main__":
    main()
