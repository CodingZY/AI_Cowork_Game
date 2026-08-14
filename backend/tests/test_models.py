from __future__ import annotations

from sqlalchemy import select

from app.models.project import Project
from app.models.agent_session import AgentSession
from app.models.event import Event


async def test_project_insert(async_db_session):
    p = Project(
        project_key="farmdemo",
        name="FarmDemo",
        status="CREATED",
        workspace_root="Games/farmdemo",
    )
    async_db_session.add(p)
    await async_db_session.flush()
    assert p.id is not None


async def test_agent_session_insert(async_db_session):
    p = Project(
        project_key="sessproj",
        name="SessProj",
        status="CREATED",
        workspace_root="Games/sessproj",
    )
    async_db_session.add(p)
    await async_db_session.flush()

    s = AgentSession(
        project_id=p.id,
        agent_type="brainstorm",
        status="RUNNING",
        working_directory="Games/sessproj",
    )
    async_db_session.add(s)
    await async_db_session.flush()
    assert s.id is not None
    assert s.project_id == p.id
    assert s.claude_session_id is None  # nullable, backfilled on system/init


async def test_event_insert_payload_roundtrip(async_db_session):
    p = Project(
        project_key="evtproj",
        name="EvtProj",
        status="CREATED",
        workspace_root="Games/evtproj",
    )
    async_db_session.add(p)
    await async_db_session.flush()

    payload = {"session_id": "sid-1", "model": "kimi-k3", "agent_type": "brainstorm"}
    e = Event(
        project_id=p.id,
        event_id="evt_abc123",
        event_type="agent.session.started",
        aggregate_type="agent_session",
        aggregate_id=p.id,
        payload=payload,
        raw_json='{"raw": "line"}',
    )
    async_db_session.add(e)
    await async_db_session.flush()
    assert e.id is not None

    # round-trip: reload from DB via fresh select, verify payload deserializes
    result = await async_db_session.execute(
        select(Event).where(Event.event_id == "evt_abc123")
    )
    fetched = result.scalar_one()
    assert fetched.payload == payload
    assert isinstance(fetched.payload, dict)
    assert fetched.event_id == "evt_abc123"
    assert fetched.aggregate_type == "agent_session"
    assert fetched.aggregate_id == p.id
