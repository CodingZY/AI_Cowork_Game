from __future__ import annotations

from app.agent.prompts import (
    BRAINSTORM_SYSTEM_PROMPT,
    GDD_BRAINSTORM_QUESTIONS_PROMPT,
    GDD_GEN_SYSTEM_PROMPT,
    GDD_GEN_FROM_ANSWERS_PROMPT,
    GDD_CHECK_SYSTEM_PROMPT,
)


def test_gdd_gen_prompt_constraints():
    # 旧 GDD_GEN_SYSTEM_PROMPT 保留（Phase 1/2 兼容，不删）
    assert "03-gdd-generator" in GDD_GEN_SYSTEM_PROMPT
    assert ".brainstorm-concept.md" in GDD_GEN_SYSTEM_PROMPT
    assert "GDD.md" in GDD_GEN_SYSTEM_PROMPT
    assert "gdd-manifest.json" in GDD_GEN_SYSTEM_PROMPT


def test_gdd_gen_from_answers_prompt_constraints():
    # Phase3a 新：03 读 answers 生成 GDD
    assert "03-gdd-generator" in GDD_GEN_FROM_ANSWERS_PROMPT
    assert "answers" in GDD_GEN_FROM_ANSWERS_PROMPT.lower()
    assert "GDD.md" in GDD_GEN_FROM_ANSWERS_PROMPT
    assert "gdd-manifest.json" in GDD_GEN_FROM_ANSWERS_PROMPT


def test_gdd_brainstorm_questions_prompt_constraints():
    # Phase3a 新：02 产出带选项问题（格式后端解析）
    assert "02-game-brainstorm" in GDD_BRAINSTORM_QUESTIONS_PROMPT
    assert "(A)" in GDD_BRAINSTORM_QUESTIONS_PROMPT
    assert "问题" in GDD_BRAINSTORM_QUESTIONS_PROMPT


def test_gdd_check_prompt_constraints():
    assert "04-gdd-check" in GDD_CHECK_SYSTEM_PROMPT
    assert "PASS" in GDD_CHECK_SYSTEM_PROMPT
    assert "FAIL" in GDD_CHECK_SYSTEM_PROMPT
