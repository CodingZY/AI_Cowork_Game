from __future__ import annotations

import pytest
from temporalio.client import Client


async def test_get_client_returns_client(monkeypatch):
    """get_client 返回 Temporal Client 单例。"""
    from temporal import client as tclient

    # reset 单例，避免跨测试污染
    tclient._client = None
    captured = {}

    async def fake_connect(target, **kw):
        captured["target"] = target
        return object()  # 假 Client

    monkeypatch.setattr(Client, "connect", fake_connect)
    c = await tclient.get_client()
    assert c is not None
    assert "localhost" in captured["target"] or "7233" in str(captured["target"])


async def test_get_client_is_singleton(monkeypatch):
    """第二次调用 get_client 不再 connect，复用单例。"""
    from temporal import client as tclient

    tclient._client = None
    call_count = {"n": 0}

    async def fake_connect(target, **kw):
        call_count["n"] += 1
        return object()

    monkeypatch.setattr(Client, "connect", fake_connect)
    c1 = await tclient.get_client()
    c2 = await tclient.get_client()
    assert c1 is c2
    assert call_count["n"] == 1
