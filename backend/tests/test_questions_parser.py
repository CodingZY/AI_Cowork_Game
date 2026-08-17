from __future__ import annotations

from app.agent.questions_parser import parse_questions


def test_parse_single_question_with_options():
    text = "1. 目标平台是什么？(A)手机移动端 (B)PC端 (C)PC/网页多平台"
    qs = parse_questions(text)
    assert len(qs) == 1
    assert qs[0]["id"] == "1"
    assert qs[0]["question"] == "目标平台是什么？"
    assert qs[0]["options"] == ["手机移动端", "PC端", "PC/网页多平台"]


def test_parse_multiple_questions():
    text = """1. 目标平台？(A)手机 (B)PC (C)网页
2. 核心玩法？(A)纯农场经营 (B)农场+RPG (C)农场+社交
4. 单人还是多人？(A)纯单人 (B)单人+访客 (C)多人社交为主"""
    qs = parse_questions(text)
    assert len(qs) == 3
    assert qs[0]["id"] == "1"
    assert qs[1]["id"] == "2"
    assert qs[2]["id"] == "4"  # 编号可不连续
    assert qs[1]["options"] == ["纯农场经营", "农场+RPG", "农场+社交"]


def test_parse_question_without_options():
    """问题无选项 → options=[]（前端自由文本答）。"""
    text = "1. 你希望游戏的核心体验是什么？"
    qs = parse_questions(text)
    assert len(qs) == 1
    assert qs[0]["question"] == "你希望游戏的核心体验是什么？"
    assert qs[0]["options"] == []


def test_parse_empty_or_garbage():
    assert parse_questions("") == []
    assert parse_questions("这是一段没有问题的文本") == []
    assert parse_questions("随机废话\n更多废话") == []


def test_parse_strips_whitespace_and_noise():
    """kimi-k3 可能加前言/后语，只取问题行。"""
    text = """好的，以下是需要澄清的问题：

1. 平台？(A)手机 (B)PC
2. 风格？(A)像素 (B)卡通

希望这些帮助你了解。"""
    qs = parse_questions(text)
    assert len(qs) == 2
    assert qs[0]["question"] == "平台？"
