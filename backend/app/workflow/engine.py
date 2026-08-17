from __future__ import annotations

from app.workflow.states import ProjectStatus


class WorkflowBlocked(Exception):
    pass


def assert_can_brainstorm(status: ProjectStatus | str) -> None:
    """Assert that the workflow is in a state that allows brainstorming.

    Accepts either a ``ProjectStatus`` member or its string value (as
    produced by ORM columns). Invalid strings are normalized via
    ``ProjectStatus(value)`` and surfaced as ``WorkflowBlocked``.

    Phase 3a：允许 CREATED/BRAINSTORMING/GDD_REVIEW（多轮改 GDD）；
    GDD_APPROVED/BRAINSTORMED/FAILED 不可。
    """
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot brainstorm from {status!r}")
    if current not in (ProjectStatus.CREATED, ProjectStatus.BRAINSTORMING, ProjectStatus.GDD_REVIEW):
        raise WorkflowBlocked(f"cannot brainstorm from {current}")


def assert_can_finalize(status: ProjectStatus | str) -> None:
    """仅 GDD_APPROVED 可 finalize（doc §84 Hard Gate，D8：Phase2 的 BRAINSTORMING 门升级）。"""
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot finalize from {status!r}")
    if current is not ProjectStatus.GDD_APPROVED:
        raise WorkflowBlocked(f"cannot finalize from {current}")


def assert_can_gdd_check(status: ProjectStatus | str) -> None:
    """GDD_REVIEW 或 GDD_CHECKING 可跑 04-gdd-check。

    GDD_CHECKING 是 approve 端点置的「check 即将跑」状态（spec §5.5：
    approve→置 GDD_CHECKING→enqueue run_gdd_check）——run_gdd_check 从
    GDD_CHECKING 继续合法。approve 端点自身已校验从 GDD_REVIEW 来，故
    允许 GDD_CHECKING 不会绕过门（重复 approve 被 409 挡）。
    """
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot gdd_check from {status!r}")
    if current not in (ProjectStatus.GDD_REVIEW, ProjectStatus.GDD_CHECKING):
        raise WorkflowBlocked(f"cannot gdd_check from {current}")
