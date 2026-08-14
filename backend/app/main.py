from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.events import router as events_router
from app.api.projects import router as projects_router
from app.models import Base
from app.persistence.db import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(projects_router)
app.include_router(events_router)
