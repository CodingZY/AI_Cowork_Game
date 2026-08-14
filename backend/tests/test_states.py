from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import assert_can_brainstorm, WorkflowBlocked


def test_can_brainstorm_from_created():
    assert_can_brainstorm(ProjectStatus.CREATED)  # 不抛


def test_can_brainstorm_from_brainstorming():
    assert_can_brainstorm(ProjectStatus.BRAINSTORMING)


def test_cannot_brainstorm_from_failed():
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm(ProjectStatus.FAILED)


def test_can_brainstorm_from_status_string():
    # ORM 返回的 status 是 str，assert_can_brainstorm 要能接受
    assert_can_brainstorm("CREATED")
    assert_can_brainstorm("BRAINSTORMING")


def test_cannot_brainstorm_from_bad_string():
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm("COMPLETED")
