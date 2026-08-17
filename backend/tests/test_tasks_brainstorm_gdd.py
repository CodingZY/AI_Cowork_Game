from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo
from app.queue.tasks import run_brainstorm
from app.workflow.states import ProjectStatus

# FakeGitService 是 Phase 2 在 conftest 提的共享 fake（test_tasks_worker 也是从
# conftest re-import 的）；按仓库既有约定（test_tasks_brainstorm_git.py）从
# tests.conftest 直接取，其余 fakers/helpers 从 tests.test_tasks_worker 取。
from tests.conftest import FakeGitService
from tests.test_tasks_worker import (
    FakeAioredis, FakeRuntime, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


async def test_run_brainstorm_two_spawns_sets_gdd_review(db_sm, fake_aioredis, monkeypatch):
    """02+03 两次 spawn，末尾置 GDD_REVIEW。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="gdd")

    # 两次 spawn：FakeRuntime 每次 start yield 事件
    spawn_count = [0]
    real_start = FakeRuntime.start

    class TwoSpawnRuntime:
        def __init__(self):
            self.cwd = None
        async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
            spawn_count[0] += 1
            self.cwd = cwd
            yield _evt(pid, "agent.session.started", {"session_id": f"s{spawn_count[0]}", "model": "kimi-k3"})
            yield _evt(pid, "agent.session.completed",
                       {"session_id": f"s{spawn_count[0]}", "result": "ok", "stop_reason": "end_turn"})

    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: TwoSpawnRuntime())

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="牧场经营游戏")

    assert spawn_count[0] == 2  # 两次 spawn
    # 末尾 GDD_REVIEW
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value
    # 两次 agent.session.started/completed 事件落库
    async with db_sm() as s:
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
    assert types.count("agent.session.started") == 2
    assert types.count("agent.session.completed") == 2


async def test_run_brainstorm_refused_sets_failed(db_sm, fake_aioredis, monkeypatch):
    """02 或 03 refusal → FAILED（不进 GDD_REVIEW）。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="ref")

    class RefusedRuntime:
        async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
            yield _evt(pid, "agent.session.started", {"session_id": "s1"})
            yield _evt(pid, "agent.refused", {"reason": "content_review"})

    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: RefusedRuntime())

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="敏感")
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.FAILED.value
