from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo
from app.queue.jobs import enqueue_brainstorm, enqueue_finalize
from app.schemas.project import ProjectCreate, ProjectRead, BrainstormRequest
from app.services import project_service

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


@router.post("/projects/{pid}/brainstorm", status_code=202)
async def start_brainstorm(pid: int, body: BrainstormRequest):
    job_id = await enqueue_brainstorm(pid, body.idea)
    return {"task_id": job_id}


@router.post("/projects/{pid}/brainstorm/finalize", status_code=202)
async def finalize_brainstorm(pid: int):
    job_id = await enqueue_finalize(pid)
    return {"task_id": job_id}
