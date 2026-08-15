from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepositoryRepo
from app.queue.tasks import run_brainstorm

from tests.test_tasks_worker import FakeRuntime, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock
from tests.conftest import FakeGitService


async def test_run_brainstorm_prepares_worktree(db_sm, fake_aioredis, monkeypatch):
    """run_brainstorm 首次：ensure_clone + ensure_template_pushed + worktree_add +
    copy_template + ClaudeRuntime cwd=worktree/games/{key} + git.worktree.added 事件。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="wtprep")

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "s1", "model": "kimi-k3"}),
        _evt(pid, "agent.session.completed",
             {"session_id": "s1", "result": "ok", "stop_reason": "end_turn"}),
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    await run_brainstorm(ctx={}, project_id=pid, prompt="种田")

    assert fake_git.clone_called
    assert fake_git.worktree_calls == [("wtprep", "agent/wtprep-brainstorm")]
    assert len(fake_git.copy_calls) == 1
    assert "games/wtprep" in str(fake_rt.cwd).replace("\\", "/")

    async with db_sm() as s:
        rows = (await s.execute(select(Event).where(Event.project_id == pid))).scalars().all()
        types = [r.event_type for r in rows]
        assert "git.worktree.added" in types

        prow = await ProjectRepositoryRepo(s).get_by_project(pid)
        assert prow.current_branch == "agent/wtprep-brainstorm"
