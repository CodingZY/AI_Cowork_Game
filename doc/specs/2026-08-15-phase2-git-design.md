# Phase 2：Git 设计规格书

- **版本**：v0.1
- **日期**：2026-08-15
- **阶段**：doc §116 Phase 2（Git）
- **定位**：在 Phase 1 Runtime 闭环之上接 Git 集成层——让 Claude 在 **git worktree** 里改代码、落 GDD，commit 后合并回共享 monorepo 的 main，push 到 GitHub，打里程碑 tag。跑通 `Claude → Worktree → Commit → merge → push → tag`，为 Phase 3（Skills/V1）的"在 git 管理的游戏代码上干活"奠基。

本 spec 是 `AI_Cowork_Game Backend v0.1 技术实现方案.md`（120 章，下称「doc」）Phase 2 部分的落地设计。doc §116 Phase 2 目标 `Claude→Worktree→Commit`；本 spec 给可施工切片 + 奠基决策 + spike 证据，并记录对 doc §8/§106 的合理偏离。

---

## 1. 目标与验收

### 1.1 目标

跑通 doc §116 Phase 2，在 Phase 1 brainstorm 闭环上叠加 git：

```
共享 GitHub monorepo + git worktree + commit + merge + push + tag
→ Claude 在 worktree 改代码 → 落 git → 推 GitHub
```

### 1.2 验收链路（Definition of Done）

一条端到端链路，全部成立即 Phase 2 完成（真打 GitHub 共享 repo + PAT）：

```
① 后端配置：backend/.env 填 GITHUB_REPO_URL（共享 repo）+ GITHUB_PAT；
   用户已在 GitHub 手动建好该共享 repo（空 repo 即可，后端首启推 template）

② POST /api/projects {name:"FarmDemo2"}
   → project_service.create() → projects 行（status=CREATED）
   → project_repositories 行（sub_path=games/{key}/, current_branch=NULL）
   （create 只落库，不 clone——clone 放 ③ brainstorm task，避免建项目 API 阻塞在网络 IO）

③ POST /api/projects/{id}/brainstorm {idea:"..."}
   → 入 Arq → 返回 202 {task_id} → project.status=BRAINSTORMING
   → Worker run_brainstorm:
       （全局幂等）GitService.ensure_clone() → workspace/games-repo/（main 跟踪 origin/main）
       （首启幂等）ensure_template_pushed() → 共享 repo 有 template/
       GitService.worktree_add(agent/{key}-brainstorm) → workspace/worktrees/{key}-brainstorm/
       （首次）copy_template() → worktree/games/{key}/（TS/Vite/Canvas 骨架）
       ClaudeRuntime.start(cwd=worktree/games/{key}) → 落 {名}-game-design.md
       多轮 resume 复用同一 worktree（中间不 commit、不碰 main）
       project_repositories.current_branch = agent/{key}-brainstorm

④ 第二轮 POST /brainstorm（resume）→ 同 worktree 续接 → 续落 GDD

⑤ POST /api/projects/{id}/brainstorm/finalize  ← 定稿端点
   → 入 Arq → 202 {task_id}
   → Worker run_finalize:
       cd worktree → git add games/{key} → commit(feat(F001): initial game + gdd)
       → merge agent/{key}-brainstorm → main（--no-ff）
       → worktree remove + branch delete（cleanup）
       → push origin main
       → tag brainstorm-{key}-v0 → push tag
       → project_repositories.last_commit_sha 回填
       → project.status=BRAINSTORMED

⑥ SSE 看流：git.repo.cloned / git.worktree.added / git.committed / git.merged /
   git.pushed / git.tagged / git.worktree.cleaned 全部可见

⑦ GitHub 上验证：共享 repo main 有 games/{key}/ + {名}-game-design.md +
   brainstorm-{key}-v0 tag
```

> Phase 2 的 tag 是**里程碑 tag**（`brainstorm-{key}-v0`），不是 doc §53 的 V1 tag（`game-v0.1.0`，需 commit+tag+build+preview，build 在 Phase 5）。Phase 2 不做 build/preview/play。

---

## 2. 奠基决策记录

经需求确认对话拍板，以下决策约束本 spec 全文：

| # | 决策点 | 选定 | 影响 |
|---|---|---|---|
| D1 | 多游戏 repo 组织 | **单仓 monorepo，每游戏一子目录** | 共享 repo 下 `games/{project_key}/`；`template/` 供新游戏复制。偏离 doc §8「每项目一 repo」原意 |
| D2 | GitHub 接入 | **手动建 repo + PAT** | 用户预先建好共享 repo；后端用 PAT 只 clone/worktree/commit/push/tag，不调建 repo API；`github_installation_id` 留空 |
| D3 | 验收范围 | **全链路含 merge/push/tag** | brainstorm→worktree→commit→merge→cleanup→push→tag 全闭环 |
| D4 | workspace 布局 | **新建 workspace/，Games/ 废弃** | `workspace/games-repo/`（共享 repo 本地 clone）+ `workspace/worktrees/{key}-brainstorm/`；Claude cwd 迁到 worktree |
| D5 | commit 触发时机 | **定稿端点一次性 commit+merge+push+tag** | 多轮 brainstorm 复用 worktree 不碰 main；新增 `POST /brainstorm/finalize` 触发收尾；approval gate 雏形（doc §82） |
| D6 | project_repositories 表 | **每项目一行**（贴近 doc §8） | 记录 `sub_path`/`current_branch`/`last_commit_sha`；monorepo 下 path 可推导但落库便于追踪/扩展 |
| D7 | Git 操作实现 | **subprocess 调本机 git CLI** | asyncio.create_subprocess_exec 调 `git`（已验 2.37.1 可用）；不用 GitPython/pygit2 |
| D8 | GDD 文件命名 | **沿用 {名}-game-design.md**（项目约定） | 偏离 doc §107 的 `GDD.md`；doc §107 的 GDD.md 是 Phase 3 GDD Skill 产物，Phase 2 brainstorm 用项目约定 [[agent-system-conventions]] |
| D9 | game-template 来源 | **后端自带 + 首启 push** | `backend/templates/game-template/` 最小 TS/Vite/Canvas；首启幂等 push 到共享 repo `template/` |
| D10 | 测试策略 | **本地 bare git fixture + e2e 手动真打 GitHub** | 单测/集成用临时 bare repo（不打 github）；e2e 手动跑真共享 repo，不进 CI（沿用 Phase 1 D12） |

---

## 3. 可行性 Spike 证据

写 spec 前实测验证本机 git 基建 + github 网络可达（对应 Phase 1 教训：外部基建没真跑就埋坑）。

| 验证项 | 命令要点 | 结果 |
|---|---|---|
| 本机 git 可用 | `git --version` | ✅ git 2.37.1.windows.1 |
| git worktree 支持 | 临时 repo `git init` → `git worktree add -b feature wt` → `git worktree list` | ✅ worktree_add rc=0，worktree 存在，list 正常（主仓 + worktree feature 两行） |
| github.com 网络可达 | `git ls-remote https://github.com/octocat/Hello-World.git HEAD`（15s 超时） | ✅ 返回 SHA，未超时——网络层可达（PAT push 可达性需共享 repo + PAT，留 e2e 验） |

**关键发现**：
1. 本机 git + worktree 完全可用，GitService 用 subprocess 调 git 方案成立。
2. github.com ls-remote 通，PAT clone/push 网络层无阻碍；PAT 认证机制见 §5.1（不落 .git/config）。
3. worktree 路径用绝对路径（spike 用 mkdtemp 绝对路径），Windows 下 `git -C <repo> worktree add <abs_wt> -b <branch> <base>` 正常。

---

## 4. 架构与数据流（doc §49-54/§106）

### 4.1 物理布局（D4）

```
<repo>/
├── workspace/                       新增，gitignore（含共享 repo clone + worktrees）
│   ├── games-repo/                  共享 repo 本地 clone，main 跟踪 origin/main
│   │   ├── .git/
│   │   ├── template/                game-template（首启 push）
│   │   └── games/                   各游戏成品（已 merge 的）
│   │       └── farmdemo-77aa59/
│   └── worktrees/
│       └── {key}-brainstorm/        worktree，分支 agent/{key}-brainstorm
│           └── games/{key}/         Claude cwd，brainstorm 落 {名}-game-design.md
├── backend/
│   ├── templates/game-template/     后端自带模板（入库，首启 push 到共享 repo）
│   └── app/...
├── Games/                           Phase 1 旧产物，保留不动（gitignore）
└── doc/  frontend/  ...
```

`workspace/` 入 .gitignore（运行时产物）。`backend/templates/game-template/` 入库（模板源，版本管理）。

### 4.2 模块清单（Phase 2 新增/改动）

```
backend/app/
├── git/                              新增
│   ├── __init__.py
│   ├── service.py                    GitService（D7：subprocess 调 git）
│   └── template.py                   game-template 管理（D9：后端自带 + 首启 push）
├── models/
│   └── project_repository.py         新增：project_repositories ORM（D6）
├── persistence/
│   └── repo.py                       改：新增 ProjectRepositoryRepo
├── config/settings.py                改：加 github_repo_url/pat/workspace_root/branch_prefix
├── workflow/
│   └── states.py                     改：加 BRAINSTORMED 状态 + assert_can_finalize
├── services/
│   └── project_service.py            改：create 落 project_repositories + ensure_clone 触发
├── agent/
│   ├── session.py                    改：ensure_workspace → ensure_worktree（废弃 Games/）
│   └── runtime.py                    不改（cwd 由调用方传，已是参数）
├── queue/
│   ├── tasks.py                      改：run_brainstorm 用 worktree cwd；新增 run_finalize
│   └── worker.py                     改：注册 run_finalize
├── api/
│   └── projects.py                   改：新增 POST /brainstorm/finalize
└── main.py                           改：lifespan create_all 含 project_repositories
backend/templates/game-template/      新增（TS/Vite/Canvas 最小骨架）
```

### 4.3 数据流（全链路）

```
② POST /projects → project_service.create()
   ├─ Project 行（status=CREATED, workspace_root=workspace/worktrees/{key}-brainstorm）
   └─ ProjectRepository 行（sub_path=games/{key}/, current_branch=NULL）
      （create 只落库；ensure_clone/ensure_template_pushed 移到 ③，避免建项目阻塞网络 IO）

③ POST /brainstorm → Arq run_brainstorm
   ├─ 状态校验 assert_can_brainstorm（CREATED/BRAINSTORMING）
   ├─ 置 BRAINSTORMING
   ├─ GitService.ensure_clone()（全局幂等）+ ensure_template_pushed()（首启幂等）
   ├─ GitService.worktree_add(agent/{key}-brainstorm)（幂等：已存在则复用）
   │   └─ event git.worktree.added
   ├─ 首次：copy_template() → worktree/games/{key}/
   ├─ ClaudeRuntime.start(cwd=worktree/games/{key}, project_id)
   │   └─ 落 games/{key}/{名}-game-design.md（经 broker 流式落库 + 广播，同 Phase 1）
   ├─ 多轮 resume：同 worktree，--resume 同 claude_session_id
   └─ ProjectRepository.current_branch = agent/{key}-brainstorm

⑤ POST /brainstorm/finalize → Arq run_finalize
   ├─ 状态校验 assert_can_finalize（BRAINSTORMING）
   ├─ acquire project lock（Redis TTL 30min，沿用 §87）
   ├─ GitService.commit(worktree, "feat(F001): initial game + gdd")
   │   └─ event git.committed {sha}
   ├─ GitService.merge_to_main(agent/{key}-brainstorm)
   │   └─ event git.merged {merge_commit}
   ├─ GitService.worktree_remove + branch delete
   │   └─ event git.worktree.cleaned
   ├─ GitService.push("origin","main") → event git.pushed {sha}
   ├─ GitService.tag(brainstorm-{key}-v0) + push tag → event git.tagged
   ├─ ProjectRepository.last_commit_sha = main HEAD
   └─ project.status = BRAINSTORMED
```

---

## 5. 模块设计

### 5.1 `git/service.py` — GitService（D7）

职责：封装共享 repo 的 clone/fetch、worktree 生命周期、commit/merge/push/tag。全部 subprocess 调本机 `git`，asyncio。

```python
class GitService:
    def __init__(self, settings): 
        self.settings = settings
        self.repo_dir = settings.workspace_base / "games-repo"   # workspace/games-repo/

    async def _git(self, args, cwd=None) -> tuple[int, str, str]:
        """asyncio.create_subprocess_exec 调 git，返回 (rc, stdout, stderr)。
        env 注入 GIT_TERMINAL_PROMPT=0（防挂起等凭据输入）+ PAT 凭据（见下）。"""

    async def ensure_clone(self) -> Path:
        """幂等：repo_dir 不存在则 clone 共享 repo（用 PAT URL），clone 后
        立即把 remote origin URL 改成不含 PAT 的（避免落 .git/config 明文）；
        已存在则 git fetch origin。返回 repo_dir。"""

    async def ensure_template_pushed(self):
        """幂等：检查 repo_dir/template/ 是否存在；不存在则从后端自带
        backend/templates/game-template/ 复制到 repo_dir/template/，
        commit + push（首启一次性）。"""

    async def worktree_add(self, project_key, branch) -> Path:
        """git -C repo_dir worktree add -b {branch} <abs_wt_path> main。
        幂等：worktree 已存在则返回其路径；分支已存在但无 worktree 则 attach。
        返回 worktree 绝对路径。"""

    async def worktree_path(self, project_key) -> Path | None:
        """查 worktree 是否存在，返回路径或 None。"""

    async def copy_template(self, worktree_path, project_key):
        """复制 worktree/template/* → worktree/games/{key}/（首次落游戏骨架）。"""

    async def commit(self, worktree_path, message) -> str:
        """git -C worktree add -A; git -C worktree commit -m {message}。
        返回 commit sha（git rev-parse HEAD）。"""

    async def merge_to_main(self, branch) -> str:
        """git -C repo_dir checkout main; git -C repo_dir merge --no-ff {branch}。
        返回 merge commit sha。冲突抛 GitConflict（见 §11）。"""

    async def worktree_remove(self, project_key, branch):
        """git -C repo_dir worktree remove <wt>; git -C repo_dir branch -d {branch}。"""

    async def push(self, remote="origin", ref="main") -> str:
        """git -C repo_dir push {remote} {ref}（用 PAT 凭据）。返回 pushed sha。"""

    async def tag(self, tag_name) -> str:
        """git -C repo_dir tag {tag_name}; git -C repo_dir push origin {tag_name}。"""

    async def current_sha(self, ref="main") -> str:
        """git -C repo_dir rev-parse {ref}。"""
```

**PAT 认证机制**（D2，安全）：
- clone 时用 `https://x-access-token:{PAT}@github.com/{owner}/{repo}.git`（PAT 仅在内存命令行，**不持久化**）。
- clone 完立即 `git remote set-url origin https://github.com/{owner}/{repo}.git`（去 PAT），避免 PAT 落 `.git/config`。
- push/tag 时用 `git -c credential.helper= -c http.extraheader="Authorization: Basic {base64(x-access-token:PAT)}"` 临时凭据（不落盘）。
- env 设 `GIT_TERMINAL_PROMPT=0`，凭据缺失直接失败而非挂起。
- 实现期 Task 0 验通一次真 clone + push（e2e 前置）。

### 5.2 `git/template.py` — game-template（D9）

- 后端自带 `backend/templates/game-template/`（入库），最小 TS/Vite/Canvas 骨架：
  ```
  game-template/
  ├── package.json      (vite + typescript devDeps, "dev"/"build" 脚本)
  ├── tsconfig.json
  ├── vite.config.ts
  ├── index.html
  ├── src/main.ts       (canvas 初始化骨架：getContext、requestAnimationFrame 空循环)
  ├── .gitignore        (node_modules, dist)
  └── README.md
  ```
- `ensure_template_pushed()`：repo_dir 无 `template/` 则复制 + commit + push（首启一次性，幂等）。
- **不含 GDD.md**（D8：brainstorm 生成 `{名}-game-design.md`，不预置空 GDD.md）。

### 5.3 `models/project_repository.py` — project_repositories（D6）

```python
class ProjectRepository(Base):
    __tablename__ = "project_repositories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="github")
    owner: Mapped[str] = mapped_column(String(255), nullable=False)       # 共享 repo owner
    repository: Mapped[str] = mapped_column(String(255), nullable=False)  # 共享 repo name
    sub_path: Mapped[str] = mapped_column(String(512), nullable=False)     # games/{key}/
    default_branch: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    current_branch: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # agent/{key}-brainstorm
    last_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    github_installation_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # PAT 模式留空
    created_at / updated_at
    UNIQUE(project_id), FK(project_id)→projects(id)
```

`ProjectRepositoryRepo`：`create/get_by_project/set_branch/set_last_sha`。

> 偏离 doc §8：原 `clone_url` 改成 `owner`+`repository`（全局一致，可由 settings 推导，但 D6 选落库便于追踪）；新增 `sub_path`/`current_branch`/`last_commit_sha`（monorepo 多游戏定位所需）；`github_installation_id` 留空（PAT 模式）。

### 5.4 `workflow/states.py` — 状态扩展

```python
class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    BRAINSTORMED = "BRAINSTORMED"   # Phase 2 新增：brainstorm 已定稿+落 git
    FAILED = "FAILED"

def assert_can_brainstorm(status):  # CREATED/BRAINSTORMING 可；BRAINSTORMED/FAILED 不可
def assert_can_finalize(status):   # 仅 BRAINSTORMING 可 finalize
```

### 5.5 `services/project_service.py` 改造

`create(session, name, description)`：
- 生成 key，Project 行 `workspace_root=workspace/worktrees/{key}-brainstorm`，status=CREATED。
- 落 ProjectRepository 行（sub_path=games/{key}/，owner/repository 从 settings，current_branch=NULL）。
- **不在此 clone**（clone 是全局幂等，由首次 brainstorm task 或 lifespan 触发，避免建项目阻塞）。
- `ensure_worktree` 不在此（brainstorm task 开 worktree）。

### 5.6 `queue/tasks.py` 改造

`run_brainstorm(ctx, project_id, prompt)`：
- 状态校验 → 置 BRAINSTORMING → 预建 agent_session（沿用 Phase 1）。
- **新增**：`GitService.ensure_clone()` + `ensure_template_pushed()`（全局幂等）。
- **新增**：`worktree_add(agent/{key}-brainstorm)`（幂等）→ event `git.worktree.added`。
- **新增**：首次（worktree/games/{key}/ 不存在）`copy_template()`。
- ClaudeRuntime.start(cwd=worktree/games/{key}, project_id)（cwd 从 Games/{key} 迁来）。
- `ProjectRepository.current_branch = agent/{key}-brainstorm`。
- brainstorm 落 `{名}-game-design.md`（D8）。**不 commit**（留 finalize）。
- 三态收尾同 Phase 1（succeeded/refused/runtime_error）。

`run_finalize(ctx, project_id)` 新增：
- 状态校验 `assert_can_finalize`（BRAINSTORMING）。
- acquire lock。
- `GitService.commit(worktree, "feat(F001): initial game + gdd")` → event git.committed。
- `merge_to_main(current_branch)` → event git.merged。
- `worktree_remove + branch -d` → event git.worktree.cleaned。
- `push("origin","main")` → event git.pushed。
- `tag(f"brainstorm-{key}-v0")` + push tag → event git.tagged。
- `ProjectRepository.last_commit_sha = current_sha("main")`。
- project.status = BRAINSTORMED。
- 异常兜底（沿用 Phase 1 e2e 修复）：任何 git 步骤失败 → event git.failed + project FAILED（不卡死）。

### 5.7 `api/projects.py` 改造

新增：
```
POST /api/projects/{id}/brainstorm/finalize  → 202 {task_id}
```
enqueue `run_finalize(project_id)`。

### 5.8 `agent/session.py` 改造

`ensure_workspace(key)` → `ensure_worktree(key, branch)`：废弃 Games/ 路径，返回 worktree 路径。Phase 1 `ensure_workspace` 保留函数但标记 deprecated，新代码用 `ensure_worktree`（或 GitService.worktree_add 直接覆盖其职责，session.py 只留 path 推导 helper）。

---

## 6. 数据模型

### 6.1 project_repositories（D6，见 §5.3 DDL）

### 6.2 projects 字段语义变更（不改表结构）

`workspace_root`：从 Phase 1 的 `Games/{key}` 改赋值 `workspace/worktrees/{key}-brainstorm`（worktree 路径）。`status` 取值集 +BRAINSTORMED。

### 6.3 agent_sessions 字段语义变更（不改表结构）

`working_directory`：从 `Games/{key}` 改赋 worktree 路径 `workspace/worktrees/{key}-brainstorm`。

### 6.4 Redis 键

```
lock:project:{id}:brainstorm     TTL 30min（brainstorm，沿用）
lock:project:{id}:finalize       TTL 30min（finalize 新增）
stream:project:{id}              事件流（git.* 事件经此广播）
```

---

## 7. 内部事件协议（Phase 2 新增 git.*）

经 EventBroker（先落库再广播，沿用 Phase 1），`aggregate_type="git"`，`aggregate_id=project_id`：

| type | data | 时机 |
|---|---|---|
| `git.repo.cloned` | `{repo_url, branch, sha}` | ensure_clone 首次/每次 fetch |
| `git.template.pushed` | `{}` | ensure_template_pushed 首启 |
| `git.worktree.added` | `{project_id, branch, path}` | worktree_add |
| `git.committed` | `{project_id, sha, message}` | finalize commit |
| `git.merged` | `{project_id, branch, merge_commit}` | finalize merge |
| `git.worktree.cleaned` | `{project_id, branch}` | finalize cleanup |
| `git.pushed` | `{project_id, ref, sha}` | finalize push |
| `git.tagged` | `{project_id, tag}` | finalize tag |
| `git.failed` | `{project_id, stage, error}` | 任何 git 步骤失败 |

复用 Phase 1 的 `CoworkEvent`/`EventBroker`/`EventRepo`，不改协议结构。

---

## 8. API（Phase 2 在 Phase 1 基础上 +1）

```
POST   /api/projects                              建项目（落 project_repositories）
GET    /api/projects/{id}                          查状态
POST   /api/projects/{id}/brainstorm               入队 brainstorm → 202 {task_id}
POST   /api/projects/{id}/brainstorm/finalize      入队 finalize → 202 {task_id}（Phase 2 新增）
GET    /api/projects/{id}/stream?after=<eid>       SSE（含 git.* 事件）
```

---

## 9. `.env` 配置（backend/.env 新增）

```ini
# === Git（Phase 2，D2） ===
GITHUB_REPO_URL=https://github.com/<owner>/<repo>.git   # 共享 monorepo repo
GITHUB_PAT=<personal access token>                       # repo 作用域，push 用
WORKSPACE_ROOT=workspace                                  # 相对 repo 根
GIT_BRANCH_PREFIX=agent                                   # worktree 分支前缀

# Phase 1 既有（ANTHROPIC_* / DB_URL / REDIS_URL / ARQ_QUEUE）保持
```

`.env.example` 同步加占位。`GITHUB_PAT` 不入库（gitignore）。

---

## 10. 测试策略（D10）

| 层级 | 方式 | 是否打 GitHub |
|---|---|---|
| 单元（GitService） | `tmp_path` 建临时 bare git repo 作 origin + clone + worktree + commit + merge，断言 | 否 |
| 集成（tasks/worker） | `FakeGitService`（in-process，模拟 worktree/commit/merge 事件序列）跑 run_brainstorm/run_finalize | 否 |
| e2e（验收链路） | 真打共享 GitHub repo（PAT push），跑 §1.2 ①-⑦ | **手动，不进 CI** |

沿用 Phase 1：单测 sqlite + FakeRedis + FakeGit；e2e 手动真打。GitService 单测是 Phase 2 新重点（worktree/merge 在 Windows 的真实行为）。

---

## 11. 已知风险与未决项

| 项 | 说明 | 处置 |
|---|---|---|
| PAT push 可达性 | ls-remote 通（§3），但 PAT clone/push 需共享 repo + PAT 实测 | 实现期 Task 0 首步验通真 clone + push（e2e 前置）；不通则降级本地 git + push 推迟 |
| merge 冲突 | 多 project 不同子目录（games/{key}/）理论不冲突；同 project 并发 brainstorm+finalize 可能 | finalize 加 lock:project:{id}:finalize；merge 冲突抛 GitConflict，project FAILED，保留 worktree debug（doc §52） |
| PAT 落 .git/config 明文 | remote URL 嵌 PAT 会落 .git/config | §5.1：clone 后立即 set-url 去 PAT；push 用 extraheader 临时凭据 |
| worktree 残留 | 失败时 worktree 不 cleanup | doc §52：失败保留 worktree + 日志，方便 debug；finalize 成功才 remove |
| game-template 内容质量 | TS/Vite/Canvas 最小骨架，Phase 2 只需能落 git，不需能 build | Phase 2 template 只求结构完整 + 能 commit；build 验证留 Phase 5 |
| 共享 repo 已有内容 | 用户手动建 repo 可能非空 | ensure_template_pushed 检查 template/ 是否存在，幂等；不覆盖已有 games/ |
| 多 project 并发 clone | ensure_clone 全局幂等，多 task 并发可能重复 clone | repo_dir 存在则只 fetch（fetch 幂等）；首 clone 加文件锁或接受幂等竞态（clone 到临时目录后 rename） |

---

## 12. 阶段边界（不属 Phase 2）

- Phase 3：Skills（Superpowers/GDD Skill/Game Codegen/Game Testing）——brainstorm 换真正 GDD Skill；V1 planning 分解 feature；Code Agent 在 worktree 写代码。Phase 2 的 worktree/git 机制被 Phase 3 直接复用。
- Phase 4：Asset（MCP/生图/抠图/存储）
- Phase 5：Build（Docker/npm test/build/preview）——V1 tag `game-v0.1.0` 在此阶段（commit+tag+build+preview）；Phase 2 的 `brainstorm-{key}-v0` 是其前身。
- Phase 6：Feedback

Phase 2 完成后，`GitService`/`project_repositories`/worktree 布局应被 Phase 3-6 直接复用（D8 价值）。

---

## 13. 下一步

本 spec 经用户 review 通过后，进入 `writing-plans` 产出实施计划：`doc/plans/2026-08-15-phase2-git-plan.md`，按 TDD 分步实现（GitService 单元先行 → project_repositories ORM → project_service 改造 → run_brainstorm worktree 集成 → run_finalize → finalize API/SSE → e2e 手动验收）。
