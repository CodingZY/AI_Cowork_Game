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
    """Lazy 单例 async engine，读 settings.db_url（真 MySQL，e2e 用）。"""
    return create_async_engine(get_settings().db_url, echo=False, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Lazy 单例 async sessionmaker。"""
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
