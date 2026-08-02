"""REST 路由集成测试（异步 httpx + ASGITransport + sqlite，runner 被 mock）。

用异步客户端而非同步 TestClient：design agent 作为 asyncio.create_task 后台任务
运行，需要在同一事件循环里 await 让出控制权才能推进；同步 TestClient 会阻塞。
"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
import api.runtime as runtime_mod


async def _fake_run_design_agent(game_root, **kw):
    (game_root / "docs").mkdir(parents=True, exist_ok=True)
    (game_root / "docs" / "game-design.md").write_text(
        "# G 游戏设计规格书\n\n## 0. 设计总览\nx\n\n## 1. A\nx\n\n## 2. B\nx\n\n## 3. C\nx\n\n## 存档持久化\nx\n\n## 经济平衡结论\nx\n",
        encoding="utf-8",
    )
    return game_root / "docs" / "game-design.md"


async def _wait_status(c, rid, status, stage=None, timeout=50):
    for _ in range(timeout):
        st = (await c.get(f"/api/runs/{rid}")).json()
        if st["status"] == status and (stage is None or st["current_stage"] == stage):
            return st
        await asyncio.sleep(0.1)
    raise AssertionError(f"未等到 status={status}: {st}")


@pytest.mark.asyncio
async def test_create_run_and_get_design(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "run_design_agent", _fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "测试游戏"})).json()
        assert r["game_name"] == "测试游戏"
        await _wait_status(c, r["id"], "awaiting_approval", stage="S1_design")
        doc = (await c.get(f"/api/runs/{r['id']}/design.md")).json()
        assert "设计总览" in doc["content"]


@pytest.mark.asyncio
async def test_approve_advances(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "run_design_agent", _fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "G2"})).json()
        await _wait_status(c, r["id"], "awaiting_approval")
        ap = await c.post(f"/api/runs/{r['id']}/approve")
        assert ap.status_code == 200
        st = (await c.get(f"/api/runs/{r['id']}")).json()
        assert st["current_stage"] == "S2_art_plan" and st["status"] == "not_implemented"


@pytest.mark.asyncio
async def test_reject_reruns(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "run_design_agent", _fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "G3"})).json()
        await _wait_status(c, r["id"], "awaiting_approval")
        rj = await c.post(f"/api/runs/{r['id']}/reject", json={"feedback": "加钓鱼"})
        assert rj.status_code == 200
