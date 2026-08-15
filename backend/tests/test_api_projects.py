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

    Phase 2：project_service.create 不再调 ensure_workspace 建目录（workspace_root
    是相对路径字符串，worktree 由 brainstorm task 建），故无需 monkeypatch 避建目录。
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


async def test_create_project_endpoint(client):
    r = await client.post(
        "/api/projects", json={"name": "FarmDemo", "description": "d"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "CREATED"
    assert "farmdemo" in body["project_key"]
    assert body["name"] == "FarmDemo"
    assert body["workspace_root"]
    assert body["id"]


async def test_get_project(client):
    create = await client.post(
        "/api/projects", json={"name": "FarmDemo", "description": "d"}
    )
    assert create.status_code == 201
    pid = create.json()["id"]
    r = await client.get(f"/api/projects/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == pid
    assert body["name"] == "FarmDemo"
    assert body["status"] == "CREATED"
    assert body["project_key"] == create.json()["project_key"]


async def test_get_project_404(client):
    r = await client.get("/api/projects/999")
    assert r.status_code == 404


async def test_brainstorm_enqueues(client, monkeypatch):
    # 先建项目拿到合法 id
    create = await client.post(
        "/api/projects", json={"name": "FarmDemo", "description": "d"}
    )
    pid = create.json()["id"]

    calls = []

    async def fake_enqueue(project_id: int, prompt: str) -> str:
        calls.append((project_id, prompt))
        return "job-x"

    monkeypatch.setattr("app.api.projects.enqueue_brainstorm", fake_enqueue)
    r = await client.post(f"/api/projects/{pid}/brainstorm", json={"idea": "种田游戏"})
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-x"
    # 验证用户 idea 透传到 enqueue_brainstorm（C1 防回归）
    assert calls == [(pid, "种田游戏")]
