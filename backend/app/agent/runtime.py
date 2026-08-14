from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator, Optional

from app.agent.parser import ClaudeEventParser
from app.config.settings import get_settings


class ClaudeRuntime:
    """spawn 官方 `claude` CLI 子进程，逐行读 stream-json，用 parser 归一化后 async yield。

    R1（统一 _run + _spawn_stream）：start/resume 委托私有 async generator _run，
    _run 内 await self._spawn_stream(cmd, env, cwd) 拿行列表，对每行 parser.parse yield。
    _spawn_stream 是可 monkeypatch 接缝——真实实现用 asyncio.create_subprocess_exec
    逐行读 stdout 收集；测试 monkeypatch 它返回行列表。start/resume 不绕过 _spawn_stream。
    """

    def __init__(self):
        self.settings = get_settings()
        self.proc: Optional[asyncio.subprocess.Process] = None

    def _build_cmd(self, prompt, resume_sid=None, system_prompt=None) -> list[str]:
        # --bare 强制：不带会背 26707 token 宿主上下文 + hook 报错 + refusal（spike）
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--include-partial-messages",
            "--bare", "--allowedTools", "Read", "Write",
            "--permission-mode", "acceptEdits",
        ]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        if resume_sid:
            cmd += ["--resume", resume_sid]
        return cmd

    def _build_env(self) -> dict:
        # R3：剥离宿主 CLAUDE_*/KSCC_*（本机 kscc 挂 ANTHROPIC_MODEL=glm-5.2 等会误连），
        # 只注入 settings 三变量 + 必要 PATH。
        env = {
            k: v for k, v in os.environ.items()
            if not k.startswith(("CLAUDE_", "KSCC_"))
        }
        env["ANTHROPIC_BASE_URL"] = self.settings.anthropic_base_url
        env["ANTHROPIC_AUTH_TOKEN"] = self.settings.anthropic_auth_token
        env["ANTHROPIC_MODEL"] = self.settings.anthropic_model
        return env

    async def _spawn_stream(self, cmd, env, cwd) -> list[str]:
        # 可 monkeypatch 接缝。真实实现：spawn 子进程逐行读 stdout 收集。
        self.proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
        lines: list[str] = []
        async for raw in self.proc.stdout:
            lines.append(raw.decode("utf-8", "replace"))
        await self.proc.wait()
        return lines

    async def _run(
        self,
        prompt,
        cwd,
        project_id,
        agent_type="brainstorm",
        resume_sid=None,
        system_prompt=None,
    ) -> AsyncIterator:
        cmd = self._build_cmd(prompt, resume_sid, system_prompt)
        env = self._build_env()
        parser = ClaudeEventParser(project_id=project_id, agent_type=agent_type)
        # R4：cwd 接绝对路径 str，runtime 不自己拼，session 按 cwd 存（Task10 控制 cwd）
        lines = await self._spawn_stream(cmd, env, cwd)
        for line in lines:
            for evt in parser.parse(line):
                yield evt

    async def start(
        self,
        prompt,
        cwd,
        project_id,
        agent_type="brainstorm",
        system_prompt=None,
    ) -> AsyncIterator:
        async for evt in self._run(
            prompt, cwd, project_id, agent_type, None, system_prompt
        ):
            yield evt

    async def resume(
        self,
        session_id,
        prompt,
        cwd,
        project_id,
        agent_type="brainstorm",
        system_prompt=None,
    ) -> AsyncIterator:
        async for evt in self._run(
            prompt, cwd, project_id, agent_type, session_id, system_prompt
        ):
            yield evt

    async def cancel(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
