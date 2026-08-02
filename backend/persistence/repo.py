"""仓储函数：对 GameRun/StageState/PendingApproval/PendingQuestion 的增查改。"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import GameRun, StageState, PendingApproval, PendingQuestion


async def create_run(session: AsyncSession, *, game_name: str, slug: str) -> GameRun:
    run = GameRun(id=slug, game_name=game_name, slug=slug, current_stage="S0_init", status="running")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: str) -> GameRun | None:
    return await session.get(GameRun, run_id)


async def list_runs(session: AsyncSession) -> list[GameRun]:
    res = await session.execute(select(GameRun).order_by(GameRun.created_at.desc()))
    return list(res.scalars().all())


async def update_stage(session: AsyncSession, run_id: str, *, stage: str, status: str) -> None:
    run = await session.get(GameRun, run_id)
    run.current_stage = stage
    run.status = status
    await session.commit()


async def create_approval(session: AsyncSession, run_id: str, *, stage: str, payload: dict) -> PendingApproval:
    ap = PendingApproval(run_id=run_id, stage=stage, payload=payload, status="pending")
    session.add(ap)
    await session.commit()
    await session.refresh(ap)
    return ap


async def resolve_approval(session: AsyncSession, approval_id: int, *, resolution: str, feedback: str | None) -> None:
    ap = await session.get(PendingApproval, approval_id)
    ap.status = resolution  # approved | rejected
    ap.feedback = feedback
    ap.resolved_at = datetime.utcnow()
    await session.commit()


async def get_pending_approval(session: AsyncSession, run_id: str, *, stage: str) -> PendingApproval | None:
    res = await session.execute(
        select(PendingApproval).where(PendingApproval.run_id == run_id, PendingApproval.stage == stage)
        .order_by(PendingApproval.created_at.desc())
    )
    return res.scalars().first()


async def create_question(session: AsyncSession, run_id: str, question_id: str, question_text: str, options: list) -> PendingQuestion:
    q = PendingQuestion(run_id=run_id, question_id=question_id, question_text=question_text, options=options, status="pending")
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q


async def answer_question(session: AsyncSession, question_id_pk: int, *, answer: str) -> None:
    q = await session.get(PendingQuestion, question_id_pk)
    q.answer = answer
    q.status = "answered"
    q.answered_at = datetime.utcnow()
    await session.commit()
