from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base


@pytest_asyncio.fixture
async def client(monkeypatch):
    """sqlite in-memory + mock temporal client（start_design_workflow/query_state/send_signal）。

    不连真 Temporal Server；ASGITransport 不触发 app lifespan（故 get_engine 不连 MySQL）。
    StaticPool 让 in-memory sqlite 跨请求共享同一连接，POST 建的 project 对 GET 可见。
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_session] = override

    # mock Temporal client（不连真 Temporal Server）
    async def fake_start(pid, idea):
        return f"game-{pid}"

    async def fake_query(pid):
        return {
            "phase": "WAITING_USER",
            "progress": {"answered": 0, "total": 2},
            "currentQuestion": {"id": "camera"},
            "decisions": [],
        }

    async def fake_signal(pid, name, arg):
        pass

    monkeypatch.setattr("app.api.projects.start_design_workflow", fake_start)
    monkeypatch.setattr("app.api.projects.query_state", fake_query)
    monkeypatch.setattr("app.api.projects.send_signal", fake_signal)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_create_project_starts_workflow(client):
    r = await client.post("/api/projects", json={"name": "Test", "description": "种田"})
    assert r.status_code == 201
    # start_design_workflow 被 mock 成不抛即证明端点走通起 Workflow 路径
    body = r.json()
    assert body["id"] == 1


async def test_get_state(client):
    await client.post("/api/projects", json={"name": "T", "description": "idea"})
    r = await client.get("/api/projects/1/state")
    assert r.status_code == 200
    data = r.json()
    assert data["phase"] == "WAITING_USER"
    assert data["currentQuestion"]["id"] == "camera"


async def test_submit_answer(client):
    await client.post("/api/projects", json={"name": "T", "description": "idea"})
    r = await client.post(
        "/api/projects/1/answer", json={"question_id": "camera", "answer": "top_down"}
    )
    assert r.status_code == 202
