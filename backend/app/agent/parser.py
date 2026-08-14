from __future__ import annotations

import json
from typing import Any

from app.schemas.event import CoworkEvent

# 重导出，便于 `from app.agent.parser import ClaudeEventParser, CoworkEvent`
__all__ = ["ClaudeEventParser", "CoworkEvent"]

# result 文本命中即判为 content_review 的关键词（小写匹配，spec §5.6 三态）
_REFUSAL_KEYWORDS = ("refusal", "policy")


class ClaudeEventParser:
    """把 claude ``stream-json`` 的单行 NDJSON 归一化为 ``CoworkEvent`` 列表。

    纯函数（无 IO）：一次 ``parse(line)`` 调用返回 0..N 个事件。

    映射表（spec §5.2）::

        system/init                              -> agent.session.started {session_id, model, agent_type}
        system/thinking_tokens                   -> 丢弃
        system/model_refusal_no_fallback         -> agent.refused {reason:"content_review"}
        stream_event/content_block_delta text_delta -> agent.message.delta {text}
        stream_event/content_block_delta thinking_delta -> 丢弃
        stream_event/content_block_start tool_use -> agent.tool.started {tool_use_id, name, input}
        stream_event/content_block_start thinking/text -> 不产
        user.message.content[tool_result]        -> agent.tool.completed {tool_use_id, content, is_error}
        assistant.message.content[text]          -> agent.message.completed {text=拼接}
        result(is_error=false, end_turn)         -> agent.session.completed {session_id, result, stop_reason, cost, duration}
        result(stop_reason=refusal 或 is_error+refusal文本) -> agent.refused {reason:"content_review", result}
        result(其他 is_error=true)              -> agent.session.failed {reason:"runtime_error", result}
    """

    def __init__(self, project_id: int, agent_type: str = "brainstorm"):
        self.project_id = project_id
        self.agent_type = agent_type

    # ---- public API ---------------------------------------------------------

    def parse(self, line: str) -> list[CoworkEvent]:
        line = line.strip() if isinstance(line, str) else ""
        if not line:
            return []
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return []
        if not isinstance(obj, dict):
            return []

        t = obj.get("type")
        if t == "system":
            return self._handle_system(obj, line)
        if t == "stream_event":
            return self._handle_stream_event(obj, line)
        if t == "user":
            return self._handle_user(obj, line)
        if t == "assistant":
            return self._handle_assistant(obj, line)
        if t == "result":
            return self._handle_result(obj, line)
        return []

    # ---- helpers ------------------------------------------------------------

    def _evt(self, type_: str, data: dict, raw: str) -> CoworkEvent:
        return CoworkEvent(
            project_id=self.project_id,
            type=type_,
            data=data,
            aggregate_id=0,
            raw_json=raw,
        )

    # ---- branch handlers ----------------------------------------------------

    def _handle_system(self, obj: dict, raw: str) -> list[CoworkEvent]:
        subtype = obj.get("subtype")
        if subtype == "init":
            return [self._evt("agent.session.started", {
                "session_id": obj.get("session_id"),
                "model": obj.get("model"),
                "agent_type": self.agent_type,
            }, raw)]
        if subtype == "thinking_tokens":
            # D10：thinking 全部丢弃
            return []
        if subtype == "model_refusal_no_fallback":
            return [self._evt("agent.refused", {"reason": "content_review"}, raw)]
        # 其它 system 子类型：不识别 -> 不产事件
        return []

    def _handle_stream_event(self, obj: dict, raw: str) -> list[CoworkEvent]:
        event = obj.get("event")
        if not isinstance(event, dict):
            return []
        et = event.get("type")

        if et == "content_block_delta":
            delta = event.get("delta")
            if not isinstance(delta, dict):
                return []
            dt = delta.get("type")
            if dt == "text_delta":
                return [self._evt("agent.message.delta", {"text": delta.get("text", "")}, raw)]
            # thinking_delta 及其它 delta 类型：丢弃
            return []

        if et == "content_block_start":
            block = event.get("content_block")
            if not isinstance(block, dict):
                return []
            bt = block.get("type")
            if bt == "tool_use":
                return [self._evt("agent.tool.started", {
                    "tool_use_id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input"),
                }, raw)]
            # thinking / text 的 content_block_start：不产事件
            return []

        # message_start / message_delta / message_stop / content_block_stop 等：不产
        return []

    def _handle_user(self, obj: dict, raw: str) -> list[CoworkEvent]:
        """user 消息可能携带上一轮 tool 的 tool_result block（spike §3.4）。"""
        message = obj.get("message")
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []
        out: list[CoworkEvent] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                out.append(self._evt("agent.tool.completed", {
                    "tool_use_id": block.get("tool_use_id"),
                    "content": block.get("content"),
                    "is_error": bool(block.get("is_error", False)),
                }, raw))
        return out

    def _handle_assistant(self, obj: dict, raw: str) -> list[CoworkEvent]:
        message = obj.get("message")
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        if not texts:
            return []
        return [self._evt("agent.message.completed", {"text": "".join(texts)}, raw)]

    def _handle_result(self, obj: dict, raw: str) -> list[CoworkEvent]:
        stop_reason = obj.get("stop_reason")
        is_error = bool(obj.get("is_error", False))
        result = obj.get("result")

        # 三态分流（spec §5.6）
        # 1) stop_reason=refusal -> content_review
        if stop_reason == "refusal":
            return [self._evt("agent.refused",
                              {"reason": "content_review", "result": result}, raw)]
        # 2) is_error=true：看 result 文本是否命中 refusal/policy
        if is_error:
            text = result if isinstance(result, str) else ""
            low = text.lower()
            if any(k in low for k in _REFUSAL_KEYWORDS):
                return [self._evt("agent.refused",
                                  {"reason": "content_review", "result": result}, raw)]
            return [self._evt("agent.session.failed",
                              {"reason": "runtime_error", "result": result}, raw)]
        # 3) 非 error（含 end_turn）-> completed
        return [self._evt("agent.session.completed", {
            "session_id": obj.get("session_id"),
            "result": result,
            "stop_reason": stop_reason,
            "cost": obj.get("total_cost_usd"),
            "duration": obj.get("duration_ms"),
        }, raw)]
