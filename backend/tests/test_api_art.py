from __future__ import annotations

import json
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.art import get_session
from app.api.projects import get_session as get_session_projects
from app.main import app
from app.models import Base


@pytest_asyncio.fixture
async def client(monkeypatch):
    """sqlite in-memory + mock temporal art client（start_art_workflow/query/send_signal）。"""
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

    # mock temporal：先建一个 project 让 /art/pipeline 校验通过
    async def fake_start(pid):
        return f"art-{pid}"

    async def fake_query(pid):
        return {"phase": "GENERATING_ASSETS", "progress": {"total": 2, "passed": 1, "failed": 0, "processing": 1, "pending": 0},
                "assets": [], "spec_check": {}, "art_report": ""}

    async def fake_signal(pid, name, arg):
        pass

    monkeypatch.setattr("app.api.art.start_art_workflow", fake_start)
    monkeypatch.setattr("app.api.art.query_art_state", fake_query)
    monkeypatch.setattr("app.api.art.send_art_signal", fake_signal)
    # B8: get_art_state 先 get_client + describe 判 RUNNING（非 RUNNING 走 fallback）
    class _Desc:
        status = "RUNNING"
    class _Handle:
        async def describe(self):
            return _Desc()
    class _Client:
        def get_workflow_handle(self, wid):
            return _Handle()
    async def fake_get_client():
        return _Client()
    monkeypatch.setattr("temporal.client.get_client", fake_get_client)
    # GitService.worktree_path 返 None（无 worktree）→ /art/pipeline 会 409
    async def fake_worktree_path(self, key):
        return None
    monkeypatch.setattr("app.git.service.GitService.worktree_path", fake_worktree_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_get_art_state(client):
    r = await client.get("/api/projects/1/art/state")
    assert r.status_code == 200
    data = r.json()
    assert data["phase"] == "GENERATING_ASSETS"
    assert data["progress"]["total"] == 2


async def test_approve(client):
    r = await client.post("/api/projects/1/art/approve")
    assert r.status_code == 202
    assert r.json()["ok"] is True


async def test_retry_asset(client):
    r = await client.post("/api/projects/1/art/retry/ANIMAL-001")
    assert r.status_code == 202
    assert r.json()["ok"] is True


async def test_start_pipeline_no_project_returns_404(client):
    """project 不存在 → 404（_require_project 先校验，早于 worktree 检查）。"""
    r = await client.post("/api/projects/1/art/pipeline")
    assert r.status_code == 404


# --- 单资产 prompt GET / regenerate POST（不经 Temporal，直接 API）---


@pytest_asyncio.fixture
async def art_asset_client(monkeypatch, tmp_path):
    """prompt/regenerate 端点测试：sqlite + 真 project 行 + worktree→tmp_path。

    新端点不经 Temporal（仅 _require_project + GitService.worktree_path + 文件 IO + ImageGenClient），
    故无需 mock temporal；直接建 project 行（不经 POST /projects 避免起 design workflow）。
    """
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

    from app.services import project_service
    async with sm() as s:
        p = await project_service.create(s, name="守灯人", description="d")
        await s.commit()
        pid, pkey = p.id, p.project_key
    game_dir = tmp_path / "games" / pkey
    game_dir.mkdir(parents=True, exist_ok=True)

    async def fake_wt(self, key):
        return tmp_path
    monkeypatch.setattr("app.git.service.GitService.worktree_path", fake_wt)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c, pid, game_dir
    app.dependency_overrides.clear()
    await engine.dispose()


def _write_assets_json(game_dir: Path, assets: list[dict]):
    (game_dir / "assets.json").write_text(json.dumps({"assets": assets}), encoding="utf-8")


async def test_get_asset_prompt_reads_prompt_files(art_asset_client):
    """GET /art/asset/{id}/prompt 读真 prompt 文件（.txt + .neg.txt）。"""
    c, pid, game_dir = art_asset_client
    _write_assets_json(game_dir, [{"asset_id": "ANIMAL-001", "name": "cow", "category": "animal"}])
    pdir = game_dir / "prompts" / "animal"
    pdir.mkdir(parents=True)
    (pdir / "ANIMAL-001.txt").write_text("a cute cow sprite", encoding="utf-8")
    (pdir / "ANIMAL-001.neg.txt").write_text("blurry, lowres", encoding="utf-8")
    r = await c.get(f"/api/projects/{pid}/art/asset/ANIMAL-001/prompt")
    assert r.status_code == 200
    d = r.json()
    assert d["prompt"] == "a cute cow sprite"
    assert d["negative_prompt"] == "blurry, lowres"


async def test_get_asset_prompt_fallback_to_description(art_asset_client):
    """prompt 文件缺失 → fallback assets.json description。"""
    c, pid, game_dir = art_asset_client
    _write_assets_json(game_dir, [{"asset_id": "X-001", "name": "x", "category": "prop", "description": "a prop"}])
    r = await c.get(f"/api/projects/{pid}/art/asset/X-001/prompt")
    assert r.status_code == 200
    assert r.json()["prompt"] == "a prop"
    assert r.json()["negative_prompt"] == ""


async def test_get_asset_prompt_404_when_not_in_assets(art_asset_client):
    """asset_id 不在 assets.json → 404。"""
    c, pid, game_dir = art_asset_client
    _write_assets_json(game_dir, [{"asset_id": "A-001", "category": "prop"}])
    r = await c.get(f"/api/projects/{pid}/art/asset/NOPE/prompt")
    assert r.status_code == 404


async def test_regenerate_asset_success(art_asset_client, monkeypatch):
    """POST regenerate：写 prompt → mock AutoDL 生图 → mock 后处理 → ok，验证 prompt 文件被写。"""
    c, pid, game_dir = art_asset_client
    _write_assets_json(game_dir, [{"asset_id": "ANIMAL-001", "name": "cow", "category": "animal",
        "post_process": {"remove_background": True, "crop": True, "resize": True, "format": "png"}}])
    from app.ai.image_client import ImageGenClient

    async def fake_generate(self, **kw):
        out = Path(kw["out_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x89PNG\r\n\x1a\n")  # 假 raw
        return {"status": "success"}

    monkeypatch.setattr(ImageGenClient, "generate", fake_generate)

    def fake_pipeline(raw_path, post_process, cwd, asset_id, category, final_size=256):
        final = Path(cwd) / "assets" / "final" / "animals" / f"{asset_id}.png"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"\x89PNG\r\n\x1a\n")  # 假 final
        return {"final_path": str(final), "status": "PROCESSED"}

    monkeypatch.setattr("app.ai.image_pipeline.run_image_pipeline", fake_pipeline)

    r = await c.post(f"/api/projects/{pid}/art/asset/ANIMAL-001/regenerate",
                     json={"prompt": "new cow", "negative_prompt": "bad"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True and d["status"] == "PASSED"
    # prompt 文件被写
    assert (game_dir / "prompts" / "animal" / "ANIMAL-001.txt").read_text(encoding="utf-8") == "new cow"
    assert (game_dir / "prompts" / "animal" / "ANIMAL-001.neg.txt").read_text(encoding="utf-8") == "bad"
    assert (game_dir / "assets" / "raw" / "animals" / "ANIMAL-001.png").exists()
    assert (game_dir / "assets" / "final" / "animals" / "ANIMAL-001.png").exists()


async def test_regenerate_asset_autodl_fail_returns_503(art_asset_client, monkeypatch):
    """AutoDL 不可达 → generate 抛错 → 503，不跑后处理，且不覆盖原 prompt 文件。"""
    c, pid, game_dir = art_asset_client
    _write_assets_json(game_dir, [{"asset_id": "ANIMAL-001", "category": "animal"}])
    # 预置原 prompt 文件（验证 503 时不被覆盖）
    pdir = game_dir / "prompts" / "animal"
    pdir.mkdir(parents=True)
    (pdir / "ANIMAL-001.txt").write_text("ORIGINAL prompt", encoding="utf-8")
    (pdir / "ANIMAL-001.neg.txt").write_text("ORIGINAL neg", encoding="utf-8")
    from app.ai.image_client import ImageGenClient

    async def fail_generate(self, **kw):
        raise RuntimeError("AutoDL 不可达: connection refused")

    monkeypatch.setattr(ImageGenClient, "generate", fail_generate)
    pipeline_called = {"v": False}

    def fake_pipeline(*a, **k):
        pipeline_called["v"] = True

    monkeypatch.setattr("app.ai.image_pipeline.run_image_pipeline", fake_pipeline)

    r = await c.post(f"/api/projects/{pid}/art/asset/ANIMAL-001/regenerate",
                     json={"prompt": "NEW prompt", "negative_prompt": "NEW neg"})
    assert r.status_code == 503
    assert "AutoDL" in r.json()["detail"]
    assert pipeline_called["v"] is False  # generate 失败 → 不跑后处理
    # 原 prompt 文件未被覆盖（generate 先于写 prompt，失败即 return）
    assert (pdir / "ANIMAL-001.txt").read_text(encoding="utf-8") == "ORIGINAL prompt"
    assert (pdir / "ANIMAL-001.neg.txt").read_text(encoding="utf-8") == "ORIGINAL neg"


async def test_regenerate_asset_empty_prompt_400(art_asset_client):
    """空 prompt → 400。"""
    c, pid, game_dir = art_asset_client
    _write_assets_json(game_dir, [{"asset_id": "ANIMAL-001", "category": "animal"}])
    r = await c.post(f"/api/projects/{pid}/art/asset/ANIMAL-001/regenerate",
                     json={"prompt": "   ", "negative_prompt": ""})
    assert r.status_code == 400
