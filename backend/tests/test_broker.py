from __future__ import annotations

from sqlalchemy import select

from app.events.broker import EventBroker
from app.models.event import Event
from app.models.agent_session import AgentSession
from app.persistence.repo import EventRepo, ProjectRepo, AgentSessionRepo
from app.schemas.event import CoworkEvent


def _make_event(project_id: int, **overrides) -> CoworkEvent:
    kw = dict(
        project_id=project_id,
        type="agent.message.delta",
        data={"text": "hi"},
        aggregate_type="agent_session",
        aggregate_id=project_id,
    )
    kw.update(overrides)
    return CoworkEvent(**kw)


# ---------------------------------------------------------------------------
# EventBroker: 先落库再广播（R2 callable + async with）
# ---------------------------------------------------------------------------


async def test_broker_persists_then_publishes(async_db_session, fake_redis):
    # 先建 project（events.project_id 是 FK，sqlite 默认 FK off，但为稳妥先建）
    project = await ProjectRepo(async_db_session).create(
        project_key="broker1",
        name="Broker1",
        status="CREATED",
        workspace_root="Games/broker1",
    )
    await async_db_session.commit()

    broker = EventBroker(session_factory=lambda: async_db_session, redis=fake_redis)
    evt = _make_event(project.id, type="agent.message.delta", data={"text": "hi"})

    await broker.publish(evt)

    # 落库：events 表有 1 行
    rows = await async_db_session.execute(
        select(Event).where(Event.project_id == project.id)
    )
    row = rows.scalars().first()
    assert row is not None
    assert row.event_type == "agent.message.delta"
    assert row.payload == {"text": "hi"}
    assert row.event_id == evt.event_id

    # 广播：FakeRedis stream 有 1 条
    stream = fake_redis.streams.get(f"stream:project:{project.id}")
    assert stream is not None
    assert len(stream) == 1


async def test_broker_history_reads_back(async_db_session, fake_redis):
    project = await ProjectRepo(async_db_session).create(
        project_key="broker2",
        name="Broker2",
        status="CREATED",
        workspace_root="Games/broker2",
    )
    await async_db_session.commit()

    broker = EventBroker(session_factory=lambda: async_db_session, redis=fake_redis)
    await broker.publish(_make_event(project.id, type="a.b", data={"i": 1}))
    await broker.publish(_make_event(project.id, type="a.b", data={"i": 2}))

    history = await broker.history(project.id)
    assert len(history) == 2
    # after_id 过滤
    first_id = history[0].id
    tail = await broker.history(project.id, after_id=first_id)
    assert len(tail) == 1


# ---------------------------------------------------------------------------
# EventRepo
# ---------------------------------------------------------------------------


async def test_event_repo_insert_and_history(async_db_session):
    project = await ProjectRepo(async_db_session).create(
        project_key="evtproj",
        name="EvtProj",
        status="CREATED",
        workspace_root="Games/evtproj",
    )
    await async_db_session.commit()

    repo = EventRepo(async_db_session)
    evt = _make_event(project.id, type="agent.session.started", data={"x": 1})
    row_id = await repo.insert(evt)
    await async_db_session.commit()
    assert row_id > 0

    history = await repo.history(project.id)
    assert len(history) == 1
    assert history[0].event_type == "agent.session.started"
    assert history[0].payload == {"x": 1}

    # after_id 过滤 + limit
    evt2 = _make_event(project.id, type="agent.message.delta", data={"y": 2})
    await repo.insert(evt2)
    await async_db_session.commit()

    tail = await repo.history(project.id, after_id=row_id)
    assert len(tail) == 1
    assert tail[0].event_type == "agent.message.delta"


# ---------------------------------------------------------------------------
# ProjectRepo
# ---------------------------------------------------------------------------


async def test_project_repo_create_get_set_status(async_db_session):
    repo = ProjectRepo(async_db_session)

    created = await repo.create(
        project_key="farmdemo",
        name="FarmDemo",
        status="CREATED",
        workspace_root="Games/farmdemo",
        description="a farm",
    )
    await async_db_session.commit()
    assert created.id is not None
    assert created.status == "CREATED"
    assert created.description == "a farm"

    # get by id
    got = await repo.get(created.id)
    assert got is not None
    assert got.project_key == "farmdemo"

    # get by key
    by_key = await repo.get_by_key("farmdemo")
    assert by_key is not None
    assert by_key.id == created.id

    # get 不存在返回 None
    assert await repo.get(999999) is None
    assert await repo.get_by_key("nope") is None

    # set_status
    await repo.set_status(created.id, "ANALYZING")
    await async_db_session.commit()
    # 新 session 视角：expire_on_commit=False，对象仍可读
    refreshed = await repo.get(created.id)
    assert refreshed.status == "ANALYZING"


# ---------------------------------------------------------------------------
# AgentSessionRepo
# ---------------------------------------------------------------------------


async def test_agent_session_repo_create_bind_finish_last_claude(async_db_session):
    project = await ProjectRepo(async_db_session).create(
        project_key="sessproj",
        name="SessProj",
        status="CREATED",
        workspace_root="Games/sessproj",
    )
    await async_db_session.commit()

    repo = AgentSessionRepo(async_db_session)

    # create：status=RUNNING，claude_session_id=None
    s = await repo.create(
        project_id=project.id,
        agent_type="brainstorm",
        working_directory="Games/sessproj",
    )
    await async_db_session.commit()
    assert s.id is not None
    assert s.status == "RUNNING"
    assert s.claude_session_id is None

    # bind_claude_session
    await repo.bind_claude_session(s.id, "claude-sess-1")
    await async_db_session.commit()

    # last_claude_session：还没有 COMPLETED，应返回 None
    assert await repo.last_claude_session(project.id, "brainstorm") is None

    # finish -> COMPLETED
    await repo.finish(s.id, "COMPLETED")
    await async_db_session.commit()

    # last_claude_session：现在应返回 claude-sess-1
    last = await repo.last_claude_session(project.id, "brainstorm")
    assert last == "claude-sess-1"

    # 第二个 session（FAILED，无 claude_session_id）不应覆盖 last
    s2 = await repo.create(
        project_id=project.id,
        agent_type="brainstorm",
        working_directory="Games/sessproj",
    )
    await repo.finish(s2.id, "FAILED")
    await async_db_session.commit()
    assert await repo.last_claude_session(project.id, "brainstorm") == "claude-sess-1"

    # 第三个 session（COMPLETED，新 claude_session_id）应成为 last
    s3 = await repo.create(
        project_id=project.id,
        agent_type="brainstorm",
        working_directory="Games/sessproj",
    )
    await repo.bind_claude_session(s3.id, "claude-sess-3")
    await repo.finish(s3.id, "COMPLETED")
    await async_db_session.commit()
    assert await repo.last_claude_session(project.id, "brainstorm") == "claude-sess-3"
