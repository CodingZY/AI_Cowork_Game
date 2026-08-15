from __future__ import annotations

from arq.connections import RedisSettings

from app.config.settings import get_settings
from app.queue.tasks import run_brainstorm, run_finalize


class WorkerSettings:
    """Arq worker 配置（spec §5.5）。

    functions: 注册 run_brainstorm / run_finalize 供 worker 消费。
    redis_settings: 从 settings.redis_url 构造（Arq 连接池用）。
    queue_name: 必须与 jobs.enqueue_brainstorm 的 _queue_name 一致
        （= settings.arq_queue，默认 "agent"）。arq 0.28 的队列 key 是裸
        queue_name（zset），worker 不设 queue_name 会默认 "arq"，与
        enqueue 的 "agent" 不匹配 → job 永不消费。
    """

    functions = [run_brainstorm, run_finalize]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    queue_name = get_settings().arq_queue
