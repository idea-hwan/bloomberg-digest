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
    late, late_marks = _macro_late(dates)
    if not early and not late:
        return "변화없음.", []
    parts = []
    if early:
        parts.append(" ".join(early))
    parts.extend(late)
    return "\n\n".join(parts), early_marks + late_marks


def _macro_late(dates: set[str]) -> tuple[list[str], list]:
    paragraphs: list[str] = []
    marks: list[tuple[str, tuple[str, ...]]] = []
    if "2026-10-19" in dates:
        paragraphs.append(
            "미국 2026회계연도 재정적자는 전년보다 12% 늘어 1.99조 달러가 됐다. "
            "4년 연속 2조 달러 안팎이라 국내총생산의 약 6%이고, 순이자비용은 1.05조 달러까지 늘어 사상 최대다."
        )
        marks.append(("2026-10-19", ("재정적자",)))
    france: list[str] = []
    if "2026-10-20" in dates:
        france.append(
            "프랑스에서는 생활비 시위가 커졌고, 프랑스 10년물 금리는 독일 10년물보다 8bp 높아져 146bp까지 벌어졌다. "
            "CAC40은 장중 1.7% 내렸다."
        )
        marks.append(("2026-10-20", ("프랑스 시위",)))
    if "2026-10-21" in dates:
        france.append(
            "20일에는 프랑스와 독일의 10년물 금리차가 150bp를 넘겨 마감했다. "
            "CTA는 바클레이스 집계대로 프랑스 주식을 줄였고, CAC40 숏을 미국과 유럽에서 가장 크게 쌓았다. "
            "프랭클린템플턴은 프랑스 국채 매도가 유로존 부채위기 2.0으로 번질 수 있다고 경고했다."
        )
        marks.append(("2026-10-21", ("CAC40", "프랭클린")))
    if "2026-10-22" in dates:
        also = "도" if dates & {"2026-10-20", "2026-10-21"} else ""
        france.append(
            "프랑스 10년물 금리는 2002년 이후 처음 5%를 넘었고, "
            f"독일 10년물과의 금리차{also} 159.4bp까지 벌어져 15년 만에 가장 넓어졌다. "
            "그래서 미국 기업과 유럽 기업은 10월 부채 발행을 50억 달러 넘게 미뤘다."
        )
        marks.append(("2026-10-22", ("5%", "부채발행", "금리 급등")))
    if "2026-10-23" in dates:
        further = "더 " if "2026-10-22" in dates else ""
        france.append(
            f"금리차는 하루 만에 19bp {further}벌어져 178bp가 됐고, 2011년 말 이후 가장 높은 수준이다. "
            "그리고 프랑스 국채 약세는 이탈리아 국채로 번지기 시작했고, CAC40도 1% 넘게 내렸다."
        )
        marks.append(("2026-10-23", ("伊로", "佛국채")))
    if france:
        paragraphs.append(" ".join(france))
    return paragraphs, marks


def _geopolitics(dates: set[str]) -> tuple[str, list]:
    early: list[str] = []
    late: list[str] = []
    marks: list[tuple[str, tuple[str, ...]]] = []
    if "2026-10-02" in dates:
        early.append("미국은 이란 인근에 항모를 더 보낼 수 있다고 전했고, 트럼프는 중간선거 이후 폭격 재개 가능성도 열어 뒀다.")
        marks.append(("2026-10-02", ("항모",)))
    if "2026-10-06" in dates:
        early.append("아람코는 글로벌 원유 재고가 전쟁 전 100억 배럴에서 60억 배럴 아래로 줄었고, 바로 쓸 수 있는 물량은 약 10%라고 했다.")
        marks.append(("2026-10-06", ("비축",)))
    if "2026-10-12" in dates:
        early.append("사우디 리야드 공항이 피격된 날, 트럼프와 푸틴은 10월 1350만 배럴의 러시아산 디젤을 미국에 공급하기로 했다.")
        marks.append(("2026-10-12", ("공항", "디젤")))
    if "2026-10-13" in dates:
        early.append("러시아와 우크라이나의 에너지 휴전은 흔들렸고, 브렌트유는 장중 2% 넘게 올라 107달러를 넘었다.")
        marks.append(("2026-10-13", ("에너지 휴전",)))
    if "2026-10-14" in dates:
        early.append("이란은 호르무즈 통과 선박 공격을 늘렸고, 사우디아람코 다란 본사는 후티 미사일에 맞았다.")
        marks.append(("2026-10-14", ("호르무즈",)))
    if "2026-10-15" in dates:
        early.append("브렌트유는 106달러를 웃돌았고, 피격된 화물선 한 척은 침몰했다.")
        marks.append(("2026-10-15", ("유가 상승",)))
    if "2026-10-19" in dates:
        late.append("브렌트유는 16일 장중 3.9% 올라 5월 이후 처음 110달러를 찍었다. 올해 유가는 70% 넘게 올랐고, 유럽 디젤 선물은 두 배 넘게 뛰었다. 유라시아그룹은 확전 가능성을 35%에서 65%로 높였다.")
        marks.append(("2026-10-19", ("110",)))
    if "2026-10-20" in dates:
        late.append("메르츠 독일 총리는 유럽이 러시아 위협을 과소평가한다고 말했고, 푸틴이 우크라이나 영토를 넘어 유럽 정치 질서까지 흔들려 한다고 경고했다.")
        marks.append(("2026-10-20", ("메르츠",)))
    if "2026-10-22" in dates:
        late.append("푸틴은 11월 초 미국, 우크라이나와 3자 협상을 제안했고, 억류된 미국인 교사 스티븐 허버드를 석방했다. 우크라이나와 직접 만나겠다는 신호는 아직 없었다.")
        marks.append(("2026-10-22", ("3자협상",)))
    if "2026-10-23" in dates:
        if "2026-10-22" in dates:
            late.append("그래서 협상 제안은 유가 강세를 되돌리지 못했다.")
        late.append("미국은 사우디 주재 외교관과 가족에게 철수 명령을 내렸고, 사우디아람코는 다란 본사 경보 뒤 직원을 대피시켰다. 아람코 시설과 사우디 동부 공항 공격으로 최소 4명이 숨졌고, 브렌트유는 장중 4% 넘게 올라 113달러를 넘었다.")
        marks.append(("2026-10-23", ("아람코 대피", "외교관")))
    paragraphs = [block for block in (" ".join(early), " ".join(late)) if block]
    if not paragraphs:
        return "변화없음.", []
    return "\n\n".join(paragraphs), marks


def _tech(dates: set[str]) -> tuple[str, list]:
    high: list[str] = []
    crash: list[str] = []
    late: list[str] = []
    marks: list[tuple[str, tuple[str, ...]]] = []
    if dates & {"2026-10-06", "2026-10-07"}:
        high.append("엔비디아 주가는 사상 최고였고, 시가총액은 6조 달러 돌파를 앞두고 있었다.")
        marks.extend([("2026-10-06", ("Nvidia", "6조")), ("2026-10-07", ("6조", "엔비디아"))])
    if "2026-10-08" in dates:
        high.append("스페이스X는 엔비디아 칩을 사려고 400억 달러 조달을 추진했고, 5년물 CDS는 16.7bp 오른 197.6bp까지 뛰었다.")
        marks.append(("2026-10-08", ("스페이스X", "CDS")))
    if "2026-10-12" in dates:
        high.append("오픈AI는 연말 연환산 매출이 700억 달러를 넘길 수 있다고 전망했다.")
        marks.append(("2026-10-12", ("오픈AI", "700억")))
    if "2026-10-13" in dates:
        high.append("메타는 뮤즈 원더를 공개했고, 주가는 장중 4.7% 올랐다.")
        marks.append(("2026-10-13", ("뮤즈",)))
    if "2026-10-14" in dates:
        crash.append("AI 투자에서는 균열이 나왔다. JP모간과 골드만삭스는 볼타 인프라스트럭처 대출을 제한했고, 퍼머스그리드 IPO도 무산됐다.")
        marks.append(("2026-10-14", ("균열",)))
    if "2026-10-15" in dates:
        crash.append("반도체주는 엿새째 내렸다. 필라델피아 반도체지수는 4.3% 빠져 6거래일 낙폭이 11%를 넘었고, 시가총액은 1조 달러 넘게 줄었다. 코어위브 2032년 채권은 달러당 80센트 아래로 내려 부실 구간에 들어갔고, CEO는 시장이 비이성적이라고 했다.")
        marks.append(("2026-10-15", ("6일째", "부실", "yikes")))
    if "2026-10-19" in dates:
        late.append("코어위브 부채 우려로 기술주가 밀렸고, 필라델피아 반도체지수는 8거래일 연속 내려 2008년 이후 가장 긴 하락이 됐다. 나스닥 100은 2.5% 내렸다. 중국은 대규모언어모델과 반도체 설계를 포함한 23개 AI 기술에 수출통제를 추진했다.")
        marks.append(("2026-10-19", ("코어위브", "수출통제")))
    if "2026-10-20" in dates:
        late.append("반도체주는 반등했고, 나스닥 100은 1.2% 올랐다. JP모간은 코어위브 부채 우려가 과도하다고 봤지만, 코어위브 주가는 지난주 20% 넘게 내린 뒤 반등 시도도 약세로 마감했다. 미국은 연방기관의 딥시크 사용을 금지했다.")
        marks.append(("2026-10-20", ("JP모간", "반도체 반등", "딥시크")))
    if "2026-10-21" in dates:
        late.append("엘리스는 상장 첫날 32% 내렸고, 퍼머스그리드는 300억 달러 IPO를 철회했다.")
        marks.append(("2026-10-21", ("옥석", "IPO")))
    if "2026-10-22" in dates:
        late.append("스페이스X는 실적 호조에 7.8% 올랐고, 트레이드네이션은 반도체 매도세가 최악의 국면을 지났을 수 있다고 봤다.")
        marks.append(("2026-10-22", ("스페이스X", "SpaceX")))
    if "2026-10-23" in dates:
        turn = "그런데 " if high or crash or late else ""
        late.append(f"{turn}나스닥 100은 2.9% 내렸고, 필라델피아 반도체지수는 6.7% 내렸다. 메타는 실적이 예상을 넘었는데도 자본지출 전망을 높이면서 7% 내렸다. 블랙스톤은 AI 수요가 폭발적이라 버블이 아니라고 했다. 알리바바는 중국 품질 규제에 6.1% 내렸다.")
        marks.append(("2026-10-23", ("블랙스톤", "알리바바", "나스닥 급락")))
    paragraphs = [block for block in (" ".join(high), " ".join(crash), " ".join(late)) if block]
    if not paragraphs:
        return "변화없음.", []
    return "\n\n".join(paragraphs), marks


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


def week_windows(days: dict[str, dict], ends: list[str]) -> dict[str, dict]:
    """One rolling week per mail day. The clicked day is the window end."""
    windows = {}
    for day_key in ends:
        end = date.fromisoformat(day_key)
        start = end - timedelta(days=6)
        windows[day_key] = {
            "start": start.isoformat(),
            "end": day_key,
            "themes": themes_for(days, start, end),
        }
    return windows


def build_payload(today: date | None = None) -> dict:
    days = _load_days()
    if not days:
        raise SystemExit("저장된 추출본이 없습니다.")
    today = today or date.today()
    latest = date.fromisoformat(max(days))
    window_end = min(today, latest)
    dates = recent_dates(sorted(days, reverse=True), window_end)
    shown = {day: days[day] for day in dates}
    return {
        "dates": dates,
        "days": shown,
        "weeks": week_windows(days, dates),
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
