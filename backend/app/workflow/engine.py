from __future__ import annotations

from app.workflow.states import ProjectStatus


class WorkflowBlocked(Exception):
    pass


def assert_can_finalize(status: ProjectStatus | str) -> None:
    """仅 COMPLETED 可 finalize（Temporal GameDesignWorkflow 完成后落 git）。

    Phase3a：状态门从旧 GDD_APPROVED 改 COMPLETED（Temporal Workflow
    check_gdd PASS/WARNING → COMPLETED，finalize 是后续 git 落库步骤）。
    """
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot finalize from {status!r}")
    if current is not ProjectStatus.COMPLETED:
        raise WorkflowBlocked(f"cannot finalize from {current}")
