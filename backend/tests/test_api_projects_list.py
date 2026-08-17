from __future__ import annotations

from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base
from app.models.project import Project


@pytest_asyncio.fixture
async def client():
    """sqlite in-memory + StaticPool，预置 2 个 project（a/b）。"""
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
        s.add(Project(project_key="a", name="A", status="CREATED", workspace_root="ws/a"))
        s.add(Project(project_key="b", name="B", status="GDD_REVIEW", workspace_root="ws/b"))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_list_projects(client):
    r = await client.get("/api/projects")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    keys = [p["project_key"] for p in data]
    assert "a" in keys and "b" in keys
    # list_all 按 id desc：b(id=2) 在前，a(id=1) 在后
    assert data[0]["project_key"] == "b"
    assert data[1]["project_key"] == "a"


class _FakeGitService:
    """worktree_path 返回真实 tmp_path，让端点读真实文件（不 mock open）。"""

    def __init__(self, wt: Path):
        self.wt = wt

    async def worktree_path(self, project_key: str):
        return self.wt


async def test_get_gdd(client, tmp_path, monkeypatch):
    """GET /projects/{id}/gdd 读 worktree 的 GDD.md + gdd-manifest.json。"""
    # pid=1 → project_key="a"
    gdd_dir = tmp_path / "games" / "a"
    gdd_dir.mkdir(parents=True)
    (gdd_dir / "GDD.md").write_text("# GDD\n", encoding="utf-8")
    (gdd_dir / "gdd-manifest.json").write_text('{"features":[]}', encoding="utf-8")

    monkeypatch.setattr("app.api.projects.GitService", lambda: _FakeGitService(tmp_path))

    r = await client.get("/api/projects/1/gdd")
    assert r.status_code == 200
    body = r.json()
    assert body["gdd_md"] == "# GDD\n"
    assert body["manifest"] == '{"features":[]}'


async def test_get_gdd_missing_files_returns_empty(client, tmp_path, monkeypatch):
    """GDD 文件未生成 → 空字符串，不 500。"""
    monkeypatch.setattr("app.api.projects.GitService", lambda: _FakeGitService(tmp_path))
    r = await client.get("/api/projects/1/gdd")
    assert r.status_code == 200
    body = r.json()
    assert body["gdd_md"] == ""
    assert body["manifest"] == ""


async def test_get_gdd_project_not_found(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.projects.GitService", lambda: _FakeGitService(tmp_path))
    r = await client.get("/api/projects/99999/gdd")
    assert r.status_code == 404
