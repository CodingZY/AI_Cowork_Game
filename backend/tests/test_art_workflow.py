from __future__ import annotations

import asyncio

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import ArtPipelineWorkflow, RetryAssetSignal


# --- Mock activities（名字对齐 workflow 调用名）---------------------------


@activity.defn(name="generate_art_style")
async def mock_generate_art_style() -> str:
    return "# ART_STYLE\n\n[STYLE_ANCHOR]\ncute farm game\n"


@activity.defn(name="generate_asset_spec")
async def mock_generate_asset_spec() -> list[dict]:
    return [
        {"asset_id": "ANIMAL-001", "name": "cow", "category": "animal", "required": True,
         "source": {"gdd_entity": "animal.cow"}, "visual": {}, "generation": {},
         "post_process": {"remove_background": True, "crop": True, "resize": True, "format": "png"},
         "output": {}},
        {"asset_id": "PLANT-001", "name": "apple_tree", "category": "plant", "required": True,
         "source": {"gdd_entity": "plant.apple_tree"}, "visual": {}, "generation": {},
         "post_process": {"remove_background": True}, "output": {}},
    ]


@activity.defn(name="validate_asset_specs")
async def mock_validate_asset_specs(assets) -> dict:
    return {"ok": True, "issues": [], "count": len(assets)}


@activity.defn(name="generate_prompts")
async def mock_generate_prompts() -> dict:
    return {"ok": True, "count": 2}


@activity.defn(name="generate_image")
async def mock_generate_image(asset_id: str) -> dict:
    return {"asset_id": asset_id, "status": "GENERATED", "image_path": f"raw/{asset_id}.png", "seed": 0}


@activity.defn(name="post_process_asset")
async def mock_post_process_asset(asset_id: str) -> dict:
    return {"asset_id": asset_id, "status": "PROCESSED",
            "processed_path": f"processed/{asset_id}.png", "final_path": f"final/{asset_id}.png"}


@activity.defn(name="validate_asset")
async def mock_validate_asset(asset_id: str) -> dict:
    return {"asset_id": asset_id, "status": "PASSED", "issues": []}


@activity.defn(name="run_consistency_check")
async def mock_run_consistency_check() -> str:
    return "# Art Report\nTotal: 2 Passed: 2\n"


@activity.defn(name="update_project_status")
async def mock_update_project_status(status: str) -> None:
    pass


@activity.defn(name="count_final_assets")
async def mock_count_final_assets() -> int:
    return 0  # 默认无 final → 停 SPEC_REVIEW 等用户点「生成图片」


@activity.defn(name="count_final_assets")
async def mock_count_final_assets_full() -> int:
    return 2  # 断点恢复：final 全在 → 自动放行 SPEC_REVIEW


MOCK_ACTIVITIES = [
    mock_generate_art_style, mock_generate_asset_spec, mock_validate_asset_specs,
    mock_generate_prompts, mock_generate_image, mock_post_process_asset,
    mock_validate_asset, mock_run_consistency_check, mock_update_project_status,
    mock_count_final_assets,
]


async def _wait_until(handle, predicate, timeout=15.0):
    import time
    elapsed = 0.0
    step = 0.05
    while elapsed < timeout:
        state = await handle.query(ArtPipelineWorkflow.get_art_state)
        if predicate(state):
            return state
        await asyncio.sleep(step)
        elapsed += step
    return state


async def test_art_pipeline_completes_after_approve():
    """完整链路：起 workflow → 走到 ART_REVIEW → approve → COMPLETED，资产全 PASSED。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client, task_queue="test-art-queue",
            workflows=[ArtPipelineWorkflow], activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                ArtPipelineWorkflow.run, 4, id="art-test-1", task_queue="test-art-queue",
            )
            # 等到 SPEC_REVIEW（art-style+asset-spec+prompts 完，暂停等 start_generation）
            state = await _wait_until(handle, lambda s: s["phase"] == "SPEC_REVIEW")
            assert state["phase"] == "SPEC_REVIEW"
            assert state["progress"]["total"] == 2
            # 触发生图 → GENERATING_ASSETS → ART_REVIEW
            await handle.signal(ArtPipelineWorkflow.start_generation)
            state = await _wait_until(handle, lambda s: s["phase"] == "ART_REVIEW")
            assert state["phase"] == "ART_REVIEW"
            assert state["progress"]["passed"] == 2
            assert state["progress"]["failed"] == 0
            # approve → COMPLETED
            await handle.signal(ArtPipelineWorkflow.approve_report)
            result = await handle.result()
            assert result["art_report"].startswith("# Art Report")
            assert result["asset_status"]["ANIMAL-001"]["status"] == "PASSED"
            assert result["asset_status"]["PLANT-001"]["status"] == "PASSED"
            final = await handle.query(ArtPipelineWorkflow.get_art_state)
            assert final["phase"] == "COMPLETED"
    finally:
        await env.shutdown()


async def test_spec_review_pause_until_start_generation():
    """SPEC_REVIEW 暂停点：art-style/spec/prompts 完后停下，不发 start_generation 则不进 GENERATING_ASSETS。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client, task_queue="test-art-queue3",
            workflows=[ArtPipelineWorkflow], activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                ArtPipelineWorkflow.run, 4, id="art-test-3", task_queue="test-art-queue3",
            )
            state = await _wait_until(handle, lambda s: s["phase"] == "SPEC_REVIEW")
            assert state["phase"] == "SPEC_REVIEW"
            # 不发 start_generation，等一会确认仍停在 SPEC_REVIEW
            await asyncio.sleep(0.3)
            still = await handle.query(ArtPipelineWorkflow.get_art_state)
            assert still["phase"] == "SPEC_REVIEW"
            assert still["progress"]["passed"] == 0  # 还没生图
            # 发 start_generation 后才推进
            await handle.signal(ArtPipelineWorkflow.start_generation)
            state = await _wait_until(handle, lambda s: s["phase"] == "ART_REVIEW")
            assert state["phase"] == "ART_REVIEW"
    finally:
        await env.shutdown()


# --- 单资产失败不阻塞整体的测试 ---------------------------------------------
# 用 validate_asset 返 FAILED（而非 generate_image 抛错）测"单资产失败但 workflow 不崩"，
# 避免 RetryPolicy 重试耗尽的时序在 time-skipping 环境下不可控。


@activity.defn(name="validate_asset")
async def mock_validate_asset_fail_animal(asset_id: str) -> dict:
    if asset_id == "ANIMAL-001":
        return {"asset_id": asset_id, "status": "FAILED", "issues": ["simulated bad alpha"]}
    return {"asset_id": asset_id, "status": "PASSED", "issues": []}


MOCK_FAIL_ACTIVITIES = [
    mock_generate_art_style, mock_generate_asset_spec, mock_validate_asset_specs,
    mock_generate_prompts, mock_generate_image, mock_post_process_asset,
    mock_validate_asset_fail_animal, mock_run_consistency_check, mock_update_project_status,
    mock_count_final_assets,
]


async def test_single_asset_failure_does_not_block_workflow():
    """一个资产 validate 返 FAILED → 该资产 FAILED，其余 PASSED，workflow 仍推进到 ART_REVIEW。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client, task_queue="test-art-queue2",
            workflows=[ArtPipelineWorkflow], activities=MOCK_FAIL_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                ArtPipelineWorkflow.run, 4, id="art-test-2", task_queue="test-art-queue2",
            )
            # SPEC_REVIEW 暂停 → start_generation 触发生图
            await _wait_until(handle, lambda s: s["phase"] == "SPEC_REVIEW")
            await handle.signal(ArtPipelineWorkflow.start_generation)
            state = await _wait_until(handle, lambda s: s["phase"] == "ART_REVIEW")
            # ANIMAL-001 validate 返 FAILED
            assert state["progress"]["failed"] == 1
            assert state["progress"]["passed"] == 1
            await handle.signal(ArtPipelineWorkflow.approve_report)
            result = await handle.result()
            assert result["asset_status"]["ANIMAL-001"]["status"] == "FAILED"
            assert result["asset_status"]["PLANT-001"]["status"] == "PASSED"
    finally:
        await env.shutdown()


# --- B7: SPEC_REVIEW 自动放行（断点恢复，final 全在则不停）---


MOCK_AUTO_SIGNAL_ACTIVITIES = [
    mock_generate_art_style, mock_generate_asset_spec, mock_validate_asset_specs,
    mock_generate_prompts, mock_generate_image, mock_post_process_asset,
    mock_validate_asset, mock_run_consistency_check, mock_update_project_status,
    mock_count_final_assets_full,
]


async def test_art_pipeline_auto_skips_spec_review_when_finals_exist():
    """B7 断点恢复：count_final_assets==total → 自动放行 SPEC_REVIEW，
    不需 signal start_generation，直接跑到 ART_REVIEW → approve → COMPLETED。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client, task_queue="test-art-auto",
            workflows=[ArtPipelineWorkflow], activities=MOCK_AUTO_SIGNAL_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                ArtPipelineWorkflow.run, 4, id="art-test-auto", task_queue="test-art-auto",
            )
            # 不发 start_generation，等自动放行到 ART_REVIEW
            state = await _wait_until(handle, lambda s: s["phase"] == "ART_REVIEW")
            assert state["phase"] == "ART_REVIEW"
            assert state["progress"]["passed"] == 2
            await handle.signal(ArtPipelineWorkflow.approve_report)
            result = await handle.result()
            assert result["art_report"].startswith("# Art Report")
    finally:
        await env.shutdown()
