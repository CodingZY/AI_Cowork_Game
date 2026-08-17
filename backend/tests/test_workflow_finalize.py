from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import assert_can_finalize, WorkflowBlocked


def test_brainstormed_member_exists():
    assert ProjectStatus("BRAINSTORMED") == ProjectStatus.BRAINSTORMED


def test_can_finalize_from_gdd_approved():
    assert_can_finalize(ProjectStatus.GDD_APPROVED)  # 不抛


def test_cannot_finalize_from_created():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.CREATED)


def test_cannot_finalize_from_brainstormed():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.BRAINSTORMED)


def test_cannot_finalize_from_failed():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.FAILED)


def test_assert_can_brainstorm_allows_brainstormed_false():
    # BRAINSTORMED 不可再 brainstorm（已定稿）
    from app.workflow.engine import assert_can_brainstorm
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm(ProjectStatus.BRAINSTORMED)
