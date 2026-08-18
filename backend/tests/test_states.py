from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import assert_can_finalize, WorkflowBlocked


def test_new_states_exist():
    """Phase3a Temporal 版 6+1 状态（CREATED/ANALYZING/WAITING_USER
    /GENERATING_GDD/CHECKING_GDD/COMPLETED + FAILED）。"""
    assert ProjectStatus("CREATED") == ProjectStatus.CREATED
    assert ProjectStatus("ANALYZING") == ProjectStatus.ANALYZING
    assert ProjectStatus("WAITING_USER") == ProjectStatus.WAITING_USER
    assert ProjectStatus("GENERATING_GDD") == ProjectStatus.GENERATING_GDD
    assert ProjectStatus("CHECKING_GDD") == ProjectStatus.CHECKING_GDD
    assert ProjectStatus("COMPLETED") == ProjectStatus.COMPLETED
    assert ProjectStatus("FAILED") == ProjectStatus.FAILED


def test_old_states_removed():
    """旧状态枚举已删（Phase3a Temporal 替代）。"""
    for old in ("BRAINSTORMING", "GDD_REVIEW", "GDD_CHECKING", "GDD_APPROVED", "BRAINSTORMED"):
        with pytest.raises(ValueError):
            ProjectStatus(old)


def test_can_finalize_from_completed():
    assert_can_finalize(ProjectStatus.COMPLETED)  # 不抛


def test_cannot_finalize_from_created():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.CREATED)


def test_cannot_finalize_from_failed():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.FAILED)


def test_cannot_finalize_from_waiting_user():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.WAITING_USER)


def test_can_finalize_from_status_string():
    # ORM 返回的 status 是 str，assert_can_finalize 要能接受
    assert_can_finalize("COMPLETED")


def test_cannot_finalize_from_bad_string():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize("BRAINSTORMING")
