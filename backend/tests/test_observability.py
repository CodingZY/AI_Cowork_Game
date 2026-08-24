from __future__ import annotations

from datetime import datetime, timedelta

from app.api.observability import get_builds, get_overview, get_phases, get_skill_tokens
from app.models.game_build import GameBuild
from app.models.game_observation import GameObservation
from app.models.project import Project


async def test_observability_aggregates(async_db_session):
    """overview/builds/phases/skills 聚合：build 成功率 + phase 耗时(MAX-MIN) + skill token 排名。"""
    p = Project(project_key="obs", name="Obs", status="DEV_DONE", workspace_root="Games/obs")
    async_db_session.add(p)
    await async_db_session.flush()
    pid = p.id

    # 2 builds: 1 success 1 fail → rate 0.5
    async_db_session.add(GameBuild(project_id=pid, version="V1", status="SUCCESS", duration_ms=1000))
    async_db_session.add(GameBuild(project_id=pid, version="V1", status="FAILED", duration_ms=500,
                                   error_message="tsc boom"))

    t0 = datetime(2026, 8, 20, 10, 0, 0)
    # Phase1 skill: 10s
    async_db_session.add(GameObservation(
        project_id=pid, phase="1", observation_type="skill", name="gdd-generator",
        status="OK", input_tokens=55, output_tokens=16, total_tokens=71,
        duration_ms=10000, started_at=t0, ended_at=t0 + timedelta(seconds=10)))
    # Phase3 skill coder: 6m (10:00+1h ~ 10:00+1h6m)
    async_db_session.add(GameObservation(
        project_id=pid, phase="3", observation_type="skill", name="game-code-generator", mode="coder", version="V1",
        status="OK", input_tokens=310, output_tokens=92, total_tokens=402,
        duration_ms=378000, started_at=t0 + timedelta(hours=1), ended_at=t0 + timedelta(hours=1, minutes=6)))
    # Phase3 activity build_game: 2m (10:06 ~ 10:08)
    async_db_session.add(GameObservation(
        project_id=pid, phase="3", observation_type="activity", name="build_game", version="V1",
        status="OK", duration_ms=108000, started_at=t0 + timedelta(hours=1, minutes=6),
        ended_at=t0 + timedelta(hours=1, minutes=8)))
    await async_db_session.flush()

    res = await get_overview(pid=pid, session=async_db_session)
    assert res["build"]["total"] == 2
    assert res["build"]["success"] == 1
    assert res["build"]["rate"] == 0.5
    assert res["total_tokens"] == 71 + 402
    phases = {p2["phase"]: p2 for p2 in res["phases"]}
    assert phases["1"]["total_tokens"] == 71
    assert phases["3"]["total_tokens"] == 402
    assert phases["1"]["duration_ms"] == 10000
    assert phases["3"]["duration_ms"] == 480000  # MAX(end 11:08) - MIN(start 11:00) = 8m（Phase E2E 含全程）

    skills = await get_skill_tokens(pid=pid, session=async_db_session)
    assert skills["total_tokens"] == 71 + 402
    assert skills["skills"][0]["skill"] == "game-code-generator (coder)"
    assert skills["skills"][0]["total_tokens"] == 402
    assert skills["skills"][0]["pct"] == round(402 / 473, 4)

    builds = await get_builds(pid=pid, session=async_db_session)
    assert len(builds["builds"]) == 2

    phases_res = await get_phases(pid=pid, session=async_db_session)
    p3 = [p2 for p2 in phases_res["phases"] if p2["phase"] == "3"][0]
    assert len(p3["observations"]) == 2
    assert p3["e2e_duration_ms"] == 480000
