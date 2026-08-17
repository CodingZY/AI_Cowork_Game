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
    s = _read("02-game-brainstorm")
    assert "(A)" in s  # 带选项格式
    assert "问题" in s
    assert "Do NOT write" in s or "不落" in s  # 不写文件


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
