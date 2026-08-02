"""SQLAlchemy 模型：游戏运行、阶段状态、待审批、待回答问答。"""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GameRun(Base):
    __tablename__ = "game_run"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="S0_init")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    stages: Mapped[list["StageState"]] = relationship(back_populates="run", cascade="all,delete-orphan")


class StageState(Base):
    __tablename__ = "stage_state"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("game_run.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run: Mapped["GameRun"] = relationship(back_populates="stages")


class PendingApproval(Base):
    __tablename__ = "pending_approval"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("game_run.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|approved|rejected
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PendingQuestion(Base):
    __tablename__ = "pending_question"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("game_run.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|answered
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
