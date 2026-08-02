"""WS 端点：订阅进度流。

WS 在 httpx 中是同步 API，且 ASGITransport 为异步传输无法驱动同步 WS。Starlette 的
TestClient 基于 httpx 并内置 ASGI WS 支持，是测试 WS over ASGI 的标准路径。本用例
不实际运行 agent（publish 手动触发），故同步 TestClient 不存在事件循环冲突问题。
"""
import asyncio
import pytest
from starlette.testclient import TestClient
from api.broker import broker


@pytest.mark.asyncio
async def test_ws_receives_published_message(monkeypatch, tmp_path):
    async def fake_run_design_agent(game_root, **kw):
        await asyncio.sleep(0)  # 不做实事，仅占位
        return game_root / "docs" / "game-design.md"
    import api.runtime as runtime_mod
    monkeypatch.setattr(runtime_mod, "run_design_agent", fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    with TestClient(app) as c:
        with c.websocket_connect("/api/ws/test-run") as ws:
            broker.publish("test-run", {"type": "progress", "event": "pre"})
            msg = ws.receive_json()
            assert msg["type"] == "progress"
