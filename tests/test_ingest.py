from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from app.ingest import ingest
from app.mail import message_to_raw
from app.store import read_json, status_rows


def _message(gmail_id: str, subject: str, plain: str) -> dict:
    sent = datetime(2026, 10, 18, 7, 0, tzinfo=timezone(timedelta(hours=9)))
    return {
        "id": gmail_id,
        "threadId": "thr",
        "snippet": plain[:40],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": "Bloomberg <news@bloomberg.net>"},
                {"name": "Date", "value": format_datetime(sent)},
            ],
            "body": {"data": _b64(plain)},
        },
    }


def _b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode()


class FakeGmail:
    def __init__(self, messages: dict[str, dict]):
        self.messages = messages
        self.fetches: list[tuple[str, str]] = []

    def search(self, query: str) -> list[str]:
        if "오늘 아침" in query:
            return ["m1"]
        if "Markets Daily" in query:
            return ["d1"]
        return []

    def fetch(self, message_id: str, fmt: str = "full") -> dict:
        self.fetches.append((message_id, fmt))
        return self.messages[message_id]


def _project(tmp_path):
    config = {
        "label": "bloomberg",
        "series": [
            {
                "id": "morning5",
                "name": "오늘 아침 5가지",
                "subject_contains": "오늘 아침 꼭 알아야 할 5가지",
            },
            {
                "id": "markets_daily",
                "name": "Markets Daily",
                "subject_contains": "Markets Daily",
            },
        ],
    }
    path = tmp_path / "config" / "series.json"
    path.parent.mkdir()
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_ingest_saves_once_and_skips_on_rerun(tmp_path):
    root = _project(tmp_path)
    morning = "1. 물가\nCPI\n\n2. 반도체\n강세\n\n3. 유가\n우려\n\n4. 환율\n1380\n\n5. 일정\n소비심리\n"
    client = FakeGmail(
        {
            "m1": _message("m1", "【오늘 아침 꼭 알아야 할 5가지】美인플레", morning),
            "d1": _message("d1", "Markets Daily: Calm no more - Plus, chip shares", "Good morning. Yields fell.\n"),
        }
    )
    first = ingest(root, days=3, client=client)
    assert [row["saved"] for row in first] == [1, 1]
    stored = read_json(root / "data" / "extracted" / "morning5" / "2026-10-18" / "m1.json")
    assert stored["hook"] == "美인플레"
    assert stored["items"][0]["headline"] == "물가"
    markets = read_json(root / "data" / "extracted" / "markets_daily" / "2026-10-18" / "d1.json")
    assert markets["headline"] == "Calm no more"
    assert "美인플레" in (root / "data" / "raw" / "morning5" / "2026-10-18" / "m1.json").read_text(encoding="utf-8")

    client.fetches.clear()
    second = ingest(root, days=3, client=client)
    assert [row["skipped"] for row in second] == [1, 1]
    assert client.fetches == []
    assert status_rows(root)[0]["count"] == 1


def test_reextract_does_not_fetch(tmp_path):
    root = _project(tmp_path)
    message = _message("m1", "【오늘 아침 꼭 알아야 할 5가지】다시", "본문")
    raw = message_to_raw(message, "morning5", "본문")
    from app.store import save_raw

    save_raw(root, raw)
    client = FakeGmail({"m1": message})
    summary = ingest(root, days=3, reextract=True, series_ids=["morning5"], client=client)
    assert summary[0]["extracted"] == 1
    assert client.fetches == []
