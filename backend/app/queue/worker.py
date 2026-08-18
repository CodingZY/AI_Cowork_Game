from __future__ import annotations

from arq.connections import RedisSettings

from app.config.settings import get_settings
from app.queue.tasks import run_finalize


class WorkerSettings:
    """Arq worker 配置（Phase3a 精简）。

    Phase3a Temporal 重构后，brainstorm/gdd_check 编排迁至 Temporal
    GameDesignWorkflow；Arq 仅保留 run_finalize（GitService 落 git）。
    redis_settings: 从 settings.redis_url 构造（Arq 连接池用）。
    queue_name: 必须与 jobs.enqueue_finalize 的 _queue_name 一致
        （= settings.arq_queue，默认 "agent"）。
    """

    functions = [run_finalize]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    queue_name = get_settings().arq_queue
    job_timeout = 900
