"""Design Agent 输出契约：从顶层 game-design-spec.md 提炼的 game-design.md 必备结构 + 校验器。"""
import re

# Design Agent 填充的骨架（通用，非 Farmer 专属）
GAME_DESIGN_TEMPLATE = """# <游戏名> 游戏设计规格书

> 技术栈：HTML + JavaScript + Phaser.js，浏览器可直接运行
> 中文撰写；每个系统给出机制/数值/解锁；每节有通俗易懂的功能说明

## 0. 设计总览
核心循环：___ → 终局目标：___
时间基准 / 节奏 / 高层设定。

## 1. <系统A名>
机制流程 / 体力消耗 / 数值表 / 解锁条件。

## 2. <系统B名>
...

## N. <系统…名>
...

## 存档持久化
玩家状态 / 时间 / 农场 / NPC / 进度 等待持久化字段。

## 经济平衡结论
基准假设 / 产能 / 结论。
"""


def validate_game_design(md: str) -> tuple[bool, list[str]]:
    """校验 game-design.md 是否满足 S1 交付契约。返回 (是否通过, 原因列表)。"""
    reasons: list[str] = []
    if not md or not md.strip():
        return False, ["内容为空"]
    if not md.lstrip().startswith("# "):
        reasons.append("缺少一级标题（游戏名）")
    # 二级标题
    h2 = re.findall(r"^##\s+(.+)$", md, flags=re.MULTILINE)
    h2_text = "\n".join(h2)
    if not re.search(r"设计总览", h2_text):
        reasons.append("缺少「设计总览」章节")
    if not re.search(r"存档", h2_text):
        reasons.append("缺少「存档持久化」章节")
    if not re.search(r"经济|平衡", h2_text):
        reasons.append("缺少「经济平衡结论」章节")
    # 玩法系统章节数：去掉总览/存档/经济后，至少 3 个
    system_headings = [h for h in h2 if not re.search(r"设计总览|存档|经济|平衡", h)]
    if len(system_headings) < 3:
        reasons.append(f"玩法系统章节不足 3 个（当前 {len(system_headings)}）")
    return (len(reasons) == 0, reasons)
