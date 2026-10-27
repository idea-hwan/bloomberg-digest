#!/usr/bin/env python3
"""
블룸버그 메일 수집 — 터미널을 켜둔 채로 계속 실행해두는 방식.

실행:
    cd /Users/kyunghwan/projects/bloomberg-digest
    source .venv/bin/activate
    caffeinate -i python automation/scheduler_ingest.py

매일 KST 08:00, 20:00에 최근 3일 메일을 저장하고 페이지를 올린다.
메일이 늦으면 그날 업데이트가 늦어질 뿐, 다음 날 아침으로 넘어가지 않는다.
Ctrl+C로 종료.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "automation" / "logs" / "scheduler.log"
PAGE = "docs/index.html"
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


def publishes(now: datetime) -> bool:
    return now.hour in RUN_HOURS and now.minute == 0


def run_ingest() -> bool:
    log("수집 시작")
    try:
        subprocess.run([sys.executable, "-m", "app", "ingest"], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        log(f"수집 실패 (exit {exc.returncode})")
        return False
    log("수집 완료")
    return True


def _git(args: list[str]) -> None:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    subprocess.run(["git", *args], cwd=ROOT, check=True, env=env)


def publish_page() -> None:
    log("페이지 생성")
    try:
        subprocess.run([sys.executable, "-m", "app.preview"], cwd=ROOT, check=True)
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", PAGE],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            log("페이지 변경 없음")
            return
        day = datetime.now(KST).date().isoformat()
        _git(["commit", "-m", f"auto: 다이제스트 {day}", "--", PAGE])
        _git(["push", "origin", "main"])
    except subprocess.CalledProcessError as exc:
        log(f"페이지 올리기 실패 (exit {exc.returncode})")
        return
    log("페이지를 올렸습니다")


def main() -> None:
    log("스케줄러 시작 — 매일 KST 08:00, 20:00 수집 후 페이지를 올립니다. Ctrl+C로 종료.")
    last_run: tuple[object, int] | None = None
    try:
        while True:
            now = datetime.now(KST)
            if due(now, last_run):
                last_run = (now.date(), now.hour)
                if run_ingest() and publishes(now):
                    publish_page()
            time.sleep(CHECK_INTERVAL_SEC)
    except KeyboardInterrupt:
        log("스케줄러 종료 (Ctrl+C)")
        sys.exit(0)


if __name__ == "__main__":
    main()
