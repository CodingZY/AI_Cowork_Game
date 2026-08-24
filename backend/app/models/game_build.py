from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    DateTime,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class GameBuild(Base):
    """game_builds 表（design §21）—— 每次 build_game activity 调用一行。

    记录 Coder Build 的成功/失败、版本、耗时、日志，是 Build 成功率的聚合源：
        success 率 = COUNT(status='SUCCESS') / COUNT(*)
    Langfuse 侧保存对应 Build Observation，langfuse_observation_id 回链下钻。
    """

    __tablename__ = "game_builds"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(16), nullable=False)  # V1/V2/V3
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # SUCCESS / FAILED
    dist_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    build_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    workflow_run_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # Temporal run_id
    langfuse_observation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())

    __table_args__ = (
        Index("idx_game_builds_project", "project_id"),
        Index("idx_game_builds_project_version", "project_id", "version"),
    )
