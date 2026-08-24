from __future__ import annotations

from sqlalchemy import select

from app.models.project import Project
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


async def test_game_build_insert(async_db_session):
    from app.models.game_build import GameBuild

    b = GameBuild(
        project_id=1, version="V1", status="SUCCESS",
        dist_path="/tmp/dist", duration_ms=4200, workflow_run_id="dev-1-run",
    )
    async_db_session.add(b)
    await async_db_session.flush()
    assert b.id is not None
    assert b.status == "SUCCESS"


async def test_game_observation_insert(async_db_session):
    from app.models.game_observation import GameObservation

    o = GameObservation(
        project_id=1, phase="3", observation_type="skill",
        name="game-code-generator", mode="coder", version="V1",
        status="OK", input_tokens=310, output_tokens=92, total_tokens=402,
        duration_ms=378000, cost_usd=0.12, meta={"run_id": "dev-1-run"},
    )
    async_db_session.add(o)
    await async_db_session.flush()
    assert o.id is not None
    assert o.meta == {"run_id": "dev-1-run"}
    assert o.total_tokens == 402
