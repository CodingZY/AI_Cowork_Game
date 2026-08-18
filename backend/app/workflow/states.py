from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    """Temporal 版状态（阶段1 GameDesignWorkflow 可观察阶段）。

    CREATED → ANALYZING（analyze_idea）→ WAITING_USER（逐题 Signal）
    → GENERATING_GDD（synthesize+generate）→ CHECKING_GDD（check_gdd）
    → COMPLETED（PASS/WARNING）/ 回 WAITING_USER（BLOCKING）；FAILED 兜底。
    """

    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    WAITING_USER = "WAITING_USER"
    GENERATING_GDD = "GENERATING_GDD"
    CHECKING_GDD = "CHECKING_GDD"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
