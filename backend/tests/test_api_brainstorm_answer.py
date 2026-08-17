from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base
from app.models.brainstorm_questions import BrainstormQuestion
from app.models.project import Project
from app.persistence.repo import QuestionRepo
from app.workflow.states import ProjectStatus


@pytest_asyncio.fixture
async def client():
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
    async with sm() as s:
        s.add(Project(
            project_key="p1", name="P",
            status=ProjectStatus.BRAINSTORMING.value,
            workspace_root="ws/p1", description="种田",
        ))
        await s.commit()
        pid = (
            await s.execute(select(Project).where(Project.project_key == "p1"))
        ).scalar_one().id
        await QuestionRepo(s).create(
            pid, 1, [{"id": "1", "question": "平台？", "options": ["手机", "PC"]}]
        )
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        async with sm() as s:
            c._pid = (
                await s.execute(select(Project).where(Project.project_key == "p1"))
            ).scalar_one().id
        c._sm = sm
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_submit_answer(client, monkeypatch):
    pid = client._pid
    calls = []

    async def fake_enqueue(p):
        calls.append(p)
        return "job-gen-1"

    monkeypatch.setattr("app.api.projects.enqueue_brainstorm_generate", fake_enqueue)
    r = await client.post(
        f"/api/projects/{pid}/brainstorm/answer",
        json={"answers": [{"question_id": "1", "answer": "PC"}]},
    )
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-gen-1"
    assert calls == [pid]

    # answers 存表：端点 set_answers + commit 后，新 session 可读
    async with client._sm() as s:
        bq = (
            await s.execute(
                select(BrainstormQuestion).where(
                    BrainstormQuestion.project_id == pid
                )
            )
        ).scalar_one()
        assert bq.answers == [{"question_id": "1", "answer": "PC"}]


async def test_submit_answer_404(client, monkeypatch):
    """project 不存在 → 404，不调 enqueue。"""
    calls = []

    async def fake_enqueue(p):
        calls.append(p)
        return "job-x"

    monkeypatch.setattr("app.api.projects.enqueue_brainstorm_generate", fake_enqueue)
    r = await client.post(
        "/api/projects/999999/brainstorm/answer",
        json={"answers": [{"question_id": "1", "answer": "PC"}]},
    )
    assert r.status_code == 404
    assert calls == []


async def test_submit_answer_wrong_status(client, monkeypatch):
    """非 BRAINSTORMING → 409，不调 enqueue。"""
    pid = client._pid
    calls = []

    async def fake_enqueue(p):
        calls.append(p)
        return "job-x"

    monkeypatch.setattr("app.api.projects.enqueue_brainstorm_generate", fake_enqueue)
    async with client._sm() as s:
        await s.execute(
            update(Project).where(Project.id == pid).values(
                status=ProjectStatus.GDD_REVIEW.value
            )
        )
        await s.commit()
    r = await client.post(
        f"/api/projects/{pid}/brainstorm/answer",
        json={"answers": [{"question_id": "1", "answer": "PC"}]},
    )
    assert r.status_code == 409
    assert calls == []
