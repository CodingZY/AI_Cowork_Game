from __future__ import annotations

import json

from app.agent.runtime import ClaudeRuntime

# 测试用 cwd（绝对路径 str；runtime 不自己拼，由 Task10 传 workspace_root 绝对路径）
TEST_CWD = "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/Games/demo"


def _stream_lines():
    """fake _spawn_stream 返回的 init + result 两行 stream-json NDJSON。"""
    return [
        json.dumps({
            "type": "system", "subtype": "init",
            "session_id": "s1", "model": "kimi-k3",
            "tools": ["Read", "Write"],
        }),
        json.dumps({
            "type": "result", "subtype": "success", "is_error": False,
            "stop_reason": "end_turn", "session_id": "s1", "result": "4",
            "total_cost_usd": 0.01, "duration_ms": 1, "num_turns": 1,
        }),
    ]


# ---------------------------------------------------------------------------
# R1: start 委托 _run -> _spawn_stream（可 monkeypatch 接缝），不直接读 proc.stdout
# ---------------------------------------------------------------------------


async def test_runtime_cmd_has_bare_and_env_injected(monkeypatch):
    """start 走 _run->_spawn_stream：cmd 含 --bare、env 注入 kimi-k3、
    cwd 透传、首事件 session.started、末事件 session.completed、project_id 透传。"""
    rt = ClaudeRuntime()
    captured: dict = {}

    async def fake_spawn(cmd, env, cwd):
        captured.update(cmd=cmd, env=env, cwd=cwd)
        return _stream_lines()

    monkeypatch.setattr(rt, "_spawn_stream", fake_spawn)

    evts = [e async for e in rt.start(
        prompt="2+2", cwd=TEST_CWD, project_id=1, agent_type="brainstorm")]

    # --bare 强制（spike：不带背 26707 token 宿主上下文 + hook 报错 + refusal）
    assert "--bare" in captured["cmd"]
    # env 注入 settings 三变量，ANTHROPIC_MODEL==kimi-k3
    assert captured["env"]["ANTHROPIC_MODEL"] == "kimi-k3"
    # cwd 接绝对路径 str，透传不拼
    assert captured["cwd"] == TEST_CWD
    # 首事件 = session.started，末事件 = session.completed
    assert evts[0].type == "agent.session.started"
    assert evts[-1].type == "agent.session.completed"
    # project_id 透传给 parser
    assert evts[0].project_id == 1


async def test_runtime_resume_adds_resume_flag(monkeypatch):
    """resume 把 session_id 作为 --resume 参数拼进 cmd。"""
    rt = ClaudeRuntime()
    captured: dict = {}

    async def fake_spawn(cmd, env, cwd):
        captured["cmd"] = cmd
        return _stream_lines()

    monkeypatch.setattr(rt, "_spawn_stream", fake_spawn)

    _ = [e async for e in rt.resume(
        session_id="s1", prompt="continue", cwd=TEST_CWD, project_id=1)]

    assert "--resume" in captured["cmd"]
    assert "s1" in captured["cmd"]


async def test_runtime_system_prompt_appended(monkeypatch):
    """system_prompt 非空时拼 --append-system-prompt <text>。"""
    rt = ClaudeRuntime()
    captured: dict = {}

    async def fake_spawn(cmd, env, cwd):
        captured["cmd"] = cmd
        return _stream_lines()

    monkeypatch.setattr(rt, "_spawn_stream", fake_spawn)

    _ = [e async for e in rt.start(
        prompt="hi", cwd=TEST_CWD, project_id=1, system_prompt="BE BRAVE")]

    assert "--append-system-prompt" in captured["cmd"]
    assert "BE BRAVE" in captured["cmd"]


# ---------------------------------------------------------------------------
# R3: _build_env 剥离宿主 CLAUDE_*/KSCC_*，只注入 settings 三变量
# ---------------------------------------------------------------------------


def test_runtime_build_env_strips_host_claude(monkeypatch):
    """宿主挂的 CLAUDE_*/KSCC_* 被剥离，ANTHROPIC_MODEL 取 .env 的 kimi-k3。"""
    monkeypatch.setenv("CLAUDE_CODE_FOO", "bar")
    monkeypatch.setenv("KSCC_BAR", "baz")

    rt = ClaudeRuntime()
    env = rt._build_env()

    assert not any(k.startswith("CLAUDE_") for k in env)
    assert not any(k.startswith("KSCC_") for k in env)
    assert env["ANTHROPIC_MODEL"] == "kimi-k3"
