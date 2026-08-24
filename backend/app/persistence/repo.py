from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.game_build import GameBuild
from app.models.game_observation import GameObservation
from app.models.project import Project
from app.models.project_repository import ProjectRepository
from app.schemas.event import CoworkEvent


class EventRepo:
    """events 表 CRUD 封装（spec §6.3）。

    payload = 归一化 CoworkEvent.data；raw_json = 原始 stream-json 行（调试用）。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert(self, evt: CoworkEvent) -> int:
        """插入一行 Event，flush 后返回自增 id。"""
        row = Event(
            event_id=evt.event_id,
            project_id=evt.project_id,
            event_type=evt.type,
            aggregate_type=evt.aggregate_type,
            aggregate_id=evt.aggregate_id,
            payload=evt.data,
            raw_json=evt.raw_json,
        )
        self.session.add(row)
        await self.session.flush()
        return row.id

    async def history(
        self, project_id: int, after_id: int = 0, limit: int = 500
    ) -> list[Event]:
        """读取某 project 的历史事件（id 升序，可从 after_id 续读）。"""
        q = (
            select(Event)
            .where(Event.project_id == project_id, Event.id > after_id)
            .order_by(Event.id)
            .limit(limit)
        )
        return (await self.session.execute(q)).scalars().all()


class ProjectRepo:
    """projects 表 CRUD 封装（spec §6.1）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_key: str,
        name: str,
        status: str,
        workspace_root: str,
        description: Optional[str] = None,
    ) -> Project:
        row = Project(
            project_key=project_key,
            name=name,
            status=status,
            workspace_root=workspace_root,
            description=description,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, project_id: int) -> Optional[Project]:
        return (
            await self.session.execute(
                select(Project).where(Project.id == project_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Project]:
        """所有 project，按 id 倒序（新建在前）。"""
        return (
            await self.session.execute(select(Project).order_by(Project.id.desc()))
        ).scalars().all()

    async def get_by_key(self, key: str) -> Optional[Project]:
        return (
            await self.session.execute(
                select(Project).where(Project.project_key == key)
            )
        ).scalar_one_or_none()

    async def set_status(self, project_id: int, status: str) -> None:
        await self.session.execute(
            update(Project).where(Project.id == project_id).values(status=status)
        )

    async def set_description(self, project_id: int, description: str) -> None:
        """写 project.description（供 job2 run_brainstorm_generate 读 idea 拼 prompt）。"""
        await self.session.execute(
            update(Project).where(Project.id == project_id).values(description=description)
        )


class ProjectRepositoryRepo:
    """project_repositories 表 CRUD（spec §5.3，D6）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: int,
        owner: str,
        repository: str,
        sub_path: str,
        default_branch: str = "main",
    ) -> ProjectRepository:
        row = ProjectRepository(
            project_id=project_id,
            provider="github",
            owner=owner,
            repository=repository,
            sub_path=sub_path,
            default_branch=default_branch,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_project(self, project_id: int) -> Optional[ProjectRepository]:
        return (
            await self.session.execute(
                select(ProjectRepository).where(
                    ProjectRepository.project_id == project_id
                )
            )
        ).scalar_one_or_none()

    async def set_branch(self, project_id: int, branch: Optional[str]) -> None:
        await self.session.execute(
            update(ProjectRepository)
            .where(ProjectRepository.project_id == project_id)
            .values(current_branch=branch)
        )

    async def set_last_sha(self, project_id: int, sha: str) -> None:
        await self.session.execute(
            update(ProjectRepository)
            .where(ProjectRepository.project_id == project_id)
            .values(last_commit_sha=sha)
        )


class GameBuildRepo:
    """game_builds 表 CRUD（Observability，design §21）。每次 build_game 调用一行。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
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
    ) -> GameBuild:
        row = GameBuild(
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
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_by_project(self, project_id: int) -> list[GameBuild]:
        return (
            await self.session.execute(
                select(GameBuild)
                .where(GameBuild.project_id == project_id)
                .order_by(GameBuild.id)
            )
        ).scalars().all()


class GameObservationRepo:
    """game_observations 表 CRUD（Observability，Phase 耗时/Token 聚合源）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
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
        langfuse_trace_id: Optional[str] = None,
        langfuse_observation_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
    ) -> GameObservation:
        row = GameObservation(
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
            meta=metadata,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
            started_at=started_at,
            ended_at=ended_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_by_project(self, project_id: int) -> list[GameObservation]:
        return (
            await self.session.execute(
                select(GameObservation)
                .where(GameObservation.project_id == project_id)
                .order_by(GameObservation.id)
            )
        ).scalars().all()
