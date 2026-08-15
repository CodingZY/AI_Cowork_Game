from __future__ import annotations

from app.workflow.states import ProjectStatus


class WorkflowBlocked(Exception):
    pass


def assert_can_brainstorm(status: ProjectStatus | str) -> None:
    """Assert that the workflow is in a state that allows brainstorming.

    Accepts either a ``ProjectStatus`` member or its string value (as
    produced by ORM columns). Invalid strings are normalized via
    ``ProjectStatus(value)`` and surfaced as ``WorkflowBlocked``.
    """
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot brainstorm from {status!r}")
    if current not in (ProjectStatus.CREATED, ProjectStatus.BRAINSTORMING):
        raise WorkflowBlocked(f"cannot brainstorm from {current}")


def assert_can_finalize(status: ProjectStatus | str) -> None:
    """仅 BRAINSTORMING 可 finalize（定稿落 git）。其余状态抛 WorkflowBlocked。"""
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot finalize from {status!r}")
    if current is not ProjectStatus.BRAINSTORMING:
        raise WorkflowBlocked(f"cannot finalize from {current}")
