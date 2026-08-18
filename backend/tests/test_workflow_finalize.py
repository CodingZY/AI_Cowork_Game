from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import assert_can_finalize, WorkflowBlocked


def test_completed_member_exists():
    assert ProjectStatus("COMPLETED") == ProjectStatus.COMPLETED


def test_can_finalize_from_completed():
    assert_can_finalize(ProjectStatus.COMPLETED)  # 不抛


def test_cannot_finalize_from_created():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.CREATED)


def test_cannot_finalize_from_waiting_user():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.WAITING_USER)


def test_cannot_finalize_from_failed():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.FAILED)
