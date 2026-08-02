"""测试夹具：in-memory SQLite 异步会话，供所有后端单测使用。

autouse _reset_shared_db：api.deps 的模块级 _engine（StaticPool in-memory sqlite）
被 ASGITransport 集成测试共享，跨用例不重置会让相同 slug 的二次 INSERT 触发
UNIQUE 约束（game_run.slug）。每个用例前清空共享库表，保证隔离。
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from persistence.models import Base


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _reset_shared_db():
    """清空 api.deps 共享 in-memory 库的表，避免跨用例 slug 唯一约束冲突。

    先 create_all（幂等）确保表存在（部分单测不经过 HTTP 中间件建表），
    再 DELETE 各表数据，保证 ASGITransport 集成测试跨用例隔离。
    """
    from api.deps import _engine
    from sqlalchemy import text
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table in Base.metadata.sorted_tables:
            await conn.execute(text(f'DELETE FROM "{table.name}"'))
