"""FastAPI 应用装配：REST 路由 + lifespan 建表。

注：Task 12 将在此处追加 `app.include_router(ws_router)` 接入 WS 端点。

兼容说明：httpx.ASGITransport 不会触发 ASGI lifespan 事件，故在 lifespan 之外
另加一道首请求建表守卫，确保测试（用 ASGITransport）与生产（走真实 lifespan）
首次请求前表都已就绪。create_all 幂等，重复调用无副作用。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from api.deps import _engine, set_games_root
from api.routes import router as rest_router
from api.ws import router as ws_router
from persistence.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(_engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(rest_router)
app.include_router(ws_router)

_init_done = False


@app.middleware("http")
async def ensure_db(request: Request, call_next):
    global _init_done
    if not _init_done:
        await init_db(_engine)
        _init_done = True
    return await call_next(request)


__all__ = ["app", "set_games_root"]
