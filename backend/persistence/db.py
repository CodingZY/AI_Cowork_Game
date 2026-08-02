"""异步 engine/session 工厂 + 建表。"""
from .models import Base


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
