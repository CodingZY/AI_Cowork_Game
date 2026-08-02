"""系统提示词必须编码 brainstorming 方法论与输出契约。"""
from agents.prompts import DESIGN_SYSTEM_PROMPT


def test_prompt_has_methodology_rules():
    for kw in ["一次只问一个", "2-3", "方案", "推荐", "分节", "确认"]:
        assert kw in DESIGN_SYSTEM_PROMPT, f"缺方法论语: {kw}"


def test_prompt_has_output_contract():
    for kw in ["game-design.md", "设计总览", "存档持久化", "经济平衡", "中文"]:
        assert kw in DESIGN_SYSTEM_PROMPT, f"缺输出契约语: {kw}"


def test_prompt_uses_ask_user_and_write_file():
    assert "ask_user" in DESIGN_SYSTEM_PROMPT and "write_file" in DESIGN_SYSTEM_PROMPT
