from __future__ import annotations

import asyncio
import os
import shutil
import sys
from typing import AsyncIterator, Optional

from app.agent.parser import ClaudeEventParser
from app.config.settings import get_settings


def _resolve_claude_bin() -> str:
    """解析 claude 可执行路径，跨平台。

    Windows: npm 全局 `claude` 是 `.cmd` shim，asyncio.create_subprocess_exec
    不经 shell（走 CreateProcess）找不到无扩展名的 `claude`；实际可执行在
    ``<node_global>/node_modules/@anthropic-ai/claude-code/bin/claude.exe``
    （claude-code 2.x 为 bun 编译的原生 exe）。直接 exec 该 .exe，绕过
    cmd.exe——避免多行 ``--append-system-prompt`` 被 cmd.exe 在换行处截断。
    Unix: ``shutil.which('claude')`` 返回的可 exec 路径直接用。
    """
    if sys.platform == "win32":
        shim = shutil.which("claude") or shutil.which("claude.cmd")
        if shim:
            exe = os.path.join(
                os.path.dirname(shim),
                "node_modules",
                "@anthropic-ai",
                "claude-code",
                "bin",
                "claude.exe",
            )
            if os.path.isfile(exe):
                return exe
        return "claude"  # fallback（可能仍 FileNotFoundError，e2e 可见）
    return shutil.which("claude") or "claude"


class ClaudeRuntime:
    """spawn 官方 `claude` CLI 子进程，逐行读 stream-json，用 parser 归一化后 async yield。

    R1（统一 _run + _spawn_stream）：start/resume 委托私有 async generator _run，
    _run 内 await self._spawn_stream(cmd, env, cwd) 拿行列表，对每行 parser.parse yield。
    _spawn_stream 是可 monkeypatch 接缝——真实实现用 asyncio.create_subprocess_exec
    逐行读 stdout 收集；测试 monkeypatch 它返回行列表。start/resume 不绕过 _spawn_stream。
    """

    def __init__(self):
        self.settings = get_settings()
        self.claude_bin = _resolve_claude_bin()
        self.proc: Optional[asyncio.subprocess.Process] = None

    def _build_cmd(self, prompt, resume_sid=None, system_prompt=None, plugin_dir=None) -> list[str]:
        # --bare 强制：不带会背 26707 token 宿主上下文 + hook 报错 + refusal（spike）
        # 首元素用解析出的 claude.exe 绝对路径（Windows，见 _resolve_claude_bin）
        # --allowedTools 是「预批准列表」非工具白名单——未列工具仍可用，只走权限判定
        # （实证：仅 --allowedTools Read Write 没拦住 PowerShell）。故加 --disallowedTools
        # 硬禁 shell（deny 压过内置只读命令启发式 + 任何继承 allow），实测工具名为 PowerShell。
        # 不用 --include-partial-messages：partial message 单行会随 LLM 输出累积超长（code-gen
        # 生成大代码时单行 >64KB 触发 asyncio readline ValueError "chunk longer than limit"）。
        # 后端只等 session.completed.result，不消费 partial，去掉后完整 event 行短且稳定。
        cmd = [
            self.claude_bin, "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--bare", "--allowedTools", "Read", "Write",
            "--disallowedTools", "PowerShell", "Bash",
            "--permission-mode", "acceptEdits",
        ]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        if plugin_dir:
            cmd += ["--plugin-dir", plugin_dir]
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
        # limit=16MB：StreamReader 默认 64KB，超长行（大 content 的 stream-json event）
        # 会触发 readline ValueError。已去 --include-partial-messages 让行变短，此处再放宽双保险。
        self.proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
            limit=2 ** 24,
        )
        lines: list[str] = []
        try:
            async for raw in self.proc.stdout:
                lines.append(raw.decode("utf-8", "replace"))
            await self.proc.wait()
        except BaseException:
            # cancel/异常（Temporal activity start_to_close_timeout 取消等）→ 强 kill 子进程。
            # 否则 Windows 上外部取消不触发 stdout EOF、proc 变孤儿
            # （实证：consistency check 卡死时 11 个 claude.exe 堆积）。
            # 用 kill()（TerminateProcess 强制）非 terminate()（CtrlEvent，Windows 不可靠）。
            if self.proc and self.proc.returncode is None:
                self.proc.kill()
            raise
        return lines

    async def _run(
        self,
        prompt,
        cwd,
        project_id,
        agent_type="brainstorm",
        resume_sid=None,
        system_prompt=None,
        plugin_dir=None,
    ) -> AsyncIterator:
        cmd = self._build_cmd(prompt, resume_sid, system_prompt, plugin_dir)
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
        plugin_dir=None,
    ) -> AsyncIterator:
        async for evt in self._run(
            prompt, cwd, project_id, agent_type, None, system_prompt, plugin_dir
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
        plugin_dir=None,
    ) -> AsyncIterator:
        async for evt in self._run(
            prompt, cwd, project_id, agent_type, session_id, system_prompt, plugin_dir
        ):
            yield evt

    async def cancel(self):
        # kill()（TerminateProcess 强制）非 terminate()（CtrlEvent，Windows console 子进程才响应）。
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
