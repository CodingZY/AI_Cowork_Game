"""权限沙箱：按工具与路径放行/拒绝。"""
from pathlib import Path
import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
from agents.permissions import make_permission_handler


@pytest.mark.asyncio
async def test_allow_write_game_design(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("write_file", {"path": "docs/game-design.md", "content": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultAllow)


@pytest.mark.asyncio
async def test_deny_write_outside_game_design(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("write_file", {"path": "src/main.js", "content": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)


@pytest.mark.asyncio
async def test_deny_absolute_escape(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("write_file", {"path": "../../etc/evil.md", "content": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)


@pytest.mark.asyncio
async def test_allow_read_inside(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("read_file", {"path": "docs/game-design.md"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultAllow)


@pytest.mark.asyncio
async def test_deny_read_outside(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("read_file", {"path": "../../etc/passwd"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)


@pytest.mark.asyncio
async def test_allow_ask_user(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("ask_user", {"question": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultAllow)


@pytest.mark.asyncio
async def test_deny_unknown_tool(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("bash", {"command": "rm -rf /"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)
