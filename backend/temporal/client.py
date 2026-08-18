from __future__ import annotations

from typing import Optional

from temporalio.client import Client

from app.config.settings import get_settings

_client: Optional[Client] = None


async def get_client() -> Client:
    """单例 Temporal Client（连 settings.temporal_host:port）。"""
    global _client
    if _client is None:
        s = get_settings()
        _client = await Client.connect(
            f"{s.temporal_host}:{s.temporal_port}", namespace=s.temporal_namespace
        )
    return _client


async def start_design_workflow(project_id: int, idea: str) -> str:
    """起 GameDesignWorkflow，返 workflow_id。"""
    from .workflows import GameDesignWorkflow  # 延迟 import（Task 2 才有）

    s = get_settings()
    client = await get_client()
    handle = await client.start_workflow(
        GameDesignWorkflow.run,
        idea,
        id=f"game-{project_id}",
        task_queue=s.temporal_task_queue,
    )
    return handle.id


async def send_signal(project_id: int, signal_name: str, signal_arg) -> None:
    """发 Signal 到 Workflow。"""
    from .workflows import GameDesignWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(f"game-{project_id}")
    await handle.signal(getattr(GameDesignWorkflow, signal_name), signal_arg)


async def query_state(project_id: int) -> dict:
    """Query get_design_state。"""
    from .workflows import GameDesignWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(f"game-{project_id}")
    return await handle.query(GameDesignWorkflow.get_design_state)
