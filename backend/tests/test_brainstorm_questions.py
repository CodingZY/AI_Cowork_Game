from __future__ import annotations

from app.models.brainstorm_questions import BrainstormQuestion
from app.persistence.repo import QuestionRepo, ProjectRepo


async def test_create_and_get_latest(async_db_session):
    proj = await ProjectRepo(async_db_session).create(
        project_key="farm", name="Farm", status="CREATED", workspace_root="ws/farm")
    repo = QuestionRepo(async_db_session)
    qs = [{"id": "1", "question": "平台？", "options": ["手机", "PC"]}]
    row = await repo.create(project_id=proj.id, round=1, questions=qs)
    assert row.id is not None
    assert row.questions == qs
    assert row.answers is None

    got = await repo.get_latest(proj.id)
    assert got is not None
    assert got.round == 1


async def test_set_answers(async_db_session):
    proj = await ProjectRepo(async_db_session).create(
        project_key="k1", name="K1", status="CREATED", workspace_root="ws/k1")
    repo = QuestionRepo(async_db_session)
    await repo.create(project_id=proj.id, round=1, questions=[{"id": "1", "question": "q", "options": []}])
    answers = [{"question_id": "1", "answer": "PC"}]
    await repo.set_answers(proj.id, 1, answers)
    got = await repo.get_latest(proj.id)
    assert got.answers == answers
