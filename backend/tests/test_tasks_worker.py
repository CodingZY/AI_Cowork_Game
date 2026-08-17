from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.persistence.repo import ProjectRepo
from app.queue.tasks import run_brainstorm_questions
from app.schemas.event import CoworkEvent, _new_event_id

from tests.conftest import FakeGitService


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeLock:
    async def acquire(self):
        return True

    async def release(self):
        pass


class FakeRedisWithLock:
    """FakeRedis + lock() support for the brainstorm tasks' project lock."""

    def __init__(self):
        self.streams: dict[str, list] = {}

    async def xadd(self, name, fields, **kw):
        self.streams.setdefault(name, []).append(fields)
        return b"0-0"

    async def xread(self, streams, block=None, count=None):
        return []

    def lock(self, name, timeout=None):
        return FakeLock()

    async def close(self):
        pass


class FakeAioredis:
    """Drop-in for the ``redis.asyncio`` module reference in tasks.py.

    ``from_url`` is sync (matches real redis.asyncio), returns the shared
    FakeRedisWithLock so both the lock and EventBroker's xadd hit the same
    instance.
    """

    def __init__(self, redis_instance):
        self._redis = redis_instance

    def from_url(self, url):
        return self._redis


class FakeRuntime:
    """Fake ClaudeRuntime：记录 start/resume 调用，每次 start yield 一组预设事件。

    start 接 plugin_dir 且支持多次调用；每次 yield 的 CoworkEvent 用新 event_id
    （events.event_id 唯一约束，复用同一事件会 IntegrityError）。spawn_count/
    agent_types/called 供回归断言（如 job1 单次 start、不调 resume）。
    """

    def __init__(self, evts):
        self.evts = evts
        self.called = []  # ["start", "start", ...] 或含 "resume"
        self.resume_sid = None
        self.cwd = None
        self.spawn_count = 0
        self.agent_types = []

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm",
                    system_prompt=None, plugin_dir=None):
        self.called.append("start")
        self.cwd = cwd
        self.spawn_count += 1
        self.agent_types.append(agent_type)
        for e in self.evts:
            # 每次调用 yield 副本（新 event_id）：events.event_id 唯一约束，
            # 多次 spawn 复用同一 CoworkEvent 会触发 IntegrityError 被兜底成 runtime_err
            yield e.model_copy(update={"event_id": _new_event_id()})

    async def resume(self, session_id, prompt, cwd, project_id, agent_type="brainstorm",
                     system_prompt=None, plugin_dir=None):
        self.called.append("resume")
        self.resume_sid = session_id
        self.cwd = cwd
        self.spawn_count += 1
        self.agent_types.append(agent_type)
        for e in self.evts:
            yield e.model_copy(update={"event_id": _new_event_id()})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


import pytest_asyncio
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def db_sm():
    """Sessionmaker backed by sqlite in-memory with StaticPool so all
    sessions (task internal sessions for run_brainstorm_questions/generate
    + test assertion sessions) share the same database across connections.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield sm
    finally:
        await engine.dispose()


@pytest.fixture
def fake_redis_lock():
    return FakeRedisWithLock()


@pytest.fixture
def fake_aioredis(fake_redis_lock):
    return FakeAioredis(fake_redis_lock)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evt(pid, type, data):
    return CoworkEvent(project_id=pid, type=type, data=data, aggregate_id=0)


async def _create_project(sm, key="demo", status="CREATED"):
    async with sm() as s:
        project = await ProjectRepo(s).create(
            project_key=key,
            name=key.title(),
            status=status,
            workspace_root=f"Games/{key}",
        )
        await s.commit()
        return project.id


# ---------------------------------------------------------------------------
# WorkerSettings
# ---------------------------------------------------------------------------


def test_worker_settings_has_run_brainstorm():
    from app.queue.worker import WorkerSettings

    assert run_brainstorm_questions in WorkerSettings.functions
    assert WorkerSettings.redis_settings is not None
