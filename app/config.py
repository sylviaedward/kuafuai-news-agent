from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def data_dir() -> Path:
    raw = Path(os.getenv("APP_DATA_DIR", "./data"))
    return raw if raw.is_absolute() else ROOT / raw


def timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Shanghai"))


def llm_ready() -> bool:
    return bool(os.getenv("OPENAI_COMPAT_API_KEY") and os.getenv("OPENAI_COMPAT_MODEL"))

