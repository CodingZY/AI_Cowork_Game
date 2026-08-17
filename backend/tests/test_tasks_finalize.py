from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo
from app.queue.tasks import run_finalize
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


class FakeGitFinalize:
    """记录 finalize 各步骤调用序列，模拟 sha。"""
    def __init__(self):
        self.calls = []
        self.merge_sha = "mergesha1"
        self.push_sha = "pushsha1"
        self.main_sha = "mainsha1"
    async def commit(self, worktree_path, message):
        self.calls.append(("commit", str(worktree_path), message)); return "commitsha1"
    async def merge_to_main(self, branch):
        self.calls.append(("merge", branch)); return self.merge_sha
    async def worktree_remove(self, project_key, branch):
        self.calls.append(("remove", project_key, branch))
    async def push(self, remote="origin", ref="main"):
        self.calls.append(("push", remote, ref)); return self.push_sha
    async def tag(self, tag_name):
        self.calls.append(("tag", tag_name)); return tag_name
    async def current_sha(self, ref="main"):
        self.calls.append(("current_sha", ref)); return self.main_sha
    async def worktree_path(self, project_key):
        from pathlib import Path
        return Path(f"/fake/wt/{project_key}-brainstorm")


async def test_run_finalize_success(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitFinalize()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)

    pid = await _create_project(db_sm, key="fin", status="GDD_APPROVED")
    # 预置 project_repositories.current_branch
    async with db_sm() as s:
        await ProjectRepositoryRepo(s).create(
            project_id=pid, owner="o", repository="r", sub_path="games/fin/")
        await ProjectRepositoryRepo(s).set_branch(pid, "agent/fin-brainstorm")
        await s.commit()

    result = await run_finalize(ctx={}, project_id=pid)

    assert result["succeeded"] is True
    # 步骤序列正确
    seq = [c[0] for c in fake_git.calls]
    assert seq == ["commit", "merge", "remove", "push", "tag", "current_sha"]
    # tag 名
    assert fake_git.calls[4] == ("tag", "brainstorm-fin-v0")
    # project BRAINSTORMED + repo last_sha + branch 清空
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.BRAINSTORMED.value
        prow = await ProjectRepositoryRepo(s).get_by_project(pid)
        assert prow.last_commit_sha == "mainsha1"
        assert prow.current_branch is None
    # git.* 事件落库
    async with db_sm() as s:
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
    for t in ("git.committed", "git.merged", "git.worktree.cleaned",
              "git.pushed", "git.tagged"):
        assert t in types


async def test_run_finalize_blocked_from_created(db_sm, monkeypatch):
    from app.workflow.engine import WorkflowBlocked
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    pid = await _create_project(db_sm, key="blk", status="CREATED")
    with pytest.raises(WorkflowBlocked):
        await run_finalize(ctx={}, project_id=pid)


async def test_run_finalize_git_failure(db_sm, fake_aioredis, monkeypatch):
    """git 步骤失败 → git.failed 事件 + project FAILED（不卡死）。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    class FailingGit(FakeGitFinalize):
        async def commit(self, worktree_path, message):
            raise RuntimeError("commit boom")

    monkeypatch.setattr("app.queue.tasks.GitService", lambda: FailingGit())
    pid = await _create_project(db_sm, key="failfin", status="GDD_APPROVED")
    async with db_sm() as s:
        await ProjectRepositoryRepo(s).create(
            project_id=pid, owner="o", repository="r", sub_path="games/failfin/")
        await ProjectRepositoryRepo(s).set_branch(pid, "agent/failfin-brainstorm")
        await s.commit()

    result = await run_finalize(ctx={}, project_id=pid)
    assert result["succeeded"] is False
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.FAILED.value
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "git.failed" in types
