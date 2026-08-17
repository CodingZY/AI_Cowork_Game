from __future__ import annotations

import json

import pytest

from app.agent.runtime import ClaudeRuntime


class FakeProc:
    def __init__(self, lines):
        self._lines = lines
        self.stdout_lines = []

    async def wait(self):
        return 0


@pytest.mark.asyncio
async def test_build_cmd_includes_plugin_dir(monkeypatch):
    """plugin_dir 传入时 cmd 含 --plugin-dir <dir>。"""
    rt = ClaudeRuntime.__new__(ClaudeRuntime)
    rt.settings = None
    rt.claude_bin = "claude"
    rt.proc = None
    cmd = rt._build_cmd("p", resume_sid=None, system_prompt=None, plugin_dir="/abs/game-skills")
    assert "--plugin-dir" in cmd
    idx = cmd.index("--plugin-dir")
    assert cmd[idx + 1] == "/abs/game-skills"


@pytest.mark.asyncio
async def test_build_cmd_no_plugin_dir_when_none(monkeypatch):
    """plugin_dir 缺省时 cmd 不含 --plugin-dir。"""
    rt = ClaudeRuntime.__new__(ClaudeRuntime)
    rt.settings = None
    rt.claude_bin = "claude"
    rt.proc = None
    cmd = rt._build_cmd("p")
    assert "--plugin-dir" not in cmd


@pytest.mark.asyncio
async def test_start_passes_plugin_dir_to_run(monkeypatch):
    """start 的 plugin_dir 透传到 _build_cmd（经 _run→_spawn_stream）。"""
    captured = {}

    class FakeRuntime(ClaudeRuntime):
        async def _spawn_stream(self, cmd, env, cwd):
            captured["cmd"] = cmd
            return []

    rt = FakeRuntime.__new__(FakeRuntime)
    from app.config.settings import get_settings
    rt.settings = get_settings()
    rt.claude_bin = "claude"
    rt.proc = None
    # 用 settings.game_skills_dir 拼绝对
    plugin_dir = str(rt.settings.workspace_base.parent / rt.settings.game_skills_dir)
    evts = [e async for e in rt.start("p", "/cwd", 1, agent_type="brainstorm", system_prompt=None, plugin_dir=plugin_dir)]
    assert "--plugin-dir" in captured["cmd"]
    assert plugin_dir in captured["cmd"]
