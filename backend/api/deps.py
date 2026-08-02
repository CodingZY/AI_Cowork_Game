"""依赖注入：DB 会话工厂、Games 根目录、配置。"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
DESIGN_MODEL = os.getenv("DESIGN_MODEL", "claude-sonnet-4-6")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN")

_games_root: Path = Path(os.getenv("GAMES_ROOT", "../Games")).resolve()


def set_games_root(p: Path) -> None:
    global _games_root
    _games_root = p.resolve()


def games_root() -> Path:
    return _games_root


# in-memory sqlite 需 StaticPool 让多连接共享同一库（测试稳定）。
# AUTOCOMMIT：后台 create_task 与请求轮询并发时，单连接 StaticPool 会让
# 轮询的 SELECT 开启的长事务阻塞后台 UPDATE 的可见性；AUTOCOMMIT 让每条
# 语句独立提交，避免跨会话事务快照互相阻塞。
if DATABASE_URL.startswith("sqlite"):
    _engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
        isolation_level="AUTOCOMMIT",
    )
else:
    _engine = create_async_engine(DATABASE_URL, future=True)

_session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with _session_factory() as session:
        yield session
