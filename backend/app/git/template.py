from __future__ import annotations

import shutil
from pathlib import Path

from app.config.settings import REPO_ROOT
from app.git.service import GitService

# 后端自带模板源（入库）
TEMPLATE_SRC = REPO_ROOT / "backend" / "templates" / "game-template"


async def ensure_template_pushed(git_service: GitService) -> bool:
    """幂等：repo_dir 无 template/ 则从后端自带复制 + commit + push。

    空repo处理（spec §11）：若本地仓无任何提交（HEAD unborn），首提交前显式
    `git checkout -b main`（git 2.37 默认 master，不显式则 worktree_add(base=main)
    失败）。返回是否本次推送（False=已有，未推）。
    """
    repo_dir = git_service.repo_dir
    if (repo_dir / "template").exists():
        return False
    # 检查 HEAD 是否 unborn（无提交）
    rc, out, err = await git_service._git(["rev-parse", "--verify", "HEAD"], cwd=str(repo_dir))
    head_unborn = rc != 0
    if head_unborn:
        await git_service._git(["checkout", "-b", "main"], cwd=str(repo_dir))
    else:
        await git_service._git(["checkout", "main"], cwd=str(repo_dir))
    # 复制后端自带模板
    if not TEMPLATE_SRC.exists():
        raise RuntimeError(f"game-template source missing: {TEMPLATE_SRC}")
    dst = repo_dir / "template"
    shutil.copytree(TEMPLATE_SRC, dst, dirs_exist_ok=True)
    await git_service._git(["add", "-A"], cwd=str(repo_dir))
    await git_service._git(["commit", "-m", "chore: add game-template"], cwd=str(repo_dir))
    await git_service.push("origin", "main")
    return True
