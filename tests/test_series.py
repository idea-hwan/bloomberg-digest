from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.errors import ConfigError
from app.series import gmail_query, load_series, subject_matches


def _write_config(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_series_and_query(tmp_path: Path):
    path = tmp_path / "series.json"
    _write_config(
        path,
        {
            "label": "bloomberg",
            "series": [
                {
                    "id": "morning5",
                    "name": "오늘 아침 5가지",
                    "subject_contains": "오늘 아침 꼭 알아야 할 5가지",
                }
            ],
        },
    )
    series = load_series(path)[0]
    assert gmail_query(series, 3) == (
        'label:"bloomberg" subject:"오늘 아침 꼭 알아야 할 5가지" newer_than:3d'
    )
    assert subject_matches(series, "【오늘 아침 꼭 알아야 할 5가지】반도체")
    assert not subject_matches(series, "Markets Daily: Calm no more")


def test_duplicate_series_id(tmp_path: Path):
    path = tmp_path / "series.json"
    _write_config(
        path,
        {
            "label": "bloomberg",
            "series": [
                {"id": "morning5", "subject_contains": "하나"},
                {"id": "morning5", "subject_contains": "둘"},
            ],
        },
    )
    with pytest.raises(ConfigError):
        load_series(path)
