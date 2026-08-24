"""Observability 包：Langfuse 埋点 + 业务表聚合源。

埋点在 Temporal activity 侧（非 workflow 线程，避确定性约束）：
  - spawn-skill activity → instrument_skill → Langfuse Generation + game_observations(skill)
  - 纯 Python activity → instrument_activity → Langfuse Span + game_observations(activity)
  - build_game → instrument_activity + game_builds(SUCCESS/FAILED)
业务表（game_builds / game_observations）是 API 聚合源，Langfuse 仅作详细 trace 下钻。
"""
