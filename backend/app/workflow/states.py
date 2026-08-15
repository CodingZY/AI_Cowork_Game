from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    BRAINSTORMED = "BRAINSTORMED"
    FAILED = "FAILED"
