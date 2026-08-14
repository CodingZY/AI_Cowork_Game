from __future__ import annotations
import json
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeRedis:
    """内存模拟 redis.asyncio 的 XADD/XREAD，给 EventBroker/SSE 单测用。"""
    def __init__(self):
        self.streams: dict[str, list] = {}

    async def xadd(self, name, fields, **kw):
        self.streams.setdefault(name, []).append(fields)
        return b"0-0"

    async def xread(self, streams, block=None, count=None):
        out = []
        for name, _ids in streams.items():
            entries = self.streams.get(name, [])
            out.append((name, [(b"0-0", e) for e in entries]))
            self.streams[name] = []
        return out


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def fixture_lines():
    def _load(name):
        return [
            json.loads(l)
            for l in (FIXTURES / name).read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    return _load
