from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AgentSession(Base):
    """agent_sessions 表（spec §6.2）。

    claude_session_id 在 system/init 到来后回填。
    agent_type Phase 1: brainstorm。status: RUNNING/COMPLETED/FAILED。
    BigInteger PK/FK 在 sqlite 退化 Integer。
    """

    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("projects.id"),
        nullable=False,
    )
    claude_session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    working_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_agent_project", "project_id"),
        Index("idx_agent_status", "status"),
    )
