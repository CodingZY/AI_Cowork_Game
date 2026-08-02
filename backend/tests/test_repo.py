"""仓储函数 CRUD 测试（in-memory SQLite）。"""
import pytest
from persistence.repo import (
    create_run, get_run, list_runs, update_stage,
    create_approval, resolve_approval, get_pending_approval,
    create_question, answer_question,
)


@pytest.mark.asyncio
async def test_create_and_get_run(async_session):
    run = await create_run(async_session, game_name="我的农场", slug="my-farm")
    assert run.id and run.current_stage == "S0_init"
    got = await get_run(async_session, run.id)
    assert got.game_name == "我的农场"


@pytest.mark.asyncio
async def test_list_runs(async_session):
    await create_run(async_session, game_name="A", slug="a")
    await create_run(async_session, game_name="B", slug="b")
    runs = await list_runs(async_session)
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_update_stage(async_session):
    run = await create_run(async_session, game_name="A", slug="a")
    await update_stage(async_session, run.id, stage="S1_design", status="running")
    got = await get_run(async_session, run.id)
    assert got.current_stage == "S1_design" and got.status == "running"


@pytest.mark.asyncio
async def test_approval_flow(async_session):
    run = await create_run(async_session, game_name="A", slug="a")
    ap = await create_approval(async_session, run.id, stage="S1_design", payload={"doc": "game-design.md"})
    assert ap.status == "pending"
    await resolve_approval(async_session, ap.id, resolution="approved", feedback=None)
    pending = await get_pending_approval(async_session, run.id, stage="S1_design")
    assert pending.status == "approved"


@pytest.mark.asyncio
async def test_question_flow(async_session):
    run = await create_run(async_session, game_name="A", slug="a")
    q = await create_question(async_session, run.id, "q1", "游戏类型？", ["RPG", "模拟"])
    assert q.status == "pending"
    await answer_question(async_session, q.id, answer="模拟")
    assert q.status == "answered" and q.answer == "模拟"
