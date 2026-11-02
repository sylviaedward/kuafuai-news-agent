from datetime import datetime
from zoneinfo import ZoneInfo

from app import db, scheduler


class RecordingPool:
    def __init__(self):
        self.jobs = []

    def submit(self, function, *args):
        self.jobs.append((function, args))


def test_daily_job_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    db.init_db()
    user = db.create_or_update_user("Lin", "lin@example.com", ["AI"], [], 9)
    monkeypatch.setattr(scheduler, "llm_ready", lambda: True)
    job = scheduler.DailyScheduler()
    job.pool.shutdown(wait=False)
    job.pool = RecordingPool()
    now = datetime(2026, 11, 2, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert len(job.tick(now)) == 1
    assert job.tick(now) == []
    assert len(job.pool.jobs) == 1
    assert db.list_runs(user["id"])[0]["status"] == "queued"

