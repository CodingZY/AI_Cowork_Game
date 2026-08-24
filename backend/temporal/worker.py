from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from temporal.client import get_client
from temporal.workflows import GameDesignWorkflow, ArtPipelineWorkflow, GameDevelopmentWorkflow
from temporal.activities import (
    analyze_idea,
    synthesize_requirements,
    generate_gdd,
    check_gdd,
    generate_clarification,
    # Phase 2
    generate_art_style,
    generate_asset_spec,
    validate_asset_specs,
    generate_prompts,
    generate_image,
    post_process_asset,
    validate_asset,
    run_consistency_check,
    count_final_assets,
    update_project_status,
    # Phase 3
    generate_architecture,
    plan_versions,
    freeze_shared_api,
    generate_contracts,
    validate_contracts,
    execute_codegen_wave,
    count_codegen_waves,
    typecheck,
    fix_codegen_wave,
    build_game,
    deploy_game,
    read_version_plan,
)
from app.config.settings import get_settings


async def run_worker():
    """起 Temporal Worker：注册 GameDesignWorkflow + ArtPipelineWorkflow + GameDevelopmentWorkflow + activities。"""
    s = get_settings()
    client = await get_client()
    worker = Worker(
        client,
        task_queue=s.temporal_task_queue,
        workflows=[GameDesignWorkflow, ArtPipelineWorkflow, GameDevelopmentWorkflow],
        activities=[
            analyze_idea,
            synthesize_requirements,
            generate_gdd,
            check_gdd,
            generate_clarification,
            # Phase 2：美术资产链路
            generate_art_style,
            generate_asset_spec,
            validate_asset_specs,
            generate_prompts,
            generate_image,
            post_process_asset,
            validate_asset,
            run_consistency_check,
            count_final_assets,
            update_project_status,
            # Phase 3：游戏开发链路
            generate_architecture,
            plan_versions,
            freeze_shared_api,
            generate_contracts,
            validate_contracts,
            execute_codegen_wave,
            count_codegen_waves,
            typecheck,
            fix_codegen_wave,
            build_game,
            deploy_game,
            read_version_plan,
        ],
    )
    print(f"Temporal Worker started on queue={s.temporal_task_queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
