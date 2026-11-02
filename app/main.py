from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from . import db
from .config import ROOT, llm_ready
from .scheduler import DailyScheduler


class UserInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(min_length=3, max_length=254)
    topics: list[str] = Field(default_factory=list, max_length=10)
    keywords: list[str] = Field(default_factory=list, max_length=15)
    delivery_hour: int = Field(default=9, ge=0, le=23)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("enter a valid email")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("topics", "keywords")
    @classmethod
    def clean_terms(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            term = value.strip()[:60]
            if term and term not in result:
                result.append(term)
        return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    app.state.scheduler = DailyScheduler()
    app.state.scheduler.start()
    yield
    app.state.scheduler.close()


app = FastAPI(title="每日 AI 新闻助手", version="1.0", lifespan=lifespan)


@app.get("/")
def home():
    return FileResponse(ROOT / "app/static/index.html")


@app.get("/style.css")
def css():
    return FileResponse(ROOT / "app/static/style.css", media_type="text/css")


@app.get("/app.js")
def js():
    return FileResponse(ROOT / "app/static/app.js", media_type="text/javascript")


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_configured": llm_ready(), "delivery": "in-app inbox; SMTP optional"}


@app.post("/api/users")
def save_user(body: UserInput):
    return db.create_or_update_user(body.name, body.email, body.topics,
                                    body.keywords, body.delivery_hour)


@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    return user


@app.get("/api/users/{user_id}/runs")
def list_user_runs(user_id: int):
    if db.get_user(user_id) is None:
        raise HTTPException(404, "user not found")
    return db.list_runs(user_id)


@app.post("/api/users/{user_id}/runs", status_code=202)
def create_user_run(user_id: int):
    if db.get_user(user_id) is None:
        raise HTTPException(404, "user not found")
    if not llm_ready():
        raise HTTPException(503, "Set OPENAI_COMPAT_API_KEY and OPENAI_COMPAT_MODEL in .env")
    return {"run_id": app.state.scheduler.submit_manual(user_id)}


@app.get("/api/runs/{run_id}")
def get_run(run_id: int):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run
