"""Design Agent 权限沙箱：can_use_tool 只放行受限读写与 ask_user。"""
from pathlib import Path
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from .tools import TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_ASK_USER


def _resolve(game_root: Path, p_str: str) -> Path:
    p = Path(p_str)
    if not p.is_absolute():
        p = game_root / p
    return p.resolve()


def _inside(game_root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(game_root.resolve())
        return True
    except ValueError:
        return False


def make_permission_handler(game_root: Path):
    async def can_use_tool(tool_name: str, tool_input: dict, ctx: ToolPermissionContext):
        if tool_name == TOOL_ASK_USER:
            return PermissionResultAllow()
        if tool_name == TOOL_READ_FILE:
            p = _resolve(game_root, tool_input.get("path", ""))
            if _inside(game_root, p):
                return PermissionResultAllow()
            return PermissionResultDeny(message=f"禁止读取 game_root 之外: {p}")
        if tool_name == TOOL_WRITE_FILE:
            p = _resolve(game_root, tool_input.get("path", ""))
            allowed = (game_root / "docs" / "game-design.md").resolve()
            if p == allowed:
                return PermissionResultAllow()
            return PermissionResultDeny(message=f"Design Agent 仅可写入 docs/game-design.md，拒绝: {p}")
        return PermissionResultDeny(message=f"未知工具 {tool_name}，拒绝")
    return can_use_tool
