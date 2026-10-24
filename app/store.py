from __future__ import annotations

import json
import re
from pathlib import Path

from app.extract import parse_raw, relative_raw_path
from app.mail import GMAIL_ID_RE
from app.series import ID_RE

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check(raw: dict) -> None:
    if not ID_RE.match(str(raw.get("series") or "")):
        raise ValueError(f"시리즈 id가 올바르지 않습니다: {raw.get('series')}")
    if not GMAIL_ID_RE.match(str(raw.get("gmail_id") or "")):
        raise ValueError(f"메시지 id가 올바르지 않습니다: {raw.get('gmail_id')}")
    if not DATE_RE.match(str(raw.get("date") or "")):
        raise ValueError(f"날짜가 올바르지 않습니다: {raw.get('date')}")


def raw_file(root: Path, raw: dict) -> Path:
    _check(raw)
    return root / relative_raw_path(raw)


def extracted_file(root: Path, raw: dict) -> Path:
    _check(raw)
    return root / "data" / "extracted" / raw["series"] / raw["date"] / f"{raw['gmail_id']}.json"


def find_raw(root: Path, series_id: str, gmail_id: str) -> Path | None:
    if not ID_RE.match(series_id) or not GMAIL_ID_RE.match(gmail_id):
        return None
    matches = sorted((root / "data" / "raw" / series_id).glob(f"*/{gmail_id}.json"))
    return matches[0] if matches else None


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def save_raw(root: Path, raw: dict) -> Path:
    path = raw_file(root, raw)
    if not path.exists():
        write_json(path, raw)
    return path


def save_extracted(root: Path, raw: dict) -> Path:
    path = extracted_file(root, raw)
    write_json(path, parse_raw(raw))
    return path


def status_rows(root: Path) -> list[dict]:
    base = root / "data" / "extracted"
    if not base.exists():
        return []
    rows = []
    for series_dir in sorted(path for path in base.iterdir() if path.is_dir()):
        files = [path for path in series_dir.glob("*/*.json") if path.is_file()]
        dates = sorted({path.parent.name for path in files})
        rows.append(
            {
                "series": series_dir.name,
                "count": len(files),
                "first": dates[0] if dates else "",
                "last": dates[-1] if dates else "",
            }
        )
    return rows
