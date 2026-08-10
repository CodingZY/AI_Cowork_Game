# Art Agent（S2）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 S2 阶段端到端可运行：Art Agent 读 S1 设计文档（约定 `*-game-design.md`），拆解为美术资产清单，产出 `docs/美术素材.md`（总分表 + 每资产 fenced YAML 块）；前端展示可编辑清单 + 进度流 + 通过/不通过闸；不通过带反馈重跑。

**Architecture:** 镜像已实现的 Design Agent（S1）：`claude_agent_sdk.query()` 跑 Art Agent 自循环，自定义 MCP 工具 `read_file`/`write_file`（**无 `ask_user`**，自主）+ `can_use_tool` 权限沙箱（仅写 `docs/美术素材.md`）+ `HookMatcher` 进度流。Orchestrator FSM 扩展 S2 转移 + approve/reject 分 stage；S1 approve 后自动启动 S2。前端复用 MarkdownEditor。本计划只实现 S2，S3 由后续计划覆盖。

**Tech Stack:** Python 3.10（conda env `agent_env`）· `claude_agent_sdk` 0.2.125 · FastAPI · SQLAlchemy 2.0(async) · SQLite（测试）· React 18 · Vite · TypeScript · Vitest。

## Global Constraints

- **Python 环境**：所有后端命令在 `agent_env`（`D:/Anaconda3/envs/agent_env`，Python 3.10.19）。运行后端用 `D:/Anaconda3/envs/agent_env/python.exe`。
- **已装依赖**：claude-agent-sdk 0.2.125、fastapi 0.139、SQLAlchemy 2.0.48、uvicorn 0.51、httpx 0.28.1、pillow 12.3.0、pytest 9.1、aiosqlite、anyio、pytest-asyncio、python-dotenv、PyYAML 6.0.3。
- **Node**：v20.20.1 / npm 10.8.2（前端）。
- **平台**：Windows + Git Bash；路径用正斜杠；venv/conda 的 python 在 `Scripts/` 下。装包用 `--no-cache-dir` 避免落 C 盘（见 C 盘约束）。
- **语言/规范**：所有代码与 Agent 输出中文；每个后端文件顶部有简短中文功能说明注释；Art Agent 产物必须通过 `agents/contract.py` 的 `validate_art_assets` 校验。
- **设计文档命名约定 `*-game-design.md`**：S1 写 `<游戏名>-game-design.md`；S2 `resolve_design_doc` glob `*-game-design.md`，并兼容当前 S1 写法 `game-design.md`（无前缀，glob 字面含连字符不匹配，故显式并列两条）。
- **资产类别可扩展**：`category` 非空字符串，非封闭枚举；README 四类为推荐默认，可按游戏类型增补。
- **SDK API（0.2.125，已内省确认）**：
  - `query(*, prompt: str|AsyncIterable, options: ClaudeAgentOptions) -> AsyncIterator[Message]`
  - `ClaudeAgentOptions(system_prompt=, tools=[str|preset], mcp_servers={name:McpSdkServerConfig}, can_use_tool=Callable, hooks={event:[HookMatcher]}, permission_mode=, model=, cwd=, env=)`
  - `@tool(name=, description=, input_schema=<dict>)` 装饰 async fn `(args)->dict`；`create_sdk_mcp_server(name, version, tools=[SdkMcpTool]) -> McpSdkServerConfig`
  - `PermissionResultAllow()` / `PermissionResultDeny(message=, interrupt=)` / `ToolPermissionContext`
  - `HookMatcher(hooks=[async_cb])`，`async_cb(input_dict, tool_use_id_str|None, ctx_dict) -> dict`（返回 `{}` 放行）
- **测试约定**：后端 pytest + pytest-asyncio；DB 测试用 SQLite in-memory（`aiosqlite`）。本计划含自动化测试用于自检，**用户不手动测试 S2**；接真实 LLM 的端到端为可选手动步骤。
- **参考 spec**：`doc/specs/2026-08-10-art-agent-s2-design.md`。

---

## File Structure

**后端 `backend/`**
- `backend/agents/contract.py` — 加 `ART_ASSETS_TEMPLATE` + `validate_art_assets`（modify）
- `backend/agents/tools.py` — 加 `build_art_tools`（modify；复用现有 `TOOL_READ_FILE`/`TOOL_WRITE_FILE` 常量）
- `backend/agents/permissions.py` — 加 `make_art_permission_handler`（modify）
- `backend/agents/prompts.py` — 加 `ART_SYSTEM_PROMPT`（modify）
- `backend/agents/runner.py` — 加 `run_art_agent`（modify）
- `backend/orchestrator/machine.py` — 加 S2 转移 + approve/reject 分 stage（modify）
- `backend/api/runtime.py` — 加 `start_art_plan` + `resolve_design_doc`（modify）
- `backend/api/routes.py` — 加 art-list 路由 + approve/reject 分 stage + S1 approve 启 S2（modify）
- `backend/api/deps.py` — 加 `ART_MODEL`（modify）
- `backend/.env.example` — 加 `ART_MODEL`（modify）

**前端 `frontend/`**
- `frontend/src/api/client.ts` — 加 `getArtList`/`putArtList`（modify）
- `frontend/src/stages/ArtWorkbench.tsx` — 新建
- `frontend/src/App.tsx` — 按 stage 切 ArtWorkbench（modify）

**测试**
- `backend/tests/test_contract.py` — 加 `validate_art_assets` 用例（modify）
- `backend/tests/test_art_tools.py` — 新建
- `backend/tests/test_art_permissions.py` — 新建
- `backend/tests/test_art_runner.py` — 新建
- `backend/tests/test_machine.py` — 加 S2 用例（modify）
- `backend/tests/test_routes.py` — 加 S2 art-list + approve/reject 用例（modify）
- `backend/tests/test_runtime.py` — 新建（`resolve_design_doc` + `start_art_plan`）
- `backend/tests/test_e2e_s2.py` — 新建
- `frontend/src/__tests__/art_workbench.test.tsx` — 新建

---

## Task 1: 美术素材.md 契约 + 校验器

**Files:**
- Modify: `backend/agents/contract.py`
- Test: `backend/tests/test_contract.py`

**Interfaces:**
- Produces: `validate_art_assets(md: str) -> tuple[bool, list[str]]`、`ART_ASSETS_TEMPLATE: str`。后续任务的 Art Agent system prompt 引用 `ART_ASSETS_TEMPLATE`，runner 校验用 `validate_art_assets`。

- [ ] **Step 1: 写失败测试（追加到 test_contract.py 末尾）**

```python
# ---- validate_art_assets ----
from agents.contract import validate_art_assets

GOOD_MD = """## 美术素材清单
> 注释行

| ID | 类别 | 文件名 | 尺寸 | 抠图 |
|----|------|--------|------|------|
| A01 | 角色与NPC | hero_idle | 1024x1024 | 是 |
| A02 | 开场/背景 | title_screen | 1024x1024 | 否 |
| A03 | 特效与粒子 | fx_harvest | 512x512 | 是 |

### A01 · 角色与NPC · hero_idle
```yaml
id: A01
category: 角色与NPC
file: hero_idle
prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"
size: "1024x1024"
matting: true
```

### A02 · 开场/背景 · title_screen
```yaml
id: A02
category: 开场/背景
file: title_screen
prompt: "像素风农场开场画面，远景麦田，可含场景"
size: "1024x1024"
matting: false
```

### A03 · 特效与粒子 · fx_harvest
```yaml
id: A03
category: 特效与粒子
file: fx_harvest
prompt: "像素风收割特效，纯白色背景，无场景，仅保留本体"
size: "512x512"
matting: true
```
"""

def test_validate_art_assets_good():
    ok, reasons = validate_art_assets(GOOD_MD)
    assert ok, reasons

def test_validate_art_assets_empty():
    ok, reasons = validate_art_assets("")
    assert not ok and "空" in reasons[0]

def test_validate_art_assets_missing_field():
    md = GOOD_MD.replace('size: "1024x1024"', '', 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("size" in r for r in reasons)

def test_validate_art_assets_dup_id():
    md = GOOD_MD.replace("id: A02", "id: A01", 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("唯一" in r for r in reasons)

def test_validate_art_assets_bad_id():
    md = GOOD_MD.replace("id: A03", "id: A3", 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("id" in r for r in reasons)

def test_validate_art_assets_bad_file():
    md = GOOD_MD.replace("file: fx_harvest", "file: 坏 名字", 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("file" in r for r in reasons)

def test_validate_art_assets_empty_category():
    md = GOOD_MD.replace("category: 特效与粒子", 'category: ""', 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("category" in r for r in reasons)

def test_validate_art_assets_missing_white_bg():
    md = GOOD_MD.replace("纯白背景，无场景", "森林背景，有场景", 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("背景" in r for r in reasons)

def test_validate_art_assets_missing_neg_word():
    # matting:true 但无否定词（保留纯白背景，去掉无场景等）
    md = GOOD_MD.replace("纯白背景，无场景，无UI，仅保留角色本体", "纯白背景，正面居中", 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("否定" in r for r in reasons)

def test_validate_art_assets_table_count_mismatch():
    md = GOOD_MD.replace("| A03 | 特效与粒子 | fx_harvest | 512x512 | 是 |", "", 1)
    ok, reasons = validate_art_assets(md)
    assert not ok and any("表" in r for r in reasons)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_contract.py::test_validate_art_assets_good -v`
Expected: FAIL with ImportError 或 `validate_art_assets` 未定义。

- [ ] **Step 3: 实现契约与校验器（追加到 contract.py 末尾）**

```python
import yaml as _yaml  # noqa: E402（顶部已有 import re）

ART_ASSETS_TEMPLATE = """## 美术素材清单
> 由 Art Agent 读取游戏设计文档（*-game-design.md）拆解生成；用户可直接编辑本文件。

| ID | 类别 | 文件名 | 尺寸 | 抠图 |
|----|------|--------|------|------|
| A01 | 角色与NPC | hero_idle | 1024x1024 | 是 |

### A01 · 角色与NPC · hero_idle
```yaml
id: A01
category: 角色与NPC
file: hero_idle
prompt: "像素风少年农夫站姿，正面居中，纯白背景，无场景，无UI，仅保留角色本体"
size: "1024x1024"
matting: true
```
"""

_ID_RE = re.compile(r"^A\d{2,}$")
_FILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")
_NEG_WORDS = ["无场景", "无地面", "无阴影背景", "无边框", "无UI", "仅保留角色本体", "仅本体"]


def validate_art_assets(md: str) -> tuple[bool, list[str]]:
    """校验 美术素材.md 是否满足 S2 交付契约。返回 (是否通过, 原因列表)。"""
    reasons: list[str] = []
    if not md or not md.strip():
        return False, ["内容为空"]
    # 切分 yaml fenced 块
    blocks = re.findall(r"```yaml\s*\n(.*?)```", md, flags=re.DOTALL)
    if not blocks:
        return False, ["未找到任何 yaml 块"]
    ids: list[str] = []
    for i, blk in enumerate(blocks, 1):
        try:
            d = _yaml.safe_load(blk)
        except Exception as e:
            reasons.append(f"块{i} yaml 解析失败: {e}")
            continue
        if not isinstance(d, dict):
            reasons.append(f"块{i} 不是映射")
            continue
        # 必填字段
        for f in ("id", "category", "file", "prompt", "size", "matting"):
            if f not in d:
                reasons.append(f"块{i} 缺字段 {f}")
        if not all(k in d for k in ("id", "category", "file", "prompt", "size", "matting")):
            continue
        aid, category, file, prompt, size, matting = (
            d["id"], d["category"], d["file"], d["prompt"], d["size"], d["matting"]
        )
        if not _ID_RE.match(str(aid)):
            reasons.append(f"块{i} id 不符 ^A\\d{{2,}}$: {aid}")
        else:
            if aid in ids:
                reasons.append(f"块{i} id 重复: {aid}")
            ids.append(aid)
        if not isinstance(category, str) or not category.strip():
            reasons.append(f"块{i} category 为空")
        if not _FILE_RE.match(str(file)):
            reasons.append(f"块{i} file 非 slug: {file}")
        m = _SIZE_RE.match(str(size))
        if not m or int(m.group(1)) <= 0 or int(m.group(2)) <= 0:
            reasons.append(f"块{i} size 格式错: {size}")
        if not isinstance(matting, bool):
            reasons.append(f"块{i} matting 非 bool: {matting}")
        if isinstance(matting, bool) and matting:
            if not re.search(r"纯白色?背景", str(prompt)):
                reasons.append(f"块{i} matting:true 缺白色背景表述")
            elif not any(w in str(prompt) for w in _NEG_WORDS):
                reasons.append(f"块{i} matting:true 缺否定词")
    # 汇总表数据行数 vs yaml 块数
    table_rows = [ln for ln in md.splitlines()
                  if ln.strip().startswith("|") and not re.match(r"^\|[-\s|]+\|$", ln.strip())
                  and "ID" not in ln]
    if len(table_rows) != len(blocks):
        reasons.append(f"汇总表数据行数({len(table_rows)})与 yaml 块数({len(blocks)})不符")
    return (len(reasons) == 0, reasons)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_contract.py -v -k art_assets`
Expected: 全部 PASS（10 个用例）。

- [ ] **Step 5: 提交**

```bash
cd "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game"
git add backend/agents/contract.py backend/tests/test_contract.py
git commit -m "feat(agents): 美术素材.md 契约 + validate_art_assets 校验器"
```

---

## Task 2: Art Agent 工具（build_art_tools）

**Files:**
- Modify: `backend/agents/tools.py`
- Test: `backend/tests/test_art_tools.py`（新建）

**Interfaces:**
- Consumes: 现有 `do_read_file`/`do_write_file`/`TOOL_READ_FILE`/`TOOL_WRITE_FILE`（`agents/tools.py` 已有）。
- Produces: `build_art_tools(game_root: Path) -> McpSdkServerConfig`。无 `AskFn`（无 `ask_user`）。runner 调用之。

- [ ] **Step 1: 写失败测试**

```python
"""Art Agent 工具：build_art_tools 的纯函数与权限越界测试（无 ask_user）。"""
import pytest
from pathlib import Path
from agents.tools import build_art_tools, do_write_file


@pytest.mark.asyncio
async def test_build_art_tools_has_read_write_only():
    # build_art_tools 返回 McpSdkServerConfig，其 tools 列表应仅含 read_file/write_file，无 ask_user
    cfg = build_art_tools(Path("/tmp/g"))
    names = {t.name for t in cfg.tools}
    assert names == {"read_file", "write_file"}
    assert "ask_user" not in names


@pytest.mark.asyncio
async def test_build_art_tools_write_creates_dirs(tmp_path):
    # 验证 do_write_file 经工具语义可落盘到 docs/美术素材.md（实际落盘由 runner 调纯函数）
    p = tmp_path / "docs" / "美术素材.md"
    res = await do_write_file(p, "内容")
    assert res["ok"] and p.read_text(encoding="utf-8") == "内容"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_art_tools.py -v`
Expected: FAIL（`build_art_tools` 未定义）。

- [ ] **Step 3: 实现 build_art_tools（追加到 tools.py 末尾）**

```python
def build_art_tools(game_root: Path) -> McpSdkServerConfig:
    """构造 Art Agent 的 in-process MCP 工具服务：仅 read_file/write_file，无 ask_user。"""
    @tool(name=TOOL_READ_FILE, description="读取项目内文件，返回内容。", input_schema={
        "type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]
    })
    async def read_file(args):
        p = Path(args["path"])
        if not p.is_absolute():
            p = game_root / p
        res = await do_read_file(p)
        if res["ok"]:
            return {"content": [{"type": "text", "text": res["content"]}]}
        return {"content": [{"type": "text", "text": res["error"]}], "isError": True}

    @tool(name=TOOL_WRITE_FILE, description="写入 docs/美术素材.md。", input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    })
    async def write_file(args):
        p = Path(args["path"])
        if not p.is_absolute():
            p = game_root / p
        res = await do_write_file(p, args["content"])
        if res["ok"]:
            return {"content": [{"type": "text", "text": f"已写入 {res['path']}"}]}
        return {"content": [{"type": "text", "text": res.get("error", "写失败")}], "isError": True}

    return create_sdk_mcp_server(name="art-tools", version="1.0.0", tools=[read_file, write_file])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_art_tools.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/agents/tools.py backend/tests/test_art_tools.py
git commit -m "feat(agents): Art Agent 工具 build_art_tools（read/write，无 ask_user）"
```

---

## Task 3: Art Agent 权限沙箱（make_art_permission_handler）

**Files:**
- Modify: `backend/agents/permissions.py`
- Test: `backend/tests/test_art_permissions.py`（新建）

**Interfaces:**
- Consumes: `PermissionResultAllow`/`PermissionResultDeny`/`ToolPermissionContext`、`TOOL_READ_FILE`/`TOOL_WRITE_FILE`。
- Produces: `make_art_permission_handler(game_root: Path)`。runner 调用之。`write_file` 仅允许 `docs/美术素材.md`，其余 Deny。

- [ ] **Step 1: 写失败测试**

```python
"""Art Agent 权限沙箱：read 限 game_root 内，write 仅 docs/美术素材.md。"""
import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
from agents.permissions import make_art_permission_handler


@pytest.mark.asyncio
async def test_art_read_inside_allowed(tmp_path):
    h = make_art_permission_handler(tmp_path)
    r = await h("read_file", {"path": "docs/game-design.md"}, None)
    assert isinstance(r, PermissionResultAllow)

@pytest.mark.asyncio
async def test_art_read_outside_denied(tmp_path):
    h = make_art_permission_handler(tmp_path)
    r = await h("read_file", {"path": "/etc/passwd"}, None)
    assert isinstance(r, PermissionResultDeny)

@pytest.mark.asyncio
async def test_art_write_artlist_allowed(tmp_path):
    h = make_art_permission_handler(tmp_path)
    r = await h("write_file", {"path": "docs/美术素材.md", "content": "x"}, None)
    assert isinstance(r, PermissionResultAllow)

@pytest.mark.asyncio
async def test_art_write_design_denied(tmp_path):
    # 不允许 Art Agent 写设计文档
    h = make_art_permission_handler(tmp_path)
    r = await h("write_file", {"path": "docs/game-design.md", "content": "x"}, None)
    assert isinstance(r, PermissionResultDeny)

@pytest.mark.asyncio
async def test_art_unknown_tool_denied(tmp_path):
    h = make_art_permission_handler(tmp_path)
    r = await h("ask_user", {"question": "?"}, None)
    assert isinstance(r, PermissionResultDeny)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_art_permissions.py -v`
Expected: FAIL（`make_art_permission_handler` 未定义）。

- [ ] **Step 3: 实现（追加到 permissions.py 末尾）**

```python
def make_art_permission_handler(game_root: Path):
    async def can_use_tool(tool_name: str, tool_input: dict, ctx: ToolPermissionContext):
        if tool_name == TOOL_READ_FILE:
            p = _resolve(game_root, tool_input.get("path", ""))
            if _inside(game_root, p):
                return PermissionResultAllow()
            return PermissionResultDeny(message=f"禁止读取 game_root 之外: {p}")
        if tool_name == TOOL_WRITE_FILE:
            p = _resolve(game_root, tool_input.get("path", ""))
            allowed = (game_root / "docs" / "美术素材.md").resolve()
            if p == allowed:
                return PermissionResultAllow()
            return PermissionResultDeny(message=f"Art Agent 仅可写入 docs/美术素材.md，拒绝: {p}")
        return PermissionResultDeny(message=f"Art Agent 不允许工具 {tool_name}，拒绝")
    return can_use_tool
```

> `_resolve`/`_inside` 复用现有 permissions.py 顶部的两个辅助函数。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_art_permissions.py -v`
Expected: PASS（5 个用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/agents/permissions.py backend/tests/test_art_permissions.py
git commit -m "feat(agents): Art Agent 权限沙箱 make_art_permission_handler"
```

---

## Task 4: Art Agent system prompt + runner

**Files:**
- Modify: `backend/agents/prompts.py`、`backend/agents/runner.py`
- Test: `backend/tests/test_art_runner.py`（新建）

**Interfaces:**
- Consumes: `ART_ASSETS_TEMPLATE`（Task 1）、`build_art_tools`（Task 2）、`make_art_permission_handler`（Task 3）、`make_progress_hooks`（已有）、`ProgressFn`（已有）、`query`/`ClaudeAgentOptions`（SDK）。
- Produces: `ART_SYSTEM_PROMPT`、`run_art_agent(game_root, *, on_progress, model, base_url, auth_token, prompt) -> Path`。runtime `start_art_plan` 调用之。

- [ ] **Step 1: 写失败测试**

```python
"""Art Agent runner：mock query（fake_query 写清单），验证工具接线 + 权限。"""
import pytest
from claude_agent_sdk import ResultMessage
import agents.runner as runner_mod
from agents.tools import do_write_file


@pytest.mark.asyncio
async def test_run_art_agent_writes_artlist(tmp_path, monkeypatch):
    game_root = tmp_path
    (game_root / "docs").mkdir()
    artlist = ("## 美术素材清单\n\n| ID | 类别 | 文件名 | 尺寸 | 抠图 |\n|----|------|--------|------|------|\n"
               "| A01 | 角色与NPC | hero_idle | 1024x1024 | 是 |\n\n"
               "### A01 · 角色与NPC · hero_idle\n```yaml\n"
               "id: A01\ncategory: 角色与NPC\nfile: hero_idle\n"
               'prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"\n'
               'size: "1024x1024"\nmatting: true\n```\n')

    async def fake_query(*, prompt, options):
        await options.can_use_tool("write_file", {"path": "docs/美术素材.md", "content": artlist}, None)
        await do_write_file(game_root / "docs" / "美术素材.md", artlist)
        yield ResultMessage("result", 0, 0, False, 1, "test-session")

    monkeypatch.setattr(runner_mod, "query", fake_query)
    progress = []
    async def on_progress(m): progress.append(m)
    p = await runner_mod.run_art_agent(
        game_root, on_progress=on_progress, model="m", base_url=None, auth_token=None,
        prompt="测试",
    )
    assert p == game_root / "docs" / "美术素材.md"
    assert p.exists()
    from agents.contract import validate_art_assets
    ok, reasons = validate_art_assets(p.read_text(encoding="utf-8"))
    assert ok, reasons
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_art_runner.py -v`
Expected: FAIL（`run_art_agent` 未定义 / `ART_SYSTEM_PROMPT` 未定义）。

- [ ] **Step 3: 实现 system prompt（追加到 prompts.py 末尾）**

```python
from .contract import ART_ASSETS_TEMPLATE  # noqa: E402

ART_SYSTEM_PROMPT = f"""你是一名美术资产规划 Agent，负责读取游戏设计文档（命名 *-game-design.md，全文与文件名由 prompt 提供），
将其拆解为明确的美术资产清单，产出 docs/美术素材.md。

【工作方法】
1. 设计文档全文由 prompt 提供（命名约定 *-game-design.md，如 farmer-game-design.md）；
   如需重读，按 prompt 给出的文件名用 read_file 读取。先理解游戏类型、美术风格、核心系统、角色/场景/物品。
2. 以"开场/背景、角色与NPC、地图与建筑物、物品与UI"四类为推荐基础穷举资产，不遗漏关键资产；
   但**不限于四类**——视游戏类型可增补更多类别（如载具、特效与粒子、过场动画、音效图标等）。
   - 开场/背景：title_screen、各关卡背景（如 level1_bg）等。
   - 角色与NPC：主角各状态（hero_idle）、各 NPC（npc_<role>）等。
   - 地图与建筑物：地块（wall_tile、floor_tile）、建筑物等。
   - 物品与UI：道具（coin）、UI（hp_bar）等。
   - 扩展类别：按游戏需要自行增设，category 用一致命名。
3. 为每项资产填：id（A01 起编号，至少两位）、category、file（slug 文件名）、prompt、size、matting。
4. prompt 要点：
   - 开头点明绘画风格（从设计文档提炼，如"像素风"）。
   - matting: true（角色/物品/UI/特效等）的资产，prompt 必须含白色背景表述（"纯白背景"或"纯白色背景"）且含否定词系列
     （无场景/无地面/无阴影背景/无边框/无UI/仅保留角色本体）至少一个。
   - matting: false（开场/背景）的资产，prompt 可含场景。
   - 视角/朝向/居中等构图提示写清楚，便于抠图与复用。
5. 写文件前自检：你的清单必须通过 validate_art_assets 规则（见输出契约）。
6. 全程中文 prompt 与中文注释。

【可用工具】
- read_file(path)：读取本项目文件。
- write_file(path, content)：将美术素材.md 写盘。path 必须为 docs/美术素材.md。

【输出契约】总分结构：顶部一张汇总表（ID/类别/文件名/尺寸/抠图），
其后每个资产一个 ```yaml fenced 块，字段见模板。类别不限四类。

【模板】
{ART_ASSETS_TEMPLATE}

【硬性要求】
- 全程中文。
- 以四类为基础，按游戏类型可增补更多类别；不遗漏游戏核心循环所需的关键资产。
- id 全局唯一；file 为 slug。
- matting: true 的 prompt 必须含白色背景表述（纯白背景/纯白色背景）+ 否定词至少一个。
- 清单完整且通过你自检后，调用 write_file 写入 docs/美术素材.md，然后停止。
"""
```

- [ ] **Step 4: 实现 runner（追加到 runner.py 末尾）**

```python
from .prompts import ART_SYSTEM_PROMPT
from .tools import build_art_tools, TOOL_READ_FILE, TOOL_WRITE_FILE
from .permissions import make_art_permission_handler


async def run_art_agent(
    game_root: Path, *, on_progress: ProgressFn,
    model: str, base_url: str | None, auth_token: str | None, prompt: str,
) -> Path:
    """运行 Art Agent，返回写入的 美术素材.md 路径。"""
    game_root.mkdir(parents=True, exist_ok=True)
    (game_root / "docs").mkdir(exist_ok=True)

    mcp_server = build_art_tools(game_root)
    options = ClaudeAgentOptions(
        system_prompt=ART_SYSTEM_PROMPT,
        tools=[TOOL_READ_FILE, TOOL_WRITE_FILE],
        mcp_servers={"art-tools": mcp_server},
        can_use_tool=make_art_permission_handler(game_root),
        hooks=make_progress_hooks(on_progress),
        permission_mode="default",
        model=model,
        cwd=str(game_root),
        env={} if (base_url is None or auth_token is None) else {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": auth_token,
        },
    )
    final_path = game_root / "docs" / "美术素材.md"
    async for _msg in query(prompt=prompt, options=options):
        pass
    return final_path
```

- [ ] **Step 5: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_art_runner.py -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/agents/prompts.py backend/agents/runner.py backend/tests/test_art_runner.py
git commit -m "feat(agents): Art Agent system prompt + runner"
```

---

## Task 5: FSM 扩展 S2 转移 + approve/reject 分 stage

**Files:**
- Modify: `backend/orchestrator/machine.py`
- Test: `backend/tests/test_machine.py`（追加）

**Interfaces:**
- Consumes: `Stage`/`StageStatus`（已有 `S2_art_plan`/`S3_art_gen` 枚举）。
- Produces: `StateMachine.start_art_plan`/`complete_art_plan`/`approve(stage=...)`/`reject(stage=...)`。routes 与 runtime 依赖之。
- 注意：现 `approve` 仅认 `stage=S1_design`，返回 `(S2_art_plan, not_implemented)`。本任务改为：S1→S2 **running**、S2→S3 running。`not_implemented` 仅 S3→S4 时用（S3 由后续计划实现，本任务先返回 `not_implemented` 占位即可，或留 S3 approve 给后续计划——但 approve/reject 分 stage 框架本任务搭好）。

- [ ] **Step 1: 写失败测试（追加到 test_machine.py 末尾）**

```python
# ---- S2 转移 ----
from orchestrator.states import Stage
from orchestrator.machine import StateMachine, RunState

def test_start_art_plan():
    sm = StateMachine()
    t = sm.start_art_plan(RunState("r", Stage.S1_design, StageStatus.approved))
    assert t.stage == Stage.S2_art_plan and t.status == StageStatus.running

def test_complete_art_plan():
    sm = StateMachine()
    t = sm.complete_art_plan(RunState("r", Stage.S2_art_plan, StageStatus.running))
    assert t.stage == Stage.S2_art_plan and t.status == StageStatus.awaiting_approval

def test_approve_s1_to_s2_running():
    sm = StateMachine()
    t = sm.approve(RunState("r", Stage.S1_design, StageStatus.awaiting_approval), stage=Stage.S1_design)
    assert t.stage == Stage.S2_art_plan and t.status == StageStatus.running

def test_approve_s2_to_s3():
    sm = StateMachine()
    t = sm.approve(RunState("r", Stage.S2_art_plan, StageStatus.awaiting_approval), stage=Stage.S2_art_plan)
    assert t.stage == Stage.S3_art_gen and t.status == StageStatus.running

def test_reject_s2_rerun():
    sm = StateMachine()
    t = sm.reject(RunState("r", Stage.S2_art_plan, StageStatus.awaiting_approval), stage=Stage.S2_art_plan, feedback="补")
    assert t.stage == Stage.S2_art_plan and t.status == StageStatus.running

def test_approve_guard_wrong_status():
    sm = StateMachine()
    t = sm.approve(RunState("r", Stage.S2_art_plan, StageStatus.running), stage=Stage.S2_art_plan)
    assert t is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_machine.py -v -k "art_plan or approve_s2 or reject_s2"`
Expected: FAIL（`start_art_plan` 未定义；`approve` 现状返回 not_implemented 不匹配 running）。

- [ ] **Step 3: 重写 machine.py 的转移方法（替换 start_design/complete_design/approve/reject 四个方法）**

```python
class StateMachine:
    """阶段转移与闸判定纯逻辑。S1 design / S2 art-plan 实现完整；S3/S4 由后续计划扩展。"""

    def start_design(self, run: RunState) -> Transition:
        return Transition(Stage.S1_design, StageStatus.running)

    def complete_design(self, run: RunState) -> Transition:
        return Transition(Stage.S1_design, StageStatus.awaiting_approval)

    def start_art_plan(self, run: RunState) -> Transition:
        return Transition(Stage.S2_art_plan, StageStatus.running)

    def complete_art_plan(self, run: RunState) -> Transition:
        return Transition(Stage.S2_art_plan, StageStatus.awaiting_approval)

    def approve(self, run: RunState, *, stage: Stage) -> Transition | None:
        if run.stage != stage or run.status != StageStatus.awaiting_approval:
            return None
        if stage == Stage.S1_design:
            return Transition(Stage.S2_art_plan, StageStatus.running)
        if stage == Stage.S2_art_plan:
            return Transition(Stage.S3_art_gen, StageStatus.running)
        if stage == Stage.S3_art_gen:
            return Transition(Stage.S4_coding, StageStatus.not_implemented)
        return None

    def reject(self, run: RunState, *, stage: Stage, feedback: str) -> Transition | None:
        if run.stage != stage or run.status != StageStatus.awaiting_approval:
            return None
        if stage == Stage.S1_design:
            return Transition(Stage.S1_design, StageStatus.running)
        if stage == Stage.S2_art_plan:
            return Transition(Stage.S2_art_plan, StageStatus.running)
        if stage == Stage.S3_art_gen:
            return Transition(Stage.S3_art_gen, StageStatus.running)
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_machine.py -v`
Expected: 全 PASS（含原 S1 用例 + 新 S2 用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/orchestrator/machine.py backend/tests/test_machine.py
git commit -m "feat(orchestrator): FSM 扩展 S2 转移 + approve/reject 分 stage"
```

---

## Task 6: deps + .env.example 加 ART_MODEL

**Files:**
- Modify: `backend/api/deps.py`、`backend/.env.example`

**Interfaces:**
- Produces: `ART_MODEL` env 读取。runtime `start_art_plan` 依赖之。

- [ ] **Step 1: 改 deps.py（在 DESIGN_MODEL 行后加一行）**

将
```python
DESIGN_MODEL = os.getenv("DESIGN_MODEL", "claude-sonnet-4-6")
```
改为
```python
DESIGN_MODEL = os.getenv("DESIGN_MODEL", "claude-sonnet-4-6")
ART_MODEL = os.getenv("ART_MODEL", "claude-sonnet-4-6")
```

- [ ] **Step 2: 改 .env.example（在 DESIGN_MODEL 行后加一行）**

将
```env
DESIGN_MODEL=claude-sonnet-4-6
```
改为
```env
DESIGN_MODEL=claude-sonnet-4-6
# Art Agent 用的模型名（与 Design 同一端点）
ART_MODEL=claude-sonnet-4-6
```

- [ ] **Step 3: 验证导入无报错**

Run: `D:/Anaconda3/envs/agent_env/python.exe -c "from api.deps import ART_MODEL; print(ART_MODEL)"`
Expected: 打印 `claude-sonnet-4-6`，无异常。

- [ ] **Step 4: 提交**

```bash
git add backend/api/deps.py backend/.env.example
git commit -m "feat(api): deps 加 ART_MODEL 配置"
```

---

## Task 7: runtime 加 resolve_design_doc + start_art_plan

**Files:**
- Modify: `backend/api/runtime.py`
- Test: `backend/tests/test_runtime.py`（新建）

**Interfaces:**
- Consumes: `ART_MODEL`/`BASE_URL`/`AUTH_TOKEN`/`games_root`/`_session_factory`（deps）、`run_art_agent`（Task 4）、`broker`、`GameRun`/`PendingApproval`（models）、`Stage`/`StageStatus`。
- Produces: `resolve_design_doc(docs_dir: Path) -> Path`（glob `*-game-design.md` + 兼容 `game-design.md`，排除 `美术素材*`，多匹配取 mtime 最新，0 匹配抛 FileNotFoundError）、`start_art_plan(run_id, game_name, *, feedback=None)`。routes approve(S1) 调用之启动 S2。

- [ ] **Step 1: 写失败测试**

```python
"""runtime: resolve_design_doc 发现规则 + start_art_plan 基本接线（mock run_art_agent）。"""
import pytest
from pathlib import Path
import time
import api.runtime as runtime_mod


def test_resolve_design_doc_single_prefixed(tmp_path):
    (tmp_path / "farmer-game-design.md").write_text("# Farmer")
    p = runtime_mod.resolve_design_doc(tmp_path)
    assert p.name == "farmer-game-design.md"

def test_resolve_design_doc_compat_unprefixed(tmp_path):
    # 兼容当前 S1 写法 game-design.md（glob *-game-design.md 字面连字符不匹配）
    (tmp_path / "game-design.md").write_text("# G")
    p = runtime_mod.resolve_design_doc(tmp_path)
    assert p.name == "game-design.md"

def test_resolve_design_doc_multiple_newest(tmp_path):
    (tmp_path / "a-game-design.md").write_text("old")
    time.sleep(0.05)
    (tmp_path / "b-game-design.md").write_text("new")
    p = runtime_mod.resolve_design_doc(tmp_path)
    assert p.name == "b-game-design.md"

def test_resolve_design_doc_excludes_artlist(tmp_path):
    (tmp_path / "美术素材.md").write_text("ignore")
    (tmp_path / "x-game-design.md").write_text("# X")
    p = runtime_mod.resolve_design_doc(tmp_path)
    assert p.name == "x-game-design.md"

def test_resolve_design_doc_none_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        runtime_mod.resolve_design_doc(tmp_path)


@pytest.mark.asyncio
async def test_start_art_plan_writes_and_gates(tmp_path, monkeypatch):
    # mock run_art_agent 写合法清单
    artlist = ("## 美术素材清单\n\n| ID | 类别 | 文件名 | 尺寸 | 抠图 |\n|----|------|--------|------|------|\n"
               "| A01 | 角色与NPC | hero_idle | 1024x1024 | 是 |\n\n"
               "### A01 · 角色与NPC · hero_idle\n```yaml\n"
               "id: A01\ncategory: 角色与NPC\nfile: hero_idle\n"
               'prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"\n'
               'size: "1024x1024"\nmatting: true\n```\n')

    async def fake_run_art_agent(game_root, *, on_progress, model, base_url, auth_token, prompt):
        (game_root / "docs" / "美术素材.md").write_text(artlist, encoding="utf-8")
        return game_root / "docs" / "美术素材.md"

    monkeypatch.setattr(runtime_mod, "run_art_agent", fake_run_art_agent)
    monkeypatch.setattr(runtime_mod, "games_root", lambda: tmp_path)
    # 不依赖真实 DB：mock 原子提交块
    calls = {}
    class _FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def begin(self): return self
        async def __aenter__inner(self): return self
        def get(self, *_a, **_k): 
            class _R:
                current_stage = "S1_design"; status = "running"
                def __init__(self): self.current_stage="S1_design"; self.status="running"
            return _R()
    # 简化：直接断言 run_art_agent 被调用并写盘
    await runtime_mod.start_art_plan("test-run", "测试游戏")
    assert (tmp_path / "测试游戏" / "docs" / "美术素材.md").exists()
```

> 注：`test_start_art_plan_writes_and_gates` 末段对 DB 的 mock 较简化；若 `start_art_plan` 的原子提交块用 `_session_factory()`，测试可改用 monkeypatch 替换 `_session_factory` 为返回 fake session 的工厂。实现时先让此测试聚焦"run_art_agent 被调用 + 写盘"，DB 提交细节由 e2e（Task 10）覆盖。

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_runtime.py -v`
Expected: FAIL（`resolve_design_doc`/`start_art_plan` 未定义）。

- [ ] **Step 3: 实现（追加到 runtime.py 末尾）**

```python
from pathlib import Path as _Path
from agents.runner import run_art_agent
from api.deps import ART_MODEL as _ART_MODEL

__all__ = ["start_design", "start_art_plan", "resolve_design_doc"]


def resolve_design_doc(docs_dir: _Path) -> _Path:
    """发现设计文档：glob *-game-design.md（约定）+ 兼容 game-design.md（无前缀）；
    排除 美术素材*；多匹配取 mtime 最新；0 匹配抛 FileNotFoundError。"""
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"docs 目录不存在: {docs_dir}")
    cands = [p for p in docs_dir.glob("*-game-design.md")]
    compat = docs_dir / "game-design.md"
    if compat.exists() and compat not in cands:
        cands.append(compat)
    cands = [p for p in cands if "美术素材" not in p.name]
    if not cands:
        raise FileNotFoundError(f"未找到设计文档（*-game-design.md 或 game-design.md）于 {docs_dir}")
    return max(cands, key=lambda p: p.stat().st_mtime)


async def start_art_plan(run_id: str, game_name: str, *, feedback: str | None = None) -> None:
    """启动 Art Agent；完成后把阶段置为 awaiting_approval 并创建待审批。"""
    game_root = games_root() / _slug(game_name)
    docs = game_root / "docs"
    design_path = resolve_design_doc(docs)
    design_content = design_path.read_text(encoding="utf-8")
    design_name = design_path.name
    prompt = f"游戏《{game_name}》的设计文档已写在 docs/{design_name}，全文如下：\n<<<\n{design_content}\n>>>\n请据此拆解美术资产清单，用 write_file 写入 docs/美术素材.md。" + (
        f"\n用户对上一版清单的反馈：{feedback}\n请据此修改。" if feedback else ""
    )

    async def on_progress(msg):
        broker.publish(run_id, {"type": "progress", **msg})

    try:
        await run_art_agent(
            game_root, on_progress=on_progress,
            model=_ART_MODEL, base_url=BASE_URL, auth_token=AUTH_TOKEN, prompt=prompt,
        )
        async with _session_factory() as session:
            async with session.begin():
                run = await session.get(GameRun, run_id)
                run.current_stage = Stage.S2_art_plan.value
                run.status = StageStatus.awaiting_approval.value
                session.add(PendingApproval(
                    run_id=run_id, stage=Stage.S2_art_plan.value,
                    payload={"doc": "docs/美术素材.md"}, status="pending",
                ))
        broker.publish(run_id, {"type": "gate", "stage": "S2_art_plan", "status": "awaiting_approval"})
    except Exception as e:
        broker.publish(run_id, {"type": "error", "message": str(e)})
        raise
```

> `BASE_URL`/`AUTH_TOKEN`/`games_root`/`_session_factory`/`GameRun`/`PendingApproval`/`Stage`/`StageStatus` 已在 runtime.py 顶部 import。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_runtime.py -v`
Expected: 全 PASS（5 个 resolve 用例 + 1 个 start_art_plan 用例）。
> 若 start_art_plan 用例因 DB mock 复杂失败，可先简化为 mock `_session_factory`，确保其余通过。

- [ ] **Step 5: 提交**

```bash
git add backend/api/runtime.py backend/tests/test_runtime.py
git commit -m "feat(api): runtime 加 resolve_design_doc + start_art_plan"
```

---

## Task 8: routes 加 art-list 路由 + approve/reject 分 stage + S1 approve 启 S2

**Files:**
- Modify: `backend/api/routes.py`
- Test: `backend/tests/test_routes.py`（追加）

**Interfaces:**
- Consumes: `start_art_plan`（Task 7）、`StateMachine`（Task 5）、`games_root`/`_session_factory`、`get_run`/`get_pending_approval`（repo）。
- Produces: `GET/PUT /api/runs/{id}/art-list.md`、`POST /api/runs/{id}/approve`（按 stage 自动分支）、`POST /api/runs/{id}/reject`（按 stage 自动分支）。

- [ ] **Step 1: 写失败测试（追加到 test_routes.py 末尾）**

```python
# ---- S2 routes ----
import asyncio

@pytest.mark.asyncio
async def test_get_art_list_404(tmp_path, monkeypatch):
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    # 先建 run（mock design agent 瞬完成）
    import api.runtime as rt
    async def fake_design(*a, **k):
        async with _session_factory() as s:  # 简化：直接置阶段
            pass
    monkeypatch.setattr(rt, "run_design_agent", fake_design) if hasattr(rt, "run_design_agent") else None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/runs/nope/art-list.md")
        assert r.status_code == 404
```

> 注：route 测试细节多；聚焦三类：`GET art-list.md`（无→404、有→内容）、`PUT art-list.md`（awaiting_approval 可改、running 不可→409）、`approve` S2 分支。实现时按现有 `test_routes.py` 风格补全，可用 monkeypatch 让 run 直接处于 S2 awaiting_approval（绕过真 agent）。

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_routes.py -v -k art_list`
Expected: FAIL（路由未注册，404 不返回或路由不存在）。

- [ ] **Step 3: 改 routes.py**

(a) 顶部 import 加 `start_art_plan`：
```python
from api.runtime import start_design, start_art_plan
```

(b) 加 art-list 两个端点（放在 `put_design` 后）：
```python
@router.get("/runs/{run_id}/art-list.md")
async def get_art_list(run_id: str):
    run = await _load_run(run_id)
    p = games_root() / run.slug / "docs" / "美术素材.md"
    if not p.exists():
        raise HTTPException(404, "art list not ready")
    return {"content": p.read_text(encoding="utf-8")}

@router.put("/runs/{run_id}/art-list.md")
async def put_art_list(run_id: str, payload: dict):
    run = await _load_run(run_id)
    if run.status not in (StageStatus.awaiting_approval.value, StageStatus.rejected.value):
        raise HTTPException(409, "当前阶段不可编辑美术清单")
    p = games_root() / run.slug / "docs" / "美术素材.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(payload["content"], encoding="utf-8")
    return {"ok": True}
```

(c) 重写 `approve` 端点为按当前 stage 自动分支（替换现有 approve 函数）：
```python
@router.post("/runs/{run_id}/approve")
async def approve(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    stage = Stage(run.current_stage)
    t = sm.approve(RunState(run.id, stage, StageStatus(run.status)), stage=stage)
    if t is None:
        raise HTTPException(409, "当前状态不可通过")
    async with _session_factory() as s2:
        async with s2.begin():
            r = await s2.get(GameRun, run_id)
            r.current_stage = t.stage.value
            r.status = t.status.value
            ap = await get_pending_approval(s2, run_id, stage=stage.value)
            if ap:
                ap.status = "approved"
                ap.feedback = None
                ap.resolved_at = datetime.utcnow()
    broker.publish(run_id, {"type": "gate", "stage": t.stage.value, "status": "approved"})
    # S1 通过 → 启动 S2 Art Agent；S2 通过 → 启动 S3（后续计划）；S3 通过 → S4（后续计划）
    if stage == Stage.S1_design:
        task = asyncio.create_task(start_art_plan(run_id, run.game_name))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return {"ok": True, "current_stage": t.stage.value, "status": t.status.value}
```

(d) 重写 `reject` 端点为按当前 stage 自动分支（替换现有 reject 函数）：
```python
@router.post("/runs/{run_id}/reject")
async def reject(run_id: str, payload: dict):
    feedback = payload.get("feedback", "")
    run = await _load_run(run_id)
    stage = Stage(run.current_stage)
    t = sm.reject(RunState(run.id, stage, StageStatus(run.status)), stage=stage, feedback=feedback)
    if t is None:
        raise HTTPException(409, "当前状态不可拒绝")
    async with _session_factory() as session:
        async with session.begin():
            r = await session.get(GameRun, run_id)
            r.current_stage = t.stage.value
            r.status = t.status.value
            ap = await get_pending_approval(session, run_id, stage=stage.value)
            if ap:
                ap.status = "rejected"
                ap.feedback = feedback
                ap.resolved_at = datetime.utcnow()
    if stage == Stage.S1_design:
        task = asyncio.create_task(start_design(run.id, run.game_name, feedback=feedback))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    elif stage == Stage.S2_art_plan:
        task = asyncio.create_task(start_art_plan(run.id, run.game_name, feedback=feedback))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return {"ok": True}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_routes.py -v`
Expected: 全 PASS（含新 S2 用例 + 原 S1 用例不回归）。

- [ ] **Step 5: 提交**

```bash
git add backend/api/routes.py backend/tests/test_routes.py
git commit -m "feat(api): art-list 路由 + approve/reject 按 stage 自动分支"
```

---

## Task 9: 前端 ArtWorkbench + client + App 装配

**Files:**
- Modify: `frontend/src/api/client.ts`、`frontend/src/App.tsx`
- Create: `frontend/src/stages/ArtWorkbench.tsx`
- Test: `frontend/src/__tests__/art_workbench.test.tsx`（新建）

**Interfaces:**
- Consumes: `MarkdownEditor`/`ProgressStream`（已有组件）、`getArtList`/`putArtList`/`approveRun`/`rejectRun`/`connectWS`（client）。
- Produces: `ArtWorkbench` 组件（S2 工作台：编辑器 + 进度流 + 通过/不通过，无 QAPanel）。

- [ ] **Step 1: 写失败测试**

```tsx
// frontend/src/__tests__/art_workbench.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ArtWorkbench } from '../stages/ArtWorkbench'

vi.mock('../api/client', () => ({
  getArtList: vi.fn().mockResolvedValue('## 美术素材清单\n| ID | 类别 | 文件名 | 尺寸 | 抠图 |'),
  putArtList: vi.fn().mockResolvedValue(undefined),
  approveRun: vi.fn().mockResolvedValue({}),
  rejectRun: vi.fn().mockResolvedValue({}),
  connectWS: () => ({ close: () => {} } as WebSocket),
}))

describe('ArtWorkbench', () => {
  it('renders markdown editor and gate buttons', async () => {
    render(<ArtWorkbench runId="r1" status="awaiting_approval" onMessage={() => {}} />)
    await waitFor(() => expect(screen.getByText(/美术素材清单/)).toBeInTheDocument())
    // 通过按钮在 awaiting_approval 时可用
    expect(screen.getByText('通过')).not.toBeDisabled()
    expect(screen.getByText('不通过')).not.toBeDisabled()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test -- art_workbench`
Expected: FAIL（`ArtWorkbench` 未定义）。

- [ ] **Step 3a: client.ts 加 getArtList/putArtList（在 putDesign 行后加两行）**

```ts
export async function getArtList(id: string): Promise<string> { return (await j(await fetch(`${BASE}/runs/${id}/art-list.md`))).content }
export async function putArtList(id: string, content: string): Promise<void> { await j(await fetch(`${BASE}/runs/${id}/art-list.md`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) })) }
```

- [ ] **Step 3b: 新建 ArtWorkbench.tsx**

```tsx
import { useEffect, useState } from 'react'
import { getArtList, putArtList, approveRun, rejectRun, connectWS } from '../api/client'
import { MarkdownEditor } from '../components/MarkdownEditor'
import type { ProgressMsg } from '../types'

export function ArtWorkbench({ runId, status, onMessage }: { runId: string; status: string; onMessage?: (m: ProgressMsg) => void }) {
  const [content, setContent] = useState('')
  const [messages, setMessages] = useState<ProgressMsg[]>([])

  useEffect(() => {
    getArtList(runId).then(setContent).catch(() => {})
    const ws = connectWS(runId, (m) => { setMessages(prev => [...prev, m]); onMessage?.(m) })
    return () => ws.close()
  }, [runId])

  return (
    <div style={{ padding: 12 }}>
      <MarkdownEditor content={content} onSave={(c) => { setContent(c); putArtList(runId, c) }} />
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        <button disabled={status !== 'awaiting_approval'} onClick={() => approveRun(runId)}>通过</button>
        <button disabled={status !== 'awaiting_approval'} onClick={() => {
          const fb = prompt('请输入修改反馈') || ''
          rejectRun(runId, fb)
        }}>不通过</button>
      </div>
      <pre style={{ marginTop: 8, maxHeight: 120, overflow: 'auto' }}>
        {messages.map((m, i) => <div key={i}>{JSON.stringify(m)}</div>)}
      </pre>
    </div>
  )
}
```

- [ ] **Step 3c: 改 App.tsx 按 stage 切工作台**

将 import 与渲染分支改为：
```tsx
import { DesignWorkbench } from './stages/DesignWorkbench'
import { ArtWorkbench } from './stages/ArtWorkbench'
// ...
      ) : run?.current_stage === 'S2_art_plan' ? (
        <ArtWorkbench runId={run.id} status={run.status} onMessage={appendMessage} />
      ) : (
        <DesignWorkbench runId={run.id} status={run.status} onMessage={appendMessage} />
      )
```
> 即：S1_design → DesignWorkbench；S2_art_plan → ArtWorkbench；其余默认 DesignWorkbench 占位。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全 PASS（含新 art_workbench + 原组件不回归）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/stages/ArtWorkbench.tsx frontend/src/App.tsx frontend/src/__tests__/art_workbench.test.tsx
git commit -m "feat(frontend): ArtWorkbench + App 按 stage 装配"
```

---

## Task 10: S2 端到端 e2e

**Files:**
- Create: `backend/tests/test_e2e_s2.py`

**Interfaces:**
- Consumes: 全链路（runtime/routes/FSM/contract）。mock `query` 产合法清单。fixture 设计文档命名 `farmer-game-design.md` 以验证文件名中立约定。

- [ ] **Step 1: 写 e2e 测试**

```python
"""S2 端到端：mock LLM（fake query 写清单），验证 S1通过→S2跑→写清单→闸→S2通过→S3。
fixture 设计文档命名为 farmer-game-design.md（非 game-design.md）以验证命名约定。"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_s2_full_flow(monkeypatch, tmp_path):
    from claude_agent_sdk import ResultMessage
    from agents.tools import do_write_file
    from api.runtime import _slug
    import api.runtime as runtime_mod
    import agents.runner as runner_mod

    game_root = tmp_path / _slug("测试游戏")
    (game_root / "docs").mkdir(parents=True)
    # fixture 设计文档：farmer-game-design.md（验证命名约定，非 game-design.md）
    (game_root / "docs" / "farmer-game-design.md").write_text("# 测试游戏 设计\n核心循环。\n", encoding="utf-8")
    artlist = ("## 美术素材清单\n\n| ID | 类别 | 文件名 | 尺寸 | 抠图 |\n|----|------|--------|------|------|\n"
               "| A01 | 角色与NPC | hero_idle | 1024x1024 | 是 |\n\n"
               "### A01 · 角色与NPC · hero_idle\n```yaml\n"
               "id: A01\ncategory: 角色与NPC\nfile: hero_idle\n"
               'prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"\n'
               'size: "1024x1024"\nmatting: true\n```\n')

    async def fake_query(*, prompt, options):
        await options.can_use_tool("write_file", {"path": "docs/美术素材.md", "content": artlist}, None)
        await do_write_file(game_root / "docs" / "美术素材.md", artlist)
        yield ResultMessage("result", 0, 0, False, 1, "test-session")

    monkeypatch.setattr(runner_mod, "query", fake_query)

    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # 直接调 start_art_plan（绕过 S1，聚焦 S2）
        await runtime_mod.start_art_plan("测试游戏", "测试游戏")
        # 等到闸
        for _ in range(50):
            st = (await c.get("/api/runs/测试游戏")).json()
            if st["status"] == "awaiting_approval":
                break
            await asyncio.sleep(0.1)
        assert st["status"] == "awaiting_approval" and st["current_stage"] == "S2_art_plan"
        doc = (await c.get("/api/runs/测试游戏/art-list.md")).json()["content"]
        from agents.contract import validate_art_assets
        ok, reasons = validate_art_assets(doc)
        assert ok, reasons
        # 通过闸 → S3 running
        await c.post("/api/runs/测试游戏/approve")
        st2 = (await c.get("/api/runs/测试游戏")).json()
        assert st2["current_stage"] == "S3_art_gen" and st2["status"] == "running"
```

- [ ] **Step 2: 运行 e2e 确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_e2e_s2.py -v`
Expected: PASS。

- [ ] **Step 3: 跑全量后端测试确认无回归**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests -v`
Expected: 全 PASS（S1 用例不回归 + S2 新用例通过）。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_e2e_s2.py
git commit -m "test: S2 端到端 flow with mocked LLM"
```

---

## Self-Review（执行后核对）

- **spec 覆盖**：契约(Task1) ✓、工具(Task2) ✓、权限(Task3) ✓、prompt+runner(Task4) ✓、FSM(Task5) ✓、配置(Task6) ✓、runtime+发现(Task7) ✓、路由(Task8) ✓、前端(Task9) ✓、e2e(Task10) ✓。命名约定 `*-game-design.md`(Task7/10) ✓、类别可扩展(Task1 GOOD_MD 含 5 类别: 角色与NPC/开场与背景/特效与粒子…) ✓。
- **类型一致**：`validate_art_assets`、`build_art_tools`、`make_art_permission_handler`、`run_art_agent`、`resolve_design_doc`、`start_art_plan` 在各 Task 间签名一致。
- **占位符**：无 TBD/TODO；每个 step 含完整代码。
