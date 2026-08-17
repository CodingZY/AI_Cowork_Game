from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import (
    assert_can_finalize, assert_can_gdd_check, assert_can_brainstorm, WorkflowBlocked,
)


def test_gdd_states_exist():
    assert ProjectStatus("GDD_REVIEW") == ProjectStatus.GDD_REVIEW
    assert ProjectStatus("GDD_CHECKING") == ProjectStatus.GDD_CHECKING
    assert ProjectStatus("GDD_APPROVED") == ProjectStatus.GDD_APPROVED


def test_finalize_requires_gdd_approved():
    """D8：finalize 门从 BRAINSTORMING 改 GDD_APPROVED。"""
    assert_can_finalize(ProjectStatus.GDD_APPROVED)  # 不抛
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.BRAINSTORMING)  # 旧门现拒
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.CREATED)


def test_gdd_check_requires_gdd_review():
    """GDD_REVIEW 或 GDD_CHECKING 可跑 04（approve 端点置 GDD_CHECKING 后 enqueue）。"""
    assert_can_gdd_check(ProjectStatus.GDD_REVIEW)  # 不抛
    assert_can_gdd_check(ProjectStatus.GDD_CHECKING)  # approve 已置，check 继续
    with pytest.raises(WorkflowBlocked):
        assert_can_gdd_check(ProjectStatus.GDD_APPROVED)


def test_brainstorm_allows_gdd_review():
    """GDD_REVIEW 时可再 brainstorm 改 GDD（多轮修正）。"""
    assert_can_brainstorm(ProjectStatus.GDD_REVIEW)
    assert_can_brainstorm(ProjectStatus.CREATED)
    assert_can_brainstorm(ProjectStatus.BRAINSTORMING)


def test_brainstorm_blocked_from_approved():
    """GDD_APPROVED 不可再 brainstorm（已定稿，进 finalize）。"""
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm(ProjectStatus.GDD_APPROVED)
