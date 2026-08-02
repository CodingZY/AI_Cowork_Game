"""Design Agent 运行器：用假 query 验证接线（不接真实 LLM）。"""
import asyncio
from pathlib import Path
import pytest
from claude_agent_sdk import ResultMessage
from agents.tools import do_write_file


@pytest.mark.asyncio
async def test_runner_writes_design_and_emits_progress(tmp_path, monkeypatch):
    import agents.runner as runner_mod

    progress = []

    async def fake_query(*, prompt, options):
        # 模拟 agent 一次完整工具往返：先 ask_user（验权限），再 write_file（验权限 + 真正落盘），
        # 再触发 Pre/Post hook 验进度流。真实 SDK 会驱动这些；fake 里手动模拟。
        await options.can_use_tool("ask_user", {"question": "类型?", "options": ["模拟"]}, None)
        write_input = {"path": "docs/game-design.md", "content": "OK"}
        await options.can_use_tool("write_file", write_input, None)
        # 模拟 MCP write_file 工具实际执行（runner 已建好 game_root/docs）
        await do_write_file(tmp_path / "docs" / "game-design.md", "OK")
        for hm in options.hooks["PreToolUse"]:
            await hm.hooks[0]({"tool_name": "write_file", "tool_input": write_input}, "tu1", {})
        for hm in options.hooks["PostToolUse"]:
            await hm.hooks[0]({"tool_name": "write_file", "tool_input": {}}, "tu1", {})
        yield ResultMessage("result", 0, 0, False, 1, "test-session")

    monkeypatch.setattr(runner_mod, "query", fake_query)

    async def ask(q, o):
        return "模拟"
    async def on_progress(m):
        progress.append(m)

    path = await runner_mod.run_design_agent(
        game_root=tmp_path, ask=ask, on_progress=on_progress,
        model="claude-sonnet-4-6", base_url=None, auth_token=None,
        prompt="设计一款农场游戏",
    )
    assert path.read_text(encoding="utf-8") == "OK"
    assert any(m["event"] == "pre" for m in progress)
