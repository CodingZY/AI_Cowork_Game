from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dev import get_session
from app.api.projects import get_session as get_session_projects
from app.main import app
from app.models import Base


@pytest_asyncio.fixture
async def dev_client(monkeypatch, tmp_path):
    """sqlite + mock temporal dev client + 真 project 行 + worktree→tmp_path（带 GDD/assets）。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override():
        async with sm() as s:
            yield s
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_session_projects] = override

    # 建真 project 行（不经 POST /projects 避免起 design workflow）
    from app.services import project_service
    async with sm() as s:
        p = await project_service.create(s, name="守灯人", description="d")
        await s.commit()
        pid, pkey = p.id, p.project_key
    game_dir = tmp_path / "games" / pkey
    game_dir.mkdir(parents=True)
    (game_dir / "GDD.md").write_text("# GDD\n", encoding="utf-8")
    (game_dir / "assets.json").write_text('{"assets":[]}', encoding="utf-8")
    (game_dir / "GAME_ARCHITECTURE.md").write_text("# arch\n", encoding="utf-8")
    (game_dir / "V1.md").write_text("# V1\n", encoding="utf-8")

    async def fake_wt(self, key):
        return tmp_path
    monkeypatch.setattr("app.git.service.GitService.worktree_path", fake_wt)

    # mock temporal dev：start/query/signal + get_client(describe RUNNING)
    async def fake_start(pid):
        return f"dev-{pid}"

    async def fake_query(pid):
        return {"phase": "WAITING_FOR_USER", "current_version": "V1", "current_idx": 0,
                "versions": ["V1"], "playtest_url": "/play/builds/k/V1/dist/",
                "build_log": "", "architecture_len": 7, "feedback_action": ""}

    async def fake_signal(pid, name, arg):
        pass

    monkeypatch.setattr("app.api.dev.start_dev_workflow", fake_start)
    monkeypatch.setattr("app.api.dev.query_dev_state", fake_query)
    monkeypatch.setattr("app.api.dev.send_dev_signal", fake_signal)

    class _Desc:
        status = "RUNNING"

    class _Handle:
        async def describe(self):
            return _Desc()

        async def terminate(self, reason):
            pass

    class _Client:
        def get_workflow_handle(self, wid):
            return _Handle()

    async def fake_get_client():
        return _Client()
    monkeypatch.setattr("temporal.client.get_client", fake_get_client)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c, pid
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_start_pipeline_ok(dev_client):
    """GDD + assets.json 存在 → 起 dev workflow，返 workflow_id。"""
    c, pid = dev_client
    r = await c.post(f"/api/projects/{pid}/develop/pipeline")
    assert r.status_code == 202
    assert r.json()["workflow_id"] == f"dev-{pid}"


async def test_start_pipeline_no_gdd_409(monkeypatch, dev_client, tmp_path):
    """GDD.md 不存在 → 409。"""
    c, pid = dev_client
    # 删 GDD（worktree_path 返 tmp_path，game_dir = tmp/games/{key}）
    import os
    from pathlib import Path
    # 找到 game_dir 删 GDD.md
    for gd in (tmp_path / "games").iterdir():
        gdd = gd / "GDD.md"
        if gdd.exists():
            gdd.unlink()
    r = await c.post(f"/api/projects/{pid}/develop/pipeline")
    assert r.status_code == 409


async def test_get_dev_state_running(dev_client):
    """workflow RUNNING → query 返真 state（WAITING_FOR_USER）。"""
    c, pid = dev_client
    r = await c.get(f"/api/projects/{pid}/develop/state")
    assert r.status_code == 200
    assert r.json()["phase"] == "WAITING_FOR_USER"
    assert r.json()["current_version"] == "V1"


async def test_get_dev_state_fallback_when_not_running(monkeypatch, dev_client):
    """workflow 非 RUNNING → 走 fallback（从盘推断）。"""
    c, pid = dev_client

    class _DescNotRun:
        status = "TERMINATED"

    class _Handle:
        async def describe(self):
            return _DescNotRun()

    class _Client:
        def get_workflow_handle(self, wid):
            return _Handle()

    async def fake_get_client_notrun():
        return _Client()
    monkeypatch.setattr("temporal.client.get_client", fake_get_client_notrun)
    r = await c.get(f"/api/projects/{pid}/develop/state")
    assert r.status_code == 200
    # fallback：有 GAME_ARCHITECTURE + V1 但无 builds 产物 → 非 WAITING_FOR_USER
    assert r.json()["phase"] != "WAITING_FOR_USER"


async def test_feedback_pass(dev_client):
    """POST feedback action=PASS → signal submit_feedback。"""
    c, pid = dev_client
    r = await c.post(f"/api/projects/{pid}/develop/feedback", json={"action": "PASS"})
    assert r.status_code == 202
    assert r.json()["ok"] is True


async def test_feedback_invalid_action_400(dev_client):
    """action 非 PASS/FIX/CHANGE → 400。"""
    c, pid = dev_client
    r = await c.post(f"/api/projects/{pid}/develop/feedback", json={"action": "NOPE"})
    assert r.status_code == 400


async def test_get_architecture_md(dev_client):
    """GET architecture → 读盘 GAME_ARCHITECTURE.md。"""
    c, pid = dev_client
    r = await c.get(f"/api/projects/{pid}/develop/architecture")
    assert r.status_code == 200
    assert "# arch" in r.json()["architecture"]


async def test_get_version_md(dev_client):
    """GET versions?version=V1 → 读盘 V1.md。"""
    c, pid = dev_client
    r = await c.get(f"/api/projects/{pid}/develop/versions?version=V1")
    assert r.status_code == 200
    assert "# V1" in r.json()["version_md"]


async def test_workflow_status(dev_client):
    """GET workflow-status → RUNNING + phase。"""
    c, pid = dev_client
    r = await c.get(f"/api/projects/{pid}/develop/workflow-status")
    assert r.status_code == 200
    assert r.json()["status"] == "RUNNING"


async def test_terminate(dev_client):
    """POST terminate → ok。"""
    c, pid = dev_client
    r = await c.post(f"/api/projects/{pid}/develop/terminate")
    assert r.status_code == 202
