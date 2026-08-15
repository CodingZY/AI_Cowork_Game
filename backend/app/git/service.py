from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Optional, Tuple

from app.config.settings import get_settings


class GitConflict(Exception):
    """merge 冲突（spec §11）。"""
    pass


class GitService:
    """封装共享 monorepo 的 git 操作（spec §5.1，D7：subprocess 调本机 git）。

    所有 git 调用经 _git（asyncio.create_subprocess_exec），env 注入
    GIT_TERMINAL_PROMPT=0 防挂起。PAT 认证：clone 用 PAT URL 后立即 set-url
    去 PAT；push/tag 用 http.extraheader 临时凭据（不落 .git/config）。
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.repo_dir: Path = self.settings.workspace_base / "games-repo"

    async def _git(self, args: list[str], cwd: Optional[str] = None,
                   use_pat: bool = False) -> Tuple[int, str, str]:
        """asyncio.create_subprocess_exec 调 git，返回 (rc, stdout, stderr)。

        use_pat=True 时注入 http.extraheader 临时凭据（push/tag 用）。
        env 设 GIT_TERMINAL_PROMPT=0（凭据缺失直接失败而非挂起）。
        """
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        cmd = ["git"]
        if use_pat and self.settings.github_pat:
            token = f"x-access-token:{self.settings.github_pat}"
            b64 = base64.b64encode(token.encode()).decode()
            cmd += ["-c", "credential.helper=", "-c",
                    f"http.extraheader=Authorization: Basic {b64}"]
        cmd += args
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
        )
        out, err = await proc.communicate()
        return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    @staticmethod
    def _strip_pat(url: str, pat: str) -> str:
        """把 PAT URL 还原成不含 PAT 的 https URL（避免落 .git/config 明文）。"""
        if pat and f"x-access-token:{pat}@" in url:
            return url.replace(f"x-access-token:{pat}@", "")
        return url

    async def ensure_clone(self, origin_url: Optional[str] = None) -> Path:
        """幂等：repo_dir 不存在则 clone（用 PAT URL 若 settings 有 pat），
        clone 后 set-url 去 PAT；已存在则 fetch。返回 repo_dir。

        origin_url 缺省用 settings.github_repo_url；测试可传本地 bare file:// url。
        空 repo 处理（首提交建 main）在 ensure_template_pushed（Task 6）。
        """
        url = origin_url if origin_url is not None else self.settings.github_repo_url
        pat = self.settings.github_pat
        clone_url = url.replace("https://", f"https://x-access-token:{pat}@") if pat else url
        if not self.repo_dir.exists():
            self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
            rc, out, err = await self._git(["clone", clone_url, str(self.repo_dir)])
            if rc != 0:
                raise RuntimeError(f"git clone failed: {err}")
            # clone 完立即去 PAT（pat 非空则 clone 时嵌了 PAT，需 set-url 还原）
            if pat:
                await self._git(["remote", "set-url", "origin", url], cwd=str(self.repo_dir))
        else:
            # 已存在：fetch（幂等，origin 变化能拿到）
            await self._git(["fetch", "origin"], cwd=str(self.repo_dir))
        return self.repo_dir

    async def current_sha(self, ref: str = "main") -> str:
        """git rev-parse {ref}。"""
        rc, out, err = await self._git(["rev-parse", ref], cwd=str(self.repo_dir))
        if rc != 0:
            raise RuntimeError(f"git rev-parse {ref} failed: {err}")
        return out.strip()
