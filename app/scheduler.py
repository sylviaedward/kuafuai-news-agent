from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import db
from .agent import AgentError, run_agent
from .config import llm_ready, timezone
from .delivery import deliver
from .llm import OpenAICompatibleClient


def process_run(run_id: int, user_id: int) -> None:
    db.set_run_running(run_id)
    trace = []
    try:
        user = db.get_user(user_id)
        if user is None:
            raise ValueError("user not found")
        briefing, trace = run_agent(user, run_id, OpenAICompatibleClient())
        delivery_status = deliver(user, briefing)
        db.finish_run(run_id, headline=briefing["headline"], briefing=briefing,
                      trace=trace, delivery_status=delivery_status)
    except Exception as exc:
        if isinstance(exc, AgentError):
            trace = exc.trace
        db.finish_run(run_id, trace=trace, error=f"{type(exc).__name__}: {exc}")


class DailyScheduler:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="briefing")
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="daily-scheduler", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=2)
        self.pool.shutdown(wait=False, cancel_futures=True)

    def submit_manual(self, user_id: int) -> int:
        day = datetime.now(timezone()).date().isoformat()
        run_id = db.create_run(user_id, day, manual=True)
        assert run_id is not None
        self.pool.submit(process_run, run_id, user_id)
        return run_id

    def tick(self, now: datetime | None = None) -> list[int]:
        if not llm_ready():
            return []
        local_now = now.astimezone(timezone()) if now else datetime.now(timezone())
        created = []
        for user in db.list_users():
            if user["active"] and local_now.hour >= user["delivery_hour"]:
                run_id = db.create_run(user["id"], local_now.date().isoformat(), manual=False)
                if run_id is not None:
                    self.pool.submit(process_run, run_id, user["id"])
                    created.append(run_id)
        return created

    def _loop(self) -> None:
        self.tick()
        while not self.stop.wait(60):
            self.tick()

