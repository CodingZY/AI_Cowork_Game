from __future__ import annotations

import secrets
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.project import Project
from app.persistence.repo import ProjectRepositoryRepo
from app.workflow.states import ProjectStatus


def _parse_owner_repo(url: str) -> tuple[str, str]:
    """从 https://github.com/{owner}/{repo}.git 解析 (owner, repo)。失败返 ('','')。"""
    try:
        path = urlparse(url).path.strip("/")
        owner, repo = path.split("/")[:2]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo
    except Exception:
        return "", ""


async def create(
    session: AsyncSession,
    name: str,
    description: str | None = None,
    workspace_base=None,  # Phase 2: 保留参数兼容但不再建目录（worktree 由 brainstorm task 建）
) -> Project:
    """生成 project_key、落 Project + ProjectRepository 行，status=CREATED。

    workspace_root = workspace/worktrees/{key}-brainstorm（相对路径字符串，
    运行时由 GitService 拼绝对）。不再调 ensure_workspace 建目录（Phase 1 旧路径）。
    """
    slug = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    key = f"{slug}-{secrets.token_hex(3)}"
    settings = get_settings()
    workspace_root = f"{settings.workspace_root}/worktrees/{key}-brainstorm"
    p = Project(
        project_key=key,
        name=name,
        description=description,
        status=ProjectStatus.CREATED,
        workspace_root=workspace_root,
    )
    session.add(p)
    await session.flush()
    # 落 project_repositories（D6）
    owner, repo = _parse_owner_repo(settings.github_repo_url)
    await ProjectRepositoryRepo(session).create(
        project_id=p.id, owner=owner, repository=repo, sub_path=f"games/{key}/",
    )
    await session.flush()
    return p
