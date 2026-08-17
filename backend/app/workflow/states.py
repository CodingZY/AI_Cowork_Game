from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    GDD_REVIEW = "GDD_REVIEW"
    GDD_CHECKING = "GDD_CHECKING"
    GDD_APPROVED = "GDD_APPROVED"
    BRAINSTORMED = "BRAINSTORMED"
    FAILED = "FAILED"
