from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.errors import ConfigError

ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


@dataclass(frozen=True)
class Series:
    id: str
    name: str
    subject_contains: str
    label: str


def load_series(path: Path) -> list[Series]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"시리즈 설정이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"시리즈 설정을 읽지 못했습니다: {path}") from exc

    default_label = str(data.get("label") or "").strip()
    items = data.get("series")
    if not isinstance(items, list) or not items:
        raise ConfigError("config/series.json에 시리즈가 없습니다.")

    series: list[Series] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("시리즈 항목은 객체여야 합니다.")
        series_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or series_id).strip()
        subject = str(item.get("subject_contains") or "").strip()
        label = str(item.get("label") or default_label).strip()
        if not ID_RE.match(series_id):
            raise ConfigError(f"시리즈 id가 올바르지 않습니다: {series_id}")
        if series_id in seen:
            raise ConfigError(f"시리즈 id가 중복입니다: {series_id}")
        if not subject or '"' in subject:
            raise ConfigError(f"{series_id}의 subject_contains가 올바르지 않습니다.")
        if not label or '"' in label or "\n" in label:
            raise ConfigError(f"{series_id}의 라벨이 올바르지 않습니다.")
        seen.add(series_id)
        series.append(Series(series_id, name, subject, label))
    return series


def gmail_query(series: Series, days: int) -> str:
    if days < 1 or days > 365:
        raise ConfigError("days는 1에서 365 사이여야 합니다.")
    return (
        f'label:"{series.label}" '
        f'subject:"{series.subject_contains}" '
        f"newer_than:{days}d"
    )


def subject_matches(series: Series, subject: str) -> bool:
    return series.subject_contains.casefold() in subject.casefold()
