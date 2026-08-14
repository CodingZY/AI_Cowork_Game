from __future__ import annotations

import json

from app.agent.parser import ClaudeEventParser, CoworkEvent


def test_parse_system_init_emits_session_started():
    line = json.dumps({
        "type": "system", "subtype": "init",
        "session_id": "sid-123",
        "model": "kimi-k3",
        "tools": ["Read", "Write"],
    })
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    e = evts[0]
    assert e.type == "agent.session.started"
    assert e.data == {"session_id": "sid-123", "model": "kimi-k3", "agent_type": "brainstorm"}
    assert e.event_id.startswith("evt_")
    assert isinstance(e, CoworkEvent)
    assert e.project_id == 1
    assert e.aggregate_type == "agent_session"
    assert e.raw_json == line


def test_parse_text_delta():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "text_delta", "text": "hello"}}})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.message.delta"
    assert evts[0].data == {"text": "hello"}


def test_parse_thinking_delta_dropped():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "thinking_delta", "thinking": "x"}}})
    assert ClaudeEventParser(project_id=1).parse(line) == []


def test_parse_thinking_tokens_dropped():
    line = json.dumps({"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 1})
    assert ClaudeEventParser(project_id=1).parse(line) == []


def test_parse_content_block_start_thinking_no_event():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "thinking", "signature": "", "thinking": ""}}})
    assert ClaudeEventParser(project_id=1).parse(line) == []


def test_parse_content_block_start_text_no_event():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_start", "index": 1,
        "content_block": {"type": "text", "text": ""}}})
    assert ClaudeEventParser(project_id=1).parse(line) == []


def test_parse_tool_use():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_start", "index": 1,
        "content_block": {"type": "tool_use", "id": "tu1", "name": "Read",
                          "input": {"file_path": "a.md"}}}})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.tool.started"
    assert evts[0].data == {"tool_use_id": "tu1", "name": "Read", "input": {"file_path": "a.md"}}


def test_parse_tool_result_from_user_message():
    line = json.dumps({"type": "user", "message": {
        "content": [{"type": "tool_result", "tool_use_id": "tu1",
                     "content": "file contents", "is_error": False}]}})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.tool.completed"
    assert evts[0].data == {"tool_use_id": "tu1", "content": "file contents", "is_error": False}


def test_parse_assistant_completed():
    line = json.dumps({"type": "assistant", "message": {
        "content": [{"type": "text", "text": "hello "},
                    {"type": "text", "text": "world"}]}})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.message.completed"
    assert evts[0].data == {"text": "hello world"}


def test_parse_result_completed():
    line = json.dumps({"type": "result", "subtype": "success", "is_error": False,
        "stop_reason": "end_turn", "session_id": "sid-1", "result": "4",
        "total_cost_usd": 0.01, "duration_ms": 100, "num_turns": 1})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.session.completed"
    assert evts[0].data == {"session_id": "sid-1", "result": "4",
                            "stop_reason": "end_turn", "cost": 0.01, "duration": 100}


def test_parse_result_refusal():
    line = json.dumps({"type": "result", "subtype": "success", "is_error": True,
        "stop_reason": "refusal", "result": "API Error: policy"})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.refused"
    assert evts[0].data == {"reason": "content_review", "result": "API Error: policy"}


def test_parse_result_runtime_error():
    line = json.dumps({"type": "result", "subtype": "success", "is_error": True,
        "stop_reason": "end_turn", "result": "some runtime boom",
        "session_id": "sid-1", "total_cost_usd": 0.0, "duration_ms": 5})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.session.failed"
    assert evts[0].data == {"reason": "runtime_error", "result": "some runtime boom"}


def test_parse_model_refusal_no_fallback():
    line = json.dumps({"type": "system", "subtype": "model_refusal_no_fallback"})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    assert evts[0].type == "agent.refused"
    assert evts[0].data == {"reason": "content_review"}


def test_parse_empty_line_returns_empty():
    assert ClaudeEventParser(project_id=1).parse("") == []
    assert ClaudeEventParser(project_id=1).parse("   ") == []


def test_parse_invalid_json_returns_empty():
    assert ClaudeEventParser(project_id=1).parse("not json") == []


def test_parse_agent_type_override():
    line = json.dumps({"type": "system", "subtype": "init", "session_id": "s", "model": "m"})
    e = ClaudeEventParser(project_id=7, agent_type="coder").parse(line)[0]
    assert e.data["agent_type"] == "coder"
    assert e.project_id == 7


def test_parse_real_ok_math_fixture(fixture_lines):
    lines = fixture_lines("ok_math.jsonl")
    evts = [e for l in lines for e in ClaudeEventParser(project_id=1).parse(json.dumps(l))]
    types = [e.type for e in evts]
    assert "agent.session.started" in types
    assert "agent.session.completed" in types
    assert all("thinking" not in e.type for e in evts)


def test_parse_real_refusal_fixture(fixture_lines):
    lines = fixture_lines("refusal.jsonl")
    evts = [e for l in lines for e in ClaudeEventParser(project_id=1).parse(json.dumps(l))]
    types = [e.type for e in evts]
    assert "agent.refused" in types
    assert all("thinking" not in e.type for e in evts)
