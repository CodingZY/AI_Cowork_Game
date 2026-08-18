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
    s = _read("03-gdd-generator")
    assert "GDD.md" in s
    assert "gdd-manifest.json" in s
    assert "answers" in s.lower() or "答案" in s
    assert "F001" in s  # manifest feature id
    assert "17 sections" in s or "Game Overview" in s  # 17节
    assert "acceptance" in s.lower()


def test_gdd_check_skill_constraints():
    s = _read("04-gdd-check")
    assert "PASS" in s
    assert "FAIL" in s
    assert "first line" in s or "line 1" in s  # 格式约束
    assert "17" in s  # 17节齐全


def test_game_requirements_skill_constraints():
    s = _read("game-requirements")
    assert "Snapshot" in s or "Requirements" in s
    assert "不调" in s or "not call" in s.lower() or "纯" in s
