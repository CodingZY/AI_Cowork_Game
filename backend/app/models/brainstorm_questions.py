from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class BrainstormQuestion(Base):
    """brainstorm_questions 表：每轮澄清问题 + 用户答案（spec §5.5）。"""

    __tablename__ = "brainstorm_questions"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    questions: Mapped[list] = mapped_column(JSON, nullable=False)  # [{id,question,options}]
    answers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{question_id,answer}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
