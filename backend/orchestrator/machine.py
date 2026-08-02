"""状态机纯逻辑：负责阶段转移与闸判定，不直接碰数据库。调用方据返回值落库。"""
from dataclasses import dataclass
from .states import Stage, StageStatus


@dataclass
class RunState:
    id: str
    stage: Stage
    status: StageStatus


@dataclass
class Transition:
    stage: Stage
    status: StageStatus


class StateMachine:
    """S1 阶段实现 start_design/complete_design/approve/reject；其余阶段由后续计划扩展。"""

    def start_design(self, run: RunState) -> Transition:
        return Transition(Stage.S1_design, StageStatus.running)

    def complete_design(self, run: RunState) -> Transition:
        # 设计产物就绪，停在阶段闸等用户确认
        return Transition(Stage.S1_design, StageStatus.awaiting_approval)

    def approve(self, run: RunState, *, stage: Stage) -> Transition | None:
        if run.stage != stage or run.status != StageStatus.awaiting_approval:
            return None
        if stage == Stage.S1_design:
            # Art 阶段尚未实现
            return Transition(Stage.S2_art_plan, StageStatus.not_implemented)
        return None

    def reject(self, run: RunState, *, stage: Stage, feedback: str) -> Transition | None:
        if run.stage != stage or run.status != StageStatus.awaiting_approval:
            return None
        # 不通过 → 回到 design 重新跑（带反馈）
        return Transition(Stage.S1_design, StageStatus.running)
