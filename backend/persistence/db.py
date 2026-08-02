"""异步 engine/session 工厂 + 建表。"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base


def get_session_factory(url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(url, future=True)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
