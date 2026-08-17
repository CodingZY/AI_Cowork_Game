from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base
from app.models.project import Project
from app.workflow.states import ProjectStatus


@pytest.fixture
async def client(tmp_path):
    """httpx AsyncClient + ASGITransport，sqlite in-memory + StaticPool
    （多请求共享同一连接），session 依赖 override。

    预置一个 GDD_REVIEW 的 project，pid 存 client._test_pid。
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
        # 预置一个 GDD_REVIEW 的 project
        async with sm() as s:
            p = Project(
                project_key="gddproj",
                name="Gdd",
                status=ProjectStatus.GDD_REVIEW.value,
                workspace_root="ws/gddproj",
            )
            s.add(p)
            await s.commit()
            c._test_pid = p.id
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_gdd_approve_endpoint(client, monkeypatch):
    """GDD_REVIEW 的 project approve → 202 + enqueue_gdd_check 透传 task_id。"""
    pid = client._test_pid

    async def _fake(pid_arg):
        return "job-chk-api-1"

    monkeypatch.setattr("app.api.projects.enqueue_gdd_check", _fake)
    r = await client.post(f"/api/projects/{pid}/gdd/approve")
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-chk-api-1"


async def test_gdd_approve_rejects_wrong_status(client):
    """project 不存在 → 404。"""
    r = await client.post("/api/projects/99999/gdd/approve")
    assert r.status_code == 404


async def test_submit_gdd(client, monkeypatch, tmp_path):
    """POST /gdd/submit：校验 GDD_REVIEW → 写回 worktree GDD.md → GDD_CHECKING → 触发 04。"""
    pid = client._test_pid

    async def _fake_enqueue(p):
        return "job-chk-submit-1"

    monkeypatch.setattr("app.api.projects.enqueue_gdd_check", _fake_enqueue)

    # worktree_path 是 async（Task 5/6 教训：用 async fake 返真实 tmp_path，别用同步 lambda）
    async def _fake_wp(self, key):
        return tmp_path

    monkeypatch.setattr(
        "app.api.projects.GitService",
        lambda: type("G", (), {"worktree_path": _fake_wp})(),
    )

    r = await client.post(
        f"/api/projects/{pid}/gdd/submit", json={"gdd_md": "# edited GDD\n"}
    )
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-chk-submit-1"
    # 文件写回 worktree
    gdd_file = tmp_path / "games" / "gddproj" / "GDD.md"
    assert gdd_file.exists()
    assert gdd_file.read_text(encoding="utf-8") == "# edited GDD\n"


async def test_submit_gdd_rejects_wrong_status(client, monkeypatch):
    """非 GDD_REVIEW → 409。"""
    pid = client._test_pid
    # client fixture 建的是 GDD_REVIEW，先 approve 掉使其变 GDD_CHECKING
    async def _fake_enqueue(p):
        return "job-chk-2"

    monkeypatch.setattr("app.api.projects.enqueue_gdd_check", _fake_enqueue)
    async def _fake_wp(self, key):
        return None
    monkeypatch.setattr(
        "app.api.projects.GitService",
        lambda: type("G", (), {"worktree_path": _fake_wp})(),
    )
    await client.post(f"/api/projects/{pid}/gdd/approve")  # GDD_REVIEW → GDD_CHECKING
    r = await client.post(
        f"/api/projects/{pid}/gdd/submit", json={"gdd_md": "# x\n"}
    )
    assert r.status_code == 409
