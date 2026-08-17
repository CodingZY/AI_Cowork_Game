# 阶段1（Phase 3a）：Skills 基座 + GDD Skill 设计规格书

- **版本**：v0.1
- **日期**：2026-08-17
- **阶段**：SKILL 设计文档 Phase 1（IDEA→GDD→GDD_CHECK）+ 主技术方案 doc §38-43/§82-85
- **定位**：在 Phase 1/2 后端 Runtime+Git 闭环之上，接入 **Skills 层**——让后端 spawn 的 claude 子进程经 `--plugin-dir` 挂载自研 game-skills plugin，跑通 `IDEA →(02 brainstorm 澄清)→(03 gdd-generator)→ GDD.md + gdd-manifest.json → GDD_REVIEW 暂停 → 用户 approve →(04 gdd-check)→ GDD_APPROVED → finalize 落 git`。为后续 SKILL 文档 Phase 2-6（美术/V1/测试/反馈）奠定 Skills 基座与 GDD 产物。

本 spec 是 `SKILL设计文档.md`（12 章，下称「skill-doc」）Phase 1 部分 + `AI_Cowork_Game Backend v0.1 技术实现方案.md`（120 章，下称「doc」）§38-43/§82-85 的落地设计，并记录对 doc §84 的最小偏离。

---

## 1. 目标与验收

### 1.1 目标

跑通 skill-doc Phase 1（IDEA→GDD→GDD_CHECK），落点**后端挂载 Skill**（衔接 Phase 1/2）：

```
IDEA → 02-game-brainstorm（澄清需求）→ 03-gdd-generator（生成 GDD.md+manifest）
    → GDD_REVIEW（暂停等用户）→ 用户 approve → 04-gdd-check（硬门禁）
    → GDD_APPROVED → finalize（commit+merge+push+tag）→ GitHub 有 GDD.md+manifest+tag
```

### 1.2 验收链路（Definition of Done）

一条端到端链路，全部成立即阶段1完成（真打 KSPMAS kimi-k3 + 共享 GitHub repo）：

```
① POST /api/projects {name:"FarmDemo3", idea:"牧场经营游戏"}
   → project_service.create() → projects 行（CREATED）+ project_repositories 行

② POST /api/projects/{id}/brainstorm {idea:"..."}
   → 入 Arq → 202 {task_id} → project.status=BRAINSTORMING
   → Worker run_brainstorm:
       GitService.worktree_add(agent/{key}-brainstorm)（复用 Phase 2）
       ClaudeRuntime --bare --plugin-dir backend/game-skills（新增）
         spawn #1: 02-game-brainstorm → 多轮澄清 → .brainstorm-concept.md
         spawn #2: 03-gdd-generator → 读 concept → games/{key}/GDD.md(17节) + gdd-manifest.json
       → project.status=GDD_REVIEW（暂停，等用户）

③ SSE 看流：git.worktree.added + agent.session.started/completed×2（02、03 两轮）
   + 生成 games/{key}/GDD.md + gdd-manifest.json 可见

④ POST /api/projects/{id}/gdd/approve
   → project.status=GDD_CHECKING → 入 Arq run_gdd_check → 202 {task_id}
   → Worker run_gdd_check:
       ClaudeRuntime --bare --plugin-dir spawn 04-gdd-check
       → 检查 GDD 17节齐全 + manifest features 有 id/验收
       → 输出 PASS/FAIL（result 文本）
       parser 抓 PASS → GDD_APPROVED / FAIL → 回 GDD_REVIEW（带 reasons 事件）

⑤ POST /api/projects/{id}/brainstorm/finalize（Phase 2 已有，门升级）
   → assert_can_finalize 现要求 GDD_APPROVED（doc §84 Hard Gate）
   → run_finalize: commit+merge+cleanup+push+tag(brainstorm-{key}-v0)
   → project.status=BRAINSTORMED
   → GitHub main 有 games/{key}/GDD.md + gdd-manifest.json + tag
```

> 阶段1只到 GDD_APPROVED + finalize 落 git。**不生成游戏代码**（skill-doc Phase 1 明确"先不要生成游戏代码"）。代码生成是 skill-doc Phase 3（本项目后续子阶段）。

---

## 2. 奠基决策记录

经需求确认对话拍板，以下决策约束本 spec 全文：

| # | 决策点 | 选定 | 影响 |
|---|---|---|---|
| D1 | Skills 落点 | **后端挂载**（`backend/game-skills/`，`claude --bare --plugin-dir`） | spike 验通：`--bare`+`--plugin-dir` 能加载项目级 plugin skills 且不染宿主（§3）。ClaudeRuntime 加 `--plugin-dir` 参数挂 game-skills |
| D2 | GDD 命名落点 | **`games/{key}/GDD.md`**（废弃 Phase 2 `{名}-game-design.md`） | 从 skill-doc 标准名；gdd-manifest.json 同落 `games/{key}/`；与 skill-doc `game-project/GDD.md` 一致（game-project=games/{key}） |
| D3 | 02+03 执行方式 | **两次 spawn 隔离** | run_brainstorm 内先 spawn 02（落 `.brainstorm-concept.md`），再 spawn 03（读 concept 生成 GDD+manifest）；两次独立 session，03 不 resume 02 |
| D4 | concept 传递 | **中间文件 `.brainstorm-concept.md`** | 02 产、03 读，两 skill 解耦，concept 可复检 |
| D5 | Approval Gate 流程 | **02+03→GDD_REVIEW 暂停→approve→04→GDD_APPROVED** | run_brainstorm(02+03)→GDD_REVIEW；POST /gdd/approve→run_gdd_check(04)→PASS/GDD_APPROVED 或 FAIL/回 GDD_REVIEW。符合 doc §82 |
| D6 | 状态机 | **扩 ProjectStatus +3 状态** | +GDD_REVIEW/GDD_CHECKING/GDD_APPROVED（最小改动）。doc §84 的 gdd_status 独立字段留待后续（V1 阶段有 version_status 时引入双字段，doc §25） |
| D7 | GDD 内容范围 | **全 17 节 + manifest** | GDD.md doc §42 全 17 节；gdd-manifest.json doc §43 features 数组（id/name/priority/status） |
| D8 | finalize Hard Gate | **硬改要求 GDD_APPROVED** | assert_can_finalize 从 BRAINSTORMING 改 GDD_APPROVED；Phase 2 既有 test_tasks_finalize 改为 GDD_APPROVED。doc §84。Phase 2 e2e 链路被升级覆盖 |
| D9 | gdd-check 判定 | **skill 文本输出 PASS/FAIL，parser 抓** | 04-gdd-check skill 输出格式化 PASS/FAIL（result 文本），run_gdd_check parser 从 agent.session.completed.result 抓。skill prompt 强制输出格式（首行 PASS 或 `FAIL: <reasons>`） |
| D10 | 测试策略 | **sqlite+Fake+e2e 手动**（沿用 Phase 1/2） | Skill 单测轻测（文本约束）；ClaudeRuntime `--plugin-dir` 单测验 cmd；状态机/run_brainstorm/run_gdd_check 集成用 FakeRuntime+FakeGitService；e2e 手动真打 |

---

## 3. 可行性 Spike 证据

写 spec 前实测验证 **Skills 加载机制**（对应 Phase 1 教训：外部基建没真跑就埋坑；Phase 3 最硬悬念：`--bare` 规避宿主污染 vs 要用 skills 的矛盾）。

| 验证项 | 方法 | 结果 |
|---|---|---|
| `--bare` + `--plugin-dir` 加载项目级 plugin | 临时目录建 `game-skills/.claude-plugin/plugin.json` + `skills/probe-skill/SKILL.md`（被调回 `PROBE_SKILL_OK`）；spawn `claude.exe --bare --plugin-dir <game-skills> -p "调用 /probe-skill" --output-format stream-json` | ✅ `result.text: PROBE_SKILL_OK`，`is_error:false`，`stop_reason:end_turn`，36.3s——子进程**发现并调用**了项目级 plugin 的 skill，不染宿主 |

**关键发现**（`claude --help` 的 `--bare` 说明）：
> `--bare` Minimal mode: skip hooks, LSP, plugin sync... **Skills still resolve via /skill-name**. Explicitly provide context via: ... `--plugin-dir`.

即 `--bare` 跳过宿主 plugin 自动 sync，但 `--plugin-dir` 显式挂载的 plugin 的 skills 仍可经 `/skill-name` 调用。**这正是 Phase 3 基石**：`--bare`（保留 Phase 1 的不染宿主）+ `--plugin-dir backend/game-skills`（挂载自研 skills）两者兼容。Phase 1 的 `--bare` 不用改，只加 `--plugin-dir`。

> spike 产物 throwaway（临时目录，已删）；实现期 ClaudeRuntime 加 `--plugin-dir` 参数复用此机制。

---

## 4. 架构与数据流

### 4.1 物理布局（衔接 Phase 2）

```
<repo>/
├── backend/
│   ├── game-skills/                   新增（入库，Skills 层）
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/
│   │       ├── 02-game-brainstorm/SKILL.md
│   │       ├── 03-gdd-generator/SKILL.md
│   │       └── 04-gdd-check/SKILL.md
│   └── app/...                         改（见 §5）
├── workspace/                          Phase 2 既有（gitignore）
│   ├── games-repo/                     共享 repo 本地 clone
│   └── worktrees/{key}-brainstorm/     worktree
│       └── games/{key}/                Claude cwd
│           ├── .brainstorm-concept.md   02 产（中间，gitignore 不入库）
│           ├── GDD.md                   03 产（17 节）
│           └── gdd-manifest.json        03 产
└── doc/  ...
```

`backend/game-skills/` 入库（Skill 源，版本管理）；`.brainstorm-concept.md` 是 worktree 内运行时中间产物（随 git commit 时是否纳入？见 §5.3——finalize 不 commit 它，仅 commit GDD.md+manifest）。

### 4.2 模块清单（阶段1 新增/改动）

```
backend/
├── game-skills/                         新增（D1）
│   ├── .claude-plugin/plugin.json
│   └── skills/{02-game-brainstorm,03-gdd-generator,04-gdd-check}/SKILL.md
├── app/
│   ├── agent/runtime.py                 改：_build_cmd/start/resume 加 plugin_dir 参数
│   ├── workflow/
│   │   ├── states.py                    改：+GDD_REVIEW/GDD_CHECKING/GDD_APPROVED
│   │   └── engine.py                    改：assert_can_finalize 改要求 GDD_APPROVED；+assert_can_gdd_check
│   ├── queue/
│   │   ├── tasks.py                     改：run_brainstorm 两次 spawn(02+03)+末尾置 GDD_REVIEW；新增 run_gdd_check
│   │   ├── jobs.py                      改：+enqueue_gdd_check
│   │   └── worker.py                    改：注册 run_gdd_check
│   ├── api/projects.py                 改：+POST /gdd/approve
│   └── config/settings.py              改：+game_skills_dir（默认 backend/game-skills）
└── tests/
    ├── test_skills.py                   新增：3 SKILL.md 轻测
    ├── test_runtime_plugin_dir.py       新增：ClaudeRuntime --plugin-dir cmd 验证
    ├── test_workflow_gdd.py             新增：GDD 状态 + assert_can_gdd_check
    ├── test_tasks_brainstorm_gdd.py     新增：run_brainstorm 两次 spawn + GDD_REVIEW
    ├── test_tasks_gdd_check.py          新增：run_gdd_check PASS/FAIL
    ├── test_api_gdd.py                  新增：POST /gdd/approve
    └── test_tasks_finalize.py           改：BRAINSTORMING→GDD_APPROVED（D8 硬改）
```

### 4.3 数据流（全链路）

```
② POST /brainstorm → Arq run_brainstorm:
   ├─ 状态校验 assert_can_brainstorm（CREATED/BRAINSTORMING/GDD_REVIEW 可；多轮改在 GDD_REVIEW 续接）
   ├─ 置 BRAINSTORMING
   ├─ GitService.worktree_add(agent/{key}-brainstorm)（复用 Phase 2）→ git.worktree.added 事件
   ├─ spawn #1: ClaudeRuntime.start(prompt02, cwd=games/{key}, plugin_dir=game_skills)
   │     prompt02 指示调 /02-game-brainstorm 澄清需求 → 落 .brainstorm-concept.md
   │     → agent.session.completed（02 轮）
   ├─ spawn #2: ClaudeRuntime.start(prompt03, cwd=games/{key}, plugin_dir=game_skills)
   │     prompt03 指示调 /03-gdd-generator 读 concept → 落 GDD.md(17节) + gdd-manifest.json
   │     → agent.session.completed（03 轮）
   ├─ 三态收尾（沿用 Phase 1：succeeded/refused/runtime_error），但成功置 GDD_REVIEW（非 BRAINSTORMING）
   └─ ProjectRepository.current_branch = agent/{key}-brainstorm

④ POST /gdd/approve → 置 GDD_CHECKING → Arq run_gdd_check:
   ├─ 状态校验 assert_can_gdd_check（仅 GDD_REVIEW 可；approve 已置 GDD_CHECKING，或 task 内校验 GDD_REVIEW/GDD_CHECKING）
   ├─ spawn: ClaudeRuntime.start(prompt04, cwd=games/{key}, plugin_dir=game_skills)
   │     prompt04 指示调 /04-gdd-check 检查 GDD.md+manifest → 输出 PASS/FAIL（result 文本）
   │     → agent.session.completed（result 含 PASS 或 FAIL: <reasons>）
   ├─ parser 抓 result：PASS → 置 GDD_APPROVED + event gdd.check.passed
   │              FAIL → 回 GDD_REVIEW + event gdd.check.failed（带 reasons）
   └─ 异常兜底：spawn 失败 → event gdd.check.failed + 回 GDD_REVIEW（不卡死）

⑤ POST /brainstorm/finalize → assert_can_finalize（现要求 GDD_APPROVED）→ run_finalize（复用 Phase 2）
```

---

## 5. 模块设计

### 5.1 `game-skills/` — 3 个 Skill（D1/D7）

**plugin.json**：
```json
{
  "name": "game-skills",
  "version": "0.1.0",
  "description": "AI_Cowork_Game 自研 Game Skills（skill-doc Phase 1）"
}
```

**02-game-brainstorm/SKILL.md** — 澄清需求：
- frontmatter: `name: 02-game-brainstorm`，`description: 澄清用户模糊游戏创意，多轮问答→结构化 Game Concept，不写 GDD`
- body 要点：
  - 输入：用户 idea（模糊）
  - 澄清维度（skill-doc 举例）：平台/2D·3D/核心循环/经营深度/系统/恋爱/NPC数量/游戏时长——**一次问一批，不一次性全问**
  - 输出：调 Write 落 `.brainstorm-concept.md`（Game Concept 结构化要点：genre/platform/core_loop/goals/mechanics/scope/key_systems）
  - 约束：**不生成游戏代码**；不写 GDD.md（03 才写）；措辞中性规避 kimi-k3 审核（沿用 Phase 1 §5.4）；只用 Read/Write

**03-gdd-generator/SKILL.md** — 生成 GDD：
- frontmatter: `name: 03-gdd-generator`，`description: 读 Game Concept 生成机器可执行 GDD.md(17节)+gdd-manifest.json`
- body 要点：
  - 输入：读 `.brainstorm-concept.md`
  - 输出：调 Write 落 `GDD.md`（doc §42 全 17 节：Overview/Target Audience/Core Loop/Player Goals/Game Mechanics/Characters/NPC/World/Level Design/Economy/Progression/UI/Audio/Art Direction/Technical Requirements/Features/Acceptance Criteria）+ `gdd-manifest.json`（doc §43：`{game:{name,genre,platform}, features:[{id,name,priority,status}]}`）
  - 重点（skill-doc）：**机器可执行**——后面能生成 Asset/Code/Test，不只是文档漂亮；Features 必须有明确 id（F001..）+ 每个有验收标准
  - 约束：不生成游戏代码；只用 Read/Write

**04-gdd-check/SKILL.md** — 硬门禁：
- frontmatter: `name: 04-gdd-check`，`description: 检查 GDD.md+gdd-manifest.json 完整性，输出 PASS 或 FAIL: <缺失项>`
- body 要点：
  - 输入：读 `GDD.md` + `gdd-manifest.json`
  - 检查：GDD 17 节齐全 + manifest features 有 id/name/priority/status + 每 feature 有验收标准
  - **输出格式（强制，D9 parser 依赖）**：result 文本首行 `PASS` 或 `FAIL: <缺失项列表>`（一行），不调工具改文件
  - 约束：只 Read，不 Write；纯判定

### 5.2 `agent/runtime.py` — `--plugin-dir` 参数（D1）

`_build_cmd` 加 `plugin_dir`：
```python
def _build_cmd(self, prompt, resume_sid=None, system_prompt=None, plugin_dir=None):
    cmd = [self.claude_bin, "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--include-partial-messages", "--bare",
           "--allowedTools", "Read", "Write", "--permission-mode", "acceptEdits"]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    if plugin_dir:
        cmd += ["--plugin-dir", plugin_dir]          # 新增
    if resume_sid:
        cmd += ["--resume", resume_sid]
    return cmd
```
`_run`/`start`/`resume` 加 `plugin_dir` 参数透传。

### 5.3 `workflow/states.py` + `engine.py` — 状态机（D6/D8）

states.py：
```python
class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    GDD_REVIEW = "GDD_REVIEW"        # 新增：02+03 跑完，等用户审查
    GDD_CHECKING = "GDD_CHECKING"    # 新增：04 跑中
    GDD_APPROVED = "GDD_APPROVED"    # 新增：04 PASS，可 finalize
    BRAINSTORMED = "BRAINSTORMED"    # Phase 2 保留：finalize 落 git 后
    FAILED = "FAILED"
```

engine.py：
```python
def assert_can_brainstorm(status):  # CREATED/BRAINSTORMING/GDD_REVIEW 可（多轮改/续接）
def assert_can_finalize(status):    # 改：仅 GDD_APPROVED 可（doc §84 Hard Gate，D8）
def assert_can_gdd_check(status):  # 新增：仅 GDD_REVIEW 可跑 04
```

### 5.4 `queue/tasks.py` — run_brainstorm 改 + run_gdd_check 新增

**run_brainstorm 改**（两次 spawn + 末尾 GDD_REVIEW）：
- 沿用 Phase 2 的 git 前置（ensure_clone/ensure_template_pushed/worktree_add/git.worktree.added）+ project_repositories.set_branch
- **两次 spawn**（D3）：
  - spawn #1：`runtime.start(prompt02, cwd=games/{key}, project_id, agent_type="BRAINSTORM", system_prompt=BRAINSTORM_SYSTEM_PROMPT, plugin_dir=game_skills_dir)` → 02 调 Write 落 `.brainstorm-concept.md`
  - spawn #2：`runtime.start(prompt03, cwd=games/{key}, project_id, agent_type="GDD_GEN", system_prompt=GDD_GEN_SYSTEM_PROMPT, plugin_dir=game_skills_dir)` → 03 调 Write 落 `GDD.md`+`gdd-manifest.json`
  - 两轮 agent.* 事件都经 broker.publish（aggregate_id 各自的 agent_session）
- **末尾置 GDD_REVIEW**（D5）：对 Phase 2 收尾的改动——Phase 2 成功时项目保持 BRAINSTORMING（可再 resume）；阶段1成功改置 `GDD_REVIEW`（暂停等用户审查）。agent_session 状态仍 COMPLETED（02/03 各自）。refused/runtime_error→FAILED（沿用）。
- prompt02/prompt03：指示子进程调对应 skill（`/02-game-brainstorm`、`/03-gdd-generator`）+ 传用户 idea + worktree 路径

**run_gdd_check 新增**（D5/D9）：
- 状态校验 assert_can_gdd_check（GDD_REVIEW）→ 置 GDD_CHECKING
- spawn：`runtime.start(prompt04, cwd=games/{key}, project_id, agent_type="GDD_CHECK", system_prompt=GDD_CHECK_SYSTEM_PROMPT, plugin_dir=game_skills_dir)` → 04 输出 PASS/FAIL
- parser 抓 `agent.session.completed.result`：
  - 首行 `PASS` → 置 GDD_APPROVED + event `gdd.check.passed`
  - 首行 `FAIL: ...` → 回 GDD_REVIEW + event `gdd.check.failed`（data 带 reasons）
- 异常兜底（沿用 Phase 1）：spawn 失败 → event `gdd.check.failed` + 回 GDD_REVIEW（不卡死）

### 5.5 `api/projects.py` — POST /gdd/approve

```python
@router.post("/projects/{pid}/gdd/approve", status_code=202)
async def approve_gdd(pid: int, session: AsyncSession = Depends(get_session)):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if p.status != ProjectStatus.GDD_REVIEW.value:
        raise HTTPException(409, f"cannot approve from {p.status}")
    await ProjectRepo(session).set_status(pid, ProjectStatus.GDD_CHECKING)
    await session.commit()
    job_id = await enqueue_gdd_check(pid)
    return {"task_id": job_id}
```
端点先校验当前 GDD_REVIEW（409 否则），置 GDD_CHECKING，再 enqueue run_gdd_check。run_gdd_check 内 assert_can_gdd_check 校验 GDD_CHECKING（approve 已置）或放宽校验 GDD_REVIEW/GDD_CHECKING。

### 5.6 `config/settings.py`

加 `game_skills_dir: str = "backend/game-skills"`（相对 REPO_ROOT，run_brainstorm/run_gdd_check 拼绝对路径传 runtime）。

---

## 6. 数据模型（不改表结构）

- `projects.status`：取值集 +GDD_REVIEW/GDD_CHECKING/GDD_APPROVED（D6）
- `agent_sessions.agent_type`：02 轮=`BRAINSTORM`，03 轮=`GDD_GEN`，04 轮=`GDD_CHECK`——三轮各自独立 agent_session（D3 两次 spawn 不 resume：02 是 BRAINSTORM session，03 是新 GDD_GEN session 不续接 02；04 又是新 GDD_CHECK session）。每个 agent_session 落各自的 claude_session_id + COMPLETED/FAILED。
- `project_repositories`/`events`：不变（git.* + agent.* + gdd.check.* 事件经既有 EventBroker）

## 7. 内部事件协议（阶段1新增 gdd.*）

| type | data | 时机 |
|---|---|---|
| `gdd.check.passed` | `{project_id, result}` | run_gdd_check PASS |
| `gdd.check.failed` | `{project_id, reasons, result}` | run_gdd_check FAIL |

复用 Phase 1/2 的 CoworkEvent/EventBroker。02/03 的 agent.* 事件沿用既有（agent.session.started/completed/message.delta）。

## 8. API（阶段1 在 Phase 2 基础上 +1）

```
POST /api/projects                         Phase 2 既有
GET  /api/projects/{id}                     Phase 2 既有
POST /api/projects/{id}/brainstorm          Phase 2 既有（run_brainstorm 内含 02+03）
POST /api/projects/{id}/gdd/approve         阶段1新增 → 202 {task_id}（enqueue run_gdd_check）
POST /api/projects/{id}/brainstorm/finalize Phase 2 既有（门升级：要求 GDD_APPROVED）
GET  /api/projects/{id}/stream              Phase 1 既有（含 gdd.* 事件）
```

## 9. `.env` 配置

无新增必要（game_skills_dir 有默认值）。`.env` 沿用 Phase 1/2。

## 10. 测试策略（D10）

| 层级 | 方式 |
|---|---|
| Skill 单测 | test_skills.py：断言 3 SKILL.md 含关键约束（02 含澄清维度+不写GDD、03 含 GDD.md+manifest+17节、04 含 PASS/FAIL 格式） |
| ClaudeRuntime --plugin-dir | test_runtime_plugin_dir.py：FakeRuntime 风格验 cmd 含 `--plugin-dir backend/game-skills` |
| 状态机 | test_workflow_gdd.py：assert_can_finalize(GDD_APPROVED) 通过/(BRAINSTORMING)抛；assert_can_gdd_check(GDD_REVIEW) 通过 |
| run_brainstorm 集成 | test_tasks_brainstorm_gdd.py：FakeRuntime（两次 spawn：02/03）+ FakeGitService，验两次 start 调用 + 末尾 GDD_REVIEW |
| run_gdd_check 集成 | test_tasks_gdd_check.py：FakeRuntime（04 返 PASS/FAIL result），验 PASS→GDD_APPROVED / FAIL→GDD_REVIEW |
| finalize 门回归 | test_tasks_finalize.py 改：用 GDD_APPROVED（D8 硬改） |
| e2e | 手动真打 KSPMAS + 共享 repo，跑 §1.2 ①-⑤ |

## 11. 已知风险与未决项

| 项 | 说明 | 处置 |
|---|---|---|
| kimi-k3 不落 GDD（Phase 2 观察 1） | brainstorm 不调 Write，只回文本 | 03-gdd-generator skill prompt 强制"调 Write 落 GDD.md+manifest"，且 `--allowedTools Read,Write` + `acceptEdits` 放行；e2e 验证真落文件。若仍不落→prompt 加更强约束（"必须调用 Write 工具，不要只在文本里写"） |
| 04 PASS/FAIL 格式不稳 | kimi-k3 可能不严格按"首行 PASS/FAIL"输出 | skill prompt 强制格式 + parser 容错（result 含 "PASS" 即 PASS，含 "FAIL" 即 FAIL，否则当 FAIL 带原 result 回 GDD_REVIEW） |
| 两次 spawn 成本 | 02+03 两次 kimi-k3 启动（各 ~30s+） | 可接受（e2e 预计 2-3 分钟）；后续可优化为一次 spawn 串调（D3 选隔离，留优化空间） |
| .brainstorm-concept.md 是否 commit | 中间产物，不应入 git | finalize 的 `git add games/{key}` 会包含它——需 run_finalize 排除（`git add games/{key}/GDD.md games/{key}/gdd-manifest.json` 精确 add，或不 commit concept）。实现期 run_finalize 改精确 add |
| GDD_REVIEW 时再 brainstorm 改 | 用户在 GDD_REVIEW 想改 GDD，再 POST /brainstorm | assert_can_brainstorm 允许 GDD_REVIEW（D6），run_brainstorm 续接 worktree（已有）+ resume 02 session 改 concept→重跑 03。但 run_brainstorm 现置 GDD_REVIEW，需确认多轮逻辑（实现期定） |
| finalize 门改影响 Phase 2 测试 | test_tasks_finalize 用 BRAINSTORMING | D8 已决：改 GDD_APPROVED |

## 12. 阶段边界（不属阶段1）

- skill-doc Phase 2（美术资产）：05-08 skill，GDD→ART_STYLE/art-assets/assets
- skill-doc Phase 3（V1 代码）：09-11 skill，GDD→architecture/V1/code
- skill-doc Phase 4-7（测试/反馈/orchestrator/质量）

阶段1完成后，`game-skills` plugin 基座 + `--plugin-dir` 机制 + GDD 产物 + Approval Gate 被 skill-doc Phase 2-6 直接复用。

## 13. 下一步

本 spec 经用户 review 通过后，进入 `writing-plans` 产出 `doc/plans/2026-08-17-phase3a-skills-gdd-plan.md`，按 TDD 分步实现（game-skills plugin + 3 SKILL.md → ClaudeRuntime --plugin-dir → 状态机 → run_brainstorm 两次 spawn → run_gdd_check → gdd/approve API → finalize 门改 + 既有测试回归 → e2e 手动验收）。
