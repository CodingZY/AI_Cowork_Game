from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Event(Base):
    """events 表（spec §6.3）—— 归一化事件流落库 + Redis Stream 双写源。

    payload: 归一化 CoworkEvent.data（JSON）。
    raw_json: 原始 claude stream-json 行（调试用）。
    aggregate_type: agent_session / project。
    BigInteger PK/FK 在 sqlite 退化 Integer；aggregate_id 不退化（非 PK/FK，无碍）。
    """

    __tablename__ = "events"

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
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())

    __table_args__ = (
        Index("idx_event_project", "project_id"),
        Index("idx_event_aggregate", "aggregate_type", "aggregate_id"),
        Index("idx_event_created", "created_at"),
    )
