from __future__ import annotations

from pathlib import Path

from app.errors import ConfigError
from app.extract import choose_text
from app.mail import bodies, edition_date, header, message_to_raw
from app.paths import ROOT
from app.series import gmail_query, load_series, subject_matches
from app.store import find_raw, read_json, save_extracted, save_raw


def _series_selection(root: Path, series_ids: list[str] | None):
    series_list = load_series(root / "config" / "series.json")
    if not series_ids:
        return series_list
    known = {series.id: series for series in series_list}
    missing = [series_id for series_id in series_ids if series_id not in known]
    if missing:
        raise ConfigError(f"없는 시리즈입니다: {', '.join(missing)}")
    return [known[series_id] for series_id in series_ids]


def ingest(
    root: Path | None = None,
    *,
    days: int = 3,
    dry_run: bool = False,
    reextract: bool = False,
    series_ids: list[str] | None = None,
    client=None,
) -> list[dict]:
    root = root or ROOT
    series_list = _series_selection(root, series_ids)
    if client is None:
        from app.gmail import connect

        client = connect()

    summary = []
    for series in series_list:
        query = gmail_query(series, days)
        stats = {
            "series": series.id,
            "query": query,
            "found": 0,
            "saved": 0,
            "extracted": 0,
            "skipped": 0,
            "unmatched": 0,
            "errors": [],
            "preview": [],
        }
        try:
            ids = client.search(query)
        except Exception as exc:
            stats["errors"].append(str(exc))
            summary.append(stats)
            continue
        stats["found"] = len(ids)

        for gmail_id in ids:
            try:
                _take_one(root, client, series, gmail_id, stats, dry_run, reextract)
            except Exception as exc:
                stats["errors"].append(f"{gmail_id}: {exc}")
        summary.append(stats)
    return summary


def _take_one(root, client, series, gmail_id, stats, dry_run: bool, reextract: bool) -> None:
    existing = find_raw(root, series.id, gmail_id)
    if dry_run:
        message = client.fetch(gmail_id, "metadata")
        subject = header(message, "Subject")
        if not subject_matches(series, subject):
            stats["unmatched"] += 1
            return
        stats["preview"].append(f"{edition_date(message)}  {subject}")
        return

    if existing and not reextract:
        from app.store import extracted_file

        raw = read_json(existing)
        if extracted_file(root, raw).exists():
            stats["skipped"] += 1
            return
        save_extracted(root, raw)
        stats["extracted"] += 1
        return

    if existing and reextract:
        save_extracted(root, read_json(existing))
        stats["extracted"] += 1
        return

    message = client.fetch(gmail_id, "full")
    subject = header(message, "Subject")
    if not subject_matches(series, subject):
        stats["unmatched"] += 1
        return
    plain, html = bodies(message.get("payload") or {})
    raw = message_to_raw(message, series.id, choose_text(plain, html))
    save_raw(root, raw)
    save_extracted(root, raw)
    stats["saved"] += 1


def reextract_all(root: Path | None = None) -> int:
    root = root or ROOT
    count = 0
    base = root / "data" / "raw"
    if not base.exists():
        return 0
    for path in sorted(base.glob("*/*/*.json")):
        save_extracted(root, read_json(path))
        count += 1
    return count
