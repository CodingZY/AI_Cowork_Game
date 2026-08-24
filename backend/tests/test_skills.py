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


# --- Phase 2：4 个美术 Skill 约束 ---


def test_game_art_style_skill_constraints():
    s = _read("game-art-style")
    assert "ART_STYLE.md" in s
    assert "STYLE_ANCHOR" in s
    assert "inferred" in s.lower() or "推断" in s


def test_art_asset_spec_skill_constraints():
    s = _read("art-asset-spec")
    assert "asset_id" in s
    assert "assets.json" in s
    # 9 类别全提及
    for cat in ["character", "npc", "building", "animal", "plant", "prop", "map", "ui", "icon"]:
        assert cat in s, f"category {cat} missing"


def test_art_pipeline_skill_boundary():
    """art-pipeline 严格划界：只生 prompt，不生图不 rembg（Temporal Activity 做）。"""
    s = _read("art-pipeline")
    assert "prompts/" in s
    # 边界词：明确禁止生图/rembg
    assert "不" in s or "not" in s.lower()
    assert "rembg" in s.lower()
    assert "Temporal" in s or "activity" in s.lower()


def test_art_consistency_check_skill_constraints():
    s = _read("art-consistency-check")
    assert "ART_REPORT.md" in s
    for layer in ["Coverage", "Technical", "Visual"]:
        assert layer in s, f"layer {layer} missing"
