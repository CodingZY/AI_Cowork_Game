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
    """仅 GDD_REVIEW 可跑 04-gdd-check。"""
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot gdd_check from {status!r}")
    if current is not ProjectStatus.GDD_REVIEW:
        raise WorkflowBlocked(f"cannot gdd_check from {current}")
