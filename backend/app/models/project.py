from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Project(Base):
    """projects 表（spec §6.1 精简）。

    status: CREATED / BRAINSTORMING / FAILED（Phase 1 子集）。
    BigInteger PK 在 sqlite 退化 Integer（autoincrement 仅 INTEGER PRIMARY KEY 生效）。
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    project_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_workflow_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    workspace_root: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_projects_status", "status"),
    )
