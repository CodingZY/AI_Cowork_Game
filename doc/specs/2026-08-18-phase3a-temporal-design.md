# 阶段1 Temporal 重构 设计规格书

- **版本**：v0.1
- **日期**：2026-08-18
- **阶段**：`第一阶段整体设计.md`（Claude Code CLI + Temporal 优化阶段1）
- **定位**：把阶段1从 **Arq task 编排** 重构为 **Temporal Workflow 编排**——`GameDesignWorkflow` 用 Activity/Signal/Query/wait_condition 实现可暂停、可恢复、可人工干预的长流程；02 brainstorm 产出结构化 **QuestionPlan JSON**（决策树+依赖+优先级+影响）；用户**逐题回答**经 Signal 回传；新增 **Requirements Snapshot** SSOT；GDD Check 改三态（PASS/WARNING/BLOCKING）。保留 ClaudeRuntime/GitService 作 Activity 底层。

本 spec 是 `第一阶段整体设计.md`（28 章）的落地设计，衔接既有 `doc/specs/2026-08-17-phase3a-frontend-design.md`（Arq 版阶段1，将被本次重构替换编排层）。

---

## 1. 目标与验收

### 1.1 目标

把阶段1的"用户创意→GDD"流程从 Arq 批量任务升级为 Temporal Human-in-the-Loop Workflow：

```
用户创意 → GameDesignWorkflow（Temporal）
  → Activity: analyze_idea（ClaudeRuntime spawn 02）→ QuestionPlan JSON
  → Workflow 暂停（wait_condition）→ 前端逐题展示
  → Signal: submit_answer/skip_question/change_answer
  → Activity: synthesize_requirements（game-requirements，不调 LLM）→ Requirements Snapshot
  → Activity: generate_gdd（ClaudeRuntime spawn 03）→ GDD.md
  → Activity: check_gdd（ClaudeRuntime spawn 04）→ PASS/WARNING/BLOCKING
  → PASS → COMPLETED；BLOCKING → 回 WAITING_USER 补充
```

### 1.2 验收链路（Definition of Done）

```
① POST /api/projects {name, idea} → 建 project + 起 GameDesignWorkflow（Temporal）
② Workflow Activity analyze_idea → spawn 02 产出 QuestionPlan JSON（结构化决策树）
③ GET /api/projects/{id}/state（Temporal Query）→ status=WAITING_USER + 当前问题 + 进度
④ 前端逐题展示（单题 + 选项 + 影响 + 推荐按钮）→ POST /api/projects/{id}/answer
⑤ Workflow Signal submit_answer → 推进下一题；skip_question 用 defaultOption；change_answer 重算依赖
⑥ 所有 blocking 问题答完 → Activity synthesize_requirements → Requirements Snapshot（SSOT）
⑦ Activity generate_gdd → spawn 03 读 Requirements Snapshot 生成 GDD.md
⑧ Activity check_gdd → spawn 04 → PASS（COMPLETED）/ BLOCKING（回 WAITING_USER）
⑨ 用户关网页后重开 → GET state 仍返回当前进度 → 继续（Workflow 持久化）
⑩ PASS 后 → POST /finalize → GitService commit/merge/push/tag → GitHub
```

---

## 2. 奠基决策记录

| # | 决策点 | 选定 | 影响 |
|---|---|---|---|
| D1 | Temporal 部署 | **Docker Temporal Server** | `docker run temporalio/auto-setup`（单容器 Temporal+Postgres）。Python 后端用 temporalio 1.31.0 SDK。与现有 MySQL/Redis 并存（Temporal 用自己的 Postgres） |
| D2 | 与现有代码关系 | **演进：保留 Runtime/Git，替换 Arq→Temporal** | ClaudeRuntime（spawn claude --bare --plugin-dir）、GitService、SSE 端点、前端骨架保留；Arq task → Temporal Workflow/Activity；02/03/04 SKILL + 前端组件按新设计重写 |
| D3 | LLM 调用策略 | **Batch LLM + Conditional Replanning** | 首轮 1 次 LLM 出 QuestionPlan；逐题答不需 LLM（Temporal 推进）；若答案触发重大分支（如选 combat）→ 第 2 次 LLM 重规划。不是"只调一次"也不是"每题一次" |
| D4 | Question Plan 形态 | **结构化 JSON 决策树** | `{questions:[{id, category, question, type, options:[{id,label,impact?,description?}], required, priority, depends_on?, default_option?, allow_custom?}]}`。02 SKILL 产出 JSON（非文本）；后端不再 parse_questions（改 JSON schema 校验） |
| D5 | 用户交互 | **逐题 Signal** | submit_answer / skip_question（用 default_option）/ change_answer（重算依赖）/ request_ai_recommendation。每题 `await wait_condition` 等待 |
| D6 | Requirements Snapshot | **SSOT 中间层** | 新增 game-requirements Skill（不调 LLM）：QuestionPlan + Answers + Defaults → requirements.json。GDD/Asset/Code 都从它派生 |
| D7 | GDD Check | **三态 PASS/WARNING/BLOCKING** | PASS→COMPLETED；WARNING→COMPLETED（带警告，不阻塞）；BLOCKING→回 WAITING_USER 补充。04 SKILL 输出三态 JSON |
| D8 | Skill 数 | **4 个** | game-brainstorm（出 QuestionPlan）/ game-requirements（轻量不调 LLM，合成 Snapshot）/ gdd-generator（读 Snapshot 生成 GDD）/ gdd-check（三态） |
| D9 | 前端状态获取 | **Temporal Query 轮询 + SSE 补充** | 主用 Query（GET /state 同步查询 Workflow 状态）；Activity 执行期（02/03/04 spawn 流）保留 SSE 推 agent.* 事件。Query 暴露可观察状态（phase/step/progress/currentQuestion/decisions），不暴露思维链 |
| D10 | 测试策略 | **temporalio TestWorkflowEnvironment + e2e 手动** | 单测用 SDK 内嵌环境（不需真 Server）；e2e 真 Temporal Server + 真打 KSPMAS + GitHub |
| D11 | Workflow 持久化 | **Temporal 自带** | `await wait_condition` 可等几天；用户关网页 Workflow 不丢；重开 Query 继续不需额外 DB 状态机（project.status 仍记录，但 Workflow 是真相） |
| D12 | 6 个状态 | **CREATED/ANALYZING/WAITING_USER/GENERATING_GDD/CHECKING_GDD/COMPLETED** | 简化状态机（文档 §26），WAITING_USER 是核心暂停态 |

---

## 3. 可行性 Spike 证据

| 验证项 | 方法 | 结果 |
|---|---|---|
| temporalio SDK | `pip install temporalio`（agent_env D 盘） | ✅ temporalio 1.31.0 |
| SDK API 语法 | 写 GameDesignWorkflow（@workflow.defn/run/signal/query + wait_condition + Worker + WorkflowEnvironment） | ✅ import/装饰器/类型全无误（`start_time_skipping` 环境启动慢，API 语法验证通过） |
| Docker | `docker --version` | ✅ 29.4.3（但 daemon 需 Docker Desktop 启动——实现期首步 `docker run temporalio/auto-setup`） |
| 真实 Temporal Server 连接 | 待 Docker Desktop 启动 | ⏳ 实现期 Task 0 验通 |

**关键发现**：temporalio Python SDK 的 `@workflow.defn`/`@workflow.signal`/`@workflow.query`/`workflow.wait_condition` 装饰器与文档设计完全对应——Signal=用户改世界（submit_answer）、Query=用户观察（get_state）、Workflow=持久化编排。`await workflow.wait_condition(lambda: q in self.answers)` 实现逐题暂停等待。

---

## 4. 架构与数据流

### 4.1 架构（文档 §23）

```
                     Frontend（React）
                       │
               HTTP（Query 轮询）+ SSE（Activity 流）
                       ▼
                Game API Server（FastAPI）
                       │
                Temporal Client
                       ▼
        ┌──────────────────────────────┐
        │     Temporal Server           │
        │  GameDesignWorkflow           │
        │  ├─ Activity: analyze_idea    │── ClaudeRuntime spawn 02 → QuestionPlan
        │  ├─ wait_condition（逐题）     │── Signal: submit_answer/skip/change
        │  ├─ Activity: synthesize_req  │── game-requirements（不调 LLM）→ Snapshot
        │  ├─ Activity: generate_gdd   │── ClaudeRuntime spawn 03 → GDD.md
        │  └─ Activity: check_gdd      │── ClaudeRuntime spawn 04 → 三态
        └──────────────────────────────┘
                       │
                GitService（finalize 落 git）
```

### 4.2 模块清单（重构后）

```
backend/
├── temporal/                         新增
│   ├── __init__.py
│   ├── workflows.py                  GameDesignWorkflow（@workflow.defn/run/signal/query/wait_condition）
│   ├── activities.py                 analyze_idea/synthesize_requirements/generate_gdd/check_gdd（调 ClaudeRuntime）
│   ├── worker.py                     Temporal Worker（注册 workflow+activities，连 Temporal Server）
│   └── client.py                     Temporal Client（start_workflow/signal/query 封装）
├── app/
│   ├── agent/runtime.py              保留（ClaudeRuntime --bare --plugin-dir，作 Activity 底层）
│   ├── git/service.py                保留（GitService，finalize 用）
│   ├── api/projects.py               改：POST /projects 起 Workflow；+GET /state（Query）+POST /answer（Signal）
│   ├── events/events.py              保留 SSE（Activity 执行期 agent.* 事件流）
│   ├── persistence/repo.py           保留（project/agent_session/project_repository）
│   └── config/settings.py           改：+temporal_host/port/namespace
├── game-skills/skills/
│   ├── game-brainstorm/SKILL.md       重写：产出 QuestionPlan JSON（非文本问题）
│   ├── game-requirements/SKILL.md    新增：QuestionPlan+Answers→Requirements Snapshot（不调 LLM）
│   ├── gdd-generator/SKILL.md        重写：读 Requirements Snapshot 生成 GDD
│   └── gdd-check/SKILL.md            重写：三态 PASS/WARNING/BLOCKING
└── （Arq tasks.py/jobs.py/worker.py  废弃或降级为仅 finalize 用）
frontend/
├── api/backend.ts                    改：+getState（Query）+submitAnswer/skipQuestion/changeAnswer（Signal）
├── features/1-brainstorm/
│   ├── QuestionCard.tsx              新增：单题展示（选项+影响+推荐+帮我决定）
│   ├── ProgressStepper.tsx          新增：✓/●/○ 进度条
│   └── SuperpowerChat.tsx           改：逐题驱动（Query 轮询 + SSE Activity 流）
```

### 4.3 数据流（全链路）

```
① POST /projects {name, idea} → project_service.create → Temporal Client.start_workflow
   (GameDesignWorkflow, id=f"game-{project_id}", input={idea})
   → project.status=ANALYZING

② Workflow.run → Activity analyze_idea
   → ClaudeRuntime.start(skill=game-brainstorm, prompt=idea, plugin_dir=game-skills)
   → spawn claude --bare → 产 question-plan.json（结构化决策树）
   → Activity 返回 QuestionPlan → Workflow 存 state.questionPlan
   → project.status=WAITING_USER

③ 前端 GET /api/projects/{id}/state → Temporal Query get_design_state
   → {phase:BRAINSTORM, status:WAITING_USER, progress:{answered:0,total:6}, currentQuestion:{...}, decisions:[]}
   → 前端 QuestionCard 渲染当前题（选项+影响+推荐按钮+帮我决定）

④ 用户选 → POST /api/projects/{id}/answer {questionId, answer}
   → Temporal Signal submit_answer → Workflow.wait_condition 解除 → 推进下一题
   → 依赖计算：若新题 depends_on 满足则问，否则 skip
   → GET /state 更新进度

⑤ 所有 blocking 问题答完 → Activity synthesize_requirements
   → game-requirements Skill（不调 LLM）：QuestionPlan + Answers + Defaults → requirements.json
   → Workflow 存 state.requirements

⑥ Activity generate_gdd → ClaudeRuntime.start(skill=gdd-generator, prompt=requirements)
   → 产 GDD.md → project.status=GENERATING_GDD

⑦ Activity check_gdd → ClaudeRuntime.start(skill=gdd-check, prompt=GDD)
   → 三态 JSON {status, blocking:[], warnings:[]}
   → PASS/WARNING → COMPLETED；BLOCKING → 回 WAITING_USER（generate_clarification）

⑧ POST /finalize → GitService commit/merge/push/tag → GitHub
```

---

## 5. 模块设计

### 5.1 `temporal/workflows.py` — GameDesignWorkflow（D5/D12）

```python
from dataclasses import dataclass, field
from temporalio import workflow

@dataclass
class AnswerSignal:
    question_id: str
    answer: str | None = None  # None = skip
    action: str = "answer"  # answer/skip/change

@workflow.defn
class GameDesignWorkflow:
    def __init__(self):
        self.question_plan: list[dict] = []
        self.answers: dict[str, str] = {}
        self.skipped: set[str] = set()
        self.requirements: dict = {}
        self.gdd: str = ""
        self.phase: str = "CREATED"

    @workflow.run
    async def run(self, idea: str) -> dict:
        self.phase = "ANALYZING"
        self.question_plan = await workflow.execute_activity(
            "analyze_idea", args=[idea], start_to_close_timeout=timedelta(minutes=15),
        )
        self.phase = "WAITING_USER"
        for q in self.question_plan:
            if not self._should_ask(q): continue
            if q.get("priority") == "optional": continue  # 不问 optional
            await workflow.wait_condition(lambda qid=q["id"]: qid in self.answers or qid in self.skipped)
            if q["id"] in self.answers and self._is_major_branch(q):
                # Conditional Replanning（D3）：重大分支触发重规划
                new_plan = await workflow.execute_activity("replan", args=[idea, self.answers])
                self.question_plan = new_plan  # 合并新问题
        self.phase = "SYNTHESIZING"
        self.requirements = await workflow.execute_activity("synthesize_requirements", args=[self.question_plan, self.answers])
        self.phase = "GENERATING_GDD"
        self.gdd = await workflow.execute_activity("generate_gdd", args=[self.requirements])
        self.phase = "CHECKING_GDD"
        check = await workflow.execute_activity("check_gdd", args=[self.gdd])
        if check["status"] in ("PASS", "WARNING"):
            self.phase = "COMPLETED"; return {"gdd": self.gdd, "check": check}
        # BLOCKING → 回 WAITING_USER
        self.phase = "WAITING_USER"
        clarification = await workflow.execute_activity("generate_clarification", args=[check])
        self.question_plan.extend(clarification["questions"])
        # 再进 wait_condition 循环（实现期用 while 包裹）

    @workflow.signal
    async def submit_answer(self, sig: AnswerSignal):
        if sig.action == "skip": self.skipped.add(sig.question_id)
        else: self.answers[sig.question_id] = sig.answer

    @workflow.query
    def get_design_state(self) -> dict:
        return {"phase": self.phase, "progress": {"answered": len(self.answers), "total": len(self.question_plan)},
                "currentQuestion": self._current_question(), "decisions": [{"id":k,"answer":v} for k,v in self.answers.items()]}
```

### 5.2 `temporal/activities.py` — Activity（D2/D4/D6/D7）

```python
@activity.defn
async def analyze_idea(idea: str) -> list[dict]:
    """Activity: spawn 02 game-brainstorm 产出 QuestionPlan JSON。"""
    runtime = ClaudeRuntime()
    result = ""
    async for evt in runtime.start(prompt=f"{idea}\n请调用 /game-brainstorm 产出 QuestionPlan JSON", cwd=..., plugin_dir=..., system_prompt=GDD_BRAINSTORM_PROMPT):
        if evt.type == "agent.session.completed": result = evt.data.get("result","")
    return _parse_json(result)  # 02 输出 JSON，schema 校验

@activity.defn
async def synthesize_requirements(question_plan, answers) -> dict:
    """Activity: 合成 Requirements Snapshot（D6：不调 LLM，纯 Python）。
    QuestionPlan + Answers + 每个 default_option → requirements dict（§20 schema）。
    不 spawn claude——game-requirements 是轻量合成层，非 LLM 推理。"""
    snapshot = {"game": {}, "core_loop": [], "v1": {}, "decisions": [], "assumptions": []}
    for q in question_plan:
        ans = answers.get(q["id"], q.get("default_option", ""))
        # 按 q["category"] 填 snapshot 对应字段（camera→game.camera 等）
        ...
    return snapshot

@activity.defn
async def generate_gdd(requirements: dict) -> str:
    """Activity: spawn 03 gdd-generator 读 Requirements Snapshot 生成 GDD.md。"""
    ...

@activity.defn
async def check_gdd(gdd: str) -> dict:
    """Activity: spawn 04 gdd-check → 三态 {status, blocking, warnings}。"""
    ...
```

### 5.3 4 个 Skill（D8）

**game-brainstorm/SKILL.md**（重写）：输入 idea → 输出 QuestionPlan JSON（§9 schema：id/category/question/type/options[{id,label,impact,description}]/required/priority/depends_on/default_option/allow_custom）。文档 §4 强调：每个选项带**设计影响**（impact）+ 推荐理由。不调 Write，只输出 JSON。

**game-requirements/SKILL.md**（新增，D6）：输入 QuestionPlan + Answers + Defaults → 输出 requirements.json（§20 schema：game/core_loop/v1/decisions/assumptions）。**不调 LLM**（纯合成，或 Activity 内纯 Python 实现，不 spawn claude）。

**gdd-generator/SKILL.md**（重写，D6/§13）：输入 Requirements Snapshot → GDD.md（§14 重点 12 节：Goal/CoreLoop/Player/Systems/Entities/Scenes/Input/UI/Assets/Progression/V1Scope/Acceptance）。**不重新理解游戏**（从 Snapshot 读，避免 GDD Agent 自行加 NPC）。调 Write 落 GDD.md。

**gdd-check/SKILL.md**（重写，D7/§15-16）：输入 GDD → 三态 JSON `{status: PASS|WARNING|BLOCKING, blocking:[...], warnings:[...]}`。检查"Code Agent 能否按此 GDD 做 V1"（非完整性）。BLOCKING=核心玩法/目标/系统规则缺失。

### 5.4 `temporal/client.py` — Temporal Client 封装

```python
async def start_design_workflow(project_id: int, idea: str) -> str:
    client = await Client.connect(f"{settings.temporal_host}:{settings.temporal_port}", namespace=settings.temporal_namespace)
    handle = await client.start_workflow(GameDesignWorkflow.run, idea, id=f"game-{project_id}", task_queue="game-design")
    return handle.id

async def send_signal(project_id, sig: AnswerSignal): await (await _get_handle(project_id)).signal(GameDesignWorkflow.submit_answer, sig)
async def query_state(project_id) -> dict: return await (await _get_handle(project_id)).query(GameDesignWorkflow.get_design_state)
```

### 5.5 API 端点（D9）

```
POST /api/projects {name, idea}    建项目 + 起 Workflow（改）
GET  /api/projects/{id}/state     Temporal Query get_design_state（新）
POST /api/projects/{id}/answer    Signal submit_answer（新，替 brainstorm/answer）
POST /api/projects/{id}/skip      Signal skip_question（新）
POST /api/projects/{id}/change     Signal change_answer（新）
POST /api/projects/{id}/finalize  GitService 落 git（保留）
GET  /api/projects/{id}/stream    SSE（Activity 执行期 agent.* 保留）
GET  /api/projects                 列表（保留）
GET  /api/projects/{id}/gdd        取 GDD（保留）
```

### 5.6 前端（D9/§12/§25）

- `QuestionCard.tsx`：单题（question + 选项带 impact + 推荐按钮 + "帮我决定"=skip + 自由输入）
- `ProgressStepper.tsx`：✓ 已答/● 当前/○ 待问（§15 状态机可视化）
- `SuperpowerChat.tsx`：Query 轮询 `/state`（每 2s）驱动 QuestionCard；Activity 期 SSE 显示 agent.* 流
- `api/backend.ts`：+getState/submitAnswer/skipQuestion/changeAnswer

---

## 6. 数据模型

- `project.status`：6 态（CREATED/ANALYZING/WAITING_USER/GENERATING_GDD/CHECKING_GDD/COMPLETED）
- `brainstorm_questions` 表：保留（存 QuestionPlan + Answers），但**Workflow 是真相**（表作快照/审计）
- Temporal 自带 Event History（design_events，文档 §21）——可查每个 Signal/Activity 记录
- `requirements.json` / `question-plan.json`：落 worktree（git 跟踪，doc §22 的 .ai-cowork/ 结构）

## 7. 测试策略（D10）

| 层级 | 方式 |
|---|---|
| Workflow 单测 | temporalio `WorkflowEnvironment.start_time_skipping`（内嵌，不需真 Server）——验 Signal 推进/wait_condition/Query 状态 |
| Activity 单测 | mock ClaudeRuntime（FakeRuntime）+ 验 Activity 返回 QuestionPlan/Snapshot/GDD/三态 |
| e2e | 真 Temporal Server（Docker）+ 真打 KSPMAS + GitHub，跑 §1.2 ①-⑩ |

## 8. 已知风险与未决项

| 项 | 说明 | 处置 |
|---|---|---|
| Docker Desktop 未启动 | daemon 连不上 | 实现期 Task 0 首步：启动 Docker Desktop + `docker run temporalio/auto-setup` 验通 |
| temporalio WorkflowEnvironment 启动慢 | spike 超时 | 单测用 `start_time_skipping`（自动跳过 wait_condition 的等待时间）；e2e 用真 Server |
| Activity 内 ClaudeRuntime spawn 慢 | 02/03/04 各 ~2min | Activity `start_to_close_timeout=15min`；Temporal 自动重试失败 Activity |
| kimi-k3 产出 JSON 不稳 | 02 应输出 JSON，但 kimi-k3 可能出文本 | 02 SKILL 强制 JSON 格式 + Activity 容错解析（JSON 失败→退解析或重试 Activity） |
| game-requirements 是否真不调 LLM | 文档说"不调 LLM" | Activity 内纯 Python 合成 Snapshot（QuestionPlan+Answers+Defaults→dict），不 spawn claude |
| Conditional Replanning 触发判定 | `_is_major_branch` 逻辑 | 简化：若答案触发 depends_on 新分支或明显改 genre → 触发；否则不重规划 |
| SSE vs Query 双通道 | Query 是轮询（非推送），Activity 期需 SSE 看流 | 前端：WAITING_USER 用 Query 轮询；Activity 期（ANALYZING/GENERATING/CHECKING）用 SSE 看 agent.* 流 |
| 既有 Arq 代码废弃 | run_brainstorm_questions/generate 删除 | 重构 Task：删 Arq task，保留 run_finalize（GitService）或也迁 Temporal |

## 9. 阶段边界

- 不做：Phase 2+（GDD→Asset/Code）；Temporal Child Workflow（留后续）；复杂 replanning（首轮简单分支判定够）
- 复用：ClaudeRuntime/GitService/SSE/前端骨架/api/backend.ts

## 10. 下一步

本 spec review 通过 → writing-plans 产出 `doc/plans/2026-08-18-phase3a-temporal-plan.md`，按 TDD 分步：Task0（Docker Temporal + SDK 连通）→ Workflows/Activities → 4 SKILL 重写 → API（Query/Signal）→ 前端逐题 → e2e。
