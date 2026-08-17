from __future__ import annotations

from sqlalchemy import select

from app.models.brainstorm_questions import BrainstormQuestion
from app.models.event import Event
from app.persistence.repo import ProjectRepo, QuestionRepo
from app.queue.tasks import run_brainstorm_questions
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, FakeGitService, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


class FakeQuestionsRuntime:
    """FakeRuntime：02 出题，result 文本含带选项问题。"""
    def __init__(self, result_text):
        self.result_text = result_text
        self.cwd = None

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm",
                    system_prompt=None, plugin_dir=None):
        self.cwd = cwd
        yield _evt(project_id, "agent.session.started", {"session_id": "q1", "model": "kimi-k3"})
        yield _evt(project_id, "agent.session.completed",
                   {"session_id": "q1", "result": self.result_text, "stop_reason": "end_turn"})


QUESTIONS_TEXT = """1. 目标平台？(A)手机 (B)PC (C)网页
2. 核心玩法？(A)纯经营 (B)经营+RPG
3. 美术风格？(A)像素 (B)卡通"""


async def test_run_brainstorm_questions(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeQuestionsRuntime(QUESTIONS_TEXT))

    pid = await _create_project(db_sm, key="q")

    result = await run_brainstorm_questions(ctx={}, project_id=pid, idea="种田游戏")

    assert result["succeeded"] is True
    # project BRAINSTORMING（等答）
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.BRAINSTORMING.value
    # 问题存表
    async with db_sm() as s:
        bq = (await s.execute(
            select(BrainstormQuestion).where(BrainstormQuestion.project_id == pid)
        )).scalar_one()
        assert len(bq.questions) == 3
        assert bq.questions[0]["id"] == "1"
        assert bq.questions[0]["options"] == ["手机", "PC", "网页"]
    # event brainstorm.questions_ready
    async with db_sm() as s:
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "brainstorm.questions_ready" in types
