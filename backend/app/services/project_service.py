from __future__ import annotations

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.session import ensure_workspace
from app.models.project import Project
from app.workflow.states import ProjectStatus


async def create(
    session: AsyncSession,
    name: str,
    description: str | None = None,
    workspace_base=None,
) -> Project:
    """生成 project_key、ensure_workspace、落库 status=CREATED，返回新 Project。

    slug 由 name 小写化、非字母数字转 - 得到；key = `<slug>-<6 hex>`。
    workspace_base 缺省时由 ensure_workspace 取 settings.workspace_base。
    """
    slug = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    key = f"{slug}-{secrets.token_hex(3)}"
    ws = ensure_workspace(key, base=workspace_base)
    p = Project(
        project_key=key,
        name=name,
        description=description,
        status=ProjectStatus.CREATED,
        workspace_root=str(ws),
    )
    session.add(p)
    await session.flush()
    return p
