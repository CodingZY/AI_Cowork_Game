"""Design Agent 工具：read_file / write_file / ask_user 的纯函数 + claude_agent_sdk 包装。"""
from pathlib import Path
from typing import Awaitable, Callable
from claude_agent_sdk import tool, create_sdk_mcp_server, McpSdkServerConfig

TOOL_READ_FILE = "read_file"
TOOL_WRITE_FILE = "write_file"
TOOL_ASK_USER = "ask_user"

AskFn = Callable[[str, list[str] | None], Awaitable[str]]


# ---- 纯函数（可单测，不依赖 SDK）----
async def do_read_file(path: Path) -> dict:
    if not path.exists():
        return {"ok": False, "error": f"文件不存在: {path}"}
    return {"ok": True, "content": path.read_text(encoding="utf-8")}


async def do_write_file(path: Path, content: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path)}


async def do_ask_user(question: str, options: list[str] | None, *, ask: AskFn) -> dict:
    answer = await ask(question, options)
    return {"question": question, "answer": answer}


# ---- SDK 包装：工具收到 args(dict)，调用纯函数 ----
def build_design_tools(game_root: Path, ask: AskFn) -> McpSdkServerConfig:
    """构造 Design Agent 的 in-process MCP 工具服务。"""
    @tool(name=TOOL_READ_FILE, description="读取项目内文件，返回内容。", input_schema={
        "type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]
    })
    async def read_file(args):
        # 允许相对 game_root 的路径
        p = Path(args["path"])
        if not p.is_absolute():
            p = game_root / p
        res = await do_read_file(p)
        if res["ok"]:
            return {"content": [{"type": "text", "text": res["content"]}]}
        return {"content": [{"type": "text", "text": res["error"]}], "isError": True}

    @tool(name=TOOL_WRITE_FILE, description="写入 docs/game-design.md。", input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    })
    async def write_file(args):
        p = Path(args["path"])
        if not p.is_absolute():
            p = game_root / p
        # 安全：只允许写到 game_root 之下（最终路径校验由 permission handler 兜底）
        res = await do_write_file(p, args["content"])
        if res["ok"]:
            return {"content": [{"type": "text", "text": f"已写入 {res['path']}"}]}
        return {"content": [{"type": "text", "text": res.get("error", "写失败")}], "isError": True}

    @tool(name=TOOL_ASK_USER, description="向用户提问并等待回答。options 为字符串列表，可空表示开放题。", input_schema={
        "type": "object",
        "properties": {"question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}},
        "required": ["question"],
    })
    async def ask_user(args):
        res = await do_ask_user(args["question"], args.get("options"), ask=ask)
        return {"content": [{"type": "text", "text": res["answer"]}]}

    return create_sdk_mcp_server(name="design-tools", version="1.0.0", tools=[read_file, write_file, ask_user])
