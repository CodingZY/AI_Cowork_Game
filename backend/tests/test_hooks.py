"""进度流 hook：工具调用前后回调 on_progress。"""
import asyncio
import pytest
from agents.hooks import make_progress_hooks


@pytest.mark.asyncio
async def test_pre_and_post_fire():
    events = []
    async def on_progress(msg):
        events.append(msg)
    hooks = make_progress_hooks(on_progress)
    pre = hooks["PreToolUse"][0]
    post = hooks["PostToolUse"][0]
    # hook 回调签名: (input_dict, tool_use_id, ctx_dict)
    out_pre = await pre.hooks[0]({"tool_name": "write_file", "tool_input": {"path": "docs/game-design.md"}}, "tu1", {})
    out_post = await post.hooks[0]({"tool_name": "write_file", "tool_input": {}}, "tu1", {})
    assert out_pre == {} and out_post == {}
    assert events[0]["event"] == "pre" and events[0]["tool"] == "write_file"
    assert events[1]["event"] == "post" and events[1]["tool"] == "write_file"
