from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.events import router as events_router
from app.api.projects import router as projects_router
from app.api.art import router as art_router
from app.api.dev import router as dev_router
from app.api.observability import router as observability_router
from app.config.settings import get_settings
from app.models import Base
from app.persistence.db import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Phase 3: 部署目录（StaticFiles 挂 /play → workspace/builds，deploy_game 落 dist 到此）
    builds_dir = get_settings().workspace_base / "builds"
    builds_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(projects_router)
app.include_router(art_router)
app.include_router(dev_router)
app.include_router(events_router)
app.include_router(observability_router)
# Phase 3: playtest 部署（StaticFiles 实时读盘，deploy_game 落 dist 后即可访问）
# /play/builds/{key}/{version}/dist/ → workspace/builds/{key}/{version}/dist/
# StaticFiles 模块加载时即要求目录存在，故先建（幂等）。
_builds_dir = get_settings().workspace_base / "builds"
_builds_dir.mkdir(parents=True, exist_ok=True)
app.mount("/play", StaticFiles(directory=str(_builds_dir), html=True), name="play")
