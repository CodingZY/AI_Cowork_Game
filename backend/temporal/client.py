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


# === Phase 2：ArtPipelineWorkflow ===


async def start_art_workflow(project_id: int) -> str:
    """起 ArtPipelineWorkflow，返 workflow_id（art-{project_id}）。

    args 取 settings.art_assets_parallel（并行生图上限）。
    """
    from .workflows import ArtPipelineWorkflow

    s = get_settings()
    client = await get_client()
    handle = await client.start_workflow(
        ArtPipelineWorkflow.run,
        s.art_assets_parallel,
        id=f"art-{project_id}",
        task_queue=s.temporal_task_queue,
    )
    return handle.id


async def send_art_signal(project_id: int, signal_name: str, signal_arg=None) -> None:
    """发 Signal 到 ArtPipelineWorkflow（approve_report / retry_asset）。"""
    from .workflows import ArtPipelineWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(f"art-{project_id}")
    await handle.signal(getattr(ArtPipelineWorkflow, signal_name), signal_arg)


async def query_art_state(project_id: int) -> dict:
    """Query get_art_state。"""
    from .workflows import ArtPipelineWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(f"art-{project_id}")
    return await handle.query(ArtPipelineWorkflow.get_art_state)


# === Phase 3：GameDevelopmentWorkflow ===


async def start_dev_workflow(project_id: int) -> str:
    """起 GameDevelopmentWorkflow，返 workflow_id（dev-{project_id}）。"""
    from .workflows import GameDevelopmentWorkflow

    client = await get_client()
    handle = await client.start_workflow(
        GameDevelopmentWorkflow.run,
        id=f"dev-{project_id}",
        task_queue=get_settings().temporal_task_queue,
    )
    return handle.id


async def send_dev_signal(project_id: int, signal_name: str, signal_arg=None) -> None:
    """发 Signal 到 GameDevelopmentWorkflow（submit_feedback）。"""
    from .workflows import GameDevelopmentWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(f"dev-{project_id}")
    await handle.signal(getattr(GameDevelopmentWorkflow, signal_name), signal_arg)


async def query_dev_state(project_id: int) -> dict:
    """Query get_dev_state。"""
    from .workflows import GameDevelopmentWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(f"dev-{project_id}")
    return await handle.query(GameDevelopmentWorkflow.get_dev_state)
