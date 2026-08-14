from __future__ import annotations

import json
from typing import Any, AsyncIterator

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config.settings import Settings, get_settings
from app.persistence.db import get_sessionmaker
from app.persistence.repo import EventRepo

router = APIRouter(prefix="/api")


async def event_stream(
    pid: int, after: int, sm: Any, settings: Settings
) -> AsyncIterator[str]:
    """SSE 事件流生成器（spec §101）。

    先从 MySQL events 表补历史（id > after，升序回放），再接 Redis Stream
    XREAD BLOCK 实时推送。生成器无限循环（生产用）；客户端断开或被取消时
    finally 关闭 redis 连接，干净退出。
    """
    r = aioredis.from_url(settings.redis_url)
    try:
        # 1. 补历史：从 events 表回放 after 之后的事件
        async with sm() as s:
            rows = await EventRepo(s).history(pid, after)
        for row in rows:
            payload = {
                "event_id": row.event_id,
                "type": row.event_type,
                "data": row.payload,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # 2. 实时：XREAD BLOCK 30000；读到条目则推送，空/异常则 keepalive
        last = "$"
        while True:
            try:
                resp = await r.xread(
                    {f"stream:project:{pid}": last}, block=30000, count=100
                )
            except Exception:
                yield ": keepalive\n\n"
                continue
            if not resp:
                yield ": keepalive\n\n"
                continue
            for _stream, entries in resp:
                for _id, fields in entries:
                    last = _id.decode() if isinstance(_id, bytes) else _id
                    data = fields.get("data", fields.get(b"data", b""))
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", "replace")
                    yield f"data: {data}\n\n"
    finally:
        await r.close()


@router.get("/projects/{pid}/stream")
async def stream(pid: int, after: int = 0):
    """SSE 端点：text/event-stream，先补历史再实时推送。"""
    settings = get_settings()
    sm = get_sessionmaker()
    return StreamingResponse(
        event_stream(pid, after, sm, settings), media_type="text/event-stream"
    )
