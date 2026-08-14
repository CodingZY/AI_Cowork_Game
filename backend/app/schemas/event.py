from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_event_id() -> str:
    return "evt_" + uuid4().hex


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CoworkEvent(BaseModel):
    """归一化事件（spec §7）。

    由 ClaudeEventParser 从 claude `stream-json` NDJSON 归一化产出；
    纯数据容器，不含 IO。
    """

    event_id: str = Field(default_factory=_new_event_id)
    project_id: int
    workflow_run_id: Optional[int] = None
    task_id: Optional[int] = None
    type: str
    timestamp: str = Field(default_factory=_now_iso)
    data: dict
    # 持久化用附加字段（不序列化给前端，repo 用）：
    aggregate_type: str = "agent_session"
    aggregate_id: int = 0
    raw_json: Optional[str] = None
