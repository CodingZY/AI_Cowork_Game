from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_build import GameBuild
from app.models.game_observation import GameObservation
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo

router = APIRouter(prefix="/api")


async def get_session() -> AsyncSession:
    sm = get_sessionmaker()
    async with sm() as s:
        yield s


def _phase_duration_ms(rows: list[GameObservation]) -> int:
    """Phase E2E 耗时 = MAX(ended_at) - MIN(started_at)（毫秒，含中间等待）。

    用 span 时间（非 SUM skill duration），符合 design §27（耗时与 token 分开算）。
    缺 started_at/ended_at 的行跳过；全缺则 0。Python 端算避 SQLite/MySQL 方言差异。
    """
    starts = [r.started_at for r in rows if r.started_at]
    ends = [r.ended_at for r in rows if r.ended_at]
    if not starts or not ends:
        return 0
    delta = max(ends) - min(starts)
    return int(delta.total_seconds() * 1000)


@router.get("/observability/overview")
async def get_overview(pid: int = Query(..., description="project_id"),
                       session: AsyncSession = Depends(get_session)):
    """总览：Build 成功率 + 各 Phase E2E 耗时 + 各 Phase Token + E2E 汇总。design §13/§23。"""
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")

    builds = (await session.execute(
        select(GameBuild).where(GameBuild.project_id == pid)
    )).scalars().all()
    total_builds = len(builds)
    success_builds = sum(1 for b in builds if b.status == "SUCCESS")
    build_rate = (success_builds / total_builds) if total_builds else 0.0

    obs = (await session.execute(
        select(GameObservation).where(GameObservation.project_id == pid)
    )).scalars().all()
    by_phase: dict[str, list[GameObservation]] = {}
    for o in obs:
        by_phase.setdefault(o.phase, []).append(o)
    phases = []
    for ph in sorted(by_phase):
        rows = by_phase[ph]
        phases.append({
            "phase": ph,
            "duration_ms": _phase_duration_ms(rows),
            "input_tokens": sum(r.input_tokens or 0 for r in rows),
            "output_tokens": sum(r.output_tokens or 0 for r in rows),
            "total_tokens": sum(r.total_tokens or 0 for r in rows),
            "skill_count": sum(1 for r in rows if r.observation_type == "skill"),
        })
    return {
        "project_id": pid,
        "build": {"total": total_builds, "success": success_builds,
                  "failed": total_builds - success_builds, "rate": round(build_rate, 4)},
        "phases": phases,
        "total_tokens": sum(p2["total_tokens"] for p2 in phases),
        "total_duration_ms": sum(p2["duration_ms"] for p2 in phases),
    }


@router.get("/observability/builds")
async def get_builds(pid: int = Query(...), session: AsyncSession = Depends(get_session)):
    """Build 明细列表。design §5。"""
    builds = (await session.execute(
        select(GameBuild).where(GameBuild.project_id == pid).order_by(GameBuild.id)
    )).scalars().all()
    return {"project_id": pid, "builds": [
        {"id": b.id, "version": b.version, "status": b.status,
         "dist_path": b.dist_path, "duration_ms": b.duration_ms,
         "error_message": b.error_message,
         "build_log": (b.build_log[:500] if b.build_log else None),
         "created_at": b.created_at.isoformat() if b.created_at else None}
        for b in builds
    ]}


@router.get("/observability/phases")
async def get_phases(pid: int = Query(...), session: AsyncSession = Depends(get_session)):
    """各 Phase E2E 耗时 + 子阶段 observations（P0 返列表；P1 前端可渲染 Timeline）。design §8/§24。"""
    obs = (await session.execute(
        select(GameObservation).where(GameObservation.project_id == pid).order_by(GameObservation.id)
    )).scalars().all()
    by_phase: dict[str, list[GameObservation]] = {}
    for o in obs:
        by_phase.setdefault(o.phase, []).append(o)
    phases = []
    for ph in sorted(by_phase):
        rows = by_phase[ph]
        phases.append({
            "phase": ph,
            "e2e_duration_ms": _phase_duration_ms(rows),
            "total_tokens": sum(r.total_tokens or 0 for r in rows),
            "observations": [
                {"name": r.name, "type": r.observation_type, "mode": r.mode,
                 "version": r.version, "status": r.status, "duration_ms": r.duration_ms,
                 "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                 "total_tokens": r.total_tokens,
                 "started_at": r.started_at.isoformat() if r.started_at else None,
                 "ended_at": r.ended_at.isoformat() if r.ended_at else None}
                for r in rows
            ],
        })
    return {"project_id": pid, "phases": phases}


@router.get("/observability/skills/tokens")
async def get_skill_tokens(pid: int = Query(...), session: AsyncSession = Depends(get_session)):
    """Skill Token 消耗排名（按 name+mode 聚合，total_tokens 降序）。design §11-12。"""
    obs = (await session.execute(
        select(GameObservation).where(
            GameObservation.project_id == pid,
            GameObservation.observation_type == "skill",
        ).order_by(GameObservation.id)
    )).scalars().all()
    skills: dict[str, dict] = {}
    for o in obs:
        key = o.name + (f" ({o.mode})" if o.mode else "")
        s = skills.setdefault(key, {
            "skill": key, "phase": o.phase, "calls": 0,
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "duration_ms": 0,
        })
        s["calls"] += 1
        s["input_tokens"] += o.input_tokens or 0
        s["output_tokens"] += o.output_tokens or 0
        s["total_tokens"] += o.total_tokens or 0
        s["duration_ms"] += o.duration_ms or 0
    ranked = sorted(skills.values(), key=lambda x: x["total_tokens"], reverse=True)
    total = sum(s["total_tokens"] for s in ranked)
    for s in ranked:
        s["pct"] = round(s["total_tokens"] / total, 4) if total else 0.0
    return {"project_id": pid, "skills": ranked, "total_tokens": total}
