"""REST 路由：run 管理、设计文档读写、阶段闸、问答回答。"""
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, games_root, _session_factory
from api.broker import broker
from api.runtime import start_design
from persistence.repo import create_run, get_run, list_runs, get_pending_approval
from persistence.models import GameRun
from orchestrator.states import Stage, StageStatus
from orchestrator.machine import StateMachine, RunState

router = APIRouter(prefix="/api")
sm = StateMachine()

# 强引用持有后台任务，避免事件循环 GC 在任务完成前回收（CPython 已知坑）。
_background_tasks: set = set()


def _slug(name: str) -> str:
    import re
    s = re.sub(r"[^\w一-龥]+", "-", name.strip().lower()).strip("-")
    return s or "game"


@router.post("/runs")
async def create_run_endpoint(payload: dict, session: AsyncSession = Depends(get_session)):
    game_name = payload["game_name"]
    slug = _slug(game_name)
    run = await create_run(session, game_name=game_name, slug=slug)
    # 启动 design agent 后台任务（持有强引用防 GC；立即 yield 让任务起步）
    task = asyncio.create_task(start_design(run.id, game_name))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    await asyncio.sleep(0)
    return {"id": run.id, "game_name": run.game_name, "current_stage": run.current_stage, "status": run.status}


@router.get("/runs")
async def list_runs_endpoint(session: AsyncSession = Depends(get_session)):
    runs = await list_runs(session)
    return [{"id": r.id, "game_name": r.game_name, "current_stage": r.current_stage, "status": r.status} for r in runs]


@router.get("/runs/{run_id}")
async def get_run_endpoint(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {"id": run.id, "game_name": run.game_name, "current_stage": run.current_stage, "status": run.status}


@router.get("/runs/{run_id}/design.md")
async def get_design(run_id: str):
    run = await _load_run(run_id)
    p = games_root() / run.slug / "docs" / "game-design.md"
    if not p.exists():
        raise HTTPException(404, "design not ready")
    return {"content": p.read_text(encoding="utf-8")}


@router.put("/runs/{run_id}/design.md")
async def put_design(run_id: str, payload: dict):
    run = await _load_run(run_id)
    if run.status not in (StageStatus.awaiting_approval.value, StageStatus.rejected.value):
        raise HTTPException(409, "当前阶段不可编辑设计文档")
    p = games_root() / run.slug / "docs" / "game-design.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(payload["content"], encoding="utf-8")
    return {"ok": True}


@router.post("/runs/{run_id}/approve")
async def approve(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    t = sm.approve(RunState(run.id, Stage(run.current_stage), StageStatus(run.status)), stage=Stage.S1_design)
    if t is None:
        raise HTTPException(409, "当前状态不可通过")
    # update_stage + 审批解析 必须原子提交（AUTOCOMMIT 下用显式事务包住），
    # 避免崩溃后出现"阶段已进 S2 但 S1 审批仍 pending"的悬挂状态。
    # 用独立会话：注入会话已被 get_run 自动开启事务，session.begin() 会冲突。
    async with _session_factory() as s2:
        async with s2.begin():
            r = await s2.get(GameRun, run_id)
            r.current_stage = t.stage.value
            r.status = t.status.value
            ap = await get_pending_approval(s2, run_id, stage=Stage.S1_design.value)
            if ap:
                ap.status = "approved"
                ap.feedback = None
                ap.resolved_at = datetime.utcnow()
    broker.publish(run_id, {"type": "gate", "stage": t.stage.value, "status": "approved"})
    return {"ok": True, "current_stage": t.stage.value, "status": t.status.value}


@router.post("/runs/{run_id}/reject")
async def reject(run_id: str, payload: dict):
    feedback = payload.get("feedback", "")
    run = await _load_run(run_id)
    # 通过状态机守卫：仅在 S1 awaiting_approval 时允许拒绝，否则 409。
    t = sm.reject(
        RunState(run.id, Stage(run.current_stage), StageStatus(run.status)),
        stage=Stage.S1_design, feedback=feedback,
    )
    if t is None:
        raise HTTPException(409, "当前状态不可拒绝")
    # update_stage + 审批解析 原子提交（显式事务），避免悬挂的 pending 审批。
    async with _session_factory() as session:
        async with session.begin():
            r = await session.get(GameRun, run_id)
            r.current_stage = t.stage.value
            r.status = t.status.value
            ap = await get_pending_approval(session, run_id, stage=Stage.S1_design.value)
            if ap:
                ap.status = "rejected"
                ap.feedback = feedback
                ap.resolved_at = datetime.utcnow()
    # 带反馈重跑 design agent（长跑，留在事务外）。
    task = asyncio.create_task(start_design(run.id, run.game_name, feedback=feedback))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"ok": True}


@router.post("/runs/{run_id}/answer")
async def answer(run_id: str, payload: dict):
    broker.deliver_answer(run_id, payload["answer"])
    return {"ok": True}


async def _load_run(run_id: str):
    async with _session_factory() as session:
        run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run
