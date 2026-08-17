from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_session import AgentSession
from app.models.brainstorm_questions import BrainstormQuestion
from app.models.event import Event
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


class AgentSessionRepo:
    """agent_sessions 表 CRUD 封装（spec §6.2）。

    claude_session_id 在 system/init 到来后回填（bind_claude_session）。
    last_claude_session 供 resume 用：取该 project+agent_type 最近一次 COMPLETED
    的 claude_session_id。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, project_id: int, agent_type: str, working_directory: str
    ) -> AgentSession:
        row = AgentSession(
            project_id=project_id,
            agent_type=agent_type,
            working_directory=working_directory,
            status="RUNNING",
            claude_session_id=None,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def bind_claude_session(self, id: int, claude_session_id: str) -> None:
        await self.session.execute(
            update(AgentSession)
            .where(AgentSession.id == id)
            .values(claude_session_id=claude_session_id)
        )

    async def finish(self, id: int, status: str) -> None:
        """结束 session：更新 status + last_message_at（DB server_side now）。"""
        await self.session.execute(
            update(AgentSession)
            .where(AgentSession.id == id)
            .values(status=status, last_message_at=func.now())
        )

    async def last_claude_session(
        self, project_id: int, agent_type: str
    ) -> Optional[str]:
        """resume 用：该 project+agent_type 最近一次 COMPLETED 的 claude_session_id。"""
        q = (
            select(AgentSession.claude_session_id)
            .where(
                AgentSession.project_id == project_id,
                AgentSession.agent_type == agent_type,
                AgentSession.status == "COMPLETED",
                AgentSession.claude_session_id.is_not(None),
            )
            .order_by(AgentSession.id.desc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalar_one_or_none()


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


class QuestionRepo:
    """brainstorm_questions 表 CRUD（spec §5.5）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: int, round: int, questions: list) -> BrainstormQuestion:
        row = BrainstormQuestion(project_id=project_id, round=round, questions=questions)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_latest(self, project_id: int) -> Optional[BrainstormQuestion]:
        q = (
            select(BrainstormQuestion)
            .where(BrainstormQuestion.project_id == project_id)
            .order_by(BrainstormQuestion.round.desc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalar_one_or_none()

    async def set_answers(self, project_id: int, round: int, answers: list) -> None:
        row = await self.get_latest(project_id)
        if row is not None:
            await self.session.execute(
                update(BrainstormQuestion)
                .where(BrainstormQuestion.id == row.id)
                .values(answers=answers)
            )
