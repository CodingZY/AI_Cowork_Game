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
