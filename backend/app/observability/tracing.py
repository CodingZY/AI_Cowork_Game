from __future__ import annotations

from typing import Optional

from app.observability.client import get_langfuse

# 进程级缓存：(project_id, phase) -> phase_span_id
# worker 重启后丢失（可接受：子 observation 仍挂同一 trace_id）。
_phase_span_cache: dict[tuple[int, str], str] = {}


def game_trace_id(project_id: int) -> str:
    """确定性 trace_id：同一 project 的 3 个 workflow 汇聚到一个 trace。

    即使 Langfuse 未启用也返回有效 id（业务表 langfuse_trace_id 用）。
    """
    from langfuse import Langfuse

    return Langfuse.create_trace_id(seed=f"game-{project_id}")


def get_or_create_phase_span(project_id: int, phase: str) -> Optional[str]:
    """lazy 创建 phase span，返回 span_id 供子 observation 用作 parent_span_id。

    Langfuse 未启用时返回 None（子 observation 的 trace_context 仅含 trace_id）。
    P0 简化：phase span 不显式 end，靠 worker shutdown flush。
    """
    lf = get_langfuse()
    if lf is None:
        return None
    key = (project_id, phase)
    cached = _phase_span_cache.get(key)
    if cached:
        return cached
    span = lf.start_observation(
        name=f"Phase {phase}",
        as_type="span",
        trace_context={"trace_id": game_trace_id(project_id)},
        metadata={"phase": phase, "game_id": project_id},
    )
    _phase_span_cache[key] = span.id
    return span.id


def record_skill_observation(
    *,
    project_id: int,
    phase: str,
    skill_name: str,
    mode: Optional[str] = None,
    version: Optional[str] = None,
    input_summary: Optional[dict] = None,
    output_summary: Optional[dict] = None,
    usage: Optional[dict] = None,  # {"input": N, "output": M, "total": T}
    model: Optional[str] = None,
    duration_ms: Optional[int] = None,
    status: str = "OK",
) -> Optional[str]:
    """记录一次 skill spawn（Generation observation），返回 observation_id 供业务表回链。

    Langfuse 未启用时静默返回 None。
    """
    lf = get_langfuse()
    if lf is None:
        return None
    parent_span_id = get_or_create_phase_span(project_id, phase)
    metadata: dict = {"phase": phase, "skill": skill_name, "game_id": project_id, "status": status}
    if mode:
        metadata["mode"] = mode
    if version:
        metadata["version"] = version
    if duration_ms is not None:
        metadata["duration_ms"] = duration_ms
    trace_ctx: dict = {"trace_id": game_trace_id(project_id)}
    if parent_span_id:
        trace_ctx["parent_span_id"] = parent_span_id
    obs = lf.start_observation(
        name=skill_name,
        as_type="generation",
        trace_context=trace_ctx,
        input=input_summary,
        output=output_summary,
        metadata=metadata,
        model=model or "kimi-k3",
        usage_details=usage or None,
    )
    obs.end()
    return obs.id


def record_activity_span(
    *,
    project_id: int,
    phase: str,
    activity_name: str,
    version: Optional[str] = None,
    duration_ms: Optional[int] = None,
    status: str = "OK",
    metadata: Optional[dict] = None,
) -> Optional[str]:
    """记录纯 Python activity（Span observation，无 token）。返回 observation_id 或 None。"""
    lf = get_langfuse()
    if lf is None:
        return None
    parent_span_id = get_or_create_phase_span(project_id, phase)
    meta: dict = {"phase": phase, "activity": activity_name, "game_id": project_id, "status": status}
    if version:
        meta["version"] = version
    if duration_ms is not None:
        meta["duration_ms"] = duration_ms
    if metadata:
        meta.update(metadata)
    trace_ctx: dict = {"trace_id": game_trace_id(project_id)}
    if parent_span_id:
        trace_ctx["parent_span_id"] = parent_span_id
    obs = lf.start_observation(
        name=activity_name,
        as_type="span",
        trace_context=trace_ctx,
        metadata=meta,
    )
    obs.end()
    return obs.id
