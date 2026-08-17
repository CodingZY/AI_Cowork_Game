from __future__ import annotations

from sqlalchemy import select

from app.models.agent_session import AgentSession
from app.models.event import Event
from app.persistence.repo import ProjectRepo, QuestionRepo
from app.queue.tasks import run_brainstorm_generate
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, FakeGitService, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


class FakeGenerateRuntime:
    """FakeRuntime：03 生成 GDD，直接 yield started + completed。"""

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm",
                    system_prompt=None, plugin_dir=None):
        yield _evt(project_id, "agent.session.started", {"session_id": "g1", "model": "kimi-k3"})
        yield _evt(project_id, "agent.session.completed",
                   {"session_id": "g1", "result": "GDD generated", "stop_reason": "end_turn"})


async def test_run_brainstorm_generate(db_sm, fake_aioredis, monkeypatch):
    """job2 成功路径：BRAINSTORMING → spawn 03 → gdd.review_ready → GDD_REVIEW。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeGenerateRuntime())

    pid = await _create_project(db_sm, key="gen", status="BRAINSTORMING")
    # 预置 questions + answers（job1 产物）
    async with db_sm() as s:
        await QuestionRepo(s).create(
            pid, 1, [{"id": "1", "question": "平台？", "options": ["手机", "PC"]}])
        await QuestionRepo(s).set_answers(
            pid, 1, [{"question_id": "1", "answer": "PC"}])
        await s.commit()

    result = await run_brainstorm_generate(ctx={}, project_id=pid)

    assert result["succeeded"] is True
    # project GDD_REVIEW
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value
        # agent_session COMPLETED + GDD_GEN 类型
        ags = (await s.execute(
            select(AgentSession).where(AgentSession.project_id == pid)
        )).scalars().all()
        assert len(ags) == 1
        assert ags[0].agent_type == "GDD_GEN"
        assert ags[0].status == "COMPLETED"
        # event gdd.review_ready
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "gdd.review_ready" in types
        # agent 事件也落了（started + completed）
        assert "agent.session.started" in types
        assert "agent.session.completed" in types
