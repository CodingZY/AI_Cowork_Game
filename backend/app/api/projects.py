from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.git.service import GitService
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo, QuestionRepo
from app.queue.jobs import (
    enqueue_brainstorm_questions,
    enqueue_brainstorm_generate,
    enqueue_finalize,
    enqueue_gdd_check,
)
from app.schemas.project import ProjectCreate, ProjectRead, BrainstormRequest, AnswerBody
from app.services import project_service
from app.workflow.states import ProjectStatus

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
        gdd_md = gdd_path.read_text(encoding="utf-8") if gdd_path.exists() else ""
        manifest = man_path.read_text(encoding="utf-8") if man_path.exists() else ""
    return {"gdd_md": gdd_md, "manifest": manifest}


@router.post("/projects/{pid}/brainstorm", status_code=202)
async def start_brainstorm(
    pid: int, body: BrainstormRequest, session: AsyncSession = Depends(get_session)
):
    # 存 idea 到 project.description（供 job2 run_brainstorm_generate 读 idea 拼 prompt）
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if not p.description:
        await ProjectRepo(session).set_description(pid, body.idea)
    await session.commit()
    job_id = await enqueue_brainstorm_questions(pid, body.idea)
    return {"task_id": job_id}


@router.post("/projects/{pid}/brainstorm/answer", status_code=202)
async def submit_answer(
    pid: int, body: AnswerBody, session: AsyncSession = Depends(get_session)
):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if p.status != ProjectStatus.BRAINSTORMING.value:
        raise HTTPException(409, f"cannot answer from {p.status}")
    await QuestionRepo(session).set_answers(pid, 1, body.answers)
    await session.commit()
    job_id = await enqueue_brainstorm_generate(pid)
    return {"task_id": job_id}


@router.post("/projects/{pid}/brainstorm/finalize", status_code=202)
async def finalize_brainstorm(pid: int):
    job_id = await enqueue_finalize(pid)
    return {"task_id": job_id}


@router.post("/projects/{pid}/gdd/approve", status_code=202)
async def approve_gdd(pid: int, session: AsyncSession = Depends(get_session)):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if p.status != ProjectStatus.GDD_REVIEW.value:
        raise HTTPException(409, f"cannot approve from {p.status}")
    await ProjectRepo(session).set_status(pid, ProjectStatus.GDD_CHECKING)
    await session.commit()
    job_id = await enqueue_gdd_check(pid)
    return {"task_id": job_id}
