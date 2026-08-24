from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    """project.status 真相（由 Temporal workflow 经 update_project_status activity 回写）。

    Phase 1（GameDesignWorkflow）：
    CREATED → ANALYZING → WAITING_USER → GENERATING_GDD → CHECKING_GDD
    → COMPLETED（PASS/WARNING）/ 回 WAITING_USER（BLOCKING）/ FAILED。
    Phase 2（ArtPipelineWorkflow）：
    ART_PIPELINE → ART_DONE（COMPLETED）/ ART_FAILED（FAILED）。

    前端 mapStatusToStage 据此映射到 EngineStage 决定跳转页。
    """

    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    WAITING_USER = "WAITING_USER"
    GENERATING_GDD = "GENERATING_GDD"
    CHECKING_GDD = "CHECKING_GDD"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    # Phase 2
    ART_PIPELINE = "ART_PIPELINE"
    ART_DONE = "ART_DONE"
    ART_FAILED = "ART_FAILED"
