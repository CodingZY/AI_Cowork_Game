"""Design Agent 运行器：装配 options 并驱动 claude_agent_sdk.query。"""
from pathlib import Path
from typing import Awaitable, Callable
from claude_agent_sdk import query, ClaudeAgentOptions

from .prompts import DESIGN_SYSTEM_PROMPT
from .tools import build_design_tools, TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_ASK_USER
from .permissions import make_permission_handler
from .hooks import make_progress_hooks

AskFn = Callable[[str, list[str] | None], Awaitable[str]]
ProgressFn = Callable[[dict], Awaitable[None]]


async def run_design_agent(
    game_root: Path,
    *,
    ask: AskFn,
    on_progress: ProgressFn,
    model: str,
    base_url: str | None,
    auth_token: str | None,
    prompt: str,
) -> Path:
    """运行 Design Agent，返回写入的 game-design.md 路径。"""
    game_root.mkdir(parents=True, exist_ok=True)
    (game_root / "docs").mkdir(exist_ok=True)

    mcp_server = build_design_tools(game_root, ask)
    options = ClaudeAgentOptions(
        system_prompt=DESIGN_SYSTEM_PROMPT,
        tools=[TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_ASK_USER],
        mcp_servers={"design-tools": mcp_server},
        can_use_tool=make_permission_handler(game_root),
        hooks=make_progress_hooks(on_progress),
        permission_mode="default",
        model=model,
        cwd=str(game_root),
        env={} if (base_url is None or auth_token is None) else {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": auth_token,
        },
    )

    final_path = game_root / "docs" / "game-design.md"
    async for _msg in query(prompt=prompt, options=options):
        # SDK 内部驱动工具循环；此处仅消费消息流（可在此追加 on_progress 文本推送）
        pass
    return final_path
