"""Design Agent 工具：纯函数行为 + SDK 包装可构建。"""
import asyncio
from pathlib import Path
import pytest
from agents.tools import do_read_file, do_write_file, do_ask_user, build_design_tools, TOOL_ASK_USER


@pytest.mark.asyncio
async def test_do_write_and_read_file(tmp_path):
    target = tmp_path / "docs" / "game-design.md"
    res = await do_write_file(target, "# 标题\n正文")
    assert target.read_text(encoding="utf-8") == "# 标题\n正文"
    assert res["ok"] is True
    content = await do_read_file(target)
    assert content["content"].startswith("# 标题")


@pytest.mark.asyncio
async def test_do_read_file_missing(tmp_path):
    res = await do_read_file(tmp_path / "nope.md")
    assert res["ok"] is False and "不存在" in res["error"]


@pytest.mark.asyncio
async def test_do_ask_user_returns_answer():
    async def fake_ask(question, options):
        return "模拟"
    res = await do_ask_user("类型？", ["RPG", "模拟"], ask=fake_ask)
    assert res["answer"] == "模拟"


def test_build_design_tools_returns_mcp_config(tmp_path):
    async def ask(q, o):
        return "x"
    cfg = build_design_tools(tmp_path, ask)
    # McpSdkServerConfig 是 dict 子类
    assert isinstance(cfg, dict)
    assert "tools" in cfg or "name" in cfg


def test_tool_name_constant():
    assert TOOL_ASK_USER == "ask_user"
