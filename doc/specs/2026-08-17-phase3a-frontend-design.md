# 阶段1前端连接 设计规格书

- **版本**：v0.1
- **日期**：2026-08-17
- **阶段**：SKILL 设计文档阶段1（需求→GDD）的前端连接
- **定位**：把阶段1后端（02 brainstorm + 03 gdd-generator + 04 gdd-check + finalize）接到前端，把前端阶段1从 mock 自演改成真后端交互——用户输入创意→02 产出**带选项的澄清问题**→用户选/答→03 生成 GDD→前端**可编辑 GDD**→04 检查→finalize 落 git。其余阶段（2-5）保留 mock。

本 spec 衔接 `doc/specs/2026-08-17-phase3a-skills-gdd-design.md`（阶段1后端）。前端现状是完整 mock 原型（`useGameStore` 用 `simulateAgentStream` + `mockData` 自演，不碰后端）。

---

## 1. 目标与验收

### 1.1 目标

跑通阶段1的**真后端逐轮交互**（前端发起、SSE 看流、可编辑 GDD），只 2 次 KSPMAS（出题 + 生成），不逐轮 resume：

```
用户输入创意 → POST /projects（CREATED）→ POST /brainstorm
  → spawn 02 一次：产出带选项问题 → 解析存 DB → BRAINSTORMING（等用户答）
  → 前端渲染问题 + OptionChips（选项 + 自由输入）
  → 用户答完 → POST /brainstorm/answer
  → spawn 03 一次：拼答案生成 GDD.md + manifest → GDD_REVIEW
  → 前端显示 GDD.md（可编辑）→ 用户改完 → POST /gdd/submit
  → 后端写回 worktree GDD.md → 04 GDD Check → PASS=GDD_APPROVED / FAIL=回 GDD_REVIEW
  → GDD_APPROVED → POST /brainstorm/finalize → commit+merge+push+tag → GitHub
```

### 1.2 验收链路（Definition of Done，前端逐条验证）

```
① 前端新建游戏（输入名）→ 后端真建 project（status=CREATED）→ 前端进入 brainstorm
② 输入游戏创意发送 → POST /brainstorm → SSE 收 02 产出的问题 → 前端渲染成
   OptionChips（每个问题：选项 chips + 自由输入框）
③ 用户选选项/自填答案 → POST /brainstorm/answer → SSE 收 03 生成 GDD 的流式文本
   → project=GDD_REVIEW → 前端显示 GDD.md
④ 前端 GDD.md 可编辑（Markdown 编辑/预览切换）→ 改完 POST /gdd/submit
   → SSE 收 04 GDD Check → PASS → GDD_APPROVED
⑤ GDD_APPROVED 后前端显示"定稿落 git"按钮 → POST /brainstorm/finalize
   → SSE 收 git.* → GitHub 有 games/{key}/GDD.md + brainstorm-{key}-v0 tag
⑥ 若 04 FAIL → 回 GDD_REVIEW，前端可再改 GDD 重提交
⑦ 若 02/03 kimi-k3 refusal → SSE 显示 agent.refused + project FAILED，前端提示
```

---

## 2. 奠基决策记录

经需求确认对话拍板，以下决策约束本 spec 全文：

| # | 决策点 | 选定 | 影响 |
|---|---|---|---|
| D1 | 改造范围 | **只接阶段1，其余保留 mock** | 阶段1（brainstorm/GDD）数据源切真后端；阶段 2-5 保持 mock 不动。最小闭环 |
| D2 | brainstorm 交互 | **2 次 KSPMAS（出题+生成）**，不逐轮 resume | 02 一次出所有带选项问题→用户答完→03 一次生成。不做"再确认是否还有需求"那轮（避免多轮 refusal 叠加，e2e 已见 kimi-k3 高度不稳） |
| D3 | 澄清问题呈现 | **带选项，用户选选项或自由输入** | 02 产出"问题+选项"文本，后端解析成结构化 `[{id,question,options}]`，前端 OptionChips 渲染（复用现有 `OptionChips` 组件风格） |
| D4 | 02 出题机制 | **02 SKILL 改：产出带选项问题文本，不落 concept、不内部多轮** | 02 输出格式 `N. 问题 (A)选项 (B)选项`（spike 验证 kimi-k3 能一次产 6 个带选项问题）。后端正则解析成结构化。concept 移到 03 读 answers 生成 |
| D5 | GDD 可编辑 | **前端可编辑 GDD.md，提交写回 worktree** | 新增 POST /gdd/submit：后端把用户编辑的 GDD.md 写回 worktree，再跑 04。用户审查/改 GDD 是 Approval Gate 的实质（doc §82） |
| D6 | 跨域 | **vite proxy（已配），不加 CORS** | vite.config 已配 `/api → 127.0.0.1:8000`，前端 dev 同源，不经浏览器跨域。SSE 经 vite proxy 需验通（长连接，vite proxy 默认支持但需测） |
| D7 | brainstorm 两阶段编排 | **两个 Arq job**（出题 job + 答案后续 job） | run_brainstorm 改两阶段：job1 spawn 02 出题→BRAINSTORMING（等答）；POST /brainstorm/answer enqueue job2 spawn 03 生成→GDD_REVIEW。比"一个 job 挂起等答"简单（复用 Arq，无挂起状态） |
| D8 | 问题解析容错 | **kimi-k3 文本格式依赖 + 容错** | 后端正则解析"N. 问题 (A).. (B).."；解析失败当"无选项，自由文本答"。02 prompt 强制格式降低失败率 |
| D9 | SSE 接入 | **复用后端 /api/projects/{id}/stream** | 阶段1后端 SSE 端点已透传 agent.*/git.*/gdd.* 事件。前端用 EventSource 连，按事件类型更新 store/UI。注意 EventSource 不支持自定义 header（用 query 传 after） |
| D10 | 测试策略 | **后端单测 sqlite+Fake，前端 e2e 手动** | 后端问题解析器/parser 单测；前端改动靠手动 e2e（真打 KSPMAS+GitHub）。沿用阶段1 D10 |

---

## 3. 可行性 Spike 证据

写 spec 前实测验证 **02 能一次产出带选项的澄清问题**（关键悬念：kimi-k3 能否按要求产出结构化带选项问题）。

| 验证项 | 方法 | 结果 |
|---|---|---|
| 02 一次出带选项问题 | spawn `claude -p "用户给了'种田游戏'创意，提一批澄清问题，每个给(A)(B)(C)选项"` `--bare` | ✅ kimi-k3 一次产出 6 个带选项问题：`1. 目标平台？(A)手机移动端 (B)PC端 (C)PC/网页多平台` / `2. 核心玩法...` 等，rc=0，stop_reason=end_turn，session_id 可 resume |

**关键发现**：kimi-k3 在 `-p` 非交互模式能一次产出结构化的"问题+选项"文本（非 JSON，是 `N. 问题 (A).. (B)..` 格式）。后端正则解析此格式即可结构化。这支撑 D2（2 次 KSPMAS：出题一次）+ D4（02 改产出问题）。

> spike 产物 throwaway；实现期 02 SKILL 改 prompt 强制此格式 + 后端解析器容错。

---

## 4. 架构与数据流

### 4.1 前端现状（衔接）

```
frontend/src/
├── main.tsx → App.tsx（BrowserRouter）         入口
├── store/useGameStore.ts                       mock 自演（simulateAgentStream + nextAgentReply 脚本）
├── api/client.ts                               早期脱节骨架（/api/runs，与后端不符，实际未用）
├── services/mockApi.ts + mockData.ts           mock 数据/流式
├── hooks/useAgentWebSocket.ts                  mock WS（dispatch no-op）
└── features/1-brainstorm/
    ├── BrainstormHub.tsx                        阶段1页面（ArchivedGameGrid + SuperpowerChat）
    ├── SuperpowerChat.tsx                        聊天 UI（用 store，模拟逐轮）
    ├── NewGameDialog.tsx                         新建游戏弹窗（startNewGame 本地建）
    ├── OptionChips.tsx                           选项 chips 组件（复用）
    └── LandedCard.tsx                            落地卡片
```

**改造原则**（D1）：只改阶段1数据源（store 的阶段1 actions + SuperpowerChat/NewGameDialog）+ 新增真 API 客户端 + SSE hook。阶段 2-5 的 store actions + 页面保持 mock 不动。

### 4.2 模块清单（新增/改动）

```
backend/
├── app/
│   ├── main.py                                改：确认无需 CORS（vite proxy 同源）；若 SSE 经 proxy 有问题再加
│   ├── api/projects.py                        改：+GET /projects（列表）+GET /projects/{id}/gdd +POST /brainstorm/answer +POST /gdd/submit
│   ├── agent/prompts.py                        改：02 出题 prompt + 03 读 answers 生成 prompt
│   ├── queue/tasks.py                         改：run_brainstorm 拆两阶段（出题 job1 / 生成 job2）；run_gdd_check 复用
│   ├── queue/jobs.py                           改：+enqueue_brainstorm_answer
│   ├── git/service.py                          不改（run_gdd_check 已用 worktree_path）
│   ├── agent/parser.py                         不改
│   └── persistence/repo.py                     改：+QuestionRepo（存/取澄清问题）+GddRepo（取 GDD.md/manifest 文件内容）
│   ├── models/                                 改：+brainstorm_questions 表（存每轮问题+答案）
├── game-skills/skills/02-game-brainstorm/SKILL.md  改：产出带选项问题（不落 concept）
└── game-skills/skills/03-gdd-generator/SKILL.md   改：读 answers（非 concept）生成 GDD
frontend/src/
├── api/backend.ts                              新增：真后端 API 客户端（createProject/listProjects/getProject/enqueueBrainstorm/submitAnswer/getGdd/submitGdd/approveGdd/finalize）+ connectSSE
├── hooks/useSSE.ts                             新增：EventSource 连 /api/projects/{id}/stream，派发事件到 store
├── store/useGameStore.ts                       改：阶段1 actions 切真后端（startNewGame/sendAnswer/submitGdd/approveGdd/finalizeGdd），保留 mock 阶段 2-5
├── features/1-brainstorm/
│   ├── SuperpowerChat.tsx                       改：真逐轮（02 问题→OptionChips→答→03 生成→GDD 审查）
│   ├── NewGameDialog.tsx                        改：startNewGame 调 createProject
│   ├── GddReviewPanel.tsx                      新增：GDD.md 可编辑（Markdown 编辑/预览）+ 提交/批准按钮
│   └── QuestionForm.tsx                        新增：一批带选项问题的表单（OptionChips + 自由输入）
└── 其余 features/2-5                            不动（mock）
```

### 4.3 数据流（全链路）

```
① 前端 NewGameDialog 输入名 → store.startNewGame(name)
   → POST /api/projects → project_service.create → CREATED + project_repositories
   → 前端存 project{id,key,status} → 进入 brainstorm 页

② SuperpowerChat 输入创意 → store.sendIdea(idea)
   → POST /api/projects/{id}/brainstorm {idea} → enqueue run_brainstorm_job1
   → SSE 连 /api/projects/{id}/stream
   → Worker job1: spawn 02（plugin_dir game-skills，prompt="提一批带选项澄清问题"）
     → 收 02 result 文本 → 解析成 questions[{id,question,options}] → 存 brainstorm_questions 表
     → event brainstorm.questions_ready {questions} → project=BRAINSTORMING（等答）
   → 前端 SSE 收 brainstorm.questions_ready → 渲染 QuestionForm（OptionChips + 自由输入）

③ 用户答完 → store.submitAnswers(answers)
   → POST /api/projects/{id}/brainstorm/answer {answers} → enqueue run_brainstorm_job2
   → Worker job2: 拼答案进 prompt → spawn 03（plugin_dir，prompt="读答案生成 GDD.md+manifest"）
     → 落 worktree/games/{key}/GDD.md + gdd-manifest.json → project=GDD_REVIEW
     → event git.*（无，brainstorm 阶段不开 worktree？或复用 Phase2 worktree）
   → 前端 SSE 收 agent.*（03 生成流）+ gdd.review_ready → 显示 GddReviewPanel

④ GddReviewPanel 显示 GDD.md（GET /api/projects/{id}/gdd）→ 可编辑
   → 用户改完 → store.submitGdd(gdd_md)
   → POST /api/projects/{id}/gdd/submit {gdd_md} → 后端写回 worktree GDD.md
     → run_gdd_check（spawn 04）→ PASS → GDD_APPROVED / FAIL → 回 GDD_REVIEW
   → 前端 SSE 收 gdd.check.passed/failed

⑤ GDD_APPROVED → 前端显示"定稿落 git" → store.finalizeGdd()
   → POST /api/projects/{id}/brainstorm/finalize → run_finalize → git.* → GitHub
```

---

## 5. 模块设计

### 5.1 后端 API 新增/改动

**GET /api/projects**（列表，前端 ArchivedGameGrid）：
```python
@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)):
    return await ProjectRepo(session).list_all()  # 新增 ProjectRepo.list_all
```

**GET /api/projects/{id}/gdd**（取 GDD.md + manifest 内容）：
```python
@router.get("/projects/{pid}/gdd")
async def get_gdd(pid: int):
    # 读 worktree/games/{key}/GDD.md + gdd-manifest.json 返回 {gdd_md, manifest}
```
用 GitService.worktree_path + 读文件。

**POST /api/projects/{id}/brainstorm/answer**（用户答案触发 03）：
```python
@router.post("/projects/{pid}/brainstorm/answer", status_code=202)
async def submit_answer(pid: int, body: AnswerBody, session=Depends(get_session)):
    # 校验 status=BRAINSTORMING，存 answers 到 brainstorm_questions 表
    # enqueue run_brainstorm_job2(pid)
    return {"task_id": job_id}
```

**POST /api/projects/{id}/gdd/submit**（用户编辑的 GDD 写回 + 04）：
```python
@router.post("/projects/{pid}/gdd/submit", status_code=202)
async def submit_gdd(pid: int, body: GddBody):
    # 校验 status=GDD_REVIEW，写回 worktree/games/{key}/GDD.md
    # 置 GDD_CHECKING，enqueue run_gdd_check(pid)
    return {"task_id": job_id}
```

### 5.2 `run_brainstorm` 拆两阶段（D7）

现有 run_brainstorm（阶段1后端：两次 spawn 02+03 一次跑完）改为两阶段：

**job1（出题）**：`run_brainstorm_questions(ctx, project_id, idea)`
- 状态校验 → 置 BRAINSTORMING → worktree_add（复用 Phase2）+ git 前置
- spawn 02（plugin_dir，prompt=GDD_BRAINSTORM_QUESTIONS_PROMPT + idea）
- 收 02 result 文本 → **解析成 questions**（§5.3）→ 存 brainstorm_questions 表
- event `brainstorm.questions_ready {questions}` → project 保持 BRAINSTORMING（等答）
- 三态：refused/runtime_error → FAILED

**job2（生成）**：`run_brainstorm_generate(ctx, project_id)`
- 状态校验 BRAINSTORMING → 读 brainstorm_questions 表的 answers
- spawn 03（plugin_dir，prompt=GDD_GEN_PROMPT + answers）
- 落 GDD.md + manifest → event `gdd.review_ready` → project=GDD_REVIEW
- 三态：refused/runtime_error → FAILED

### 5.3 问题解析器（D8）

`app/agent/questions_parser.py`（新）：
```python
def parse_questions(text: str) -> list[dict]:
    """解析 kimi-k3 的 'N. 问题 (A)选项 (B)选项' 文本成 [{id, question, options:[...]}]。
    容错：解析失败返回 []（前端当无选项自由文本答）。"""
    # 正则：行首 数字. 问题文本，然后匹配 (A).. (B).. 选项
    # 例："1. 目标平台？(A)手机 (B)PC (C)网页" → {id:"1", question:"目标平台？", options:["手机","PC","网页"]}
```
单测：给 spike 的 6 问题文本，断言解析出 6 个结构。容错：乱格式→[]。

### 5.4 02/03 SKILL 改 + prompts 改（D4）

**02-game-brainstorm/SKILL.md** 改：
- 不再"内部多轮澄清 + 落 concept"
- 改为：输入用户创意 → 输出"一批带选项的澄清问题"（格式 `N. 问题 (A)选项 (B)选项`，4-6 个，覆盖平台/2D·3D/核心循环/时长/NPC/美术风格）
- 只 Read，不 Write（不落文件）

**03-gdd-generator/SKILL.md** 改：
- 不再"读 .brainstorm-concept.md"
- 改为：输入"用户创意 + 澄清答案" → 生成 GDD.md(17节) + gdd-manifest.json
- 读 answers（后端拼进 prompt 或落 answers.json 让 03 读），Write GDD.md+manifest

**prompts.py** 改：
- `GDD_BRAINSTORM_QUESTIONS_PROMPT`：指示 02 产出带选项问题（强制格式）
- `GDD_GEN_PROMPT`：指示 03 读 answers 生成 GDD

### 5.5 brainstorm_questions 表（新）

```sql
CREATE TABLE brainstorm_questions (
    id BIGINT PK, project_id BIGINT NOT NULL,
    round INT NOT NULL,              -- 第几轮（阶段1固定 1，留扩展）
    questions JSON NOT NULL,         -- [{id,question,options}]
    answers JSON NULL,               -- 用户答案 [{question_id, answer}]
    created_at, updated_at,
    FK(project_id)→projects
);
```
QuestionRepo：`create(project_id, round, questions)` / `get_latest(project_id)` / `set_answers(project_id, round, answers)`。

### 5.6 前端 `api/backend.ts`（D9）

```typescript
const BASE = '/api'  // vite proxy → 后端 8000
export async function createProject(name, description) { /* POST /projects */ }
export async function listProjects() { /* GET /projects */ }
export async function getProject(id) { /* GET /projects/{id} */ }
export async function enqueueBrainstorm(id, idea) { /* POST /brainstorm */ }
export async function submitAnswer(id, answers) { /* POST /brainstorm/answer */ }
export async function getGdd(id) { /* GET /projects/{id}/gdd → {gdd_md, manifest} */ }
export async function submitGdd(id, gddMd) { /* POST /gdd/submit */ }
export async function finalizeGdd(id) { /* POST /brainstorm/finalize */ }

export function connectSSE(projectId, onEvent, onDone?) {
  const es = new EventSource(`${BASE}/projects/${projectId}/stream?after=0`)
  es.onmessage = (e) => onEvent(JSON.parse(e.data))
  return () => es.close()  // 返回取消函数
}
```

### 5.7 前端 store 阶段1 actions 改

`useGameStore` 阶段1 actions 从 mock 改真后端：
- `startNewGame(name)` → `createProject(name)` → � project 到 store.games
- `sendIdea(idea)` → `enqueueBrainstorm(id, idea)` + `connectSSE` 收事件
- `submitAnswers(answers)` → `submitAnswer(id, answers)`
- `loadGdd()` → `getGdd(id)` → store.gddMd
- `submitGdd(gddMd)` → `submitGdd(id, gddMd)`（写回 GDD + 触发 04，主路径）
- `approveGdd()` → `/gdd/approve`（不改 GDD 直接 04，快路径——用户认可 03 生成的不改）。submit 与 approve 都跑 04，区别是 submit 先写回 GDD.md。前端按是否编辑选其一。
- `approveGdd()` → （04 PASS 后自动 GDD_APPROVED，无需额外 approve；或保留 /gdd/approve 走 04）
- `finalizeGdd()` → `finalizeGdd(id)`

SSE 事件驱动 store 更新：
- `brainstorm.questions_ready` → store.currentQuestions = questions（渲染 QuestionForm）
- `agent.message.delta` → store.chat 追加（03 生成流）
- `gdd.review_ready` → store.stage = GDD_REVIEW（显示 GddReviewPanel）
- `gdd.check.passed` → store.stage = GDD_APPROVED
- `gdd.check.failed` → store.stage = GDD_REVIEW + 显示 reasons
- `git.*` → 终态 git.tagged → 完成

**阶段 2-5 的 actions（sendCoderFeedback/generateAsset 等）保持 mock 不动**（D1）。

### 5.8 前端组件

- `QuestionForm.tsx`（新）：渲染一批问题，每个用 `OptionChips`（选项）+ Input（自由输入），收集答案 submit
- `GddReviewPanel.tsx`（新）：GDD.md 显示/编辑（react-markdown 渲染 + textarea 编辑切换），提交/批准按钮
- `SuperpowerChat.tsx` 改：状态机驱动——BRAINSTORMING 显示 QuestionForm，GDD_REVIEW 显示 GddReviewPanel，GDD_APPROVED 显示定稿按钮
- 复用现有 `OptionChips`/`LandedCard`/`MarkdownView`

---

## 6. 数据模型

### 6.1 brainstorm_questions 表（新，§5.5）

### 6.2 ProjectRead 扩展（不改表，加字段）

前端要 status + project_key，ProjectRead 已有。加 `GET /projects` 列表。

### 6.3 Redis 键

沿用：`lock:project:{id}:brainstorm` / `lock:project:{id}:gdd_check` / `stream:project:{id}`。

---

## 7. 内部事件协议（阶段1前端连接新增）

| type | data | 时机 |
|---|---|---|
| `brainstorm.questions_ready` | `{project_id, questions:[{id,question,options}]}` | job1 出题完成 |
| `gdd.review_ready` | `{project_id}` | job2 生成 GDD 完成，进 GDD_REVIEW |

复用既有：`agent.message.delta`（02/03 流）、`agent.session.completed`、`agent.refused`、`git.*`、`gdd.check.passed/failed`。

---

## 8. API（阶段1前端连接完整）

```
GET  /api/projects                              列表（新）
POST /api/projects                              建（既有）
GET  /api/projects/{id}                          查（既有）
POST /api/projects/{id}/brainstorm               入队 job1 出题（既有端点，改 run_brainstorm 为 job1）
POST /api/projects/{id}/brainstorm/answer       入队 job2 生成（新）
GET  /api/projects/{id}/gdd                      取 GDD.md+manifest（新）
POST /api/projects/{id}/gdd/submit               写回 GDD + 04（新）
POST /api/projects/{id}/gdd/approve              （保留，或与 submit 合并）
POST /api/projects/{id}/brainstorm/finalize      finalize（既有）
GET  /api/projects/{id}/stream                   SSE（既有）
```

---

## 9. 测试策略（D10）

| 层级 | 方式 |
|---|---|
| 问题解析器单测 | tests/test_questions_parser.py：spike 6 问题文本 → 6 结构；乱格式→[] |
| run_brainstorm job1/job2 集成 | FakeRuntime（02 出题 result / 03 生成）+ FakeGitService，验状态流转 |
| API 端点单测 | test_api_projects（列表）/ test_api_gdd（GET/submit） |
| 前端 | 手动 e2e（真打 KSPMAS+GitHub），前端无单测（沿用现状） |

---

## 10. 已知风险与未决项

| 项 | 说明 | 处置 |
|---|---|---|
| kimi-k3 02 出题格式不稳 | spike 那次成功，但 kimi-k3 高度不稳，可能 refusal 或格式乱 | 解析器容错（乱→自由文本答）；02 prompt 强制格式；refusal 三态处理（FAILED，前端提示重试） |
| SSE 经 vite proxy | vite proxy 默认支持 SSE 长连接，但需验通 | 实现期首步验 SSE 经 proxy 真通（curl localhost:5173/api/.../stream）；不通则加 CORS 或改 proxy 配置 |
| EventSource 无自定义 header | after 参数走 query（既有端点已支持 ?after=） | 既有，无需改 |
| brainstorm_questions 表新增 | 需 migration / create_all | lifespan create_all 自动建（沿用阶段1） |
| 02 不再落 concept | 阶段1后端 02 产 concept，前端连接版 02 产问题 | 02 SKILL 改（D4）；旧 concept 路径废弃。需同步旧测试（test_tasks_brainstorm_gdd 适配） |
| GDD 可编辑写回 | 用户改的 GDD 写回 worktree，覆盖 03 生成的 | submit 端点直接写文件（git add 不在此步，finalize 才 commit） |
| 阶段 2-5 mock 保留 | store 改阶段1 actions 不破坏 2-5 | 阶段1 actions 独立命名，2-5 mock actions 不动（D1） |
| 旧 api/client.ts（/api/runs 脱节） | 早期骨架，与后端不符 | 不删（避免破坏引用），新 backend.ts 并存；后续清理 |

---

## 11. 阶段边界

- 不做：阶段 2-5 前端连接（保持 mock）；brainstorm 多轮 resume（D2 定 2 次 KSPMAS）；GDD 之外的可编辑（manifest 不编辑，只 GDD.md）。
- 后续：阶段 2（美术）前端连接时复用 backend.ts + SSE 模式。

---

## 12. 下一步

本 spec 经用户 review 通过后，进入 `writing-plans` 产出 `doc/plans/2026-08-17-phase3a-frontend-plan.md`，按 TDD 分步实现（问题解析器单测 → 02/03 SKILL+prompts 改 → brainstorm_questions 表 + Repo → run_brainstorm 拆 job1/job2 → 新 API 端点 → 前端 backend.ts + SSE hook → store 阶段1 actions → 前端组件 → e2e 手动验收）。
