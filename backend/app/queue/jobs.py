from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings

from app.config.settings import get_settings


async def enqueue_brainstorm(project_id: int, prompt: str) -> str:
    """向 Arq 队列 enqueue run_brainstorm(project_id, prompt)，返回 job_id。

    用 settings.redis_url 构造 RedisSettings，队列名取 settings.arq_queue。
    """
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_brainstorm", project_id, prompt, _queue_name=s.arq_queue)
    return job.job_id


async def enqueue_finalize(project_id: int) -> str:
    """向 Arq 队列 enqueue run_finalize(project_id)，返回 job_id。

    用 settings.redis_url 构造 RedisSettings，队列名取 settings.arq_queue
    （与 enqueue_brainstorm 一致）。
    """
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_finalize", project_id, _queue_name=s.arq_queue)
    return job.job_id


async def enqueue_gdd_check(project_id: int) -> str:
    """向 Arq 队列 enqueue run_gdd_check(project_id)，返回 job_id。"""
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_gdd_check", project_id, _queue_name=s.arq_queue)
    return job.job_id
