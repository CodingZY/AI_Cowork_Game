"""状态机转移与闸逻辑测试。"""
from orchestrator.states import Stage, StageStatus
from orchestrator.machine import StateMachine, RunState


def test_start_design():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S0_init, status=StageStatus.running)
    t = sm.start_design(run)
    assert t.stage == Stage.S1_design and t.status == StageStatus.running


def test_complete_design_holds_gate():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S1_design, status=StageStatus.running)
    t = sm.complete_design(run)
    assert t.stage == Stage.S1_design and t.status == StageStatus.awaiting_approval


def test_approve_design_advances_to_art_plan_not_implemented():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S1_design, status=StageStatus.awaiting_approval)
    t = sm.approve(run, stage=Stage.S1_design)
    # S2 尚未实现，标记为 not_implemented
    assert t.stage == Stage.S2_art_plan and t.status == StageStatus.not_implemented


def test_reject_design_back_to_revising():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S1_design, status=StageStatus.awaiting_approval)
    t = sm.reject(run, stage=Stage.S1_design, feedback="再加一个钓鱼系统")
    assert t.stage == Stage.S1_design and t.status == StageStatus.running


def test_cannot_approve_wrong_stage():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S0_init, status=StageStatus.running)
    t = sm.approve(run, stage=Stage.S1_design)
    assert t is None  # 状态不匹配，拒绝转移
