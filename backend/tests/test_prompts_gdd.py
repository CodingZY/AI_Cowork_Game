from __future__ import annotations

from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT, GDD_GEN_SYSTEM_PROMPT, GDD_CHECK_SYSTEM_PROMPT


def test_gdd_gen_prompt_constraints():
    assert "03-gdd-generator" in GDD_GEN_SYSTEM_PROMPT
    assert ".brainstorm-concept.md" in GDD_GEN_SYSTEM_PROMPT
    assert "GDD.md" in GDD_GEN_SYSTEM_PROMPT
    assert "gdd-manifest.json" in GDD_GEN_SYSTEM_PROMPT


def test_gdd_check_prompt_constraints():
    assert "04-gdd-check" in GDD_CHECK_SYSTEM_PROMPT
    assert "PASS" in GDD_CHECK_SYSTEM_PROMPT
    assert "FAIL" in GDD_CHECK_SYSTEM_PROMPT
