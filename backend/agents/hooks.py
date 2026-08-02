"""进度流 hook：把工具调用前后事件推给前端，不干预放行。"""
from typing import Awaitable, Callable
from claude_agent_sdk import HookMatcher

ProgressFn = Callable[[dict], Awaitable[None]]


def make_progress_hooks(on_progress: ProgressFn) -> dict:
    async def pre(input_dict, tool_use_id, ctx):
        await on_progress({
            "event": "pre",
            "tool": input_dict.get("tool_name"),
            "input": input_dict.get("tool_input", {}),
        })
        return {}

    async def post(input_dict, tool_use_id, ctx):
        await on_progress({
            "event": "post",
            "tool": input_dict.get("tool_name"),
        })
        return {}

    return {
        "PreToolUse": [HookMatcher(hooks=[pre])],
        "PostToolUse": [HookMatcher(hooks=[post])],
    }
