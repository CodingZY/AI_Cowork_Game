from __future__ import annotations
import json
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base

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


@pytest_asyncio.fixture
async def async_db_session():
    """R5: 单元/集成测试用 sqlite in-memory，不用 settings.db_url
    （真 MySQL 仅 Task 13 e2e）。每测试建表 + 结束回滚 + dispose。
    sqlite 的 BigInteger 退化 INTEGER、JSON 原生存 TEXT，方言兼容。
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()
