from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from temporalio import activity

from app.observability.tracing import (
    game_trace_id,
    record_activity_span,
    record_skill_observation,
)
from app.persistence.db import get_sessionmaker
from app.persistence.repo import GameBuildRepo, GameObservationRepo


def _now() -> datetime:
    """UTC naive datetime（DateTime(timezone=False) 列用）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _activity_ctx() -> dict:
    """从 temporal activity.info() 提取埋点上下文（project_id/phase/run_id）。

    phase 由 workflow_id 前缀推断：game-/art-/dev- → 1/2/3。
    project_id 由 workflow_id 的 `split("-",1)[1]` 解析（与 _project_id_from_workflow 同源）。
    不在 activity context 时（如单元测试直接 await activity）返回默认，不抛错。
    """
    try:
        info = activity.info()
        wid = info.workflow_id
    except Exception:
        return {"project_id": 0, "phase": "unknown", "workflow_id": "",
                "run_id": None, "activity_type": None}
    if wid.startswith("game-"):
        phase = "1"
    elif wid.startswith("art-"):
        phase = "2"
    elif wid.startswith("dev-"):
        phase = "3"
    else:
        phase = "unknown"
    try:
        pid = int(wid.split("-", 1)[1])
    except (ValueError, IndexError):
        pid = 0
    return {
        "project_id": pid,
        "phase": phase,
        "workflow_id": wid,
        "run_id": getattr(info, "run_id", None),
        "activity_type": getattr(info, "activity_type", None),
    }


async def _record_observation_row(
    *,
    project_id: int,
    phase: str,
    observation_type: str,
    name: str,
    mode: Optional[str] = None,
    version: Optional[str] = None,
    status: str = "OK",
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    duration_ms: Optional[int] = None,
    cost_usd: Optional[float] = None,
    metadata: Optional[dict] = None,
    langfuse_observation_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
) -> None:
    """写 game_observations 业务表（聚合源）。失败不阻塞 activity。"""
    try:
        sm = get_sessionmaker()
        async with sm() as s:
            await GameObservationRepo(s).create(
                project_id=project_id,
                phase=phase,
                observation_type=observation_type,
                name=name,
                mode=mode,
                version=version,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                cost_usd=cost_usd,
                metadata=metadata,
                langfuse_trace_id=game_trace_id(project_id),
                langfuse_observation_id=langfuse_observation_id,
                started_at=started_at,
                ended_at=ended_at,
            )
            await s.commit()
    except Exception:
        # 埋点失败不影响主流程
        pass


async def _record_build_row(
    *,
    project_id: int,
    version: str,
    status: str,
    dist_path: Optional[str] = None,
    build_log: Optional[str] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    workflow_run_id: Optional[str] = None,
    langfuse_observation_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
) -> None:
    """写 game_builds 业务表。失败不阻塞。"""
    try:
        sm = get_sessionmaker()
        async with sm() as s:
            await GameBuildRepo(s).create(
                project_id=project_id,
                version=version,
                status=status,
                dist_path=dist_path,
                build_log=build_log,
                error_message=error_message,
                duration_ms=duration_ms,
                workflow_run_id=workflow_run_id,
                langfuse_observation_id=langfuse_observation_id,
                started_at=started_at,
                ended_at=ended_at,
            )
            await s.commit()
    except Exception:
        pass


def instrument_skill(skill_name: str, mode: Optional[str] = None):
    """返回 async context manager 工厂，包裹 _spawn_skill 的 spawn 循环。

    记录 Langfuse Generation + game_observations(skill 行)。
    用法：
        async with instrument_skill("gdd-generator")(pid, phase, version) as tok:
            async for evt in runtime.start(...):
                if evt.type == "agent.session.completed":
                    tok["usage"] = {"input":..,"output":..,"total":..}
                    tok["model"] = "kimi-k3"; tok["cost"] = ...
    """
    @asynccontextmanager
    async def _ctx(project_id: int, version: Optional[str] = None):
        ctx = _activity_ctx()
        phase = ctx["phase"]
        t0 = time.monotonic()
        started_at = _now()
        status = "OK"
        token_data: dict = {}
        try:
            yield token_data
        except Exception:
            status = "ERROR"
            raise
        finally:
            ended_at = _now()
            duration_ms = int((time.monotonic() - t0) * 1000)
            usage = token_data.get("usage") or {}
            langfuse_obs_id = record_skill_observation(
                project_id=project_id,
                phase=phase,
                skill_name=skill_name,
                mode=mode,
                version=version,
                input_summary=token_data.get("input_summary"),
                output_summary=token_data.get("output_summary"),
                usage=usage or None,
                model=token_data.get("model"),
                duration_ms=duration_ms,
                status=status,
            )
            await _record_observation_row(
                project_id=project_id,
                phase=phase,
                observation_type="skill",
                name=skill_name,
                mode=mode,
                version=version,
                status=status,
                input_tokens=usage.get("input"),
                output_tokens=usage.get("output"),
                total_tokens=usage.get("total"),
                duration_ms=duration_ms,
                cost_usd=token_data.get("cost"),
                metadata={"run_id": ctx.get("run_id"), "workflow_id": ctx.get("workflow_id")},
                langfuse_observation_id=langfuse_obs_id,
                started_at=started_at,
                ended_at=ended_at,
            )

    return _ctx


@asynccontextmanager
async def instrument_activity(activity_name: str, version: Optional[str] = None):
    """包裹纯 Python activity 函数体，记录 Langfuse Span + game_observations(activity 行)。"""
    ctx = _activity_ctx()
    t0 = time.monotonic()
    started_at = _now()
    status = "OK"
    try:
        yield
    except Exception:
        status = "ERROR"
        raise
    finally:
        ended_at = _now()
        duration_ms = int((time.monotonic() - t0) * 1000)
        langfuse_obs_id = record_activity_span(
            project_id=ctx["project_id"],
            phase=ctx["phase"],
            activity_name=activity_name,
            version=version,
            duration_ms=duration_ms,
            status=status,
        )
        await _record_observation_row(
            project_id=ctx["project_id"],
            phase=ctx["phase"],
            observation_type="activity",
            name=activity_name,
            version=version,
            status=status,
            duration_ms=duration_ms,
            metadata={"run_id": ctx.get("run_id"), "workflow_id": ctx.get("workflow_id")},
            langfuse_observation_id=langfuse_obs_id,
            started_at=started_at,
            ended_at=ended_at,
        )
