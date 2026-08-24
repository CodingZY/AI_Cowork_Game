from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class GameObservation(Base):
    """game_observations 表（Observability）—— 每次 skill spawn / 纯 Python activity 一行。

    作为 Phase 耗时与 Token 的聚合源，避免依赖 Langfuse 查询 API 的延迟：
        Phase 耗时 = MAX(ended_at) - MIN(started_at) by phase（Python 端算，避方言差异）
        Phase Token = SUM(total_tokens) by phase
        Skill Token = SUM(total_tokens) by name (+mode)
    注意：列名 `metadata` 与 DeclarativeBase 保留属性冲突，故 Python 属性名为 `meta`。
    """

    __tablename__ = "game_observations"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    phase: Mapped[str] = mapped_column(String(4), nullable=False)  # "1" / "2" / "3"
    observation_type: Mapped[str] = mapped_column(String(16), nullable=False)  # skill / activity
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # skill_name 或 activity_name
    mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # freeze/contracts/coder/fix
    version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")  # OK / ERROR
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 列名 metadata（避 Base.metadata 保留字冲突，Python 属性用 meta）
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    langfuse_trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    langfuse_observation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())

    __table_args__ = (
        Index("idx_obs_project_phase", "project_id", "phase"),
        Index("idx_obs_project_name", "project_id", "name"),
        Index("idx_obs_created", "created_at"),
    )
