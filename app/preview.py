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
    ("Macro", ("금리", "국채", "년물", "yield", "yields", "treasury", "treasuries", "gilt", "길트", "부채", "물가", "인플레", "cpi", "pce", "연준", "재정", "디폴트", "ecb", "프랑스", "france", "佛", "이탈리아", "伊", "유로", "스페인", "영국", "英", "boe", "모기지", "듀레이션", "인상")),
    ("Geopolitics", ("유가", "원유", "브렌트", "brent", "사우디", "아람코", "호르무즈", "디젤", "중동", "러시아", "우크라", "이란", "푸틴", "항모", "메르츠", "하이브리드")),
    ("Tech", ("반도체", "엔비디아", "nvidia", "하이닉스", "삼성전자", "코어위브", "coreweave", "openai", "오픈ai", "스페이스x", "spacex", "ai", "알리바바", "딥시크", "뮤즈")),
)

WEEKDAYS = "월화수목금토일"
LATIN_ALIAS = re.compile(r"^[a-z0-9]+$")
LAYOUT_FROM = date(2026, 10, 23)
MARKET_NAMES = {
    "S&P 500 지수": "S&P 500",
    "나스닥 100 지수": "Nasdaq 100",
    "美 국채 10년물 금리": "US 10Y",
    "달러-원 환율": "USD/KRW",
    "블룸버그 달러 지수": "Bloomberg Dollar",
    "브렌트 원유 선물": "Brent",
}


def _skipped(heading: str) -> bool:
    return heading.casefold().startswith(DAILY_SKIP)


def five_lines(body: str) -> list[str]:
    return [part.strip() for part in (body or "").split("\n\n") if part.strip()]


def commentary_summary(body: str, limit: int = 900) -> str:
    """About ten lines. Later paragraphs stay off the page."""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", body or "") if part.strip()]
    chosen: list[str] = []
    total = 0
    for paragraph in paragraphs:
        if chosen and total + len(paragraph) > limit:
            break
        chosen.append(paragraph)
        total += len(paragraph)
    return "\n\n".join(chosen)


def market_label(name: str) -> str:
    return MARKET_NAMES.get(name, name)


def first_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(
        r"(?<=[가-힣]) (?=(?:까지|에서|으로|에게|와|과|은|는|이|가|을|를|도|로|의)(?:\s|[.]))",
        "",
        cleaned,
    )
    found = re.search(r".+?다\.", cleaned)
    return found.group(0) if found else cleaned


def summarize(body: str) -> str:
    """The lead paragraph. The rest of the story stays off the page."""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", body or "") if part.strip()]
    return paragraphs[0] if paragraphs else ""


def daily_view(row: dict) -> dict:
    notes = [
        {
            "heading": section.get("heading") or "",
            "summary": commentary_summary(section.get("body") or ""),
        }
        for section in row.get("sections") or []
        if section.get("heading") and not _skipped(section.get("heading") or "")
    ]
    view = {"headline": row.get("headline") or "", "sections": [note["heading"] for note in notes]}
    if date.fromisoformat(row["date"]) < LAYOUT_FROM:
        return view
    five_body = next(
        (
            section.get("body") or ""
            for section in row.get("sections") or []
            if _skipped(section.get("heading") or "") and (section.get("heading") or "").casefold().startswith("five things")
        ),
        "",
    )
    view["five"] = five_lines(five_body)
    view["commentary"] = notes
    return view


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
                "line": first_sentence(row.get("lead") or ""),
                "markets": [
                    {**item, "name": market_label(item.get("name") or "")}
                    for item in row.get("markets") or []
                ],
                "items": [
                    {
                        "n": item["n"],
                        "headline": item["headline"],
                        "summary": summarize(item.get("body") or ""),
                    }
                    for item in row.get("items") or []
                ],
            }
        elif row["series"] == "markets_daily":
            day["daily"] = daily_view(row)
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


def narrative_for(name: str, hits: list[dict]) -> str:
    """Flow for the days still inside this review."""
    text, _needles = review(name, {hit["date"] for hit in hits})
    return text


def _take(dates: set[str], specs: list[tuple]) -> tuple[list[str], list[tuple[str, tuple[str, ...]]]]:
    lines: list[str] = []
    needles: list[tuple[str, tuple[str, ...]]] = []
    for need, line, marks in specs:
        if dates & set(need):
            lines.append(line)
            needles.extend(marks)
    return lines, needles


def _join(status: str, blocks: list[list[str]]) -> str:
    parts = [status]
    parts.extend(" ".join(block) for block in blocks if block)
    return "\n\n".join(parts)


def review(name: str, dates: set[str]) -> tuple[str, list[tuple[str, tuple[str, ...]]]]:
    if name == "Macro":
        return _macro(dates)
    if name == "Geopolitics":
        return _geopolitics(dates)
    if name == "Tech":
        return _tech(dates)
    return "", []


def _macro(dates: set[str]) -> tuple[str, list]:
    early, early_marks = _take(dates, [
        ({"2026-10-01"}, "TS롬바드는 미국 10년물 8%를 경고했다. 근원 PCE 상승률은 예상을 밑돌았다.", [("2026-10-01", ("8%", "PCE"))]),
        ({"2026-10-02"}, "영국 30년물은 6%를 넘었다. 6% 돌파는 G7에서 유로존 위기 이후 처음이다.", [("2026-10-02", ("6%",))]),
        ({"2026-10-06"}, "BMO는 미국 부채의 덫을 경고하며 30년물이 이달 6%에 갈 수 있다고 봤다.", [("2026-10-06", ("부채의 덫",))]),
        ({"2026-10-07"}, "르펜은 프랑스 디폴트를 경고하며 ECB 개입을 촉구했다.", [("2026-10-07", ("디폴트",))]),
        ({"2026-10-08"}, "연준 9월 의사록은 금리 인상에 매파적 공감대를 남겼다.", [("2026-10-08", ("의사록",))]),
        ({"2026-10-12"}, "프랑스 국채는 이탈리아 국채보다 위험하다는 비교가 나왔다.", [("2026-10-12", ("이탈리아보다",))]),
        ({"2026-10-14"}, "윌리엄스는 올해 한 차례 추가 인상을 말했고, 내년 인상은 불필요하다고 봤다.", [("2026-10-14", ("윌리엄스",))]),
        ({"2026-10-15"}, "9월 CPI는 0.6% 올랐다.", [("2026-10-15", ("CPI",))]),
    ])
    late, late_marks = _take(dates, [
        ({"2026-10-19"}, "미국 재정적자는 1.99조 달러, 이자비용은 사상 최대를 기록했다.", [("2026-10-19", ("재정적자",))]),
        ({"2026-10-20"}, "프랑스 시위 이후 국채 불안이 다시 켜졌다.", [("2026-10-20", ("프랑스 시위",))]),
        ({"2026-10-21"}, "CAC40는 최대 숏으로 집계됐고, 프랭클린템플턴은 유로존 부채위기 2.0을 경고했다.", [("2026-10-21", ("CAC40", "프랭클린"))]),
        ({"2026-10-22"}, "프랑스 10년물은 5%를 넘었고, 독일과의 금리차는 15년 만에 가장 넓어졌다. 금리 급등으로 미국과 유럽의 부채 발행은 줄줄이 미뤄졌다.", [("2026-10-22", ("5%", "부채발행", "금리 급등"))]),
        ({"2026-10-23"}, "프랑스 국채 불안이 이탈리아로 번지는 조짐이 나왔다.", [("2026-10-23", ("伊로", "佛국채"))]),
    ])
    if not early and not late:
        return "변화없음.", []
    return _join("약세.", [early, late]), early_marks + late_marks


def _geopolitics(dates: set[str]) -> tuple[str, list]:
    lines, marks = _take(dates, [
        ({"2026-10-02"}, "미국은 이란 인근에 항모를 추가 배치할 수 있다고 전했다.", [("2026-10-02", ("항모",))]),
        ({"2026-10-06"}, "사우디아람코는 글로벌 원유 비축이 놀랄 만큼 부족하다고 했다.", [("2026-10-06", ("비축",))]),
        ({"2026-10-12"}, "사우디 공항이 피격됐다. 트럼프와 푸틴은 러시아산 디젤의 미국 공급에 합의했다.", [("2026-10-12", ("공항", "디젤"))]),
        ({"2026-10-13"}, "러시아-우크라이나 에너지 휴전이 흔들리고, 중동 긴장과 함께 유가 불안이 나왔다.", [("2026-10-13", ("에너지 휴전",))]),
        ({"2026-10-14"}, "호르무즈 선박 공격이 늘었고, 사우디아람코 본사가 피격됐다.", [("2026-10-14", ("호르무즈",))]),
        ({"2026-10-15"}, "중동과 러시아 긴장으로 유가가 올랐다.", [("2026-10-15", ("유가 상승",))]),
        ({"2026-10-19"}, "브렌트유는 110달러를 기록했다. 유라시아그룹은 확전 가능성을 65%로 제시했다.", [("2026-10-19", ("110",))]),
        ({"2026-10-20"}, "메르츠는 유럽이 러시아 위협을 과소평가한다고 말했다.", [("2026-10-20", ("메르츠",))]),
        ({"2026-10-22"}, "푸틴은 미국, 우크라이나와 3자 협상 재개를 제안했고, 억류된 미국인을 석방했다.", [("2026-10-22", ("3자협상",))]),
        ({"2026-10-23"}, "미국은 중동 주재 외교관을 철수했고, 사우디아람코는 직원을 대피시켰다.", [("2026-10-23", ("아람코 대피", "외교관"))]),
    ])
    if not lines:
        return "변화없음.", []
    return _join("강세.", [lines]), marks


def _tech(dates: set[str]) -> tuple[str, list]:
    high, high_marks = _take(dates, [
        ({"2026-10-06", "2026-10-07"}, "엔비디아 시가총액은 6조 달러에 다가섰고, 주가는 사상 최고였다.", [("2026-10-06", ("Nvidia", "6조")), ("2026-10-07", ("6조", "엔비디아"))]),
        ({"2026-10-08"}, "스페이스X는 400억 달러 조달을 추진했고, 신용위험이 높아졌다.", [("2026-10-08", ("스페이스X", "CDS"))]),
        ({"2026-10-12"}, "오픈AI는 연말 연환산 매출 700억 달러 이상을 전망했다.", [("2026-10-12", ("오픈AI", "700억"))]),
        ({"2026-10-13"}, "메타는 새 AI 모델 뮤즈 원더를 공개했다.", [("2026-10-13", ("뮤즈",))]),
    ])
    crash, crash_marks = _take(dates, [
        ({"2026-10-14"}, "AI 투자 열풍에서 균열이 보인다는 진단이 나왔다.", [("2026-10-14", ("균열",))]),
        ({"2026-10-15"}, "반도체주는 엿새째 내리며 시가총액이 1조 달러 넘게 줄었다. 코어위브 채권은 부실 수준까지 밀렸고, 코어위브 CEO는 시장이 비이성적이라고 했다.", [("2026-10-15", ("6일째", "부실", "yikes"))]),
    ])
    late, late_marks = _take(dates, [
        ({"2026-10-19"}, "코어위브 부채 우려로 AI 거래가 흔들렸다. 중국은 AI 수출통제를 추진했다.", [("2026-10-19", ("코어위브", "수출통제"))]),
        ({"2026-10-20"}, "JP모간은 코어위브 부채 우려가 과도하다고 했고, 반도체주는 반등했다. 미국은 연방기관의 딥시크 사용을 금지했다.", [("2026-10-20", ("JP모간", "반도체 반등", "딥시크"))]),
        ({"2026-10-21"}, "IPO와 주가는 옥석 가리기 과정에서 흔들렸다.", [("2026-10-21", ("옥석", "IPO"))]),
        ({"2026-10-22"}, "스페이스X와 테슬라의 연계 논의가 나오며 스페이스X 조달에 훈풍이 붙었다.", [("2026-10-22", ("스페이스X", "SpaceX"))]),
        ({"2026-10-23"}, "블랙스톤은 AI 수요가 폭발적이며 버블이 아니라고 했다. 23일 나스닥은 급락했다. 알리바바와 홍콩 기술주는 중국 규제와 AI 우려로 내렸다.", [("2026-10-23", ("블랙스톤", "알리바바", "나스닥 급락"))]),
    ])
    if not high and not crash and not late:
        return "변화없음.", []
    high_on = bool(dates & {"2026-10-06", "2026-10-07"})
    crash_on = "2026-10-15" in dates
    rebound = "2026-10-20" in dates
    nasdaq = "2026-10-23" in dates
    wobble = "2026-10-21" in dates
    if high_on and crash_on and nasdaq:
        status = "전환. 엔비디아 고점 이후 반도체 급락이 왔고, 반등 뒤 23일 나스닥이 다시 급락했다."
    elif high_on and crash_on:
        status = "전환. 엔비디아 고점 이후 반도체 급락이 왔다."
    elif rebound and nasdaq:
        status = "전환. 반도체 반등 뒤 23일 나스닥이 다시 급락했다."
    elif high_on and nasdaq:
        status = "전환. 엔비디아 고점 뒤 23일 나스닥이 급락했다."
    elif crash_on or wobble or nasdaq:
        status = "약세."
    elif high_on or rebound:
        status = "강세."
    else:
        status = "변화없음."
    return _join(status, [high, crash, late]), high_marks + crash_marks + late_marks


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
    for name, _aliases in THEMES:
        hits = grouped[name]
        distinct = sorted({hit["date"] for hit in hits})
        text, needles = review(name, set(distinct))
        for hit in hits:
            hit["cited"] = any(
                hit["date"] == day and any(token in hit["headline"] for token in tokens)
                for day, tokens in needles
            )
        ranked.append(
            {
                "name": name,
                "days": len(distinct),
                "narrative": text,
                "hits": sorted(hits, key=lambda hit: hit["date"], reverse=True),
            }
        )
    return ranked


def recent_dates(dates: list[str], end: date) -> list[str]:
    """Day chips stay within the latest month. Older letters stay on disk."""
    start = end - timedelta(days=30)
    return [day for day in dates if start <= date.fromisoformat(day) <= end]


def build_payload(today: date | None = None) -> dict:
    days = _load_days()
    if not days:
        raise SystemExit("저장된 추출본이 없습니다.")
    today = today or date.today()
    latest = date.fromisoformat(max(days))
    window_end = min(today, latest)
    window_start = window_end - timedelta(days=6)
    month_start = window_end - timedelta(days=29)
    dates = recent_dates(sorted(days, reverse=True), window_end)
    shown = {day: days[day] for day in dates}
    return {
        "dates": dates,
        "days": shown,
        "windows": {
            "week": {
                "label": "Weekly review",
                "themes": themes_for(days, window_start, window_end),
            },
            "month": {
                "label": "Monthly review",
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
