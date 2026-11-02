from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import ROOT, data_dir


def connect() -> sqlite3.Connection:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "briefings.db", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def init_db() -> None:
    with connect() as db:
        db.executescript((ROOT / "sql/001_init.sql").read_text(encoding="utf-8"))


def row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    for key in ("topics_json", "keywords_json", "briefing_json", "trace_json"):
        if key in result and result[key] is not None:
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
    return result


def create_or_update_user(name: str, email: str, topics: list[str], keywords: list[str], hour: int) -> dict:
    with connect() as db:
        db.execute(
            """INSERT INTO users(name,email,topics_json,keywords_json,delivery_hour)
               VALUES(?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET
               name=excluded.name, topics_json=excluded.topics_json,
               keywords_json=excluded.keywords_json, delivery_hour=excluded.delivery_hour,
               active=1""",
            (name, email, json.dumps(topics, ensure_ascii=False),
             json.dumps(keywords, ensure_ascii=False), hour),
        )
        return row_dict(db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())


def get_user(user_id: int) -> dict | None:
    with connect() as db:
        return row_dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def list_users() -> list[dict]:
    with connect() as db:
        return [row_dict(r) for r in db.execute("SELECT * FROM users ORDER BY id DESC")]


def create_run(user_id: int, local_day: str, manual: bool) -> int | None:
    with connect() as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO runs(user_id,local_day,is_manual,status) VALUES(?,?,?, 'queued')",
            (user_id, local_day, int(manual)),
        )
        return cursor.lastrowid if cursor.rowcount else None


def set_run_running(run_id: int) -> None:
    with connect() as db:
        db.execute("UPDATE runs SET status='running' WHERE id=? AND status='queued'", (run_id,))


def finish_run(run_id: int, *, headline: str | None = None,
               briefing: dict | None = None, trace: list | None = None,
               delivery_status: str | None = None, error: str | None = None) -> None:
    with connect() as db:
        db.execute(
            """UPDATE runs SET status=?, headline=?, briefing_json=?, trace_json=?,
               delivery_status=?, error=?, finished_at=CURRENT_TIMESTAMP WHERE id=?""",
            ("failed" if error else "completed", headline,
             json.dumps(briefing, ensure_ascii=False) if briefing is not None else None,
             json.dumps(trace, ensure_ascii=False) if trace is not None else None,
             delivery_status, error, run_id),
        )


def get_run(run_id: int) -> dict | None:
    with connect() as db:
        return row_dict(db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())


def list_runs(user_id: int) -> list[dict]:
    with connect() as db:
        return [row_dict(r) for r in db.execute(
            "SELECT * FROM runs WHERE user_id=? ORDER BY id DESC LIMIT 30", (user_id,))]
