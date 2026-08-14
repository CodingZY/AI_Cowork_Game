from __future__ import annotations

from arq.connections import RedisSettings

from app.config.settings import get_settings
from app.queue.tasks import run_brainstorm


class WorkerSettings:
    """Arq worker 配置（spec §5.5）。

    functions: 注册 run_brainstorm 供 worker 消费。
    redis_settings: 从 settings.redis_url 构造（Arq 连接池用）。
    """

    functions = [run_brainstorm]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
