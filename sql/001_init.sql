PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    topics_json TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    delivery_hour INTEGER NOT NULL DEFAULT 9 CHECK (delivery_hour BETWEEN 0 AND 23),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    local_day TEXT NOT NULL,
    is_manual INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    headline TEXT,
    briefing_json TEXT,
    trace_json TEXT,
    delivery_status TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_scheduled_run_per_day
    ON runs(user_id, local_day) WHERE is_manual = 0;
CREATE INDEX IF NOT EXISTS idx_runs_user_created ON runs(user_id, id DESC);

