---
name: game-requirements
description: QuestionPlan + Answers + Defaults → Requirements Snapshot（SSOT）。纯合成，不调 LLM。
---

## 作用
把 game-brainstorm 的 QuestionPlan + 用户答案 + 默认值合成为 **Requirements Snapshot**（单一事实来源 SSOT）。

## 实现
**不 spawn claude、不调 LLM**——后端 `synthesize_requirements` Activity 内纯 Python 合成：
- 按 question 的 `category` 填 snapshot 字段（camera→game.camera, core_loop→game.genre）
- 未答的题用 `default_option`
- 每个决策记入 `decisions`（source: user/default）

## Snapshot schema（文档 §20）
```json
{
  "game": {"genre", "camera", "platform", "engine"},
  "core_loop": ["plant", "grow", "harvest", "sell"],
  "v1": {"map", "crops", "npc", "shop"},
  "decisions": [{"id", "value", "source"}],
  "assumptions": [{"id", "value", "source": "system_default"}]
}
```

后续 gdd-generator / Asset / Code 都从此 Snapshot 派生。
