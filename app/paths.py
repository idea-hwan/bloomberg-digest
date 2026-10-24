from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def configured_path(name: str, default: str) -> Path:
    load_env()
    raw = os.environ.get(name, default)
    path = Path(raw)
    if path.is_absolute():
        return path
    return ROOT / path
