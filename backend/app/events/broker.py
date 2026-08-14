from __future__ import annotations

import json
from typing import Any, Callable

from app.persistence.repo import EventRepo
from app.schemas.event import CoworkEvent


class EventBroker:
    """事件双写：先落库（EventRepo.insert + commit），再广播（Redis Stream XADD）。

    session_factory 是一个 callable，`session_factory()` 返回一个可 `async with`
    的 AsyncSession（sessionmaker 或返回 session 的 lambda 均可，只要 callable 且
    结果能 async with）。Task 10 会传 `EventBroker(session_factory=get_sessionmaker(), redis=r)`。

    publish 语义：先落库成功后再广播——落库失败则不广播（异常上抛）；
    广播失败时事件已落库，可由 history 兜底恢复（Task 10 决定是否补偿）。
    """

    def __init__(self, session_factory: Callable[[], Any], redis):
        self.session_factory = session_factory
        self.redis = redis

    async def publish(self, evt: CoworkEvent) -> None:
        # 先落库
        async with self.session_factory() as session:
            await EventRepo(session).insert(evt)
            await session.commit()
        # 再广播
        await self.redis.xadd(
            f"stream:project:{evt.project_id}",
            {"data": json.dumps(evt.model_dump(mode="json"), ensure_ascii=False)},
        )

    async def history(self, project_id: int, after_id: int = 0) -> list:
        async with self.session_factory() as session:
            return await EventRepo(session).history(project_id, after_id)
