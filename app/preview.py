from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from app.paths import ROOT

DAILY_SKIP = (
    "five things you need to know",
    "on the move",
    "what else we're reading",
    "what else we’re reading",
    "the week ahead",
    "word from",
    "one number to start your day",
    "one chart to start your day",
    "one map to start your day",
    "play alphadots",
)

THEMES = (
    ("금리 · 국채", ("금리", "국채", "년물", "yield", "treasury", "treasuries", "bond", "길트", "gilt", "듀레이션")),
    ("물가 · 연준", ("물가", "인플레", "cpi", "pce", "연준", "베이지북")),
    ("반도체 · AI", ("반도체", "엔비디아", "nvidia", "하이닉스", "삼성전자", "코어위브", "coreweave", "openai", "오픈ai", "스페이스x", "spacex", "ai")),
    ("유가 · 중동", ("유가", "원유", "브렌트", "brent", "사우디", "아람코", "호르무즈", "디젤")),
    ("유럽", ("프랑스", "佛", "ecb", "유로", "유럽", "france", "스페인", "이탈리아")),
    ("중국", ("중국", "中")),
    ("부채", ("부채",)),
)

WEEKDAYS = "월화수목금토일"
LATIN_ALIAS = re.compile(r"^[a-z0-9]+$")


def _load_days() -> dict[str, dict]:
    extracted = ROOT / "data" / "extracted"
    days: dict[str, dict] = {}
    for path in extracted.glob("*/*/*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        day = days.setdefault(
            row["date"],
            {"date": row["date"], "morning": None, "daily": None},
        )
        if row["series"] == "morning5":
            day["morning"] = {
                "hook": row.get("hook") or "",
                "markets": row.get("markets") or [],
                "items": [{"n": item["n"], "headline": item["headline"]} for item in row.get("items") or []],
            }
        elif row["series"] == "markets_daily":
            sections = []
            for section in row.get("sections") or []:
                heading = section.get("heading") or ""
                if heading.casefold().startswith(DAILY_SKIP):
                    continue
                sections.append(heading)
            day["daily"] = {
                "headline": row.get("headline") or "",
                "sections": sections,
            }
    return days


def _mentions(alias: str, text: str) -> bool:
    folded = text.casefold()
    if LATIN_ALIAS.fullmatch(alias):
        return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", folded) is not None
    return alias.casefold() in folded.replace(" ", "")


def _headlines(day: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    morning = day.get("morning") or {}
    if morning.get("hook"):
        rows.append(("아침", morning["hook"]))
    for item in morning.get("items") or []:
        rows.append(("아침", item["headline"]))
    daily = day.get("daily") or {}
    if daily.get("headline"):
        rows.append(("데일리", daily["headline"]))
    for heading in daily.get("sections") or []:
        rows.append(("데일리", heading))
    return rows


def themes_for(days: dict[str, dict], start: date, end: date) -> list[dict]:
    grouped: dict[str, list[dict]] = {name: [] for name, _ in THEMES}
    seen: dict[str, set[tuple[str, str]]] = {name: set() for name, _ in THEMES}
    for day_key in sorted(days):
        current = date.fromisoformat(day_key)
        if current < start or current > end:
            continue
        for series, headline in _headlines(days[day_key]):
            for name, aliases in THEMES:
                if not any(_mentions(alias, headline) for alias in aliases):
                    continue
                key = (day_key, headline)
                if key in seen[name]:
                    continue
                seen[name].add(key)
                grouped[name].append({"date": day_key, "series": series, "headline": headline})
    ranked = []
    for name, _ in THEMES:
        hits = grouped[name]
        distinct = sorted({hit["date"] for hit in hits})
        if len(distinct) < 2:
            continue
        ranked.append(
            {
                "name": name,
                "days": len(distinct),
                "hits": sorted(hits, key=lambda hit: hit["date"], reverse=True),
            }
        )
    ranked.sort(key=lambda item: (-item["days"], item["name"]))
    return ranked


def build_payload(today: date | None = None) -> dict:
    days = _load_days()
    if not days:
        raise SystemExit("저장된 추출본이 없습니다.")
    today = today or date.today()
    dates = sorted(days, reverse=True)
    latest = date.fromisoformat(dates[0])
    window_end = min(today, latest)
    window_start = window_end - timedelta(days=6)
    month_start = date(window_end.year, window_end.month, 1)
    return {
        "dates": dates,
        "days": days,
        "windows": {
            "week": {
                "label": f"{window_start.month}/{window_start.day}–{window_end.month}/{window_end.day}",
                "themes": themes_for(days, window_start, window_end),
            },
            "month": {
                "label": f"{window_end.month}월",
                "themes": themes_for(days, month_start, window_end),
            },
        },
    }


def weekday_label(day: str) -> str:
    return WEEKDAYS[date.fromisoformat(day).weekday()]


def write_preview(target: Path | None = None) -> Path:
    payload = build_payload()
    payload["weekdays"] = {day: weekday_label(day) for day in payload["dates"]}
    target = target or ROOT / "docs" / "index.html"
    template = (ROOT / "templates" / "preview.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/ null", json.dumps(payload, ensure_ascii=False))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


if __name__ == "__main__":
    print(write_preview())
