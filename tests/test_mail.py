from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from app.mail import bodies, edition_date, message_to_raw


def _b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def test_nested_mime_bodies():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("본문")}},
                    {"mimeType": "text/html", "body": {"data": _b64("<p>본문</p>")}},
                ],
            }
        ],
    }
    plain, html = bodies(payload)
    assert plain == "본문"
    assert html == "<p>본문</p>"


def test_edition_date_uses_kst():
    sent = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
    message = {
        "id": "abc",
        "payload": {"headers": [{"name": "Date", "value": format_datetime(sent)}]},
    }
    assert edition_date(message) == "2026-10-18"


def test_edition_date_falls_back_to_internal_date():
    sent = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
    message = {"id": "abc", "internalDate": str(int(sent.timestamp() * 1000)), "payload": {}}
    assert edition_date(message) == "2026-10-18"


def test_message_to_raw_keeps_korean_subject():
    sent = datetime(2026, 10, 18, 7, 0, tzinfo=timezone(timedelta(hours=9)))
    message = {
        "id": "abc123",
        "threadId": "thr",
        "snippet": "미리보기",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "【오늘 아침 꼭 알아야 할 5가지】테스트"},
                {"name": "From", "value": "Bloomberg <news@bloomberg.net>"},
                {"name": "Date", "value": format_datetime(sent)},
            ],
            "body": {"data": _b64("안녕하세요")},
        },
    }
    raw = message_to_raw(message, "morning5", "안녕하세요")
    assert raw["date"] == "2026-10-18"
    assert raw["subject"].endswith("테스트")
    assert raw["plain"] == "안녕하세요"
