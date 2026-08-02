"""Design 输出契约校验器测试。"""
from pathlib import Path
from agents.contract import validate_game_design, GAME_DESIGN_TEMPLATE


def _valid_doc() -> str:
    return (
        "# 我的游戏 游戏设计规格书\n\n"
        "## 0. 设计总览\n核心循环：种田→赚钱。\n\n"
        "## 1. 玩法系统A\n机制说明。\n\n"
        "## 2. 玩法系统B\n机制说明。\n\n"
        "## 3. 玩法系统C\n机制说明。\n\n"
        "## 10. 存档持久化\n字段列表。\n\n"
        "## 11. 经济平衡结论\n基准假设。\n"
    )


def test_valid_doc_passes():
    ok, reasons = validate_game_design(_valid_doc())
    assert ok, reasons


def test_missing_overview_fails():
    doc = _valid_doc().replace("## 0. 设计总览\n核心循环：种田→赚钱。\n\n", "")
    ok, reasons = validate_game_design(doc)
    assert not ok and any("总览" in r for r in reasons)


def test_missing_persist_fails():
    doc = _valid_doc().replace("## 10. 存档持久化\n字段列表。\n\n", "")
    ok, reasons = validate_game_design(doc)
    assert not ok and any("存档" in r for r in reasons)


def test_missing_economy_fails():
    doc = _valid_doc().replace("## 11. 经济平衡结论\n基准假设。\n", "")
    ok, reasons = validate_game_design(doc)
    assert not ok and any("经济" in r or "平衡" in r for r in reasons)


def test_too_few_sections_fails():
    doc = "# X 游戏设计规格书\n\n## 0. 设计总览\na\n\n## 10. 存档持久化\nb\n\n## 11. 经济平衡结论\nc\n"
    ok, reasons = validate_game_design(doc)
    assert not ok and any("玩法系统" in r for r in reasons)


def test_reference_fixture_passes():
    """顶层 game-design-spec.md（Farmer）作为测试夹具，必须通过契约校验。"""
    fixture = Path(__file__).resolve().parents[2] / "game-design-spec.md"
    ok, reasons = validate_game_design(fixture.read_text(encoding="utf-8"))
    assert ok, f"参考交付物未通过契约校验: {reasons}"


def test_template_is_markdown_with_sections():
    assert "# " in GAME_DESIGN_TEMPLATE
    assert "设计总览" in GAME_DESIGN_TEMPLATE and "存档持久化" in GAME_DESIGN_TEMPLATE
