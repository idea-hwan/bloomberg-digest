from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

KST = timezone(timedelta(hours=9))
TEXT_TYPES = {"text/plain", "text/html"}
GMAIL_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def header(message: dict, name: str) -> str:
    wanted = name.casefold()
    for item in message.get("payload", {}).get("headers", []):
        if str(item.get("name", "")).casefold() == wanted:
            return str(item.get("value") or "")
    return ""


def decode_b64(data: str) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    return raw.decode("utf-8", errors="replace")


def iter_text_parts(payload: dict):
    mime = payload.get("mimeType", "")
    data = (payload.get("body") or {}).get("data")
    if data and mime in TEXT_TYPES:
        yield mime, decode_b64(data)
    for part in payload.get("parts") or []:
        yield from iter_text_parts(part)


def bodies(payload: dict) -> tuple[str, str]:
    plain: list[str] = []
    html: list[str] = []
    for mime, text in iter_text_parts(payload or {}):
        if mime == "text/plain":
            plain.append(text)
        else:
            html.append(text)
    return "\n".join(plain), "\n".join(html)


def edition_date(message: dict) -> str:
    """KST calendar date of the message, taken from the Date header."""
    raw_date = header(message, "Date")
    if raw_date:
        parsed = parsedate_to_datetime(raw_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(KST).date().isoformat()

    internal = message.get("internalDate")
    if internal:
        received = datetime.fromtimestamp(int(internal) / 1000, tz=timezone.utc)
        return received.astimezone(KST).date().isoformat()
    raise ValueError(f"날짜를 읽지 못했습니다: {message.get('id')}")


def message_to_raw(message: dict, series_id: str, text: str) -> dict:
    gmail_id = str(message.get("id") or "")
    if not GMAIL_ID_RE.match(gmail_id):
        raise ValueError(f"메시지 id가 올바르지 않습니다: {gmail_id}")
    plain, html = bodies(message.get("payload") or {})
    day = edition_date(message)
    return {
        "schema_version": 1,
        "gmail_id": gmail_id,
        "thread_id": str(message.get("threadId") or ""),
        "series": series_id,
        "date": day,
        "subject": header(message, "Subject"),
        "from": header(message, "From"),
        "snippet": str(message.get("snippet") or ""),
        "plain": plain,
        "html": html,
        "text": text,
    }


def unescape_text(value: str) -> str:
    return unescape(value or "").replace("\u00a0", " ").replace("\u200b", "")
