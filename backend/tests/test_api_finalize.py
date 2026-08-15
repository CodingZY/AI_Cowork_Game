from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """httpx AsyncClient 走 ASGITransport，DB 用 sqlite in-memory + StaticPool
    （多请求共享同一连接），session 依赖 override。lifespan 在 ASGITransport 下
    不跑，故手动 create_all。

    Phase 2：与 test_api_projects.py 的 client fixture 一致（asyncio_mode=auto，
    @pytest.fixture 即可用于 async fixture；create 不再建目录，无需 monkeypatch）。
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_finalize_endpoint(client, monkeypatch):
    async def _ret(pid):
        return "job-fin-1"

    monkeypatch.setattr("app.api.projects.enqueue_finalize", _ret)
    r = await client.post("/api/projects/1/brainstorm/finalize")
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-fin-1"


async def test_enqueue_finalize(monkeypatch):
    from app.queue import jobs

    class FakeJob:
        job_id = "job-fin-1"

    class FakeRedis:
        async def enqueue_job(self, func, *args, _queue_name=None):
            assert func == "run_finalize"
            assert args[0] == 7
            return FakeJob()

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(jobs, "create_pool", fake_create_pool)
    jid = await jobs.enqueue_finalize(7)
    assert jid == "job-fin-1"
