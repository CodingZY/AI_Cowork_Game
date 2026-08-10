# Art Agent（S2）设计规格书

> 本 spec 覆盖 `美术素材.md` 的生产者：Art Agent（S2 阶段）。
>
> Art Agent 读取 S1 产出的设计文档（约定命名 `*-game-design.md`，如 `farmer-game-design.md`，由运行时发现），将其拆解为明确的美术资产清单，产出 `docs/美术素材.md`。该清单同时供 Asset Pipeline（S3）消费——故 `美术素材.md` 的格式契约由本 spec 拥有，S3 spec 引用并定义其解析器。
>
> 本文是 `doc/agent-system-design.md`（总架构）的子项目细化，仅描述 S2。S1 已实现（Design Agent），S3/S4 由各自 spec 覆盖。

---

## 0. 设计总览

### 0.1 定位

Art Agent 是 S2 阶段的 **LLM agent**：它读设计文档、推理该拆哪些资产、为每项生成含背景约束的 prompt，是真正需要 LLM 推理的环节。这与 S3（Asset Pipeline，确定性异步流水线、无 LLM）形成对照——S2 生产清单，S3 消费清单。

Art Agent **镜像 Design Agent 的接线**，但去掉 `ask_user`：它是**自主**的——读设计 → 拆清单 → 写文件，不向用户提问。用户在阶段闸前直接在 MarkdownEditor 里编辑 `美术素材.md`；不通过则带反馈重跑 agent。

### 0.2 与 README/总架构的对齐

- README §Art Agent 要求：每个资产含 `[ID]、[类别]、[描述]、[推荐生成 Prompt：含纯白背景/无场景/无地面/无阴影背景/无边框/无UI/仅保留角色本体]、[尺寸/透明度要求]`；并举例四类资产——开场/背景、角色与NPC、地图与建筑物、物品与UI。**README 的"等等"表明该清单非穷举**——本 spec 视其为推荐默认集，`category` 可按游戏类型扩展更多类别（见 §1.2、§0.3 决策 8）。
- 总架构 §1 工具表：Art Agent 工具 = `read_file`、`write_file(美术素材.md)`，写权限作用域仅 `Games/<name>/docs/美术素材.md`。
- 总架构 §0.2 阶段链：S1 design → **S2 art-plan**（本 spec）→ S3 art-gen。闸：用户确认素材清单。
- **设计文档命名约定 `*-game-design.md`**：S1 将设计文档命名为 `<游戏名>-game-design.md`（`*` = 游戏名/项目名前缀，如 `farmer-game-design.md`）。S2 按此模式发现，不硬编码具体文件名（见 §4.2、§0.3 决策 7）。

### 0.3 已确认的设计决策

1. **形状**：S2 是 LLM agent（跑 `claude_agent_sdk.query()`），不是确定性流水线。
2. **自主**：无 `ask_user`，不问用户；产物闸前用户直接编辑文件。
3. **`美术素材.md` 格式**：总分结构 + 每资产一个 fenced YAML 块（见 §1）。人可编辑、机可解析。
4. **抠图时机**：S2 不抠图，只产清单；抠图是 S3 逐张按需（见 S3 spec）。
5. **approve/reject**：按 run 当前 stage 自动判定，不新增持久化表。
6. **重跑**：不通过 → 带反馈重调 `query()`（镜像 S1 reject）。
7. **设计文档命名 `*-game-design.md`（兼容性）**：S1 将设计文档命名为 `<游戏名>-game-design.md`（如 `farmer-game-design.md`）。S2 运行时 glob `*-game-design.md` 发现，不硬编码具体文件名。兼容当前 S1 写法 `game-design.md`（无前缀，glob `*-game-design.md` 字面含连字符故不匹配它，发现规则同时接受之，见 §4.2）。S1 日后按约定改命名，S2 无需改动。
8. **资产类别可扩展（兼容性）**：`category` 为非空字符串而非封闭枚举。README 四类（开场/背景、角色与NPC、地图与建筑物、物品与UI）为推荐默认集；Art Agent 视游戏类型可增补更多类别（如载具、特效与粒子、过场动画、音效图标等），不限四类。详见 §1.2、§2.3。

---

## 1. 共享契约：`美术素材.md` 格式

本节是 S2 的**输出契约**，也是 S3 的**输入契约**（S3 spec 引用此节）。

### 1.1 总分布局

顶部一张汇总表，其后每个资产一个 ` ```yaml ` fenced 块：

````markdown
## 美术素材清单
> 由 Art Agent 读取游戏设计文档（`*-game-design.md`）拆解生成；用户可直接编辑本文件。
> 每项资产对应下方一个 YAML 块；Pipeline 按块批量生成图像。

| ID | 类别 | 文件名 | 尺寸 | 抠图 |
|----|------|--------|------|------|
| A01 | 角色与NPC | hero_idle | 1024×1024 | 是 |
| A02 | 开场/背景 | title_screen | 1024×1024 | 否 |
| A03 | 地图与建筑物 | floor_tile | 512×512 | 是 |
| A04 | 物品与UI | coin | 512×512 | 是 |
| A05 | 特效与粒子 | harvest_effect | 512×512 | 是 |

> 上表含 5 个类别——前 4 个为 README 推荐默认集，第 5 个「特效与粒子」为按本游戏类型增补的扩展类别，说明类别不限于四类。

### A01 · 角色与NPC · hero_idle
```yaml
id: A01
category: 角色与NPC
file: hero_idle
prompt: "像素风少年农夫站姿，正面居中，纯白背景，无场景，无地面，无阴影背景，无边框，无UI，仅保留角色本体"
size: "1024x1024"
matting: true
```

### A02 · 开场/背景 · title_screen
```yaml
id: A02
category: 开场/背景
file: title_screen
prompt: "像素风农场开场画面，远景麦田与农舍，天空晨光，16:9 构图，可含场景"
size: "1024x1024"
matting: false
```
````

### 1.2 YAML 块字段 schema

| 字段 | 必填 | 类型 | 约束 |
|---|---|---|---|
| `id` | 是 | str | 全局唯一；正则 `^A\d{2,}$`（`A` + 至少 2 位数字，如 A01、A12、A123、A9999）；无上限，兼容大型游戏大量资产 |
| `category` | 是 | str | **非空字符串，非封闭枚举**。推荐默认四类：`开场/背景`、`角色与NPC`、`地图与建筑物`、`物品与UI`；可按游戏类型增补更多类别（如`载具`、`特效与粒子`、`过场动画`、`音效图标`）。Art Agent 须用一致命名 |
| `file` | 是 | str | 文件名（无后缀）；slug 安全（小写字母/数字/下划线/连字符，正则 `^[a-z0-9][a-z0-9_-]*$`）；产物为 `<file>.png` |
| `prompt` | 是 | str | 非空；含绘画风格（从设计文档提炼，如"像素风"） |
| `size` | 是 | str | `WxH` 格式（如 `1024x1024`、`512x512`）；宽高须为正整数 |
| `matting` | 是 | bool | `true`→该资产建议抠图（角色/物品/UI/特效等）；`false`→背景类不抠图 |

设计要点：
- **`id` 不含类别前缀**：类别作为字段而非 id 前缀，避免改名牵连编号。编号两位起步保证排序稳定，无上限兼容大型游戏。
- **`file` 是 slug**：直接作产物文件名，避免中文/空格落盘问题。
- **`matting` 是"是否建议抠图"**：决定 Pipeline 是否默认建议抠图，而非强制；S3 用户逐张可覆盖。
- **`category` 可扩展**：非封闭枚举，保证不同类型游戏（农场/科幻/解谜等）可自带所需类别，不被四类框死。

### 1.3 强制 prompt 子句（抠图可用性）

`matting: true` 的资产，其 `prompt` **必须**满足以下两条，保证抠图可用：
1. 含白色背景表述——正则 `纯白色?背景` 命中即可（兼容「纯白背景」与 README 原文「纯白色背景」）；
2. 含以下否定词系列中**至少一个**：「无场景」「无地面」「无阴影背景」「无边框」「无UI」「仅保留角色本体」「仅…本体」。

`matting: false`（开场/背景等）豁免此约束——其 prompt 允许含场景。

### 1.4 校验器 `validate_art_assets(md)`

放 `backend/agents/contract.py`，与 `validate_game_design` 并列。签名 `validate_art_assets(md: str) -> tuple[bool, list[str]]`，返回 (是否通过, 原因列表)。

校验项：
1. 内容非空；至少 1 个 ` ```yaml ` 块。
2. 每块 6 个必填字段齐全且类型正确（缺失/类型错记一条原因）。
3. `id` 全局唯一；符合 `^A\d{2,}$`。
4. `file` 符合 slug 规则 `^[a-z0-9][a-z0-9_-]*$`。
5. `category` 为非空字符串（**不做枚举校验**——允许 README 四类之外的扩展类别，保证不同游戏类型兼容）。
6. `size` 符合 `^\d+x\d+$`，宽高为正整数。
7. `matting: true` 者，prompt 命中 `纯白色?背景`（兼容「纯白背景」/「纯白色背景」）且含至少一个否定词（§1.3）。
8. 汇总表数据行数（排除表头行 `| ID |…|` 与分隔行 `|----|`）与 YAML 块数一致——人改易错处，不符给明确原因（在 S3 流水线启动时校验，避免花额度生成后才发现清单与表不一致）。

> 校验器不持有封闭类别集合——`category` 仅查非空。这使 S2 输出对任意游戏类型保持开放，是 §0.3 决策 8 的落地点。

---

## 2. Agent 接线

### 2.1 工具

镜像 Design Agent（`backend/agents/tools.py`），**去掉 `ask_user`**：

| 工具 | 用途 | 实现 |
|---|---|---|
| `read_file(path)` | 读设计文档（命名 `*-game-design.md`，运行时发现，见 §4.2）与本项目其他文件 | 复用现有 `do_read_file` 纯函数；权限限 game_root 内 |
| `write_file(path, content)` | 写 `docs/美术素材.md` | 复用现有 `do_write_file` 纯函数；路径限 `docs/美术素材.md` |

工具常量：**复用现有** `TOOL_READ_FILE` / `TOOL_WRITE_FILE`（`backend/agents/tools.py` 已定义，工具名同为 `read_file`/`write_file`）——Art Agent 不引入新工具名，仅工具集不含 `TOOL_ASK_USER`、写权限作用域不同（§2.2）。

新增 `build_art_tools(game_root) -> McpSdkServerConfig`：与 `build_design_tools` 同构，仅含 `read_file`/`write_file`，无 `ask_user`（故无 `AskFn` 参数）。

### 2.2 权限沙箱

新增 `make_art_permission_handler(game_root)`（`backend/agents/permissions.py` 扩展），与 `make_permission_handler` 同构，写作用域改：

- `read_file`：路径解析后须在 game_root 内（同 Design）。
- `write_file`：仅允许 `(game_root / "docs" / "美术素材.md").resolve()`，其余 Deny。
- 未知工具 Deny。

### 2.3 System prompt

新增 `ART_SYSTEM_PROMPT`（`backend/agents/prompts.py` 扩展）。内容：

```
你是一名美术资产规划 Agent，负责读取游戏设计文档（命名 `*-game-design.md`，全文与文件名由 prompt 提供），
将其拆解为明确的美术资产清单，产出 docs/美术素材.md。

【工作方法】
1. 设计文档全文由 prompt 提供（命名约定 `*-game-design.md`，如 `farmer-game-design.md`）；
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
```

`ART_ASSETS_TEMPLATE`（与 `GAME_DESIGN_TEMPLATE` 并列，放 `contract.py`）即 §1.1 示例的通用骨架。

### 2.4 Runner

新增 `run_art_agent(...)`（`backend/agents/runner.py` 扩展），与 `run_design_agent` 同构，差异：
- `system_prompt=ART_SYSTEM_PROMPT`
- `tools=[TOOL_READ_FILE, TOOL_WRITE_FILE]`（无 `TOOL_ASK_USER`）
- `mcp_servers={"art-tools": build_art_tools(game_root)}`（无 `AskFn`）
- `can_use_tool=make_art_permission_handler(game_root)`
- 产物路径 `final_path = game_root / "docs" / "美术素材.md"`
- 无 `ask` 参数（签名去掉 `ask`）

签名：
```python
async def run_art_agent(
    game_root: Path, *, on_progress: ProgressFn,
    model: str, base_url: str | None, auth_token: str | None, prompt: str,
) -> Path:
```

`query()` 消息流消费同 Design（仅 `pass`；进度由 hooks 推）。

---

## 3. Orchestrator / FSM

`backend/orchestrator/states.py` 已有 `S2_art_plan`。`machine.py` 现仅实现 S1。扩展 S2 转移：

| 方法 | 触发 | 返回 Transition |
|---|---|---|
| `start_art_plan(run)` | runtime 启动 Art Agent | `(S2_art_plan, running)` |
| `complete_art_plan(run)` | agent 写完清单 | `(S2_art_plan, awaiting_approval)` |
| `approve(run, stage=S2_art_plan)` | 用户通过 S2 闸 | `(S3_art_gen, running)`（触发 S3 流水线） |
| `reject(run, stage=S2_art_plan, feedback)` | 用户不通过 | `(S2_art_plan, running)`（带反馈重跑） |

`approve` 改为按传入 `stage` 分支：S1→S2 **running**（本 spec §4.3 改：现状为 not_implemented，改为 running 以便 approve 路由随即启动 Art Agent）、S2→S3 running（本 spec）、S3→S4 not_implemented（S3 spec 加）。`reject` 同理分认 stage。守卫：仅在 `run.stage==stage and run.status==awaiting_approval` 时允许。

---

## 4. 持久化与 runtime

### 4.1 不新增表

现有 `GameRun` / `PendingApproval` 足够。S2 审批 payload：`{"doc": "docs/美术素材.md"}`（与 S1 审批 payload 同形——S1 的 `{"doc": "docs/<设计文档名>"}` 中设计文档名由 S1 实际写入决定，不固定）。资产逐张状态不入库——S3 由磁盘 `processed/` 存在性决定（见 S3 spec）。

### 4.2 Runtime

新增 `start_art_plan(run_id, game_name, *, feedback=None)`（`backend/api/runtime.py` 扩展），镜像 `start_design`：
- `game_root = games_root() / _slug(game_name)`
- **发现设计文档**（约定 `*-game-design.md`，§0.3 决策 7）：
  - `resolve_design_doc(game_root / "docs")`：glob `*-game-design.md`；为兼容当前 S1 写法，同时匹配无前缀的 `game-design.md`（glob `*-game-design.md` 字面含连字符，不匹配 `game-design.md`，故显式并列两条）。
  - 候选排除匹配 `*美术素材*` 者（本 spec 产物，非设计文档）。
  - 多匹配 → 取 mtime 最新；0 匹配 → 抛错并推 `error`（无设计文档，不启动 Art Agent）。
  - 读其全文 `design_content`、记文件名 `design_name`。
- `prompt`：注入设计文档全文与文件名，而非硬编码 `docs/game-design.md`：
  `f"游戏《{game_name}》的设计文档已写在 docs/{design_name}，全文如下：\n<<<\n{design_content}\n>>>\n请据此拆解美术资产清单，用 write_file 写入 docs/美术素材.md。"` + 反馈附言（重跑时附"上一版清单反馈：…"）。
- `ask` 参数：**无**（Art Agent 自主，工具集不含 `ask_user`，SDK 不暴露该工具；权限沙箱对未知工具 Deny，双重保证其无法调用 `ask_user`。agent 遇不确定时按设计文档自行决断，不阻塞）。
- `on_progress` 推 broker 进度流（同 Design）。
- 跑完 `run_art_agent` 后，**原子提交** `update_stage(S2 awaiting_approval) + create_approval(payload={"doc":"docs/美术素材.md"})`，复用现有显式事务模式（`async with _session_factory() as session: async with session.begin(): ...`）。
- broker 推 `{"type":"gate","stage":"S2_art_plan","status":"awaiting_approval"}`。
- 异常 → `broker.publish(run_id, {"type":"error","message":str(e)})` + raise。

> 发现规则对设计文档文件名按约定 `*-game-design.md` glob，并兼容当前 S1 的 `game-design.md`。S1 现写 `game-design.md`，将来按约定改写 `<游戏名>-game-design.md`（如 `farmer-game-design.md`），S2 无需改动。`resolve_design_doc` 可放 `backend/api/runtime.py` 或 `backend/agents/` 工具模块，单测覆盖 0/1/多匹配三种情形。

### 4.3 S1→S2 衔接

S1 `approve` 当前返回 `(S2_art_plan, not_implemented)`。改为 `(S2_art_plan, running)` 并在 `approve` 路由里启动 `start_art_plan` 后台任务（强引用持有，复用 `_background_tasks`）。即：用户通过 S1 设计闸 → 自动进 S2 跑 Art Agent。

---

## 5. REST 路由

`backend/api/routes.py` 扩展：

| 方法 路径 | 行为 |
|---|---|
| `GET /runs/{id}/art-list.md` | 读 `Games/<slug>/docs/美术素材.md`，返回 `{content}`；不存在 404 |
| `PUT /runs/{id}/art-list.md` | 仅 `awaiting_approval`/`rejected` 可编辑；写盘 |
| `POST /runs/{id}/approve` | 按 run 当前 stage 自动判定：S1→启 S2、S2→启 S3、S3→S4 |
| `POST /runs/{id}/reject` | 按 run 当前 stage：S1/S2 带反馈重跑；S3 重跑批量（兜底） |

`approve/reject` **不要求前端传 stage**——按 `run.current_stage` 自动分支（见 D 节决策）。`answer`（问答）路由 S2 不用，保留供 S1。

---

## 6. 前端

### 6.1 ArtWorkbench（S2）

新增 `frontend/src/stages/ArtWorkbench.tsx`，镜像 `DesignWorkbench.tsx`，差异：
- 读/写 `美术素材.md`（`getArtList`/`putArtList`，`client.ts` 扩展）。
- **无 QAPanel**（Art Agent 不问问题）。
- 保留进度流 + 通过/不通过按钮（按 `status==='awaiting_approval'` 启用）。

### 6.2 App 装配

`App.tsx` 按 `current_stage` 切工作台：`S1_design`→DesignWorkbench、`S2_art_plan`→ArtWorkbench、`S3_art_gen`→ArtifactsBoard（S3 spec）、其余占位。

---

## 7. 配置

`backend/.env.example` 扩展（本 spec 仅涉及 Art Agent 模型；图像 API key 归 S3）：
```env
# Art Agent 用的模型名（与 Design 同一端点）
ART_MODEL=claude-sonnet-4-6
```
真实 key 落 gitignored 的 `backend/.env`（复用 `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`）。

---

## 8. 测试

pytest + pytest-asyncio；mock 为主；用户不手动测 S2。

- **contract**：`validate_art_assets` 正反例——缺字段、重复 id、id 不符正则（如 `A1`/`A1`）、file 非 slug、**category 为空被拒但扩展类别（如`特效与粒子`）通过**、size 格式错、`matting:true` 缺白色背景表述、`matting:true` 缺否定词、汇总表行数与块数不符、空内容。各给通过/失败用例。**重点：含 5+ 类别的清单须通过校验，证明类别不限四类。**
- **discovery**：`resolve_design_doc` 情形——0 匹配（抛错）、单个 `farmer-game-design.md`（取之）、单个 `game-design.md`（兼容当前 S1，取之）、多个 `*-game-design.md`（取 mtime 最新）、排除 `美术素材*`。
- **runner**：mock `query`（`fake_query` 读设计 + 写清单），验证工具接线 + 权限作用域（写越界 Deny）。镜像 `test_runner.py`/`test_permissions.py`。
- **FSM**：`S1→S2 running→awaiting_approval→(approve)S3 running`、`(reject)S2 running`；守卫（非 awaiting_approval 时 approve/reject 返回 None）。
- **routes**：`GET/PUT art-list.md`（awaiting_approval 可改、running 不可）、`approve` S1 自动启 S2、`approve` S2、`reject` S2 带反馈重跑。
- **e2e**：`test_e2e_s2`——mock `query` 产合法清单 → 等到 awaiting_approval → 读 art-list.md 含校验通过内容 → approve → 进 S3 running。复用 `test_e2e_s1` 的 ASGITransport + set_games_root 模式。**fixture 设计文档命名为 `farmer-game-design.md`（非 `game-design.md`）以验证文件名中立。**

接真实 LLM 的端到端为可选手动步骤（用户授权时）。

---

## 9. 文件清单

**新建**：无独立新包；均在现有 `backend/agents/` 与 `frontend/src/stages/` 内扩展。

**修改**：
- `backend/agents/contract.py` — 加 `ART_ASSETS_TEMPLATE` + `validate_art_assets`
- `backend/agents/tools.py` — 加 `build_art_tools`（复用现有工具常量，无新常量）
- `backend/agents/permissions.py` — 加 `make_art_permission_handler`
- `backend/agents/prompts.py` — 加 `ART_SYSTEM_PROMPT`
- `backend/agents/runner.py` — 加 `run_art_agent`
- `backend/orchestrator/machine.py` — 加 S2 转移 + approve/reject 分 stage
- `backend/api/runtime.py` — 加 `start_art_plan` + `resolve_design_doc`（设计文档发现）
- `backend/api/routes.py` — 加 art-list 路由 + approve/reject 分 stage + S1 approve 启 S2
- `backend/api/deps.py` — 加 `ART_MODEL`
- `backend/.env.example` — 加 `ART_MODEL`
- `frontend/src/api/client.ts` — 加 `getArtList`/`putArtList`
- `frontend/src/stages/ArtWorkbench.tsx` — 新建
- `frontend/src/App.tsx` — 按 stage 切 ArtWorkbench
- `backend/tests/*` — 加 S2 用例（含 `resolve_design_doc` 三情形、5+ 类别清单校验）
- `frontend/src/__tests__/art_workbench.test.tsx` — 新建

---

## 10. 范围与边界

- **本 spec 只覆盖 S2**（Art Agent + `美术素材.md` 格式契约 + S1→S2→S3 衔接的 S2 侧）。
- **S3**（Asset Pipeline：imagegen/styletransfer/cutout/storage/编排 + 前端卡片）由 `doc/specs/2026-08-10-asset-pipeline-s3-design.md` 覆盖。两 spec 的接口面是 **`美术素材.md` 格式**（本 spec 拥有）与 **FSM `approve(S2)→S3 running`**（双方各写己侧）。
- **兼容性**（§0.3 决策 7/8）：设计文档命名约定 `*-game-design.md`（S2 按约定 glob 发现，兼容当前 S1 的 `game-design.md`，不要求立即改 S1）；资产类别可扩展（非封闭枚举）。S1 日后按约定写 `<游戏名>-game-design.md`，S2 无需改动。
- **S4**（Coder）与总架构子项目拆分（§6）由后续 spec 覆盖。
- 实施计划由后续 `writing-plans` 环节产出。
