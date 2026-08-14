from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.agent_session import AgentSession
from app.models.event import Event
from app.persistence.repo import AgentSessionRepo, ProjectRepo
from app.queue.tasks import run_brainstorm
from app.schemas.event import CoworkEvent
from app.workflow.engine import WorkflowBlocked


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeLock:
    async def acquire(self):
        return True

    async def release(self):
        pass


class FakeRedisWithLock:
    """FakeRedis + lock() support for run_brainstorm's project lock."""

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
    """Fake ClaudeRuntime: records start/resume call, yields preset events."""

    def __init__(self, evts):
        self.evts = evts
        self.called = None
        self.resume_sid = None

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None):
        self.called = "start"
        for e in self.evts:
            yield e

    async def resume(self, session_id, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None):
        self.called = "resume"
        self.resume_sid = session_id
        for e in self.evts:
            yield e


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


import pytest_asyncio
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def db_sm():
    """Sessionmaker backed by sqlite in-memory with StaticPool so all
    sessions (run_brainstorm's internal sessions + test's assertion sessions)
    share the same database across connections.
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
# Tests
# ---------------------------------------------------------------------------


async def test_run_brainstorm_success(db_sm, fake_aioredis, monkeypatch):
    """成功路径：CREATED→BRAINSTORMING→COMPLETED，project 保持 BRAINSTORMING。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    pid = await _create_project(db_sm, key="success")

    evts = [
        _evt(pid, "agent.session.started",
             {"session_id": "s1", "model": "kimi-k3", "agent_type": "brainstorm"}),
        _evt(pid, "agent.message.delta", {"text": "hi"}),
        _evt(pid, "agent.session.completed",
             {"session_id": "s1", "result": "ok", "stop_reason": "end_turn",
              "cost": 0.0, "duration": 1}),
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="种田游戏")

    assert result["succeeded"] is True
    assert result["refused"] is False
    assert result["session_id"] == "s1"
    assert result["reason"] is None

    async with db_sm() as s:
        # agent_session: COMPLETED + bound claude_session_id
        ags = (
            await s.execute(
                select(AgentSession).where(AgentSession.project_id == pid)
            )
        ).scalars().first()
        assert ags is not None
        assert ags.status == "COMPLETED"
        assert ags.claude_session_id == "s1"
        assert ags.agent_type == "BRAINSTORM"

        # project: kept BRAINSTORMING (可再 resume)
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == "BRAINSTORMING"

        # events: 3 rows, aggregate_id 关联到 agent_session
        rows = (
            await s.execute(select(Event).where(Event.project_id == pid))
        ).scalars().all()
        assert len(rows) == 3
        for r in rows:
            assert r.aggregate_id == ags.id

        # broadcast: FakeRedis stream 有 3 条
        stream = fake_aioredis._redis.streams.get(f"stream:project:{pid}")
        assert stream is not None
        assert len(stream) == 3


async def test_run_brainstorm_refusal(db_sm, fake_aioredis, monkeypatch):
    """拒绝路径：session.started + agent.refused → FAILED + project FAILED。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    pid = await _create_project(db_sm, key="refused")

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "s1"}),
        _evt(pid, "agent.refused", {"reason": "content_policy"}),
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="敏感内容")

    assert result["refused"] is True
    assert result["reason"] == "content_review"
    assert result["succeeded"] is False

    async with db_sm() as s:
        ags = (
            await s.execute(
                select(AgentSession).where(AgentSession.project_id == pid)
            )
        ).scalars().first()
        assert ags.status == "FAILED"

        proj = await ProjectRepo(s).get(pid)
        assert proj.status == "FAILED"


async def test_run_brainstorm_resume(db_sm, fake_aioredis, monkeypatch):
    """resume 路径：有 COMPLETED session → runtime.resume 被调用，session_id=prev-sid。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    pid = await _create_project(db_sm, key="resumeproj")

    # 预置一个 COMPLETED 的 agent_session（有 claude_session_id）
    async with db_sm() as s:
        prev = await AgentSessionRepo(s).create(
            pid, "BRAINSTORM", "Games/resumeproj"
        )
        await AgentSessionRepo(s).bind_claude_session(prev.id, "prev-sid")
        await AgentSessionRepo(s).finish(prev.id, "COMPLETED")
        await s.commit()

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "new-sid"}),
        _evt(pid, "agent.session.completed",
             {"session_id": "new-sid", "result": "ok", "stop_reason": "end_turn"}),
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="继续设计")

    assert fake_rt.called == "resume"
    assert fake_rt.resume_sid == "prev-sid"
    assert result["succeeded"] is True


async def test_run_brainstorm_blocked_status(db_sm, monkeypatch):
    """非法状态：project=FAILED → WorkflowBlocked 抛出。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)

    pid = await _create_project(db_sm, key="blocked", status="FAILED")

    with pytest.raises(WorkflowBlocked):
        await run_brainstorm(ctx={}, project_id=pid, prompt="test")


async def test_run_brainstorm_project_not_found(db_sm, fake_aioredis, monkeypatch):
    """project 不存在 → 返回 failed dict。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    result = await run_brainstorm(ctx={}, project_id=999999, prompt="test")

    assert result["failed"] is True
    assert result["reason"] == "project_not_found"


async def test_run_brainstorm_runtime_error(db_sm, fake_aioredis, monkeypatch):
    """runtime 异常路径：只有 session.started 无 completed/refused → FAILED + runtime_error。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    pid = await _create_project(db_sm, key="rterr")

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "s1"}),
        _evt(pid, "agent.message.delta", {"text": "partial"}),
        # 没有 session.completed 也没有 refused（如子进程崩溃）
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="test")

    assert result["succeeded"] is False
    assert result["refused"] is False
    assert result["reason"] == "runtime_error"

    async with db_sm() as s:
        ags = (
            await s.execute(
                select(AgentSession).where(AgentSession.project_id == pid)
            )
        ).scalars().first()
        assert ags.status == "FAILED"

        proj = await ProjectRepo(s).get(pid)
        assert proj.status == "FAILED"


# ---------------------------------------------------------------------------
# WorkerSettings
# ---------------------------------------------------------------------------


def test_worker_settings_has_run_brainstorm():
    from app.queue.worker import WorkerSettings

    assert run_brainstorm in WorkerSettings.functions
    assert WorkerSettings.redis_settings is not None
