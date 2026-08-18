from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from temporal.client import get_client
from temporal.workflows import GameDesignWorkflow
from temporal.activities import (
    analyze_idea,
    synthesize_requirements,
    generate_gdd,
    check_gdd,
    generate_clarification,
)
from app.config.settings import get_settings


async def run_worker():
    """起 Temporal Worker：注册 GameDesignWorkflow + activities。"""
    s = get_settings()
    client = await get_client()
    worker = Worker(
        client,
        task_queue=s.temporal_task_queue,
        workflows=[GameDesignWorkflow],
        activities=[
            analyze_idea,
            synthesize_requirements,
            generate_gdd,
            check_gdd,
            generate_clarification,
        ],
    )
    print(f"Temporal Worker started on queue={s.temporal_task_queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
