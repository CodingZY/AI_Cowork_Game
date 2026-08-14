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
