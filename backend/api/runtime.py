"""后台 agent 任务管理：启动 Design Agent 并把进度/问答接到 broker。"""
import re
from api.broker import broker
from api.deps import DESIGN_MODEL, BASE_URL, AUTH_TOKEN, games_root, _session_factory
from persistence.repo import update_stage, create_approval
from orchestrator.states import Stage, StageStatus
from agents.runner import run_design_agent

__all__ = ["start_design"]


def _slug(name: str) -> str:
    s = re.sub(r"[^\w一-龥]+", "-", name.strip().lower()).strip("-")
    return s or "game"


async def start_design(run_id: str, game_name: str, *, feedback: str | None = None) -> None:
    """启动 Design Agent；完成后把阶段置为 awaiting_approval 并创建待审批。"""
    game_root = games_root() / _slug(game_name)
    prompt = f"请为游戏《{game_name}》进行需求确认。" + (
        f"\n用户对上一版设计的反馈：{feedback}\n请据此修改。" if feedback else ""
    )

    async def ask(question, options):
        return await broker.register_question(run_id, "q", question, options or [])

    async def on_progress(msg):
        broker.publish(run_id, {"type": "progress", **msg})

    try:
        await run_design_agent(
            game_root, ask=ask, on_progress=on_progress,
            model=DESIGN_MODEL, base_url=BASE_URL, auth_token=AUTH_TOKEN, prompt=prompt,
        )
        async with _session_factory() as session:
            await update_stage(session, run_id, stage=Stage.S1_design.value, status=StageStatus.awaiting_approval.value)
            await create_approval(session, run_id, stage=Stage.S1_design.value, payload={"doc": "docs/game-design.md"})
        broker.publish(run_id, {"type": "gate", "stage": "S1_design", "status": "awaiting_approval"})
    except Exception as e:
        broker.publish(run_id, {"type": "error", "message": str(e)})
        raise
