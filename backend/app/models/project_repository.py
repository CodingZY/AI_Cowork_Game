from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ProjectRepository(Base):
    """project_repositories 表（spec §5.3，D6：每项目一行，monorepo 定位）。

    owner/repository: 共享 monorepo repo（全局一致，settings 可推导，落库便于追踪）。
    sub_path: 该游戏在共享 repo 的路径（games/{key}/）。
    current_branch: brainstorm worktree 分支（agent/{key}-brainstorm），finalize 后清空。
    last_commit_sha: finalize 后 main HEAD。
    github_installation_id: PAT 模式留空（D2）。
    """

    __tablename__ = "project_repositories"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="github")
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_path: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    current_branch: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    github_installation_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
