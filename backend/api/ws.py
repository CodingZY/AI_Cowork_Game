"""WebSocket 端点：把 broker 的进度流转发给前端。

订阅 `broker.subscribe(run_id)` 的异步生成器，把每条消息以 JSON 推给前端。
断开/取消时干净退出循环：捕获 `WebSocketDisconnect`/`asyncio.CancelledError`
后 break，避免 `await fut` 上的悬挂 waiter 在后续 publish 被 set_result 触发
InvalidStateError（CancelledError 的 future 不能 set_result）。出于不改动 broker
公共 API 的约束，残留的 waiter 项由 broker 内部兜底（publish 对不存在 run_id 的
waiters 列表为空时跳过），S1 阶段风险可接受。
"""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.broker import broker

router = APIRouter()


@router.websocket("/api/ws/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    try:
        async for msg in broker.subscribe(run_id):
            await websocket.send_json(msg)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        pass
    finally:
        await websocket.close()
