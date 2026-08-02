"""REST 路由：run 管理、设计文档读写、阶段闸、问答回答。"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, games_root, _session_factory
from api.broker import broker
from api.runtime import start_design
from persistence.repo import create_run, get_run, list_runs, update_stage, get_pending_approval, resolve_approval
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
    await update_stage(session, run_id, stage=t.stage.value, status=t.status.value)
    ap = await get_pending_approval(session, run_id, stage=Stage.S1_design.value)
    if ap:
        await resolve_approval(session, ap.id, resolution="approved", feedback=None)
    broker.publish(run_id, {"type": "gate", "stage": t.stage.value, "status": "approved"})
    return {"ok": True, "current_stage": t.stage.value, "status": t.status.value}


@router.post("/runs/{run_id}/reject")
async def reject(run_id: str, payload: dict):
    feedback = payload.get("feedback", "")
    run = await _load_run(run_id)
    # 状态回到 design running，带反馈重跑
    async with _session_factory() as session:
        await update_stage(session, run_id, stage=Stage.S1_design.value, status=StageStatus.running.value)
        ap = await get_pending_approval(session, run_id, stage=Stage.S1_design.value)
        if ap:
            await resolve_approval(session, ap.id, resolution="rejected", feedback=feedback)
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
