"""S1 端到端：mock LLM（假 query），验证 建run→问答→写设计→闸→通过→S2。"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_s1_full_flow(monkeypatch, tmp_path):
    from claude_agent_sdk import ResultMessage
    from agents.tools import do_write_file
    from api.runtime import _slug
    import agents.runner as runner_mod

    game_root = tmp_path / _slug("测试游戏")

    async def fake_query(*, prompt, options):
        # 1) agent 问一个问题（仅走权限校验；真实问答环路见 Task 10/11 的 broker 测试）
        await options.can_use_tool("ask_user", {"question": "类型?", "options": ["模拟"]}, None)
        # 2) agent 写设计文件：先过权限沙箱，再真正落盘（runner 已建好 game_root/docs）
        md = ("# 测试游戏 游戏设计规格书\n\n## 0. 设计总览\n核心循环。\n\n"
              "## 1. 系统A\n机制。\n\n## 2. 系统B\n机制。\n\n## 3. 系统C\n机制。\n\n"
              "## 存档持久化\n字段。\n\n## 经济平衡结论\n结论。\n")
        await options.can_use_tool("write_file", {"path": "docs/game-design.md", "content": md}, None)
        await do_write_file(game_root / "docs" / "game-design.md", md)
        # SDK 0.2.125 的 ResultMessage 需要 6 个位置参数；runner 忽略 yield 的消息
        yield ResultMessage("result", 0, 0, False, 1, "test-session")

    monkeypatch.setattr(runner_mod, "query", fake_query)

    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "测试游戏"})).json()
        rid = r["id"]
        # 等到闸
        for _ in range(50):
            st = (await c.get(f"/api/runs/{rid}")).json()
            if st["status"] == "awaiting_approval":
                break
            await asyncio.sleep(0.1)
        assert st["status"] == "awaiting_approval"
        doc = (await c.get(f"/api/runs/{rid}/design.md")).json()["content"]
        assert "设计总览" in doc and "存档持久化" in doc
        # 通过闸 → S2 not_implemented
        await c.post(f"/api/runs/{rid}/approve")
        st2 = (await c.get(f"/api/runs/{rid}")).json()
        assert st2["current_stage"] == "S2_art_plan" and st2["status"] == "not_implemented"
