from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectRead(BaseModel):
    id: int
    project_key: str
    name: str
    status: str
    workspace_root: str


class BrainstormRequest(BaseModel):
    idea: str


class AnswerBody(BaseModel):
    """单题答题载荷（Temporal 版，逐题 Signal）。"""

    question_id: str
    answer: str


class SkipBody(BaseModel):
    """跳过单题载荷（skip_question Signal）。"""

    question_id: str


class GddBody(BaseModel):
    gdd_md: str
