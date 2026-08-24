from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.git.service import GitService
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo
from app.queue.jobs import enqueue_finalize
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    AnswerBody,
    SkipBody,
    GddBody,
)
from app.services import project_service
from temporal.client import start_design_workflow, send_signal, query_state
from temporal.workflows import AnswerSignal

router = APIRouter(prefix="/api")


async def get_session() -> AsyncSession:
    sm = get_sessionmaker()
    async with sm() as s:
        yield s


@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_project(
    body: ProjectCreate, session: AsyncSession = Depends(get_session)
):
    p = await project_service.create(
        session, name=body.name, description=body.description
    )
    await session.commit()
    # 起 Temporal GameDesignWorkflow（idea 优先用 description，退回 name）
    await start_design_workflow(p.id, body.description or body.name)
    return ProjectRead(
        id=p.id,
        project_key=p.project_key,
        name=p.name,
        status=p.status,
        workspace_root=p.workspace_root,
    )


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)):
    return await ProjectRepo(session).list_all()


@router.get("/projects/{pid}", response_model=ProjectRead)
async def get_project(pid: int, session: AsyncSession = Depends(get_session)):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    return ProjectRead(
        id=p.id,
        project_key=p.project_key,
        name=p.name,
        status=p.status,
        workspace_root=p.workspace_root,
    )


@router.get("/projects/{pid}/gdd")
async def get_gdd(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree 里的 GDD.md + gdd-manifest.json（供前端 GddReviewPanel 渲染）。"""
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    game_dir = wt / "games" / p.project_key if wt is not None else None
    gdd_md = ""
    manifest = ""
    if game_dir is not None:
        gdd_path = game_dir / "GDD.md"
        man_path = game_dir / "gdd-manifest.json"
        gdd_md = gdd_path.read_text(encoding="utf-8-sig") if gdd_path.exists() else ""
        manifest = man_path.read_text(encoding="utf-8-sig") if man_path.exists() else ""
    return {"gdd_md": gdd_md, "manifest": manifest}


@router.post("/projects/{pid}/gdd/save", status_code=202)
async def save_gdd(pid: int, body: GddBody, session: AsyncSession = Depends(get_session)):
    """写回用户编辑后的 GDD.md 到 worktree + 发 save_gdd signal 推进 workflow。

    GDD_REVIEW 阶段用户在 UI 编辑 markdown 保存：落盘持久化（finalize/git 用）
    + Signal 通知 workflow 继续 check_gdd（check 用 signal 带的正文）。
    """
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        raise HTTPException(409, "worktree not ready")
    game_dir = wt / "games" / p.project_key
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "GDD.md").write_text(body.gdd_md, encoding="utf-8")
    await send_signal(pid, "save_gdd", body.gdd_md)
    return {"ok": True}


@router.post("/projects/{pid}/brainstorm/finalize", status_code=202)
async def finalize_brainstorm(pid: int):
    job_id = await enqueue_finalize(pid)
    return {"task_id": job_id}


# --- Temporal 端点（阶段1 GameDesignWorkflow） ---


@router.get("/projects/{pid}/state")
async def get_state(pid: int):
    """Query GameDesignWorkflow.get_design_state（前端轮询当前阶段/题目/进度）。"""
    return await query_state(pid)


@router.post("/projects/{pid}/answer", status_code=202)
async def submit_answer(pid: int, body: AnswerBody):
    """Signal submit_answer（单题答题推进 Workflow）。"""
    await send_signal(pid, "submit_answer", AnswerSignal(body.question_id, body.answer))
    return {"ok": True}


@router.post("/projects/{pid}/skip", status_code=202)
async def skip_question(pid: int, body: SkipBody):
    """Signal skip_question（跳过当前题，用 default_option 或留空）。"""
    await send_signal(pid, "skip_question", body.question_id)
    return {"ok": True}
