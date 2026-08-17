from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.agent_session import AgentSession
from app.models.event import Event
from app.persistence.repo import AgentSessionRepo, ProjectRepo
from app.queue.tasks import run_brainstorm
from app.schemas.event import CoworkEvent, _new_event_id
from app.workflow.engine import WorkflowBlocked
from app.workflow.states import ProjectStatus

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
    """Fake ClaudeRuntime：记录 start/resume 调用，每次 start yield 一组预设事件。

    Phase 3a run_brainstorm 两次 spawn（02 BRAINSTORM + 03 GDD_GEN），每次都调
    runtime.start(..., plugin_dir=...)，故 start 需接 plugin_dir 且支持多次调用。
    spawn_count/agent_types/called 供回归断言"两次 start、不调 resume"。
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
            # 两次 spawn 复用同一 CoworkEvent 会触发 IntegrityError 被兜底成 runtime_err
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
    """成功路径：CREATED→BRAINSTORMING→两次 spawn(02+03)→GDD_REVIEW。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

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

    # Phase 3a return dict：succeeded/refused/error（无 session_id/reason）
    assert result["succeeded"] is True
    assert result["refused"] is False
    assert result["error"] is None
    # 两次 start（02 BRAINSTORM + 03 GDD_GEN），不调 resume
    assert fake_rt.spawn_count == 2
    assert fake_rt.agent_types == ["BRAINSTORM", "GDD_GEN"]

    async with db_sm() as s:
        # 两个 agent_session（BRAINSTORM + GDD_GEN），都 COMPLETED
        ags_rows = (
            await s.execute(
                select(AgentSession)
                .where(AgentSession.project_id == pid)
                .order_by(AgentSession.id)
            )
        ).scalars().all()
        assert len(ags_rows) == 2
        assert ags_rows[0].agent_type == "BRAINSTORM"
        assert ags_rows[1].agent_type == "GDD_GEN"
        for a in ags_rows:
            assert a.status == "COMPLETED"

        # project: 末尾置 GDD_REVIEW（非 BRAINSTORMING）
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value

        # events: 7 rows（两次 spawn 各 started/delta/completed = 6 agent + 1 git）
        rows = (
            await s.execute(select(Event).where(Event.project_id == pid))
        ).scalars().all()
        assert len(rows) == 7
        # agent 事件 aggregate_id 关联到各自 agent_session；git 事件 aggregate_type="git"
        agent_rows = [r for r in rows if r.aggregate_type != "git"]
        assert len(agent_rows) == 6
        as1, as2 = ags_rows[0].id, ags_rows[1].id
        assert sum(1 for r in agent_rows if r.aggregate_id == as1) == 3
        assert sum(1 for r in agent_rows if r.aggregate_id == as2) == 3

        # broadcast: FakeRedis stream 有 7 条
        stream = fake_aioredis._redis.streams.get(f"stream:project:{pid}")
        assert stream is not None
        assert len(stream) == 7


async def test_run_brainstorm_refusal(db_sm, fake_aioredis, monkeypatch):
    """拒绝路径：session.started + agent.refused → FAILED + project FAILED。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="refused")

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "s1"}),
        _evt(pid, "agent.refused", {"reason": "content_policy"}),
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="敏感内容")

    assert result["refused"] is True
    assert result["succeeded"] is False
    assert result["error"] is None
    # spawn #1 refused → 不跑 spawn #2
    assert fake_rt.spawn_count == 1

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
    """Phase 3a：run_brainstorm 不再 resume 旧 session（spec D3），02/03 都 start 新 session。

    预置 COMPLETED session（Phase 2 会 resume 的场景）→ 验两次 start、不调 resume。
    """
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="resumeproj")

    # 预置一个 COMPLETED 的 agent_session（Phase 2 会 resume，阶段1 不再 resume）
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

    # 两次 start（BRAINSTORM + GDD_GEN），不调 resume（spec D3）
    assert fake_rt.spawn_count == 2
    assert fake_rt.called == ["start", "start"]
    assert fake_rt.agent_types == ["BRAINSTORM", "GDD_GEN"]
    assert result["succeeded"] is True


async def test_run_brainstorm_blocked_status(db_sm, monkeypatch):
    """非法状态：project=FAILED → WorkflowBlocked 抛出。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="blocked", status="FAILED")

    with pytest.raises(WorkflowBlocked):
        await run_brainstorm(ctx={}, project_id=pid, prompt="test")


async def test_run_brainstorm_project_not_found(db_sm, fake_aioredis, monkeypatch):
    """project 不存在 → 返回 failed dict。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    result = await run_brainstorm(ctx={}, project_id=999999, prompt="test")

    assert result["failed"] is True
    assert result["reason"] == "project_not_found"


async def test_run_brainstorm_runtime_error(db_sm, fake_aioredis, monkeypatch):
    """无 completed（子进程崩溃/异常终止）→ spawn_ok=False → succeeded_all=False → project FAILED。

    Phase 3a：FakeRuntime.start 已接 plugin_dir，不再 TypeError 兜底；此处真正模拟
    "只 yield started 无 completed" → _spawn_once 返回 False → 不跑 spawn #2。
    """
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="rterr")

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "s1"}),
        _evt(pid, "agent.message.delta", {"text": "partial"}),
        # 没有 session.completed 也没有 refused（如子进程崩溃）
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="test")

    # 无 completed 也无 refused → spawn_ok=False → succeeded_all=False → FAILED
    assert result["succeeded"] is False
    assert result["refused"] is False
    assert result["error"] is None
    # spawn #1 无 completed → ok1=False → 不跑 spawn #2
    assert fake_rt.spawn_count == 1

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
