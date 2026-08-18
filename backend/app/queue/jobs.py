from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings

from app.config.settings import get_settings


async def enqueue_finalize(project_id: int) -> str:
    """向 Arq 队列 enqueue run_finalize(project_id)，返回 job_id。

    用 settings.redis_url 构造 RedisSettings，队列名取 settings.arq_queue
    （与旧 enqueue_brainstorm_* 一致）。
    """
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_finalize", project_id, _queue_name=s.arq_queue)
    return job.job_id
