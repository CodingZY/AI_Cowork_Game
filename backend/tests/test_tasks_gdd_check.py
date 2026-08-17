from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo
from app.queue.tasks import run_gdd_check
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


def _evt(pid, type, data):
    from app.schemas.event import CoworkEvent
    return CoworkEvent(project_id=pid, type=type, data=data, aggregate_id=0)


async def _fake_worktree_path(self, project_key):
    """async fake git worktree_path（真实 GitService.worktree_path 为 async，实现里 await 它）。"""
    from pathlib import Path
    return Path(f"/fake/wt/{project_key}-brainstorm")


class FakeCheckRuntime:
    """FakeRuntime for 04: yields session.started + session.completed(result=verdict)。"""
    def __init__(self, verdict_result):
        self.verdict = verdict_result
        self.cwd = None

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
        self.cwd = cwd
        yield _evt(project_id, "agent.session.started", {"session_id": "chk1", "model": "kimi-k3"})
        yield _evt(project_id, "agent.session.completed",
                   {"session_id": "chk1", "result": self.verdict, "stop_reason": "end_turn"})


async def _setup_gdd_review_project(db_sm, key):
    pid = await _create_project(db_sm, key=key, status="GDD_REVIEW")
    async with db_sm() as s:
        await ProjectRepositoryRepo(s).create(
            project_id=pid, owner="o", repository="r", sub_path=f"games/{key}/")
        await ProjectRepositoryRepo(s).set_branch(pid, f"agent/{key}-brainstorm")
        await s.commit()
    return pid


async def test_run_gdd_check_pass(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = type("G", (), {"worktree_path": _fake_worktree_path})()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeCheckRuntime("PASS"))

    pid = await _setup_gdd_review_project(db_sm, "pass")

    result = await run_gdd_check(ctx={}, project_id=pid)
    assert result["passed"] is True
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_APPROVED.value
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "gdd.check.passed" in types


async def test_run_gdd_check_fail(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = type("G", (), {"worktree_path": _fake_worktree_path})()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeCheckRuntime("FAIL: GDD missing section NPC, F002 lacks acceptance"))

    pid = await _setup_gdd_review_project(db_sm, "fail")

    result = await run_gdd_check(ctx={}, project_id=pid)
    assert result["passed"] is False
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value  # 回 GDD_REVIEW
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "gdd.check.failed" in types


async def test_run_gdd_check_blocked_from_approved(db_sm, monkeypatch):
    from app.workflow.engine import WorkflowBlocked
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    pid = await _create_project(db_sm, key="blkchk", status="GDD_APPROVED")
    with pytest.raises(WorkflowBlocked):
        await run_gdd_check(ctx={}, project_id=pid)
