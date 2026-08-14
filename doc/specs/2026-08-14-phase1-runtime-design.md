# Phase 1：Runtime 设计规格书

- **版本**：v0.1
- **日期**：2026-08-14
- **阶段**：doc §116 Phase 1（Runtime）
- **定位**：AI_Cowork_Game Backend 的 Agent Runtime 基座——把「官方 Claude Code CLI + 自部署 LLM 端点」以子进程方式接入 FastAPI 后端，跑通 `API → Claude → Stream → MySQL` 闭环，并为后续 Phase 2-6 提供可复用的 Runtime/Parser/EventStore。

本 spec 是 `AI_Cowork_Game Backend v0.1 技术实现方案.md`（120 章，下称「doc」）Phase 1 部分的落地设计。doc 给的是全貌，本 spec 给的是 Phase 1 的**精简、可施工**切片，并记录所有奠基决策与 spike 证据。

---

## 1. 目标与验收

### 1.1 目标

跑通 doc §116 Phase 1：

```
FastAPI + MySQL + Redis + Claude CLI + stream-json + session/resume
→ API → Claude → Stream → MySQL
```

### 1.2 验收链路（Definition of Done）

一条端到端链路，全部成立即 Phase 1 完成：

```
① POST /api/projects {name:"FarmDemo"}
   → project_service.create() → projects 行（status=CREATED）

② POST /api/projects/{id}/brainstorm {idea:"种田游戏"}
   → 入 Arq 队列 → 返回 202 {task_id}
   → project.status=BRAINSTORMING

③ Arq Worker run_brainstorm:
   → spawn `claude -p ... --output-format stream-json --bare`（子进程 cwd=workspace）
   → 经 KSPMAS kimi-k3 流式响应
   → Parser 归一化 → 每条 CoworkEvent 先落 MySQL events，再 XADD Redis Stream
   → brainstorm 多轮澄清后调 Write 落 Games/{key}/{名}-game-design.md
   → 收 result 事件 → 更新 agent_sessions + project 状态

④ GET /api/projects/{id}/stream?after=<event_id>
   → SSE：MySQL events 补历史 → Redis Stream 实时 → 逐条 yield CoworkEvent
   → 前端能看到 agent.message.delta / agent.tool.started / agent.session.completed 等

⑤ 第二轮 POST /api/projects/{id}/brainstorm {idea:"补充：NPC 要有作息"}
   → Worker 以 --resume <session_id> 续接同一 session
   → 续落库 → SSE 续看（验证 session/resume）
```

> MVP 验收（doc §117）的整链 Idea→GDD→Asset→V1→Build→Preview→Play→Feedback→V2→Approve 不在 Phase 1；Phase 1 只验收上述 ①-⑤ 的 Runtime 子链路。

---

## 2. 奠基决策记录

经需求确认对话拍板，以下决策约束本 spec 全文：

| # | 决策点 | 选定 | 影响 |
|---|---|---|---|
| D1 | 与旧 claude_agent_sdk 后端关系 | **清洁重建弃旧码** | `backend/` 已在工作区删除；不沿用旧 S1-S4 代码，从零搭 Phase 1 |
| D2 | 「Claude Code CLI 作 Agent Runtime」实现 | **真实 CLI 子进程** | 后端 spawn `claude`，解析 stream-json NDJSON |
| D3 | LLM 端点 | **KSPMAS kimi-k3** | 经金山云 Anthropic 兼容端点；需控制台已启用 kimi-k3 |
| D4 | 执行模型 | **异步队列 + Arq** | API 只建 Job 返 task_id，Worker 异步跑流式落库（doc §103） |
| D5 | 运行环境与基建 | **本机现成栈** | kscc + 本机 MySQL 8.0.39（在跑）+ 本机 Redis 5.0.14；Agent 的 Docker 隔离留 Phase 5 |
| D6 | 验收链路 | **brainstorm→落库→回放→resume** | 含 --resume，完整 Phase 1 栈 |
| D7 | 官方 CLI 安装与 spike | **现在装+重做 spike** | 已完成，见 §3 |
| D8 | 架构方案 | **A. 文档忠实型** | 严格按 doc §35/§102-105 建全模块 |
| D9 | workspace(cwd) 位置 | **项目内 `Games/{key}/`** | 沿用旧后端 farmer 夹具约定；git 内可追溯 |
| D10 | thinking block 处理 | **丢弃** | parser 不持久化/广播 thinking_delta、thinking_tokens |
| D11 | brainstorm agent 形态 | **对话 + 落 GDD 初稿** | brainstorm 末尾调 Write 落 `*-game-design.md` |
| D12 | 测试策略 | **CI mock + e2e 手动真打** | 单元/集成用录制 NDJSON；e2e 手动跑真 KSPMAS，不进 CI |

---

## 3. 可行性 Spike 证据

在写设计前，用「官方 claude 2.1.197 + KSPMAS kimi-k3」实测验证三件套（累计成本 ≈ $0.07）。

### 3.1 环境事实

- 本机**无** Anthropic `claude`，原有 `kscc 1.2.1`（金山系，D 盘 `node_global`）。
- 已 `npm i -g @anthropic-ai/claude-code` → **官方 claude 2.1.197**，装到 D 盘 `D:\Program Files (x86)\nodejs\node_global`（满足 C 盘约束）。
- 切端点机制（官方 claude）：`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_MODEL`。

### 3.2 spike 结果

| 验证项 | 命令要点 | 结果 |
|---|---|---|
| ① 端点连通 + stream-json | `claude -p "2+2" --output-format stream-json --verbose --include-partial-messages --bare` | ✅ `model:kimi-k3`，input 1546，`is_error:false`，`result:"4"`，事件序列完整 |
| ③ --resume 召回 | `claude --resume <sid> -p "上一轮答了什么" --bare` | ✅ `result:"4"` 正确召回，session_id 一致，input 仅 112 |
| ② tool_use 形态 | `--bare --allowedTools Read --permission-mode acceptEdits`，让它读 README.md | ✅ 事件结构清晰（见 §3.4），但触发 kimi-k3 审核 refusal（见 §3.5） |

### 3.3 关键发现（塑造架构）

1. **`--bare` 是硬性前提**。不带 `--bare` → 背 26707 token 宿主上下文（CLAUDE.md+memory+skills+superpowers plugin）+ superpowers 的 `SessionStart` hook 在 Windows PowerShell 报错 + 易触发 kimi-k3 审核 refusal。带 `--bare` → 1546 token、无 hook、正常完成。**doc §28 论点被实测验证**。
   - 注：`--bare` 未完全跳过 superpowers plugin（init 仍列它）。实现期需用更显式方式禁用（`--settings` 显式空配置 / 不挂载），确保 Runtime 子进程不染宿主环境。
2. **kimi-k3 带 `thinking` block**（glm-5.2 无）。`content_block` type=`thinking`，delta type=`thinking_delta`，另有 `system/thinking_tokens` 事件。parser 必须能跳过 thinking（D10 决策丢弃）。
3. **KSPMAS kimi-k3 内容审核风险真实**。非纯对话 / 多轮工具调用易触发 `stop_reason:refusal` / `is_error:true`（② 验证时调 PowerShell 找文件即触发）。runtime 必须区分**正常完成 / refusal / 协议错误**三态。
4. **session 按 cwd 存**。claude 本地 JSONL：`C:\Users\39335\.claude\projects\<cwd-hash>\<session_id>.jsonl`。`--resume` 要求子进程 cwd 与创建时一致——workspace 策略受此约束（D9）。

### 3.4 实测事件形态（补充 doc §31）

顶层事件类型：`system`、`stream_event`、`assistant`、`result`。

- `system` 子类型：`init`（含 session_id/model/tools）、`status`（requesting）、`thinking_tokens`、`hook_started`/`hook_response`（仅非 --bare）、`model_refusal_no_fallback`（审核拒绝）
- `stream_event.event.type`：`message_start`、`content_block_start`、`content_block_delta`、`content_block_stop`、`message_delta`、`message_stop`
- `content_block.type`：`thinking`、`text`、`tool_use`
- `delta.type`：`thinking_delta`、`text_delta`、`message_delta`（tool_use 无 delta，一次性）
- `tool_use`：`{"type":"tool_use","id":...,"name":"Read","input":{"file_path":...}}`
- `tool_result`（在后续 user 消息）：`{"type":"tool_result","content":...,"is_error":true/false}`
- `result`（终态）：含 `session_id`、`result`、`is_error`、`stop_reason`、`total_cost_usd`、`usage`、`duration_ms`、`num_turns`、`permission_denials`、`terminal_reason`

### 3.5 BASE_URL 待确认项

`.spike.env` 实测连通用的是 `ANTHROPIC_BASE_URL=https://kspmas.ksyun.com/v1/chat/completions`（注意是 `/v1/chat/completions` 路径，非 memory 记载的 `/v1/messages`）。实测确实返回 Anthropic 格式 stream-json，机制未深究（可能 KSPMAS 该路径同时兼容 Anthropic 协议，或 claude 路径拼接行为）。**实现期第一步需确认正确 BASE_URL 值与 claude 路径拼接机制**，写进 `.env` 前��通一次最小请求。

---

## 4. 架构与数据流（doc §2/§102-105）

### 4.1 模块清单（doc §5 目录，Phase 1 精简）

```
backend/app/
├── main.py                    FastAPI 入口；路由注册；lifespan（Arq pool 连接）
├── config/settings.py         Pydantic Settings：DB / Redis / Arq / LLM env
├── api/
│   ├── projects.py            POST /api/projects、GET /api/projects/{id}
│   └── events.py              GET /api/projects/{id}/stream（SSE 实时+补历史）
├── schemas/
│   ├── project.py             ProjectCreate / ProjectRead
│   └── event.py               CoworkEvent（对外统一事件，doc §33）
├── models/
│   ├── project.py             projects 表（doc §7 精简）
│   ├── agent_session.py       agent_sessions 表（doc §9）
│   └── event.py               events 表（doc §21）
├── agent/
│   ├── runtime.py             ClaudeRuntime（doc §102）：start / resume / cancel
│   ├── parser.py              ClaudeEventParser：stream-json → CoworkEvent 归一化
│   ├── session.py             session/workspace 管理（cwd 绑定、session_id 记录）
│   └── prompts.py             brainstorm agent 自研内联 system prompt
├── workflow/
│   ├── states.py              project 状态枚举（CREATED/BRAINSTORMING/...）
│   └── engine.py              状态机流转入口（Phase 1 只走 CREATED→BRAINSTORMING）
├── queue/
│   ├── tasks.py               Arq task：run_brainstorm(project_id)
│   ├── worker.py              Arq Worker 配置（Functions / RedisSettings）
│   └── jobs.py                enqueue 封装（API 调用入队）
├── services/
│   └── project_service.py     建项目、查状态、落 agent_session
├── persistence/
│   ├── db.py                  SQLAlchemy engine / session
│   └── repo.py                EventRepo / ProjectRepo / AgentSessionRepo
└── events/
    └── broker.py              EventBroker：先写 MySQL events，再 XADD Redis Stream
```

### 4.2 数据流

```
① POST /projects → project_service.create() → projects 行（CREATED）

② POST /projects/{id}/brainstorm
   → jobs.enqueue(run_brainstorm, id) → 返回 202 {task_id}
   → project.status = BRAINSTORMING

③ Arq Worker run_brainstorm:
   ├─ workflow.engine：状态校验（CREATED/BRAINSTORMING）
   ├─ acquire project lock（Redis，TTL 30min，doc §87）
   ├─ agent.session：确定 workspace=Games/{key}/ + 预备 agent_session 行
   ├─ agent.runtime.start(prompt, workspace, --bare):
   │    spawn claude -p ... --output-format stream-json --bare ...
   │    async for line in proc.stdout:
   │       for evt in parser.parse(line):
   │          broker.publish(evt)  ──► MySQL events 落库
   │                          └──► Redis Stream XADD stream:project:{id}
   ├─ 收 result 事件 → 提取 session_id/result/cost/is_error/stop_reason
   │    → 更新 agent_sessions + project 状态
   └─ release lock
   （第二轮）runtime.resume(session_id, 新prompt)：加 --resume，同上流式落库

④ GET /projects/{id}/stream?after=<event_id>:
   ├─ MySQL events where project_id=id and after 条件 → yield 历史
   └─ Redis XREAD stream:project:{id} block → yield 实时
   └─ SSE 逐条 yield CoworkEvent
```

---

## 5. 模块设计

### 5.1 `agent/runtime.py` — ClaudeRuntime（doc §102）

职责：封装 claude 子进程的启动、流式读取、resume、cancel；产出归一化前的逐行 NDJSON（交 parser）。

```python
class ClaudeRuntime:
    def __init__(self, settings: Settings): ...

    async def start(
        self, prompt: str, workspace: str,
        agent_type: str = "brainstorm",
        system_prompt: str | None = None,
    ) -> AsyncIterator[CoworkEvent]:
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json",
            "--verbose", "--include-partial-messages",
            "--bare",
            "--allowedTools", "Read", "Write",
            "--permission-mode", "acceptEdits",
        ]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        env = self._build_env()        # 注入 ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=PIPE, stderr=PIPE, cwd=workspace, env=env)
        async for line in proc.stdout:          # NDJSON，逐行
            for evt in self.parser.parse(line):
                yield evt
        await proc.wait()
        # 末条 result 事件含 session_id/result/cost/is_error/stop_reason

    async def resume(
        self, session_id: str, prompt: str, workspace: str, ...
    ) -> AsyncIterator[CoworkEvent]:
        # 同 start，追加 ["--resume", session_id]

    async def cancel(self, session_id: str):
        # Phase 1：终止 proc（保留接口，doc §102 cancel）
```

约束：
- **必须 `--bare`**（spike §3.3-1）。
- `cwd=workspace`：因 session 按 cwd 存（spike §3.3-4），workspace 全程不变。
- `env` 不继承宿主污染：仅注入 `.env` 的三变量 + 必要 PATH；剥离宿主 `CLAUDE_*`/`KSCC_*` 避免误连 glm-5.2。
- `--allowedTools Read,Write` + `--permission-mode acceptEdits`：brainstorm 需 Write 落 GDD 初稿（D11）；非交互 `-p` 下 acceptEdits 让 Write 自动放行。
- 子进程 stderr 收集用于诊断（不进 events，仅 log）。

### 5.2 `agent/parser.py` — ClaudeEventParser

职责：逐行 `json.loads` → 归一化为 `CoworkEvent`（doc §32-33，前端不直接依赖 claude 协议）。每条 CoworkEvent 带 `event_id`(uuid4)/`project_id`/`timestamp`/`type`/`data`。

事件映射（spike §3.4 实测）：

| claude 原始 | CoworkEvent.type | data | 说明 |
|---|---|---|---|
| `system/init` | `agent.session.started` | `{session_id, model, agent_type}` | 记 session_id；首条即有 |
| `content_block_delta` `text_delta` | `agent.message.delta` | `{text}` | 广播文本增量 |
| `content_block` `tool_use` | `agent.tool.started` | `{tool_use_id, name, input}` | 工具调用开始 |
| user 消息 `tool_result` | `agent.tool.completed` | `{tool_use_id, content, is_error}` | 工具返回 |
| `assistant` 完整消息 | `agent.message.completed` | `{text}` | 本轮终态文本 |
| `thinking_delta` / `thinking_tokens` | — | — | **丢弃**（D10） |
| `model_refusal_no_fallback` | `agent.refused` | `{reason:"content_review"}` | 审核拒绝 |
| `result`（is_error=false, stop_reason=end_turn） | `agent.session.completed` | `{session_id, result, cost, duration, stop_reason}` | 正常完成 |
| `result`（is_error=true / stop_reason=refusal） | `agent.refused` | `{reason, result}` | 审核失败（§5.6） |
| `result`（其他 is_error=true） | `agent.session.failed` | `{reason:"runtime_error", result}` | 协议/IO 错误 |

### 5.3 `agent/session.py` — session/workspace 管理

- `workspace_root = <repo>/Games/{project_key}/`（D9）。建项目时 `ensure_dir`。
- 每次 `runtime.start` 在 `agent_sessions` 预建一行（status=RUNNING, working_directory=workspace）；`system/init` 到来后回填 `claude_session_id`。
- `--resume`：从 `agent_sessions.claude_session_id` 取上次 session_id，`cwd` 必须与创建时一致（同一 workspace）。

### 5.4 `agent/prompts.py` — brainstorm 自研 system prompt

- Phase 1 **不依赖 superpowers**（doc §116 Phase 3 才接 Skills）。brainstorm 用内联 system prompt，经 `--append-system-prompt` 注入。
- prompt 要点：多轮澄清游戏创意（类型/核心玩法/美术风格/胜利条件等）→ 澄清充分后调 `Write` 落 `Games/{key}/{游戏名}-game-design.md` 初稿。
- **审核规避**（spike §3.3-3）：措辞中性、避免敏感词；工具调用受控（仅 Read/Write）；尽量少调 PowerShell/Bash（② 触发 refusal 的根因之一）。

### 5.5 `events/broker.py` — EventBroker（doc §35）

```python
class EventBroker:
    async def publish(self, evt: CoworkEvent):
        async with self.db.session() as s:        # 事务
            await EventRepo(s).insert(evt)        # 先落 MySQL events
        await self.redis.xadd(f"stream:project:{evt.project_id}", evt.dict())  # 再广播
```

原则：**每个 claude 原始事件先持久化，再向外广播**（doc §35）——前端断开事件不丢。

### 5.6 三态处理（spike §3.3-3）

`run_brainstorm` 收到 `result` 后按 `is_error`/`stop_reason` 分流：

| 状态 | 判定 | 处理 |
|---|---|---|
| 正常完成 | `is_error=false` 且 `stop_reason=end_turn` | `agent_sessions.status=COMPLETED`；`project.status` 保持 `BRAINSTORMING`（Phase 1 无后续阶段；可再 `POST /brainstorm` 以 `--resume` 续接澄清） |
| 审核 refusal | `stop_reason=refusal` 或 `model_refusal_no_fallback` | `agent_sessions.status=FAILED(reason=content_review)`；**Phase 1 不自动重试**；API/SSE 暴露 `agent.refused` |
| 协议/IO 错误 | proc 非零退出且无 result，或 `is_error=true` 非 refusal | `agent_sessions.status=FAILED(reason=runtime_error)` |

> refusal 自动重试留待后续阶段（doc §90 区分「盲目重试 vs 创建修复任务」）。Phase 1 先如实记录失败。

---

## 6. 数据模型（Phase 1 三表）

字符集 `utf8mb4`，引擎 `InnoDB`（doc §6）。

### 6.1 `projects`（doc §7 精简）

```sql
CREATE TABLE projects (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    project_key VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL,
    current_workflow_run_id BIGINT UNSIGNED NULL,
    workspace_root VARCHAR(1024) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX idx_projects_status(status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Phase 1 不用 `current_version_id`。`status`：CREATED / BRAINSTORMING / FAILED（Phase 1 子集，doc §7 全集后续补）。

### 6.2 `agent_sessions`（doc §9）

```sql
CREATE TABLE agent_sessions (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    project_id BIGINT UNSIGNED NOT NULL,
    claude_session_id VARCHAR(128) NULL,        -- system/init 到来后回填
    agent_type VARCHAR(64) NOT NULL,            -- Phase 1: BRAINSTORM
    status VARCHAR(32) NOT NULL,                 -- RUNNING/COMPLETED/FAILED
    working_directory VARCHAR(1024) NOT NULL,
    last_message_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX idx_agent_project(project_id),
    INDEX idx_agent_status(status),
    CONSTRAINT fk_agent_project FOREIGN KEY(project_id) REFERENCES projects(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 6.3 `events`（doc §21）

```sql
CREATE TABLE events (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    project_id BIGINT UNSIGNED NOT NULL,
    event_id CHAR(36) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,        -- agent_session / project
    aggregate_id BIGINT UNSIGNED NOT NULL,
    payload JSON NOT NULL,                       -- 归一化 CoworkEvent.data
    raw_json TEXT NULL,                           -- 原始 claude 行（调试用）
    created_at DATETIME(6) NOT NULL,
    UNIQUE KEY uk_event(event_id),
    INDEX idx_event_project(project_id),
    INDEX idx_event_aggregate(aggregate_type, aggregate_id),
    INDEX idx_event_created(created_at),
    CONSTRAINT fk_event_project FOREIGN KEY(project_id) REFERENCES projects(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 6.4 Redis 键（doc §22/§87）

```
lock:project:{project_id}:brainstorm     TTL 30min，heartbeat 续租
stream:project:{project_id}              XADD/XREAD 事件流
```

---

## 7. 内部事件协议（doc §33-34）

统一 `CoworkEvent`：

```json
{
  "event_id": "evt_<uuid4>",
  "project_id": 1001,
  "workflow_run_id": null,
  "task_id": null,
  "type": "agent.message.delta",
  "timestamp": "2026-08-14T10:00:00Z",
  "data": { "text": "我正在分析游戏核心循环..." }
}
```

Phase 1 事件类型子集（doc §34 全集的 Runtime 部分）：

```
agent.session.started
agent.session.completed
agent.session.failed
agent.refused
agent.message.delta
agent.message.completed
agent.tool.started
agent.tool.completed
workflow.started
workflow.state.changed
workflow.failed
```

---

## 8. API（doc §99/§100，Phase 1 精简）

```
POST   /api/projects                         建项目
GET    /api/projects/{id}                     查项目状态
POST   /api/projects/{id}/brainstorm          入队 brainstorm → 202 {task_id}
GET    /api/projects/{id}/stream?after=<eid>  SSE：补历史 + 实时
```

- `POST /brainstorm` 只建 Job 返 task_id（doc §104），Worker 异步执行。
- `GET /stream`：MySQL events（after 之后）→ yield 历史 → `XREAD stream:project:{id} BLOCK` → yield 实时（doc §101）。

---

## 9. `.env` 配置模板（backend/.env）

```ini
# === LLM（D3：KSPMAS kimi-k3，官方 claude 经此端点） ===
ANTHROPIC_BASE_URL=https://kspmas.ksyun.com/v1/chat/completions   # ⚠️ 待确认（spike §3.5）
ANTHROPIC_AUTH_TOKEN=<金山云 key>
ANTHROPIC_MODEL=kimi-k3
# 前置：KSPMAS 控制台已为本 consumer 启用 kimi-k3，否则 403

# === MySQL（D5：本机） ===
DB_URL=mysql+asyncmy://<user>:<pass>@127.0.0.1:3306/ai_cowork_game?charset=utf8mb4

# === Redis（D5：本机） ===
REDIS_URL=redis://127.0.0.1:6379/0

# === Arq ===
ARQ_QUEUE=agent

# === Runtime ===
WORKSPACE_ROOT=Games          # 相对 repo 根，project workspace = <repo>/Games/{key}/
```

> `.spike.env`（含真实 key，已 gitignore）作此模板底；实现期确认 BASE_URL 后迁入 `.env`。

---

## 10. 测试策略（D12）

| 层级 | 方式 | 是否打 KSPMAS |
|---|---|---|
| 单元（Parser） | 录制的 stream-json NDJSON 文件（spike 产物）喂入，断言归一化事件 | 否 |
| 集成（Arq worker） | "fake runtime"（in-process，吐录制事件）跑通 enqueue→落库→SSE | 否 |
| e2e（验收链路） | 真打 KSPMAS kimi-k3 跑 §1.2 ①-⑤ | **手动，不进 CI** |

理由：kimi-k3 审核 refusal 不可控（spike §3.3-3），进 CI 会不稳；e2e 手动跑既能验真链路又不拖 CI。

---

## 11. 已知风险与未决项

| 项 | 说明 | 处置 |
|---|---|---|
| BASE_URL 路径 | `/v1/chat/completions` vs `/v1/messages`，实测前者通、机制未明 | 实现期首步确认 claude 路径拼接，写 `.env` 前验通最小请求（spike §3.5） |
| `--bare` 未完全跳过 superpowers | init 仍列 plugin | 实现期用 `--settings` 显式空配置/不挂载，确保子进程不染宿主 |
| kimi-k3 审核 refusal | 多轮工具调用易触发 | brainstorm prompt 规避敏感词+少调 Bash/PowerShell（§5.4）；三态处理 §5.6；自动重试留后续 |
| thinking 丢弃是否够 | 调试期可能想看 thinking | D10 先丢弃；若调试需要，parser 加开关落 raw_json（不改协议） |
| 本机 Redis 未在跑 | 探测时 6379 拒绝连接 | 实现期启动本机 Redis 服务（或 `docker run -p 6379:6379 redis`） |

---

## 12. 阶段边界（不属 Phase 1）

- Phase 2：Git（GitHub App / clone / worktree / commit / tag）
- Phase 3：Skills（Superpowers / GDD / Game Design / Game Codegen / Game Testing）——brainstorm 换真正 skill
- Phase 4：Asset（MCP / 生图 / 抠图 / 存储）
- Phase 5：Build（Docker / npm test / build / preview）+ Agent Docker 隔离（doc §55）
- Phase 6：Feedback（分析 / 特征映射 / 改码 / V2）

Phase 1 完成后，`ClaudeRuntime`/`Parser`/`EventBroker`/`EventRepo` 应被后续阶段直接复用，无需重构（D8 价值）。

---

## 13. 下一步

本 spec 经用户 review 通过后，进入 `writing-plans` 产出实施计划：`doc/plans/2026-08-14-phase1-runtime-plan.md`，按 TDD 分步实现（Parser 单元先行 → Runtime → EventBroker → Arq worker → API/SSE → e2e 手动验收）。
