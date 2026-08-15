from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Lazy 单例 async engine，读 settings.db_url（真 MySQL，e2e 用）。

    不开 pool_pre_ping：asyncmy 的异步 ping 适配签名与 SQLAlchemy 默认
    do_ping（pymysql 同步签名）不兼容，会抛
    ``ping() missing 1 required positional argument: 'reconnect'``。
    本地 MySQL 稳定，依赖默认 pool 行为即可；若将来长连接需防 stale，
    用 pool_recycle 而非 pre_ping。
    """
    return create_async_engine(get_settings().db_url, echo=False)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Lazy 单例 async sessionmaker。"""
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
