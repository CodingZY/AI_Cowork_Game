from __future__ import annotations

from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT


def test_brainstorm_prompt_has_write_instruction():
    assert "game-design.md" in BRAINSTORM_SYSTEM_PROMPT
    assert "Write" in BRAINSTORM_SYSTEM_PROMPT


def test_brainstorm_prompt_avoids_shell():
    # 规避审核：只用 Read/Write，不用 shell
    assert "shell" in BRAINSTORM_SYSTEM_PROMPT.lower()  # 文本里说明 do not run shell
    assert "Bash" not in BRAINSTORM_SYSTEM_PROMPT  # 不引导用 Bash


def test_brainstorm_prompt_is_nonempty_and_structured():
    assert len(BRAINSTORM_SYSTEM_PROMPT) > 100
    assert "Goal:" in BRAINSTORM_SYSTEM_PROMPT
    assert "Process:" in BRAINSTORM_SYSTEM_PROMPT
    assert "Rules:" in BRAINSTORM_SYSTEM_PROMPT
