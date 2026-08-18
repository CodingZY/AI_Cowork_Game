from __future__ import annotations

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "game-skills" / "skills"


def _read(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_json():
    p = SKILLS.parent / ".claude-plugin" / "plugin.json"
    import json
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["name"] == "game-skills"


def test_brainstorm_skill_constraints():
    s = _read("game-brainstorm")  # Temporal 新名（不带 02 前缀）
    assert "QuestionPlan" in s or "question" in s.lower()
    assert "impact" in s  # 选项带影响
    assert "priority" in s
    assert "JSON" in s or "json" in s


def test_gdd_generator_skill_constraints():
    s = _read("gdd-generator")  # Temporal 新名（不带 03 前缀）
    assert "Snapshot" in s or "Requirements" in s
    assert "GDD.md" in s
    assert "Do NOT re-interpret" in s or "不重新" in s


def test_gdd_check_skill_constraints():
    s = _read("gdd-check")  # Temporal 新名（不带 04 前缀）
    assert "PASS" in s and "WARNING" in s and "BLOCKING" in s
    assert "JSON" in s or "json" in s


def test_game_requirements_skill_constraints():
    s = _read("game-requirements")
    assert "Snapshot" in s or "Requirements" in s
    assert "不调" in s or "not call" in s.lower() or "纯" in s
