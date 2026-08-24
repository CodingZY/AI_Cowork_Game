from __future__ import annotations

import asyncio

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import AnswerSignal, GameDesignWorkflow


# --- Mock activities -----------------------------------------------------------
# Workflow 用字符串名调 Activity（execute_activity("analyze_idea", ...)），
# 故 mock 必须以被调用的名字注册（@activity.defn(name=...)），否则 worker 注册名
# "mock_analyze_idea" 与 workflow 调用名 "analyze_idea" 不匹配。
@activity.defn(name="analyze_idea")
async def mock_analyze_idea(idea: str) -> list[dict]:
    return [
        {
            "id": "camera",
            "category": "camera",
            "question": "视角？",
            "type": "single_choice",
            "options": [
                {"id": "top_down", "label": "俯视"},
                {"id": "side", "label": "横版"},
            ],
            "required": True,
            "priority": "blocking",
        },
        {
            "id": "core_loop",
            "category": "core_loop",
            "question": "核心玩法？",
            "type": "single_choice",
            "options": [{"id": "farming", "label": "种田"}],
            "required": True,
            "priority": "blocking",
        },
    ]


@activity.defn(name="synthesize_requirements")
async def mock_synthesize_requirements(qp, answers) -> dict:
    return {
        "game": {"camera": answers.get("camera", "top_down")},
        "core_loop": ["plant", "harvest"],
        "v1": {},
        "decisions": [],
        "assumptions": [],
    }


@activity.defn(name="generate_gdd")
async def mock_generate_gdd(req) -> str:
    return "# GDD\n"


@activity.defn(name="check_gdd")
async def mock_check_gdd(gdd) -> dict:
    return {"status": "PASS", "blocking": [], "warnings": []}


@activity.defn(name="update_project_status")
async def mock_update_project_status(status: str) -> None:
    pass


MOCK_ACTIVITIES = [
    mock_analyze_idea,
    mock_synthesize_requirements,
    mock_generate_gdd,
    mock_check_gdd,
    mock_update_project_status,
]


async def _wait_until(handle, predicate, timeout: float = 5.0) -> dict:
    """轮询 get_design_state 直到 predicate 为真，避免初始/信号竞态。"""
    step = 0.05
    elapsed = 0.0
    state: dict = {}
    while elapsed < timeout:
        state = await handle.query(GameDesignWorkflow.get_design_state)
        if predicate(state):
            return state
        await asyncio.sleep(step)
        elapsed += step
    return state  # 超时返回最后状态，让断言给出真实值


async def test_workflow_signal_advances_questions():
    """Signal submit_answer 逐题推进，答完→synthesize→gdd→GDD_REVIEW→save_gdd→check→COMPLETED。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[GameDesignWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                GameDesignWorkflow.run,
                "种田游戏",
                id="game-test-1",
                task_queue="test-queue",
            )
            # 初始：WAITING_USER，0/2
            state = await _wait_until(handle, lambda s: s["phase"] == "WAITING_USER")
            assert state["phase"] == "WAITING_USER"
            assert state["progress"]["answered"] == 0
            assert state["progress"]["total"] == 2
            # 答 camera
            await handle.signal(
                GameDesignWorkflow.submit_answer,
                AnswerSignal(question_id="camera", answer="top_down"),
            )
            state = await _wait_until(handle, lambda s: s["progress"]["answered"] == 1)
            assert state["progress"]["answered"] == 1
            # 答 core_loop
            await handle.signal(
                GameDesignWorkflow.submit_answer,
                AnswerSignal(question_id="core_loop", answer="farming"),
            )
            # 答完→生成 GDD→暂停在 GDD_REVIEW，需 save_gdd signal 放行
            await _wait_until(handle, lambda s: s["phase"] == "GDD_REVIEW")
            await handle.signal(GameDesignWorkflow.save_gdd, "# GDD\n")
            result = await handle.result()
            assert result["check"]["status"] == "PASS"
            final = await handle.query(GameDesignWorkflow.get_design_state)
            assert final["phase"] == "COMPLETED"
    finally:
        await env.shutdown()


async def test_workflow_skip_uses_default():
    """skip_question 跳过题（用 default_option 或留空），仍推进到 COMPLETED。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[GameDesignWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                GameDesignWorkflow.run,
                "test",
                id="game-skip-1",
                task_queue="test-queue",
            )
            await _wait_until(handle, lambda s: s["phase"] == "WAITING_USER")
            # 跳过 camera（无 default_option，留空），再答 core_loop
            await handle.signal(GameDesignWorkflow.skip_question, "camera")
            await handle.signal(
                GameDesignWorkflow.submit_answer,
                AnswerSignal(question_id="core_loop", answer="farming"),
            )
            # 答完→GDD_REVIEW→save_gdd 放行→check→COMPLETED
            await _wait_until(handle, lambda s: s["phase"] == "GDD_REVIEW")
            await handle.signal(GameDesignWorkflow.save_gdd, "# GDD\n")
            result = await handle.result()
            assert result["check"]["status"] == "PASS"
    finally:
        await env.shutdown()
