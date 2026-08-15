from __future__ import annotations

from pathlib import Path

from app.config.settings import get_settings


def ensure_workspace(project_key: str, base: Path | None = None) -> Path:
    """[DEPRECATED Phase 1] 创建 `<base>/<project_key>/` 目录。

    Phase 2 改用 GitService.worktree_add（git 管理的 worktree）。保留本函数
    仅为 Phase 1 测试兼容，新代码勿用。
    """
    root = base if base is not None else get_settings().workspace_base
    p = root / project_key
    p.mkdir(parents=True, exist_ok=True)
    return p


def worktree_path(project_key: str, settings=None) -> Path:
    """推导 worktree 路径 `<workspace_base>/worktrees/{key}-brainstorm`（纯路径，不建目录）。

    建目录由 GitService.worktree_add 负责；本函数仅供"已知 worktree 路径"场景
    （如 run_finalize 查 worktree）。
    """
    s = settings or get_settings()
    return s.workspace_base / "worktrees" / f"{project_key}-brainstorm"
