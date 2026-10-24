from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.mail import unescape_text

FOOTER_MARKERS = (
    "unsubscribe",
    "subscription preferences",
    "manage your subscription",
    "view in browser",
    "you received this",
    "this email was sent",
    "수신 거부",
    "구독 해지",
    "구독 취소",
)
MIN_BODY_BEFORE_FOOTER = 80
ITEM_RE = re.compile(
    r"(?m)^[ \t]*([1-9])[\.\)、][ \t]*(.+?)(?=^[ \t]*[1-9][\.\)、][ \t]|\Z)",
    re.S,
)
MARKETS_SUBJECT_RE = re.compile(r"^Markets Daily:\s*(.+)$", re.I)
PLUS_RE = re.compile(r"\s+[-–—]\s+Plus,?\s+", re.I)
SKIP_PARAGRAPHS = {"markets daily", "bloomberg"}


def clean_text(value: str) -> str:
    text = unescape_text(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return cut_footer(text)


def cut_footer(text: str) -> str:
    lowered = text.casefold()
    cut_at = len(text)
    for marker in FOOTER_MARKERS:
        idx = lowered.find(marker.casefold(), MIN_BODY_BEFORE_FOOTER)
        if idx != -1:
            cut_at = min(cut_at, idx)
    return text[:cut_at].strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return clean_text(soup.get_text("\n"))


def choose_text(plain: str, html: str) -> str:
    cleaned = clean_text(plain)
    if len(cleaned) >= 200:
        return cleaned
    if html:
        return html_to_text(html)
    return cleaned


def numbered_items(text: str) -> list[dict]:
    found: list[tuple[int, str]] = []
    for match in ITEM_RE.finditer(text):
        chunk = match.group(2).strip()
        if chunk:
            found.append((int(match.group(1)), chunk))

    items: list[dict] = []
    expected = 1
    for number, chunk in found:
        if number != expected:
            if items:
                break
            continue
        lines = [line for line in chunk.split("\n") if line.strip()]
        if not lines:
            continue
        items.append(
            {
                "n": number,
                "headline": lines[0],
                "summary": "\n".join(lines[1:]).strip(),
            }
        )
        expected += 1
        if expected > 5:
            break
    return items


def items_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    nodes = soup.select("ol li")
    if len(nodes) < 3:
        return []
    items: list[dict] = []
    for index, node in enumerate(nodes[:5], start=1):
        lines = [line for line in clean_text(node.get_text("\n", strip=True)).split("\n") if line.strip()]
        if not lines:
            continue
        items.append(
            {
                "n": index,
                "headline": lines[0],
                "summary": "\n".join(lines[1:]).strip(),
            }
        )
    return items


def morning_hook(subject: str) -> str:
    if "】" in subject:
        return subject.split("】", 1)[1].strip()
    return ""


def markets_subject(subject: str) -> tuple[str, str]:
    match = MARKETS_SUBJECT_RE.match(subject.strip())
    rest = match.group(1).strip() if match else subject.strip()
    parts = PLUS_RE.split(rest, maxsplit=1)
    headline = parts[0].strip()
    secondary = parts[1].strip() if len(parts) > 1 else ""
    return headline, secondary


def paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def is_heading(paragraph: str) -> bool:
    if "\n" in paragraph or len(paragraph) > 80:
        return False
    if paragraph.endswith((".", "。", "!", "?", "…")):
        return False
    return 1 <= len(paragraph.split()) <= 8


def heading_of(paragraph: str) -> tuple[str, str] | None:
    lines = [line for line in paragraph.split("\n") if line.strip()]
    if not lines or not is_heading(lines[0]):
        return None
    if len(lines) == 1:
        return lines[0], ""
    return lines[0], "\n".join(lines[1:]).strip()


def markets_body(text: str, headline: str) -> tuple[str, list[dict]]:
    blocks = [part for part in paragraphs(text) if part.casefold() not in SKIP_PARAGRAPHS]
    if blocks and headline and blocks[0].casefold() == headline.casefold():
        blocks = blocks[1:]

    lead: list[str] = []
    sections: list[dict] = []
    index = 0
    while index < len(blocks):
        found = heading_of(blocks[index])
        if found is None:
            if sections:
                previous = sections[-1]["body"]
                sections[-1]["body"] = "\n\n".join(part for part in (previous, blocks[index]) if part)
            else:
                lead.append(blocks[index])
            index += 1
            continue

        heading, body = found
        index += 1
        if not body:
            extra: list[str] = []
            while index < len(blocks) and heading_of(blocks[index]) is None:
                extra.append(blocks[index])
                index += 1
            body = "\n\n".join(extra)
        sections.append({"heading": heading, "body": body})
    return "\n\n".join(lead), sections


STOP_PREFIXES = (
    "최다열람기사",
    "팔로우하세요",
    "팔로우 하세요",
    "이 메일은",
    "구독 취소",
    "you received this",
    "enjoying markets daily",
    "follow us",
)
PROMO_MARKERS = (
    "follow the news that matters",
    "introducing your news",
    "markets pulse survey",
    "please share your thoughts",
    "we're improving your newsletter",
    "we’re improving your newsletter",
    "you received this message",
    "bloomberg.com subscribers have exclusive",
    "if a friend forwarded",
    "뉴스레터는 무료로 제공되며",
    "나의 워치리스트",
)
DROP_HEADINGS = (
    "test your knowledge",
    "enjoying markets daily",
    "follow us",
)
MORNING_BOILERPLATE = re.compile(
    r"블룸버그 뉴스 한글팀은.*?구독하실 수 있습니다\.?\s*"
)


def squash(value: str) -> str:
    text = unescape_text(value)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_stop(text: str) -> bool:
    return text.casefold().startswith(STOP_PREFIXES)


def _is_promo(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in PROMO_MARKERS)


def _paragraphs_after(heading) -> list[str]:
    chunks: list[str] = []
    for node in heading.find_all_next(["p", "li", "h3"]):
        if node.name == "h3":
            break
        if node.find_previous("h3") is not heading:
            continue
        text = squash(node.get_text(" ", strip=True))
        if not text or (chunks and chunks[-1] == text):
            continue
        if _is_stop(text):
            break
        if _is_promo(text):
            continue
        chunks.append(text)
    return chunks


def _story_sections(soup) -> list[dict]:
    sections = []
    for heading in soup.find_all("h3"):
        title = squash(heading.get_text(" ", strip=True))
        if not title or title.casefold().startswith(DROP_HEADINGS):
            continue
        body = _paragraphs_after(heading)
        if not body:
            continue
        sections.append({"heading": title, "body": "\n\n".join(body)})
    return sections


def _morning_lead(soup) -> str:
    first = soup.find("h3")
    if first is None:
        return ""
    parts: list[str] = []
    for node in reversed(first.find_all_previous("p")):
        text = MORNING_BOILERPLATE.sub("", squash(node.get_text(" ", strip=True))).strip()
        if not text or _is_stop(text) or _is_promo(text):
            continue
        parts.append(text)
    return "\n\n".join(parts)


def _market_rows(soup) -> list[dict]:
    rows = []
    for row in soup.find_all("tr"):
        cells = [squash(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        cells = [cell for cell in cells if cell]
        if len(cells) != 3:
            continue
        name, value, change = cells
        if "시장 데이터" in name or "구독" in name or not re.search(r"\d", value):
            continue
        rows.append({"name": name, "value": value, "change": change})
    return rows


def _compose(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part)


def relative_raw_path(raw: dict) -> str:
    return f"data/raw/{raw['series']}/{raw['date']}/{raw['gmail_id']}.json"


def _base(raw: dict) -> dict:
    return {
        "schema_version": 1,
        "gmail_id": raw["gmail_id"],
        "series": raw["series"],
        "date": raw["date"],
        "subject": raw.get("subject") or "",
        "from": raw.get("from") or "",
        "raw_path": relative_raw_path(raw),
    }


def _parse_morning_html(raw: dict) -> dict | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw.get("html") or "", "html.parser")
    if soup.find("h3") is None:
        return None
    sections = _story_sections(soup)
    items = [
        {"n": index, "headline": section["heading"], "body": section["body"]}
        for index, section in enumerate(sections, start=1)
    ]
    lead = _morning_lead(soup)
    markets = _market_rows(soup)
    market_lines = ["시장을 한눈에"] if markets else []
    market_lines.extend(f"{row['name']}  {row['value']}  {row['change']}" for row in markets)
    text = _compose(
        [lead, _compose(market_lines), _compose(f"{item['headline']}\n\n{item['body']}" for item in items)]
    )
    parsed = _base(raw)
    parsed.update(
        {
            "parser": "morning5",
            "hook": morning_hook(raw.get("subject") or ""),
            "lead": lead,
            "markets": markets,
            "items": items,
            "text": text,
            "body_parsed": len(items) >= 3 and all(item["body"] for item in items),
        }
    )
    return parsed


def parse_morning5(raw: dict) -> dict:
    parsed_html = _parse_morning_html(raw)
    if parsed_html is not None:
        return parsed_html
    items = numbered_items(raw.get("text") or "")
    if len(items) < 3:
        html_items = items_from_html(raw.get("html") or "")
        if len(html_items) > len(items):
            items = html_items
    for item in items:
        item["body"] = item.get("body") or item.get("summary") or ""
    parsed = _base(raw)
    parsed.update(
        {
            "parser": "morning5",
            "hook": morning_hook(raw.get("subject") or ""),
            "items": items,
            "text": raw.get("text") or "",
            "body_parsed": len(items) >= 3,
        }
    )
    return parsed


def _parse_markets_html(raw: dict) -> dict | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw.get("html") or "", "html.parser")
    if soup.find("h3") is None:
        return None
    sections = _story_sections(soup)
    text = _compose(f"{section['heading']}\n\n{section['body']}" for section in sections)
    headline, secondary = markets_subject(raw.get("subject") or "")
    parsed = _base(raw)
    parsed.update(
        {
            "parser": "markets_daily",
            "headline": headline,
            "secondary": secondary,
            "sections": sections,
            "text": text,
            "body_parsed": bool(sections),
        }
    )
    return parsed


def parse_markets_daily(raw: dict) -> dict:
    parsed_html = _parse_markets_html(raw)
    if parsed_html is not None:
        return parsed_html
    headline, secondary = markets_subject(raw.get("subject") or "")
    lead, sections = markets_body(raw.get("text") or "", headline)
    parsed = _base(raw)
    parsed.update(
        {
            "parser": "markets_daily",
            "headline": headline,
            "secondary": secondary,
            "lead": lead,
            "sections": sections,
            "text": raw.get("text") or "",
            "body_parsed": bool(lead or sections),
        }
    )
    return parsed


def parse_generic(raw: dict) -> dict:
    parsed = _base(raw)
    text = raw.get("text") or ""
    parsed.update(
        {
            "parser": "generic",
            "text": text,
            "body_parsed": bool(text.strip()),
        }
    )
    return parsed


PARSERS = {
    "morning5": parse_morning5,
    "markets_daily": parse_markets_daily,
}


def parse_raw(raw: dict) -> dict:
    parser = PARSERS.get(raw.get("series") or "", parse_generic)
    return parser(raw)
