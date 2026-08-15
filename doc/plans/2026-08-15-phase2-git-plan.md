# Phase 2 Git 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 跑通 `建项目 → (brainstorm task) clone 共享 GitHub monorepo + 开 git worktree + 复制 game-template → Claude 在 worktree 落 GDD → 定稿端点一次性 commit+merge+cleanup+push+tag`，把 Phase 1 的 Runtime 闭环从 `Games/{key}/` 迁到 git 管理的 worktree。

**Architecture:** 共享 GitHub monorepo（`CodingZY/Game_Template_Repo`，用户手建 + PAT）下每游戏一子目录 `games/{key}/`。brainstorm 多轮复用同一 worktree（`agent/{key}-brainstorm` 分支），中间不碰 main；新增 `POST /brainstorm/finalize` 端点触发 Arq `run_finalize`：commit → `--no-ff` merge 回 main → worktree/branch cleanup → push origin → 打里程碑 tag `brainstorm-{key}-v0`。`GitService` 用 `asyncio.create_subprocess_exec` 调本机 git 2.37.1；PAT 仅内存不落 `.git/config`。

**Tech Stack:** Python 3.10（agent_env，D 盘）/ FastAPI / SQLAlchemy 2.0 async / arq / redis / 本机 git 2.37.1 / GitHub PAT / pytest + pytest-asyncio（sqlite + FakeRedis + FakeGitService + 本地 bare git fixture）

**Spec:** `doc/specs/2026-08-15-phase2-git-design.md`（本计划从 spec 推导，spec 与计划一并阅读）

## Global Constraints

- **Python 解释器固定** `D:/Anaconda3/envs/agent_env/python.exe`（C 盘约束：依赖只装 agent_env，禁碰 C 盘）。下文 `python` 均指此解释器。
- **Python 版本 3.10**：类型标注用 `Optional[X]` / 文件首 `from __future__ import annotations`；`X | None` 仅在 pydantic 模型字段可用。
- **Phase 1 既有不动**：`ClaudeRuntime`/`ClaudeEventParser`/`EventBroker`/`EventRepo`/`CoworkEvent`/`ProjectRepo`/`AgentSessionRepo`/SSE 端点已就绪且 61 测试通过。本阶段**叠加** git 层，不改其内部逻辑；只改 `run_brainstorm` 的 cwd 来源 + 新增 `run_finalize`/finalize 端点。
- **测试不打 GitHub**（D10）：单测/集成用 sqlite + FakeRedis + FakeGitService + 本地 `tmp_path` bare git repo 作 origin；e2e 手动真打共享 repo，不进 CI（沿用 Phase 1 D12）。
- **GitService 用 subprocess 调本机 git**（D7）：`asyncio.create_subprocess_exec("git", ...)`，不用 GitPython/pygit2。已验 git 2.37.1 + worktree 可用（spec §3）。
- **空 repo 须显式建 main**（spec §11）：共享 repo 初始无提交，clone 得 HEAD unborn 本地仓；`ensure_template_pushed` 首提交前必须 `git checkout -b main`（git 2.37 默认 init.master），否则 `worktree_add(base=main)` 失败。**这是 Phase 1 教训的同类坑（外部基建没真跑），Task 0 必须 e2e 前置验通真 clone+push。**
- **PAT 不落盘**（spec §5.1）：clone 用 `https://x-access-token:{PAT}@github.com/...`，clone 完立即 `git remote set-url` 去 PAT；push/tag 用 `git -c http.extraheader="Authorization: Basic {base64}"` 临时凭据；env 设 `GIT_TERMINAL_PROMPT=0` 防挂起。
- **worktree 路径用绝对路径**（spec §3）：Windows 下 `git -C <repo> worktree add <abs_wt> -b <branch> <base>`，spike 已验。
- **Settings 新字段给默认值**：`github_repo_url`/`github_pat`/`git_branch_prefix` 默认空串/`agent`，避免测试 import settings 时若 `.env` 未填而崩（e2e 才填真值）。
- **workspace 布局**（D4）：`<repo>/workspace/games-repo/`（共享 repo 本地 clone）+ `<repo>/workspace/worktrees/{key}-brainstorm/`；`workspace/` 入 .gitignore（运行时产物）。`Games/` 废弃但保留不动。
- **commit 规范**（doc §54）：`feat(F001): initial game + gdd`；tag `brainstorm-{key}-v0`（里程碑，非 V1）。
- **GDD 命名沿用**（D8）：`{名}-game-design.md`（项目约定 [[agent-system-conventions]]），不预置空 GDD.md。
- **commit 规范（本计划）**：每 task 末提交，message 前缀按改动类型（feat/fix/test/chore/docs）。
- **不碰 frontend**：Phase 2 只在 `backend/` 与 `doc/` 下作业。

---

## File Structure

```
backend/
├── .env                              改 Task 0：加 GITHUB_REPO_URL/PAT/WORKSPACE_ROOT/GIT_BRANCH_PREFIX
├── .env.example                      改 Task 0：同步占位
├── templates/
│   └── game-template/                新增 Task 6：TS/Vite/Canvas 最小骨架（入库，首启 push）
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       ├── .gitignore
│       ├── README.md
│       └── src/main.ts
├── app/
│   ├── config/settings.py            改 Task 0：+4 字段（默认值）
│   ├── git/                           新增
│   │   ├── __init__.py                新增 Task 3
│   │   ├── service.py                 新增 Task 3-5：GitService
│   │   └── template.py                新增 Task 6：ensure_template_pushed
│   ├── models/
│   │   ├── __init__.py                改 Task 1：import ProjectRepository
│   │   └── project_repository.py      新增 Task 1：project_repositories ORM
│   ├── persistence/repo.py            改 Task 1：+ProjectRepositoryRepo
│   ├── workflow/
│   │   ├── states.py                  改 Task 2：+BRAINSTORMED
│   │   └── engine.py                  改 Task 2：+assert_can_finalize
│   ├── services/project_service.py    改 Task 7：create 落 project_repositories + workspace_root=worktree
│   ├── agent/session.py               改 Task 8：+ensure_worktree path helper（保留 ensure_workspace 标 deprecated）
│   ├── queue/
│   │   ├── tasks.py                   改 Task 9：run_brainstorm 集成 GitService（worktree cwd + git.worktree.added）；新增 Task 10 run_finalize
│   │   ├── jobs.py                    改 Task 11：+enqueue_finalize
│   │   └── worker.py                  改 Task 11：注册 run_finalize
│   ├── api/projects.py                改 Task 11：+POST /brainstorm/finalize
│   └── main.py                        改 Task 1：create_all 含 project_repositories（自动，因 import 链）
└── tests/
    ├── conftest.py                    改 Task 3：+local_bare_repo fixture
    ├── test_project_repository.py     新增 Task 1
    ├── test_workflow_finalize.py      新增 Task 2
    ├── test_git_service.py            新增 Task 3-5（核心，本地 bare fixture）
    ├── test_template.py               新增 Task 6
    ├── test_project_service.py        改 Task 7：+project_repositories 断言
    ├── test_session_worktree.py        新增 Task 8
    ├── test_tasks_brainstorm_git.py   新增 Task 9（FakeGitService）
    ├── test_tasks_finalize.py         新增 Task 10（FakeGitService + git.* 事件）
    ├── test_api_finalize.py           新增 Task 11
    └── test_tasks_worker.py           改 Task 9：run_brainstorm 集成 GitService 后，FakeGitService 注入
```

**责任划分**：GitService（纯 git 操作，无 DB/业务）最易用本地 bare repo 测，先行；project_repositories ORM 纯模型；states 纯枚举；project_service 落库；tasks 串联（注入 GitService）。每层接口在对应 task 的 **Interfaces** 块钉死。

---

## Task 0: 环境与基建（Git 配置 + game-template 骨架占位 + e2e 前置验通）

**Files:**
- Modify: `backend/.env`（加 Git 字段，不入库）
- Modify: `backend/.env.example`（同步占位）
- Modify: `backend/app/config/settings.py`（+4 字段）
- Modify: `.gitignore`（+`workspace/`）
- Verify: 真 clone + push 共享 repo（e2e 前置，本 task 末手动验）

**Interfaces:**
- Produces: `Settings` 新增 `github_repo_url: str = ""` / `github_pat: str = ""` / `git_branch_prefix: str = "agent"`（`workspace_root` 已存在，Task 0 改默认值为 `workspace`）；`workspace_base` property 不变。后续所有 task 经此读 git 配置。

- [ ] **Step 1: 改 settings.py 加 4 字段**

`backend/app/config/settings.py`：`workspace_root` 默认值 `Games` → `workspace`；加三字段：
```python
    workspace_root: str = "workspace"
    github_repo_url: str = ""
    github_pat: str = ""
    git_branch_prefix: str = "agent"
```
保留既有 `workspace_base` property 与 `settings_customise_sources`。

- [ ] **Step 2: 改 .env（加真实 Git 配置，不入库）**

`backend/.env` 末尾加：
```ini
# === Git（Phase 2，D2） ===
GITHUB_REPO_URL=https://github.com/CodingZY/Game_Template_Repo.git
GITHUB_PAT=<填你的 personal access token，repo 作用域>
WORKSPACE_ROOT=workspace
GIT_BRANCH_PREFIX=agent
```

- [ ] **Step 3: 改 .env.example（占位，入库）**

`backend/.env.example` 末尾加：
```ini
# === Git（Phase 2，D2） ===
GITHUB_REPO_URL=https://github.com/<owner>/<repo>.git
GITHUB_PAT=
WORKSPACE_ROOT=workspace
GIT_BRANCH_PREFIX=agent
```

- [ ] **Step 4: 改 .gitignore 加 workspace/**

`.gitignore`：在 `Games/` 行下加 `workspace/`（增量加，勿整体回退——Phase 1 教训：Edit .gitignore 易误删安全忽略行如 `.spike.env`）。

- [ ] **Step 5: 验 settings 可加载 + gitignore 生效**

Run:
```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -c "from app.config.settings import get_settings; s=get_settings(); print(s.github_repo_url, bool(s.github_pat), s.workspace_root, s.git_branch_prefix)"
```
Expected: 打印 repo url + `True`（pat 非空）+ `workspace` + `agent`。
```bash
git check-ignore workspace/ && echo "ignoreOK"
```
Expected: `workspace/`

- [ ] **Step 6: e2e 前置验通——真 clone 共享 repo（PAT）**

这一步验通 Phase 1 教训对应的外部基建（PAT push 可达性），不通过则本阶段降级。用 PAT URL clone 到临时目录确认可达：
```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -c "
import asyncio, os, tempfile, shutil
from app.config.settings import get_settings
async def main():
    s = get_settings()
    url = s.github_repo_url.replace('https://', f'https://x-access-token:{s.github_pat}@')
    d = tempfile.mkdtemp(prefix='e2e_clone_')
    import asyncio
    proc = await asyncio.create_subprocess_exec(
        'git','clone', url, d,
        env={**os.environ, 'GIT_TERMINAL_PROMPT':'0'},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.wait()
    err = (await proc.stderr.read()).decode('utf-8','replace')
    print('clone_rc=', proc.returncode)
    print('clone_stderr=', err[:300])
    print('dir_contents=', os.listdir(d))
    shutil.rmtree(d, ignore_errors=True)
asyncio.run(main())
"
```
Expected: `clone_rc= 0`，dir 含（可能为空 list，因 repo 初始空，或有 `.git`）。若 `clone_rc != 0`：PAT/网络问题，需用户确认 PAT 作用域含 repo + github push 可达；不通则记录并降级（本地 git + push 推迟）。
> 注：此步只验 clone 可达性，真 clone+push+tag 在 Task 13 e2e。

- [ ] **Step 7: 提交**

```bash
git add backend/app/config/settings.py backend/.env.example .gitignore
git commit -m "chore(backend): Phase2 基建——settings 加 Git 字段 + .env.example + workspace gitignore"
```
（`.env` 与 `.gitignore` 中真实 PAT 不入库。）

---

## Task 1: project_repositories ORM + Repo

**Files:**
- Create: `backend/app/models/project_repository.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/persistence/repo.py`（+ProjectRepositoryRepo）
- Test: `backend/tests/test_project_repository.py`

**Interfaces:**
- Consumes: `Base`（`app.models`），`ProjectRepo` 模式（见 repo.py 既有 Repo 风格）。
- Produces: `ProjectRepository` ORM（字段见 spec §5.3）；`ProjectRepositoryRepo(session)` 含 `create(project_id, owner, repository, sub_path, default_branch="main") -> ProjectRepository` / `get_by_project(project_id) -> Optional[ProjectRepository]` / `set_branch(project_id, branch) -> None` / `set_last_sha(project_id, sha) -> None`。后续 Task 7/9/10 依赖此。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_project_repository.py`:
```python
from __future__ import annotations

from sqlalchemy import select

from app.models.project_repository import ProjectRepository
from app.persistence.repo import ProjectRepositoryRepo, ProjectRepo


async def test_create_project_repository(async_db_session):
    # 先建 project（外键）
    proj = await ProjectRepo(async_db_session).create(
        project_key="farmdemo-aaa", name="FarmDemo", status="CREATED",
        workspace_root="workspace/worktrees/farmdemo-aaa-brainstorm",
    )
    repo = await ProjectRepositoryRepo(async_db_session).create(
        project_id=proj.id, owner="CodingZY", repository="Game_Template_Repo",
        sub_path="games/farmdemo-aaa/",
    )
    assert repo.id is not None
    assert repo.provider == "github"
    assert repo.default_branch == "main"
    assert repo.current_branch is None
    assert repo.last_commit_sha is None
    assert repo.github_installation_id is None


async def test_set_branch_and_sha(async_db_session):
    proj = await ProjectRepo(async_db_session).create(
        project_key="k1", name="K1", status="CREATED", workspace_root="ws/k1",
    )
    rrepo = ProjectRepositoryRepo(async_db_session)
    await rrepo.create(project_id=proj.id, owner="o", repository="r", sub_path="games/k1/")
    await rrepo.set_branch(proj.id, "agent/k1-brainstorm")
    await rrepo.set_last_sha(proj.id, "abc123")
    got = await rrepo.get_by_project(proj.id)
    assert got.current_branch == "agent/k1-brainstorm"
    assert got.last_commit_sha == "abc123"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_project_repository.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.project_repository`）

- [ ] **Step 3: 实现 models/project_repository.py**

`backend/app/models/project_repository.py`:
```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ProjectRepository(Base):
    """project_repositories 表（spec §5.3，D6：每项目一行，monorepo 定位）。

    owner/repository: 共享 monorepo repo（全局一致，settings 可推导，落库便于追踪）。
    sub_path: 该游戏在共享 repo 的路径（games/{key}/）。
    current_branch: brainstorm worktree 分支（agent/{key}-brainstorm），finalize 后清空。
    last_commit_sha: finalize 后 main HEAD。
    github_installation_id: PAT 模式留空（D2）。
    """

    __tablename__ = "project_repositories"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="github")
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_path: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    current_branch: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    github_installation_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: 改 models/__init__.py 注册**

`backend/app/models/__init__.py`：在 `from .event import Event` 下加 `from .project_repository import ProjectRepository  # noqa: E402,F401`，`__all__` 加 `"ProjectRepository"`。

- [ ] **Step 5: 实现 ProjectRepositoryRepo（追加到 repo.py）**

`backend/app/persistence/repo.py` 末尾追加：
```python
from app.models.project_repository import ProjectRepository


class ProjectRepositoryRepo:
    """project_repositories 表 CRUD（spec §5.3，D6）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, project_id: int, owner: str, repository: str, sub_path: str,
        default_branch: str = "main",
    ) -> ProjectRepository:
        row = ProjectRepository(
            project_id=project_id, provider="github", owner=owner,
            repository=repository, sub_path=sub_path, default_branch=default_branch,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_project(self, project_id: int) -> Optional[ProjectRepository]:
        return (
            await self.session.execute(
                select(ProjectRepository).where(
                    ProjectRepository.project_id == project_id
                )
            )
        ).scalar_one_or_none()

    async def set_branch(self, project_id: int, branch: Optional[str]) -> None:
        await self.session.execute(
            update(ProjectRepository)
            .where(ProjectRepository.project_id == project_id)
            .values(current_branch=branch)
        )

    async def set_last_sha(self, project_id: int, sha: str) -> None:
        await self.session.execute(
            update(ProjectRepository)
            .where(ProjectRepository.project_id == project_id)
            .values(last_commit_sha=sha)
        )
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_project_repository.py -v`
Expected: PASS

- [ ] **Step 7: 跑全量测试确认未破坏 Phase 1**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 61 passed（Phase 1 全绿，新表 import 链不破坏既有）。

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/ backend/app/persistence/repo.py backend/tests/test_project_repository.py
git commit -m "feat(models): project_repositories ORM + ProjectRepositoryRepo（monorepo 每项目一行）"
```

---

## Task 2: workflow states 扩展（BRAINSTORMED + assert_can_finalize）

**Files:**
- Modify: `backend/app/workflow/states.py`
- Modify: `backend/app/workflow/engine.py`
- Test: `backend/tests/test_workflow_finalize.py`

**Interfaces:**
- Produces: `ProjectStatus.BRAINSTORMED`（新成员）；`assert_can_finalize(status)` 仅 `BRAINSTORMING` 可，否则抛 `WorkflowBlocked`。后续 Task 10 run_finalize 调 `assert_can_finalize`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_workflow_finalize.py`:
```python
from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import assert_can_finalize, WorkflowBlocked


def test_brainstormed_member_exists():
    assert ProjectStatus("BRAINSTORMED") == ProjectStatus.BRAINSTORMED


def test_can_finalize_from_brainstorming():
    assert_can_finalize(ProjectStatus.BRAINSTORMING)  # 不抛


def test_cannot_finalize_from_created():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.CREATED)


def test_cannot_finalize_from_brainstormed():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.BRAINSTORMED)


def test_cannot_finalize_from_failed():
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.FAILED)


def test_assert_can_brainstorm_allows_brainstormed_false():
    # BRAINSTORMED 不可再 brainstorm（已定稿）
    from app.workflow.engine import assert_can_brainstorm
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm(ProjectStatus.BRAINSTORMED)
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_workflow_finalize.py -v`
Expected: FAIL（`BRAINSTORMED` 不存在 / `assert_can_finalize` 未定义）

- [ ] **Step 3: 改 states.py**

`backend/app/workflow/states.py`：`FAILED` 行上加 `BRAINSTORMED = "BRAINSTORMED"`：
```python
class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    BRAINSTORMED = "BRAINSTORMED"
    FAILED = "FAILED"
```

- [ ] **Step 4: 改 engine.py 加 assert_can_finalize**

`backend/app/workflow/engine.py` 末尾加：
```python
def assert_can_finalize(status: ProjectStatus | str) -> None:
    """仅 BRAINSTORMING 可 finalize（定稿落 git）。其余状态抛 WorkflowBlocked。"""
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot finalize from {status!r}")
    if current is not ProjectStatus.BRAINSTORMING:
        raise WorkflowBlocked(f"cannot finalize from {current}")
```
（`assert_can_brainstorm` 既有逻辑已自动排斥 `BRAINSTORMED`，因其不在 `(CREATED, BRAINSTORMING)`——无需改。）

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_workflow_finalize.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿（既有 brainstorm 状态校验不受影响）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/workflow/ backend/tests/test_workflow_finalize.py
git commit -m "feat(workflow): +BRAINSTORMED 状态 + assert_can_finalize（定稿门）"
```

---

## Task 3: GitService 核心单元（_git + ensure_clone + 空 repo main 处理）

**Files:**
- Create: `backend/app/git/__init__.py`
- Create: `backend/app/git/service.py`
- Modify: `backend/tests/conftest.py`（+`local_bare_repo` fixture）
- Test: `backend/tests/test_git_service.py`

**Interfaces:**
- Consumes: `Settings`（`github_repo_url`/`github_pat`/`workspace_base`）。
- Produces: `GitService(settings)`；`GitConflict` 异常类；`_git(args, cwd=None) -> tuple[int,str,str]`；`ensure_clone(origin_url=None) -> Path`（origin_url 缺省用 settings.github_repo_url，测试传本地 bare url）；`repo_dir` 属性（`workspace_base / "games-repo"`）；`current_sha(ref="main") -> str`。后续 Task 4-5 扩展。

**关键设计**：`ensure_clone(origin_url=None)` 接可注入 origin——测试传本地 bare repo url（不打 github），生产缺省用 settings。空 repo 处理逻辑放 Task 6 `ensure_template_pushed`（建首提交 + main），本 task 只验 clone 幂等 + repo_dir 存在 + PAT 去 URL（若 origin_url 含 PAT）。

- [ ] **Step 1: 加 local_bare_repo fixture 到 conftest.py**

`backend/tests/conftest.py` 末尾加（提供本地 bare git origin，作 GitService 单测的 clone 源，不打 github）：
```python
import subprocess
import pytest


def _run(args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


@pytest.fixture
def local_bare_repo(tmp_path):
    """本地 bare git repo（origin），含一个初始 main 提交，作 GitService clone 源。

    用真实 git 子进程（非 mock），验证 worktree/clone/merge 在 Windows 的真实行为。
    返回 (bare_path, origin_url)，origin_url 形如 file:///.../origin.git。
    """
    origin = tmp_path / "origin.git"
    _run(["init", "--bare", str(origin)])
    # 建一个有 main 提交的工作仓再推到 bare（让 origin 有 main 分支 + 内容）
    seed = tmp_path / "seed"
    _run(["init", str(seed)])
    _run(["config", "user.email", "t@t.com"], cwd=str(seed))
    _run(["config", "user.name", "tester"], cwd=str(seed))
    (seed / "README.md").write_text("# seed\n", encoding="utf-8")
    _run(["checkout", "-b", "main"], cwd=str(seed))
    _run(["add", "-A"], cwd=str(seed))
    _run(["commit", "-m", "seed init"], cwd=str(seed))
    _run(["remote", "add", "origin", str(origin)], cwd=str(seed))
    _run(["push", "-u", "origin", "main"], cwd=str(seed))
    return origin, f"file:///{origin.as_posix()}"
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_git_service.py`:
```python
from __future__ import annotations

from pathlib import Path

from app.git.service import GitService


def _make_service(tmp_path, origin_url="https://github.com/o/r.git", pat=""):
    """构造 GitService，workspace_base 指 tmp_path，避免碰真实 workspace/。"""
    class S:
        workspace_base = tmp_path
        github_repo_url = origin_url
        github_pat = pat
        git_branch_prefix = "agent"
    return GitService(S())


async def test_ensure_clone_creates_repo_dir(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    repo_dir = await svc.ensure_clone(origin_url=url)
    assert repo_dir == tmp_path / "games-repo"
    assert (repo_dir / ".git").exists()
    # clone 后 main 分支存在
    rc, out, err = await svc._git(["rev-parse", "main"], cwd=str(repo_dir))
    assert rc == 0


async def test_ensure_clone_idempotent(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    d1 = await svc.ensure_clone(origin_url=url)
    d2 = await svc.ensure_clone(origin_url=url)
    assert d1 == d2  # 不重复 clone


async def test_ensure_clone_fetches_new_commits(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    repo_dir = await svc.ensure_clone(origin_url=url)
    sha_before = (await svc._git(["rev-parse", "main"], cwd=str(repo_dir))[1]).strip()
    # 给 origin 加一个提交
    import subprocess
    seed = tmp_path / "seed2"
    subprocess.run(["git", "init", str(seed)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.name", "t"], check=True)
    (seed / "a.txt").write_text("x")
    subprocess.run(["git", "-C", str(seed), "checkout", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(seed), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-qm", "second"], check=True)
    subprocess.run(["git", "-C", str(seed), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(["git", "-C", str(seed), "push", "origin", "main"], check=True)
    # 再 ensure_clone 应 fetch
    await svc.ensure_clone(origin_url=url)
    sha_after = (await svc._git(["rev-parse", "origin/main"], cwd=str(repo_dir))[1]).strip()
    assert sha_after != sha_before


async def test_current_sha(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    sha = await svc.current_sha("main")
    assert isinstance(sha, str) and len(sha) >= 7
```

- [ ] **Step 3: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_git_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.git.service`）

- [ ] **Step 4: 实现 git/__init__.py + service.py 核心**

`backend/app/git/__init__.py`：空文件。

`backend/app/git/service.py`:
```python
from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Optional, Tuple

from app.config.settings import get_settings


class GitConflict(Exception):
    """merge 冲突（spec §11）。"""
    pass


class GitService:
    """封装共享 monorepo 的 git 操作（spec §5.1，D7：subprocess 调本机 git）。

    所有 git 调用经 _git（asyncio.create_subprocess_exec），env 注入
    GIT_TERMINAL_PROMPT=0 防挂起。PAT 认证：clone 用 PAT URL 后立即 set-url
    去 PAT；push/tag 用 http.extraheader 临时凭据（不落 .git/config）。
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.repo_dir: Path = self.settings.workspace_base / "games-repo"

    async def _git(self, args: list[str], cwd: Optional[str] = None,
                   use_pat: bool = False) -> Tuple[int, str, str]:
        """asyncio.create_subprocess_exec 调 git，返回 (rc, stdout, stderr)。

        use_pat=True 时注入 http.extraheader 临时凭据（push/tag 用）。
        env 设 GIT_TERMINAL_PROMPT=0（凭据缺失直接失败而非挂起）。
        """
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        cmd = ["git"]
        if use_pat and self.settings.github_pat:
            token = f"x-access-token:{self.settings.github_pat}"
            b64 = base64.b64encode(token.encode()).decode()
            cmd += ["-c", "credential.helper=", "-c",
                    f"http.extraheader=Authorization: Basic {b64}"]
        cmd += args
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
        )
        out, err = await proc.communicate()
        return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    @staticmethod
    def _strip_pat(url: str, pat: str) -> str:
        """把 PAT URL 还原成不含 PAT 的 https URL（避免落 .git/config 明文）。"""
        if pat and f"x-access-token:{pat}@" in url:
            return url.replace(f"x-access-token:{pat}@", "")
        return url

    async def ensure_clone(self, origin_url: Optional[str] = None) -> Path:
        """幂等：repo_dir 不存在则 clone（用 PAT URL 若 settings 有 pat），
        clone 后 set-url 去 PAT；已存在则 fetch。返回 repo_dir。

        origin_url 缺省用 settings.github_repo_url；测试可传本地 bare file:// url。
        空 repo 处理（首提交建 main）在 ensure_template_pushed（Task 6）。
        """
        url = origin_url if origin_url is not None else self.settings.github_repo_url
        pat = self.settings.github_pat
        clone_url = url.replace("https://", f"https://x-access-token:{pat}@") if pat else url
        if not self.repo_dir.exists():
            self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
            rc, out, err = await self._git(["clone", clone_url, str(self.repo_dir)])
            if rc != 0:
                raise RuntimeError(f"git clone failed: {err}")
            # clone 完立即去 PAT（pat 非空则 clone 时嵌了 PAT，需 set-url 还原）
            if pat:
                await self._git(["remote", "set-url", "origin", url], cwd=str(self.repo_dir))
        else:
            # 已存在：fetch（幂等，origin 变化能拿到）
            await self._git(["fetch", "origin"], cwd=str(self.repo_dir))
        return self.repo_dir

    async def current_sha(self, ref: str = "main") -> str:
        """git rev-parse {ref}。"""
        rc, out, err = await self._git(["rev-parse", ref], cwd=str(self.repo_dir))
        if rc != 0:
            raise RuntimeError(f"git rev-parse {ref} failed: {err}")
        return out.strip()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_git_service.py -v`
Expected: PASS（4 测试：clone 建目录/幂等/fetch 新提交/current_sha）

- [ ] **Step 6: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 7: 提交**

```bash
git add backend/app/git/__init__.py backend/app/git/service.py backend/tests/conftest.py backend/tests/test_git_service.py
git commit -m "feat(git): GitService 核心（_git + ensure_clone 幂等 + PAT 去 URL + current_sha）"
```

---

## Task 4: GitService worktree + copy_template + commit + merge + remove

**Files:**
- Modify: `backend/app/git/service.py`（+worktree_add/worktree_path/copy_template/commit/merge_to_main/worktree_remove）
- Test: `backend/tests/test_git_service.py`（+测试）

**Interfaces:**
- Produces（追加）：`worktree_add(project_key, branch) -> Path`（`git -C repo_dir worktree add -b {branch} <abs_wt> main`，幂等：已存在返回路径）；`worktree_path(project_key) -> Optional[Path]`（查 worktree 是否存在）；`copy_template(worktree_path, project_key) -> None`（复制 worktree/template/* → worktree/games/{key}/）；`commit(worktree_path, message) -> str`（返回 sha）；`merge_to_main(branch) -> str`（`--no-ff`，返回 merge sha，冲突抛 `GitConflict`）；`worktree_remove(project_key, branch) -> None`。

- [ ] **Step 1: 写失败测试（追加到 test_git_service.py）**

```python
async def test_worktree_add_creates_branch_and_dir(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    assert wt.exists()
    assert (wt / ".git").exists() or (wt / ".git").is_file()
    # 分支存在
    rc, out, err = await svc._git(["branch", "--list", "agent/k1-brainstorm"], cwd=str(svc.repo_dir))
    assert "agent/k1-brainstorm" in out


async def test_worktree_add_idempotent(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt1 = await svc.worktree_add("k1", "agent/k1-brainstorm")
    wt2 = await svc.worktree_add("k1", "agent/k1-brainstorm")
    assert wt1 == wt2


async def test_worktree_path(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    assert await svc.worktree_path("k1") is None
    await svc.worktree_add("k1", "agent/k1-brainstorm")
    assert await svc.worktree_path("k1") is not None


async def test_copy_template(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    # 在 worktree 里放一个 template/ 占位（Task 6 才有真模板，这里用临时文件）
    (wt / "template").mkdir()
    (wt / "template" / "package.json").write_text('{}')
    await svc.copy_template(wt, "k1")
    assert (wt / "games" / "k1" / "package.json").exists()


async def test_commit_returns_sha(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    sha = await svc.commit(wt, "feat(F001): initial game + gdd")
    assert isinstance(sha, str) and len(sha) >= 7


async def test_merge_to_main(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    await svc.commit(wt, "feat(F001): initial game + gdd")
    merge_sha = await svc.merge_to_main("agent/k1-brainstorm")
    assert isinstance(merge_sha, str) and len(merge_sha) >= 7
    # main 上有 games/k1/
    rc, out, err = await svc._git(["ls-tree", "main", "games/k1/"], cwd=str(svc.repo_dir))
    assert "GDD.md" in out


async def test_worktree_remove(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    await svc.worktree_add("k1", "agent/k1-brainstorm")
    await svc.merge_to_main("agent/k1-brainstorm")  # 分支已 merge 才能 -d 删
    await svc.worktree_remove("k1", "agent/k1-brainstorm")
    assert await svc.worktree_path("k1") is None
    rc, out, err = await svc._git(["branch", "--list", "agent/k1-brainstorm"], cwd=str(svc.repo_dir))
    assert "agent/k1-brainstorm" not in out
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_git_service.py -v -k worktree or copy_template or commit or merge or remove`
Expected: FAIL（方法未定义）

- [ ] **Step 3: 实现 worktree/copy/commit/merge/remove（追加到 service.py）**

```python
    def _worktree_dir(self, project_key: str) -> Path:
        """worktree 物理路径：workspace/worktrees/{key}-brainstorm。"""
        return self.settings.workspace_base / "worktrees" / f"{project_key}-brainstorm"

    async def worktree_add(self, project_key: str, branch: str) -> Path:
        """git -C repo_dir worktree add -b {branch} <abs_wt> main。幂等。

        已存在则返回其路径；分支已存在但无 worktree 则 attach（worktree add <wt> <branch>）。
        worktree 的 .git 是文件（指向主仓 .git/worktrees/...），.exists() 对文件也 True。
        """
        wt = self._worktree_dir(project_key)
        if wt.exists() and (wt / ".git").exists():
            return wt
        self._worktree_dir(project_key).parent.mkdir(parents=True, exist_ok=True)
        # 先查分支是否已存在
        rc, out, err = await self._git(["branch", "--list", branch], cwd=str(self.repo_dir))
        if branch in out:
            # 分支在但 worktree 不在：attach
            rc, out, err = await self._git(["worktree", "add", str(wt), branch], cwd=str(self.repo_dir))
        else:
            rc, out, err = await self._git(
                ["worktree", "add", "-b", branch, str(wt), "main"], cwd=str(self.repo_dir)
            )
        if rc != 0:
            raise RuntimeError(f"git worktree add failed: {err}")
        return wt

    async def worktree_path(self, project_key: str) -> Optional[Path]:
        """查 worktree 是否存在，返回路径或 None。"""
        wt = self._worktree_dir(project_key)
        if wt.exists() and ((wt / ".git").exists() or (wt / ".git").is_file()):
            return wt
        return None

    async def copy_template(self, worktree_path: Path, project_key: str) -> None:
        """复制 worktree/template/* → worktree/games/{key}/（首次落游戏骨架）。"""
        import shutil
        src = worktree_path / "template"
        dst = worktree_path / "games" / project_key
        if not src.exists():
            raise RuntimeError(f"template not found in worktree: {src}")
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.name == ".git":
                continue
            target = dst / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    async def commit(self, worktree_path: Path, message: str) -> str:
        """git -C worktree add -A; commit -m {message}。返回 commit sha。"""
        await self._git(["add", "-A"], cwd=str(worktree_path))
        rc, out, err = await self._git(["commit", "-m", message], cwd=str(worktree_path))
        if rc != 0:
            # 无变更也算成功场景由调用方判断；此处有变更才 commit
            if "nothing to commit" in (out + err):
                pass
            else:
                raise RuntimeError(f"git commit failed: {err}")
        rc, out, err = await self._git(["rev-parse", "HEAD"], cwd=str(worktree_path))
        return out.strip()

    async def merge_to_main(self, branch: str) -> str:
        """git -C repo_dir checkout main; merge --no-ff {branch}。返回 merge sha。

        冲突抛 GitConflict（spec §11）。
        """
        await self._git(["checkout", "main"], cwd=str(self.repo_dir))
        rc, out, err = await self._git(["merge", "--no-ff", branch, "-m", f"merge {branch}"], cwd=str(self.repo_dir))
        if rc != 0:
            if "CONFLICT" in (out + err) or "conflict" in (out + err):
                raise GitConflict(f"merge {branch} conflicted: {err}")
            raise RuntimeError(f"git merge failed: {err}")
        rc, out, err = await self._git(["rev-parse", "HEAD"], cwd=str(self.repo_dir))
        return out.strip()

    async def worktree_remove(self, project_key: str, branch: str) -> None:
        """git -C repo_dir worktree remove <wt>; branch -d {branch}。"""
        wt = self._worktree_dir(project_key)
        await self._git(["worktree", "remove", str(wt), "--force"], cwd=str(self.repo_dir))
        await self._git(["branch", "-d", branch], cwd=str(self.repo_dir))
```
> 注：`commit` 里 `nothing to commit` 处理——若 finalize 时无变更（已 commit 过），不应崩；但 finalize 首次必有 GDD 变更，此分支仅防御。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_git_service.py -v`
Expected: PASS（含 worktree/copy/commit/merge/remove 共 7 新测试）。

- [ ] **Step 5: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add backend/app/git/service.py backend/tests/test_git_service.py
git commit -m "feat(git): GitService worktree/copy_template/commit/merge/remove（worktree 全生命周期）"
```

---

## Task 5: GitService push + tag

**Files:**
- Modify: `backend/app/git/service.py`（+push/tag）
- Test: `backend/tests/test_git_service.py`（+测试，用本地 bare origin 验 push/tag）

**Interfaces:**
- Produces（追加）：`push(remote="origin", ref="main") -> str`（返回 pushed sha）；`tag(tag_name) -> str`（`git tag` + `push origin <tag>`，返回 tag 名）。

- [ ] **Step 1: 写失败测试（追加）**

```python
async def test_push_to_origin(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    await svc.commit(wt, "feat(F001): initial game + gdd")
    await svc.merge_to_main("agent/k1-brainstorm")
    pushed = await svc.push("origin", "main")
    assert isinstance(pushed, str) and len(pushed) >= 7
    # bare origin 的 main 现在有 games/k1/GDD.md
    rc, out, err = await svc._git(["ls-tree", "main", "games/k1/"], cwd=str(origin))
    assert "GDD.md" in out


async def test_tag(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    await svc.commit(wt, "feat(F001): initial game + gdd")
    await svc.merge_to_main("agent/k1-brainstorm")
    await svc.push("origin", "main")
    tag = await svc.tag("brainstorm-k1-v0")
    assert tag == "brainstorm-k1-v0"
    # bare origin 有该 tag
    rc, out, err = await svc._git(["ls-remote", "--tags", "origin"], cwd=str(svc.repo_dir))
    assert "brainstorm-k1-v0" in out
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_git_service.py -v -k push or tag`
Expected: FAIL（方法未定义）

- [ ] **Step 3: 实现 push/tag（追加到 service.py）**

```python
    async def push(self, remote: str = "origin", ref: str = "main") -> str:
        """git -C repo_dir push {remote} {ref}（PAT 凭据经 extraheader，use_pat=True）。
        返回 pushed sha。"""
        rc, out, err = await self._git(["push", remote, ref], cwd=str(self.repo_dir), use_pat=True)
        if rc != 0:
            raise RuntimeError(f"git push {remote} {ref} failed: {err}")
        return await self.current_sha(ref)

    async def tag(self, tag_name: str) -> str:
        """git -C repo_dir tag {tag_name}; push origin {tag_name}。返回 tag 名。"""
        rc, out, err = await self._git(["tag", tag_name], cwd=str(self.repo_dir))
        if rc != 0:
            raise RuntimeError(f"git tag {tag_name} failed: {err}")
        rc, out, err = await self._git(["push", "origin", tag_name], cwd=str(self.repo_dir), use_pat=True)
        if rc != 0:
            raise RuntimeError(f"git push tag {tag_name} failed: {err}")
        return tag_name
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_git_service.py -v -k push or tag`
Expected: PASS

- [ ] **Step 5: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add backend/app/git/service.py backend/tests/test_git_service.py
git commit -m "feat(git): GitService push + tag（PAT extraheader 临时凭据）"
```

---

## Task 6: game-template 骨架 + ensure_template_pushed

**Files:**
- Create: `backend/templates/game-template/package.json`、`tsconfig.json`、`vite.config.ts`、`index.html`、`.gitignore`、`README.md`、`src/main.ts`
- Create: `backend/app/git/template.py`
- Test: `backend/tests/test_template.py`

**Interfaces:**
- Consumes: `GitService`（用其 `repo_dir`/`_git`/`push`）；后端自带模板目录 `backend/templates/game-template/`（`REPO_ROOT / "backend" / "templates" / "game-template"`）。
- Produces: `ensure_template_pushed(git_service) -> bool`（幂等：repo_dir 无 `template/` 则从后端自带复制 + commit + push，首启一次性；空 repo 时显式 `git checkout -b main` 建首提交；返回是否本次推送）。Task 9 run_brainstorm 调用。

- [ ] **Step 1: 建 game-template 骨架文件**

`backend/templates/game-template/package.json`:
```json
{
  "name": "game-template",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

`backend/templates/game-template/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

`backend/templates/game-template/vite.config.ts`:
```ts
import { defineConfig } from 'vite'

export default defineConfig({
  server: { port: 5173 },
  build: { outDir: 'dist' },
})
```

`backend/templates/game-template/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Game</title>
</head>
<body>
  <canvas id="game" width="800" height="600"></canvas>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

`backend/templates/game-template/src/main.ts`:
```ts
// game-template canvas skeleton (spec §108: TS/Vite/Canvas)
const canvas = document.getElementById('game') as HTMLCanvasElement
const ctx = canvas.getContext('2d')!

function loop() {
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  requestAnimationFrame(loop)
}

loop()
```

`backend/templates/game-template/.gitignore`:
```
node_modules/
dist/
```

`backend/templates/game-template/README.md`:
```md
# game-template

最小 TS/Vite/Canvas 游戏骨架。新游戏复制自此（spec §108）。
Phase 2 只需结构完整能落 git；build 验证留 Phase 5。
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_template.py`:
```python
from __future__ import annotations

from pathlib import Path

from app.config.settings import REPO_ROOT
from app.git.service import GitService
from app.git.template import ensure_template_pushed


def _make_service(tmp_path, origin_url):
    class S:
        workspace_base = tmp_path
        github_repo_url = origin_url
        github_pat = ""
        git_branch_prefix = "agent"
    return GitService(S())


async def test_ensure_template_pushed_to_empty_repo(tmp_path):
    """空 bare origin：ensure_template_pushed 建首提交（显式 main）+ push template/。"""
    import subprocess
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    url = f"file:///{origin.as_posix()}"
    svc = _make_service(tmp_path, url)
    await svc.ensure_clone(origin_url=url)  # clone 空仓（HEAD unborn）
    pushed = await ensure_template_pushed(svc)
    assert pushed is True
    # repo_dir 有 template/ 且 main 分支有提交
    assert (svc.repo_dir / "template" / "package.json").exists()
    rc, out, err = await svc._git(["rev-parse", "main"], cwd=str(svc.repo_dir))
    assert rc == 0
    # origin 有 template/
    rc, out, err = await svc._git(["ls-tree", "main", "template/"], cwd=str(svc.repo_dir))
    assert "package.json" in out


async def test_ensure_template_pushed_idempotent(local_bare_repo, tmp_path):
    """已有 template/：不重复推送。"""
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, url)
    await svc.ensure_clone(origin_url=url)
    # origin 已有 main（local_bare_repo fixture 带初始提交），手动放 template/ 并推
    import shutil
    src = REPO_ROOT / "backend" / "templates" / "game-template"
    dst = svc.repo_dir / "template"
    shutil.copytree(src, dst, dirs_exist_ok=True)
    await svc._git(["checkout", "main"], cwd=str(svc.repo_dir))
    await svc._git(["add", "-A"], cwd=str(svc.repo_dir))
    await svc._git(["commit", "-m", "add template"], cwd=str(svc.repo_dir))
    await svc._git(["push", "origin", "main"], cwd=str(svc.repo_dir))
    pushed = await ensure_template_pushed(svc)
    assert pushed is False  # 已有，本次不推
```

- [ ] **Step 3: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_template.py -v`
Expected: FAIL（`ModuleNotFoundError: app.git.template`）

- [ ] **Step 4: 实现 template.py**

`backend/app/git/template.py`:
```python
from __future__ import annotations

import shutil
from pathlib import Path

from app.config.settings import REPO_ROOT
from app.git.service import GitService

# 后端自带模板源（入库）
TEMPLATE_SRC = REPO_ROOT / "backend" / "templates" / "game-template"


async def ensure_template_pushed(git_service: GitService) -> bool:
    """幂等：repo_dir 无 template/ 则从后端自带复制 + commit + push。

    空repo处理（spec §11）：若本地仓无任何提交（HEAD unborn），首提交前显式
    `git checkout -b main`（git 2.37 默认 master，不显式则 worktree_add(base=main)
    失败）。返回是否本次推送（False=已有，未推）。
    """
    repo_dir = git_service.repo_dir
    if (repo_dir / "template").exists():
        return False
    # 检查 HEAD 是否 unborn（无提交）
    rc, out, err = await git_service._git(["rev-parse", "--verify", "HEAD"], cwd=str(repo_dir))
    head_unborn = rc != 0
    if head_unborn:
        await git_service._git(["checkout", "-b", "main"], cwd=str(repo_dir))
    else:
        await git_service._git(["checkout", "main"], cwd=str(repo_dir))
    # 复制后端自带模板
    if not TEMPLATE_SRC.exists():
        raise RuntimeError(f"game-template source missing: {TEMPLATE_SRC}")
    dst = repo_dir / "template"
    shutil.copytree(TEMPLATE_SRC, dst, dirs_exist_ok=True)
    await git_service._git(["add", "-A"], cwd=str(repo_dir))
    await git_service._git(["commit", "-m", "chore: add game-template"], cwd=str(repo_dir))
    await git_service.push("origin", "main")
    return True
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_template.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 7: 提交**

```bash
git add backend/templates/ backend/app/git/template.py backend/tests/test_template.py
git commit -m "feat(git): game-template 骨架 + ensure_template_pushed（空 repo 显式建 main）"
```

---

## Task 7: project_service.create 改造（落 project_repositories + worktree 路径）

**Files:**
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/tests/test_project_service.py`
- Test: 见 Step 1

**Interfaces:**
- Consumes: `ProjectRepositoryRepo`（Task 1）；`Settings`（owner/repository 从 settings，但 settings 此时无 owner/repo 字段——从 `github_repo_url` 解析）。
- Produces: `create` 新增落 `ProjectRepository` 行（sub_path=`games/{key}/`，owner/repository 解析自 `settings.github_repo_url`）；`workspace_root` 改赋 `workspace/worktrees/{key}-brainstorm`（相对路径字符串，运行时拼绝对）。

**关键决策**：owner/repository 从 `settings.github_repo_url` 解析（`https://github.com/{owner}/{repo}.git` → owner/repo），避免加冗余 settings 字段。解析失败（url 空/格式不对）时 owner/repository 用空串——e2e 填了真 url 才有效，测试可注入。

- [ ] **Step 1: 写失败测试（追加到 test_project_service.py）**

```python
from app.persistence.repo import ProjectRepositoryRepo


async def test_create_project_writes_repository_row(async_db_session, monkeypatch):
    from app.services import project_service
    from app.config.settings import get_settings

    # 注入 settings：github_repo_url 可解析 owner/repo
    s = get_settings()
    monkeypatch.setattr(s, "github_repo_url",
                        "https://github.com/CodingZY/Game_Template_Repo.git")
    monkeypatch.setattr(project_service, "get_settings", lambda: s)

    p = await project_service.create(
        async_db_session, name="FarmDemo2", description="d",
        workspace_base=None,  # 用真实 settings.workspace_base？测试用 tmp 避免碰磁盘
    )
    # workspace_root 是 worktree 相对路径
    assert "worktrees" in p.workspace_root
    assert p.project_key in p.workspace_root
    # project_repositories 行
    rrepo = ProjectRepositoryRepo(async_db_session)
    row = await rrepo.get_by_project(p.id)
    assert row is not None
    assert row.owner == "CodingZY"
    assert row.repository == "Game_Template_Repo"
    assert row.sub_path == f"games/{p.project_key}/"
    assert row.current_branch is None
```
> 注：此测试需 `create` 签名支持 `workspace_base`（已有）+ 不真建 worktree（worktree 由 brainstorm task 建，create 只写 workspace_root 字符串）。故 create 不再调 ensure_workspace 建目录（Phase 1 是建的，Phase 2 改为只写路径字符串）。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_project_service.py -v`
Expected: FAIL（无 repository 行 / workspace_root 还是 Games 风格）

- [ ] **Step 3: 改 project_service.create**

`backend/app/services/project_service.py`：
```python
from __future__ import annotations

import secrets
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.project import Project
from app.persistence.repo import ProjectRepositoryRepo
from app.workflow.states import ProjectStatus


def _parse_owner_repo(url: str) -> tuple[str, str]:
    """从 https://github.com/{owner}/{repo}.git 解析 (owner, repo)。失败返 ('','')。"""
    try:
        path = urlparse(url).path.strip("/")
        owner, repo = path.split("/")[:2]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo
    except Exception:
        return "", ""


async def create(
    session: AsyncSession,
    name: str,
    description: str | None = None,
    workspace_base=None,  # Phase 2: 保留参数兼容但不再建目录（worktree 由 brainstorm task 建）
) -> Project:
    """生成 project_key、落 Project + ProjectRepository 行，status=CREATED。

    workspace_root = workspace/worktrees/{key}-brainstorm（相对路径字符串，
    运行时由 GitService 拼绝对）。不再调 ensure_workspace 建目录（Phase 1 旧路径）。
    """
    slug = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    key = f"{slug}-{secrets.token_hex(3)}"
    settings = get_settings()
    workspace_root = f"{settings.workspace_root}/worktrees/{key}-brainstorm"
    p = Project(
        project_key=key,
        name=name,
        description=description,
        status=ProjectStatus.CREATED,
        workspace_root=workspace_root,
    )
    session.add(p)
    await session.flush()
    # 落 project_repositories（D6）
    owner, repo = _parse_owner_repo(settings.github_repo_url)
    await ProjectRepositoryRepo(session).create(
        project_id=p.id, owner=owner, repository=repo, sub_path=f"games/{key}/",
    )
    await session.flush()
    return p
```

- [ ] **Step 4: 修旧测试兼容**

`test_project_service.py` 旧 `test_create_project` 断言 `p.workspace_root.endswith(p.project_key)`——Phase 2 改成 `.../{key}-brainstorm`，故断言改为 `assert p.workspace_root.endswith(f"{p.project_key}-brainstorm")`。`workspace_base=tmp_path` 参数保留但不生效（create 不再用它建目录），无害。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_project_service.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿（test_api_projects 建项目端点会落 repository 行，ProjectRead 不含 repository 字段，不影响）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/project_service.py backend/tests/test_project_service.py
git commit -m "feat(service): create 落 project_repositories + workspace_root=worktree 路径"
```

---

## Task 8: agent/session.py 改造（ensure_worktree path helper）

**Files:**
- Modify: `backend/app/agent/session.py`
- Test: `backend/tests/test_session_worktree.py`

**Interfaces:**
- Produces: `worktree_path(project_key, settings=None) -> Path`（返回 `<workspace_base>/worktrees/{key}-brainstorm`，纯路径推导，不建目录）；`ensure_workspace` 保留但 docstring 标 deprecated（Phase 1 用，新代码勿用）。GitService.worktree_add 已覆盖建目录职责，本 helper 仅供"已知 worktree 路径"场景。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_session_worktree.py`:
```python
from __future__ import annotations

from pathlib import Path

from app.agent.session import worktree_path


def test_worktree_path(tmp_path, monkeypatch):
    from app.config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "workspace_base", tmp_path)
    monkeypatch.setattr("app.agent.session.get_settings", lambda: s)
    p = worktree_path("farmdemo-aaa")
    assert p == tmp_path / "worktrees" / "farmdemo-aaa-brainstorm"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_session_worktree.py -v`
Expected: FAIL（`worktree_path` 未定义）

- [ ] **Step 3: 改 session.py**

`backend/app/agent/session.py`：
```python
from __future__ import annotations

from pathlib import Path

from app.config.settings import get_settings


def ensure_workspace(project_key: str, base: Path | None = None) -> Path:
    """[DEPRECATED Phase 1] 创建 `<base>/<project_key>/` 目录。

    Phase 2 改用 GitService.worktree_add（git 管理的 worktree）。保留本函数
    仅为 Phase 1 测试兼容，新代码勿用。
    """
    root = base if base is not None else get_settings().workspace_base
    p = root / project_key
    p.mkdir(parents=True, exist_ok=True)
    return p


def worktree_path(project_key: str, settings=None) -> Path:
    """推导 worktree 路径 `<workspace_base>/worktrees/{key}-brainstorm`（纯路径，不建目录）。

    建目录由 GitService.worktree_add 负责；本函数仅供"已知 worktree 路径"场景
    （如 run_finalize 查 worktree）。
    """
    s = settings or get_settings()
    return s.workspace_base / "worktrees" / f"{project_key}-brainstorm"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_session_worktree.py -v`
Expected: PASS

- [ ] **Step 5: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add backend/app/agent/session.py backend/tests/test_session_worktree.py
git commit -m "feat(agent): +worktree_path helper（ensure_workspace 标 deprecated）"
```

---

## Task 9: run_brainstorm 集成 GitService（worktree cwd + git.worktree.added 事件）

**Files:**
- Modify: `backend/app/queue/tasks.py`
- Modify: `backend/tests/test_tasks_worker.py`（注入 FakeGitService，使既有 5 测试仍绿）
- Test: `backend/tests/test_tasks_brainstorm_git.py`（新）

**Interfaces:**
- Consumes: `GitService`（ensure_clone/ensure_template_pushed/worktree_add/copy_template/worktree_path），`worktree_path`（session.py）。
- Produces: `run_brainstorm` 流程加 git 层：状态校验后 → `GitService().ensure_clone()` + `ensure_template_pushed()` → `worktree_add(agent/{key}-brainstorm)` → event `git.worktree.added` → 首次 `copy_template` → ClaudeRuntime.start(cwd=worktree/games/{key}) → `ProjectRepositoryRepo.set_branch`。`run_brainstorm` 模块级 import `GitService`/`ensure_template_pushed`/`ProjectRepositoryRepo`（可 monkeypatch）。

**关键决策**：GitService 在 run_brainstorm 内 `GitService()` 构造（模块级 import，测试 monkeypatch `app.queue.tasks.GitService` 注入 FakeGitService）。worktree 的 games/{key} 子目录 = Claude cwd。首词 brainstorm 仍走 Phase 1 闭环（parser/broker），只换 cwd + 加 git 前置。

- [ ] **Step 1: 写失败测试（新文件，FakeGitService）**

`backend/tests/test_tasks_brainstorm_git.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.agent_session import AgentSession
from app.models.event import Event
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo
from app.queue.tasks import run_brainstorm
from app.schemas.event import CoworkEvent
from app.workflow.engine import WorkflowBlocked

# 复用 test_tasks_worker 的 fakes/fixture 风格
from tests.test_tasks_worker import (
    FakeAioredis, FakeRuntime, _evt, _create_project, db_sm, fake_aioredis,
)


class FakeGitService:
    """FakeGitService：记录调用，模拟 worktree 路径 + copy_template。"""
    def __init__(self):
        self.clone_called = False
        self.template_pushed = False
        self.worktree_calls = []
        self.copy_calls = []
        self.wt_root = Path("/fake/workspace/worktrees")

    async def ensure_clone(self, origin_url=None):
        self.clone_called = True
        return self.wt_root / "games-repo"

    async def ensure_template_pushed(self, git_service=None):
        # signature: ensure_template_pushed(git_service) —— tasks 调用时传 self
        self.template_pushed = True
        return False

    async def worktree_add(self, project_key, branch):
        self.worktree_calls.append((project_key, branch))
        wt = self.wt_root / f"{project_key}-brainstorm"
        return wt

    async def worktree_path(self, project_key):
        return self.wt_root / f"{project_key}-brainstorm"

    async def copy_template(self, worktree_path, project_key):
        self.copy_calls.append((str(worktree_path), project_key))


async def test_run_brainstorm_prepares_worktree(db_sm, fake_aioredis, monkeypatch):
    """run_brainstorm 首次：ensure_clone + ensure_template_pushed + worktree_add +
    copy_template + ClaudeRuntime cwd=worktree/games/{key} + git.worktree.added 事件。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="wtprep")

    evts = [
        _evt(pid, "agent.session.started", {"session_id": "s1", "model": "kimi-k3"}),
        _evt(pid, "agent.session.completed",
             {"session_id": "s1", "result": "ok", "stop_reason": "end_turn"}),
    ]
    fake_rt = FakeRuntime(evts)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: fake_rt)

    await run_brainstorm(ctx={}, project_id=pid, prompt="种田")

    assert fake_git.clone_called
    assert fake_git.worktree_calls == [("wtprep", "agent/wtprep-brainstorm")]
    assert len(fake_git.copy_calls) == 1  # 首次 copy_template
    # ClaudeRuntime 收到的 cwd 含 games/{key}
    assert "games/wtprep" in str(fake_rt.cwd if hasattr(fake_rt, "cwd") else "")

    # git.worktree.added 事件落库
    async with db_sm() as s:
        rows = (await s.execute(select(Event).where(Event.project_id == pid))).scalars().all()
        types = [r.event_type for r in rows]
        assert "git.worktree.added" in types

    # ProjectRepository.current_branch 已设
    async with db_sm() as s:
        prow = await ProjectRepositoryRepo(s).get_by_project(pid)
        assert prow.current_branch == "agent/wtprep-brainstorm"
```
> 注：FakeRuntime 需记录 cwd——改 `test_tasks_worker.py` 的 FakeRuntime.start/resume 加 `self.cwd = cwd`（Step 4 改）。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_git.py -v`
Expected: FAIL（run_brainstorm 未调 GitService）

- [ ] **Step 3: 改 tasks.py run_brainstorm 集成 GitService**

`backend/app/queue/tasks.py`：顶部 import 加：
```python
from app.git.service import GitService
from app.git.template import ensure_template_pushed
from app.persistence.repo import AgentSessionRepo, ProjectRepo, ProjectRepositoryRepo
from app.agent.session import worktree_path
```
async def run_brainstorm(ctx, project_id, prompt):
    ...状态校验 + 置 BRAINSTORMING + 预建 agent_session → as_id...
    ...resume 判定 prev_sid（纯 DB 查，不依赖 git）...
    ...acquire lock → broker = EventBroker(session_factory=sm, redis=r)...
    # --- Phase 2: git 前置（在 lock 内、broker 之后；发事件需 broker）---
    git = GitService()
    await git.ensure_clone()
    await ensure_template_pushed(git)
    branch = f"{settings.git_branch_prefix}/{p.project_key}-brainstorm"
    wt = await git.worktree_add(p.project_key, branch)
    await broker.publish(CoworkEvent(... type="git.worktree.added" ...))
    games_dir = wt / "games" / p.project_key
    if not games_dir.exists():
        await git.copy_template(wt, p.project_key)
    claude_cwd = str(games_dir)
    async with sm() as s:
        await ProjectRepositoryRepo(s).set_branch(project_id, branch)
        await s.commit()
    # --- _events 用 claude_cwd（worktree/games/{key}）---
    ...三态收尾（同 Phase 1）...
    ...release lock...
```
即：原 lock 内的 `broker` 定义保持位置，git 前置插入在 `broker` 之后、`_events` 之前。`as_id`/`prev_sid` 在 lock 外的前置 sm 块（原结构不变）。

- [ ] **Step 4: 改 FakeRuntime 记录 cwd（test_tasks_worker.py）**

`backend/tests/test_tasks_worker.py` 的 `FakeRuntime`：
```python
class FakeRuntime:
    def __init__(self, evts):
        self.evts = evts
        self.called = None
        self.resume_sid = None
        self.cwd = None

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None):
        self.called = "start"
        self.cwd = cwd
        for e in self.evts:
            yield e

    async def resume(self, session_id, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None):
        self.called = "resume"
        self.resume_sid = session_id
        self.cwd = cwd
        for e in self.evts:
            yield e
```

- [ ] **Step 5: 改 test_tasks_worker 既有 5 测试注入 FakeGitService**

既有 `test_run_brainstorm_*` 现在会因 run_brainstorm 调真 GitService.ensure_clone（碰真 github）而失败。每个测试加：
```python
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)
```
（`FakeGitService` 从 `test_tasks_brainstorm_git` import 或提到 conftest 共享——建议提到 conftest 避免循环 import。）
> **执行决策**：把 `FakeGitService` 放 `backend/tests/conftest.py`，两个测试文件都 import。`_create_project` 的 `workspace_root=f"Games/{key}"` 保留（run_brainstorm 用 p.project_key + settings 拼 worktree，不读 workspace_root 字段）。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_git.py tests/test_tasks_worker.py -v`
Expected: PASS（新 1 + 既有 5 + worker_settings 1）。

- [ ] **Step 7: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 8: 提交**

```bash
git add backend/app/queue/tasks.py backend/tests/conftest.py backend/tests/test_tasks_brainstorm_git.py backend/tests/test_tasks_worker.py
git commit -m "feat(queue): run_brainstorm 集成 GitService（clone+worktree+copy_template+git.worktree.added）"
```

---

## Task 10: run_finalize + finalize lock + git.* 事件 + 异常兜底

**Files:**
- Modify: `backend/app/queue/tasks.py`（+run_finalize）
- Test: `backend/tests/test_tasks_finalize.py`

**Interfaces:**
- Consumes: `GitService`（commit/merge_to_main/worktree_remove/push/tag/current_sha），`assert_can_finalize`（Task 2），`ProjectRepositoryRepo`（set_last_sha/set_branch），`ProjectRepo`（set_status）。
- Produces: `async def run_finalize(ctx, project_id)`：状态校验 → acquire `lock:project:{id}:finalize` → commit → merge → worktree_remove+branch -d → push → tag → set_last_sha + set_branch(None) → project.status=BRAINSTORMED。每步发 git.* 事件（aggregate_type="git"）。异常兜底（沿用 Phase 1）：任何 git 步骤失败 → event `git.failed` + project FAILED（不卡死，保留 worktree debug）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_tasks_finalize.py`:
```python
from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo
from app.queue.tasks import run_finalize
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import FakeAioredis, _create_project, db_sm, fake_aioredis


class FakeGitFinalize:
    """记录 finalize 各步骤调用序列，模拟 sha。"""
    def __init__(self):
        self.calls = []
        self.merge_sha = "mergesha1"
        self.push_sha = "pushsha1"
        self.main_sha = "mainsha1"
    async def commit(self, worktree_path, message):
        self.calls.append(("commit", str(worktree_path), message)); return "commitsha1"
    async def merge_to_main(self, branch):
        self.calls.append(("merge", branch)); return self.merge_sha
    async def worktree_remove(self, project_key, branch):
        self.calls.append(("remove", project_key, branch))
    async def push(self, remote="origin", ref="main"):
        self.calls.append(("push", remote, ref)); return self.push_sha
    async def tag(self, tag_name):
        self.calls.append(("tag", tag_name)); return tag_name
    async def current_sha(self, ref="main"):
        self.calls.append(("current_sha", ref)); return self.main_sha
    async def worktree_path(self, project_key):
        from pathlib import Path
        return Path(f"/fake/wt/{project_key}-brainstorm")


async def test_run_finalize_success(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitFinalize()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)

    pid = await _create_project(db_sm, key="fin", status="BRAINSTORMING")
    # 预置 project_repositories.current_branch
    async with db_sm() as s:
        await ProjectRepositoryRepo(s).create(
            project_id=pid, owner="o", repository="r", sub_path="games/fin/")
        await ProjectRepositoryRepo(s).set_branch(pid, "agent/fin-brainstorm")
        await s.commit()

    result = await run_finalize(ctx={}, project_id=pid)

    assert result["succeeded"] is True
    # 步骤序列正确
    seq = [c[0] for c in fake_git.calls]
    assert seq == ["commit", "merge", "remove", "push", "tag", "current_sha"]
    # tag 名
    assert fake_git.calls[4] == ("tag", "brainstorm-fin-v0")
    # project BRAINSTORMED + repo last_sha + branch 清空
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.BRAINSTORMED.value
        prow = await ProjectRepositoryRepo(s).get_by_project(pid)
        assert prow.last_commit_sha == "mainsha1"
        assert prow.current_branch is None
    # git.* 事件落库
    async with db_sm() as s:
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
    for t in ("git.committed", "git.merged", "git.worktree.cleaned",
              "git.pushed", "git.tagged"):
        assert t in types


async def test_run_finalize_blocked_from_created(db_sm, monkeypatch):
    from app.workflow.engine import WorkflowBlocked
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    pid = await _create_project(db_sm, key="blk", status="CREATED")
    with pytest.raises(WorkflowBlocked):
        await run_finalize(ctx={}, project_id=pid)


async def test_run_finalize_git_failure(db_sm, fake_aioredis, monkeypatch):
    """git 步骤失败 → git.failed 事件 + project FAILED（不卡死）。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)

    class FailingGit(FakeGitFinalize):
        async def commit(self, worktree_path, message):
            raise RuntimeError("commit boom")

    monkeypatch.setattr("app.queue.tasks.GitService", lambda: FailingGit())
    pid = await _create_project(db_sm, key="failfin", status="BRAINSTORMING")
    async with db_sm() as s:
        await ProjectRepositoryRepo(s).create(
            project_id=pid, owner="o", repository="r", sub_path="games/failfin/")
        await ProjectRepositoryRepo(s).set_branch(pid, "agent/failfin-brainstorm")
        await s.commit()

    result = await run_finalize(ctx={}, project_id=pid)
    assert result["succeeded"] is False
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.FAILED.value
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "git.failed" in types
```
> 注：`test_run_finalize_blocked_from_created` 用 `pytest`，顶部 import。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_finalize.py -v`
Expected: FAIL（`run_finalize` 未定义）

- [ ] **Step 3: 实现 run_finalize（追加到 tasks.py）**

```python
async def run_finalize(ctx, project_id: int):
    """Arq task：把 brainstorm 成果定稿落 git（spec §5.6/§4.3 ⑤）。

    流程：状态校验(BRAINSTORMING) → acquire lock:finalize → commit → merge --no-ff
    → worktree remove + branch -d → push origin main → tag brainstorm-{key}-v0
    → set_last_sha + set_branch(None) → project BRAINSTORMED。
    每步发 git.* 事件；任何 git 步骤失败 → git.failed + project FAILED（不卡死，
    保留 worktree debug，doc §52）。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    # 1. 状态校验 + 取 project/repo 信息
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_finalize(p.status)
        prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
        branch = prow.current_branch if prow else None
        project_key = p.project_key
        await s.commit()
    if not branch:
        return {"failed": True, "reason": "no_current_branch"}

    # 2. acquire finalize lock
    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:finalize", timeout=1800)
    await lock.acquire()
    broker = EventBroker(session_factory=sm, redis=r)
    git = GitService()
    succeeded = False
    try:
        wt = await git.worktree_path(project_key)
        # 3. commit
        await git.commit(wt, "feat(F001): initial game + gdd")
        await broker.publish(CoworkEvent(project_id=project_id, type="git.committed",
            data={"project_id": project_id, "sha": "", "message": "feat(F001): initial game + gdd"},
            aggregate_type="git", aggregate_id=project_id))
        # 4. merge
        merge_sha = await git.merge_to_main(branch)
        await broker.publish(CoworkEvent(project_id=project_id, type="git.merged",
            data={"project_id": project_id, "branch": branch, "merge_commit": merge_sha},
            aggregate_type="git", aggregate_id=project_id))
        # 5. worktree remove + branch -d
        await git.worktree_remove(project_key, branch)
        await broker.publish(CoworkEvent(project_id=project_id, type="git.worktree.cleaned",
            data={"project_id": project_id, "branch": branch},
            aggregate_type="git", aggregate_id=project_id))
        # 6. push
        push_sha = await git.push("origin", "main")
        await broker.publish(CoworkEvent(project_id=project_id, type="git.pushed",
            data={"project_id": project_id, "ref": "main", "sha": push_sha},
            aggregate_type="git", aggregate_id=project_id))
        # 7. tag
        tag_name = f"brainstorm-{project_key}-v0"
        await git.tag(tag_name)
        await broker.publish(CoworkEvent(project_id=project_id, type="git.tagged",
            data={"project_id": project_id, "tag": tag_name},
            aggregate_type="git", aggregate_id=project_id))
        # 8. 收尾：last_sha + branch 清空 + BRAINSTORMED
        last_sha = await git.current_sha("main")
        async with sm() as s:
            await ProjectRepositoryRepo(s).set_last_sha(project_id, last_sha)
            await ProjectRepositoryRepo(s).set_branch(project_id, None)
            await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMED)
            await s.commit()
        succeeded = True
        return {"succeeded": True, "tag": tag_name, "last_sha": last_sha}
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        await broker.publish(CoworkEvent(project_id=project_id, type="git.failed",
            data={"project_id": project_id, "stage": "finalize", "error": err},
            aggregate_type="git", aggregate_id=project_id))
        async with sm() as s:
            await ProjectRepo(s).set_status(project_id, ProjectStatus.FAILED)
            await s.commit()
        return {"succeeded": False, "error": err}
    finally:
        await lock.release()
        await r.close()
```
> 注：`assert_can_finalize` 需在 tasks.py 顶部 import（已有 `assert_can_brainstorm`，加 `assert_can_finalize`）。

- [ ] **Step 4: 顶部 import 补 assert_can_finalize**

`backend/app/queue/tasks.py`：
```python
from app.workflow.engine import assert_can_brainstorm, assert_can_finalize
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_finalize.py -v`
Expected: PASS（3 测试：success/blocked/git_failure）

- [ ] **Step 6: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 7: 提交**

```bash
git add backend/app/queue/tasks.py backend/tests/test_tasks_finalize.py
git commit -m "feat(queue): run_finalize（commit+merge+cleanup+push+tag + git.* 事件 + 异常兜底）"
```

---

## Task 11: finalize API 端点 + enqueue_finalize + worker 注册

**Files:**
- Modify: `backend/app/queue/jobs.py`（+enqueue_finalize）
- Modify: `backend/app/queue/worker.py`（注册 run_finalize）
- Modify: `backend/app/api/projects.py`（+POST /brainstorm/finalize）
- Test: `backend/tests/test_api_finalize.py`

**Interfaces:**
- Produces: `jobs.enqueue_finalize(project_id) -> str`（enqueue `run_finalize(project_id)`）；`POST /api/projects/{id}/brainstorm/finalize` → 202 `{task_id}`；`WorkerSettings.functions = [run_brainstorm, run_finalize]`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_finalize.py`:
```python
from __future__ import annotations

import pytest


async def test_finalize_endpoint(client, monkeypatch):
    async def _ret(pid):
        return "job-fin-1"
    monkeypatch.setattr("app.api.projects.enqueue_finalize", _ret)
    r = await client.post("/api/projects/1/brainstorm/finalize")
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-fin-1"


async def test_enqueue_finalize(monkeypatch):
    from app.queue import jobs

    class FakeJob:
        job_id = "job-fin-1"

    class FakeRedis:
        async def enqueue_job(self, func, *args, _queue_name=None):
            assert func == "run_finalize"
            assert args[0] == 7
            return FakeJob()

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(jobs, "create_pool", fake_create_pool)
    jid = await jobs.enqueue_finalize(7)
    assert jid == "job-fin-1"
```
> 注：`client` fixture 在 `test_api_projects.py` 已有（若没有则 Step 3 补，见 Step 3 说明）。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_finalize.py -v`
Expected: FAIL（`enqueue_finalize` 未定义 / 端点 404）

- [ ] **Step 3: 实现 enqueue_finalize（jobs.py 追加）**

`backend/app/queue/jobs.py`：
```python
async def enqueue_finalize(project_id: int) -> str:
    """向 Arq 队列 enqueue run_finalize(project_id)，返回 job_id。"""
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_finalize", project_id, _queue_name=s.arq_queue)
    return job.job_id
```

- [ ] **Step 4: 实现 finalize 端点（projects.py 追加）**

`backend/app/api/projects.py`：import 加 `from app.queue.jobs import enqueue_brainstorm, enqueue_finalize`；追加：
```python
@router.post("/projects/{pid}/brainstorm/finalize", status_code=202)
async def finalize_brainstorm(pid: int):
    job_id = await enqueue_finalize(pid)
    return {"task_id": job_id}
```

- [ ] **Step 5: 改 worker.py 注册 run_finalize**

`backend/app/queue/worker.py`：
```python
from app.queue.tasks import run_brainstorm, run_finalize

class WorkerSettings:
    functions = [run_brainstorm, run_finalize]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    queue_name = get_settings().arq_queue
```

- [ ] **Step 6: 确认 client fixture（若 test_api_projects 已有则跳过）**

Run: `grep -n "def client" backend/tests/test_api_projects.py`。若无 `client` fixture，在 `test_api_finalize.py` 顶部加本地 fixture（用 httpx AsyncClient + ASGITransport）：
```python
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```
（参照 test_api_projects.py 既有 client fixture 风格，若已有则直接 import 复用。）

- [ ] **Step 7: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_finalize.py -v`
Expected: PASS

- [ ] **Step 8: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 9: 提交**

```bash
git add backend/app/queue/jobs.py backend/app/queue/worker.py backend/app/api/projects.py backend/tests/test_api_finalize.py
git commit -m "feat(api): POST /brainstorm/finalize 端点 + enqueue_finalize + worker 注册 run_finalize"
```

---

## Task 12: SSE git.* 事件可见性验证

**Files:**
- Modify: `backend/tests/test_api_events_sse.py`（+git.* 事件回放测试）

**Interfaces:**
- Consumes: Phase 1 SSE 端点（已透传 events 表，git.* 事件 aggregate_type="git" 也会落 events 表，SSE history 回放天然覆盖）。
- Produces: 验证 git.* 事件经 SSE 回放可见（无需改 events.py，git.* 走同一 EventRepo.insert + broker.history）。

- [ ] **Step 1: 写失败测试（追加到 test_api_events_sse.py）**

```python
async def test_stream_replays_git_events(client, async_db_session):
    """git.* 事件落 events 表后，SSE history 回放可见（aggregate_type=git 也走同表）。"""
    from app.persistence.repo import EventRepo
    from app.schemas.event import CoworkEvent
    broker = EventBroker(session_factory=lambda: _session_ctx(async_db_session), redis=None)
    # 直接插一条 git.committed 事件到 events 表
    async with async_db_session.begin():
        from app.models.event import Event
        async_db_session.add(Event(
            event_id="evt_git1", project_id=1, event_type="git.committed",
            aggregate_type="git", aggregate_id=1,
            payload={"project_id": 1, "sha": "abc"}, raw_json=None,
        ))
        await async_db_session.commit()
    r = await client.get("/api/projects/1/stream?after=0")
    assert r.status_code == 200
    assert "git.committed" in r.text
```
> 注：`_session_ctx` 若无，用既有 `async_db_session` 直接查 + 端点 history 读同表。简化：直接 `async_db_session.add(Event(...))` + `await async_db_session.commit()`，端点经独立 sessionmaker 读——但 sqlite StaticPool 下端点用真 app 的 sessionmaker 连不同库。**故本测试用真 app（lifespan 建表到 sqlite？）——简化为只验证 events 表有 git.committed 即 SSE text 含它**。若 client fixture 用真 app lifespan（连真 MySQL），则需真 DB。**执行决策**：本测试用与 test_api_projects 相同的 client/db 体系（看既有 test_api_events_sse 如何连 DB），直接沿用其 fixture，只改插的 event_type 为 git.committed。

- [ ] **Step 2: 跑确认失败/通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_events_sse.py -v -k git`
Expected: 若既有 SSE 测试已验证任意 event 回放，本测试应 PASS（git.* 走同表同端点）。若 FAIL（fixture 不匹配），按 Step 1 注调整 fixture 对齐既有 test_api_events_sse.py。

- [ ] **Step 3: 跑全量确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q`
Expected: 全绿。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_api_events_sse.py
git commit -m "test(sse): git.* 事件经 SSE history 回放可见"
```

---

## Task 13: e2e 手动验收（真打共享 GitHub repo，不进 CI）

**Goal:** 跑通 spec §1.2 验收链路 ①-⑦，真打 KSPMAS kimi-k3 + 共享 GitHub repo（PAT push）。

- [ ] **Step 1: 确认基建**

```bash
redis-cli ping           # PONG
# MySQL 库 ai_cowork_game 已建（Phase 1）；project_repositories 表由 lifespan create_all 建表
# .env 已填 GITHUB_REPO_URL + GITHUB_PAT（Task 0 Step 2）
git ls-remote https://github.com/CodingZY/Game_Template_Repo.git  # 确认可达
```

- [ ] **Step 2: 起 Arq worker（终端A）**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m arq app.queue.worker.WorkerSettings
```
确认日志：`Starting worker for 2 functions: run_brainstorm, run_finalize` + `queue_name=agent`。

- [ ] **Step 3: 起 FastAPI（终端B）**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
确认 `Application startup complete`（create_all 含 project_repositories）。

- [ ] **Step 4: 跑验收链路（终端C，用 httpx 脚本避免中文编码问题）**

```python
# 脚本：建项目→brainstorm→SSE看流→finalize→查GitHub
import asyncio, httpx, json
async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as c:
        # ① 建项目
        r = await c.post("/api/projects", json={"name":"FarmDemo2","description":"种田游戏"})
        pid = r.json()["id"]; print("project", r.json())
        # ② brainstorm 入队
        r = await c.post(f"/api/projects/{pid}/brainstorm", json={"idea":"种田游戏：经营农场..."})
        print("brainstorm", r.json())
    # ③ SSE 看流（见 Step 5）
    # ⑤ finalize
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as c:
        r = await c.post(f"/api/projects/{pid}/brainstorm/finalize")
        print("finalize", r.json())
asyncio.run(main())
```

- [ ] **Step 5: SSE 看流 + 查 GitHub**

SSE（after=0）应见：`agent.session.started → agent.message.delta → ... → agent.session.completed` + `git.worktree.added`；finalize 后见 `git.committed → git.merged → git.worktree.cleaned → git.pushed → git.tagged`。
GitHub 验证：`git ls-remote --tags https://github.com/CodingZY/Game_Template_Repo.git` 见 `brainstorm-{key}-v0`；web 看 main 有 `games/{key}/` + `{名}-game-design.md`。

- [ ] **Step 6: 验收检查清单**

- [ ] project_repositories 行：sub_path=games/{key}/，current_branch finalize 后清空，last_commit_sha 回填
- [ ] workspace/games-repo/ 有 template/ + games/{key}/
- [ ] worktree finalize 后 cleanup（workspace/worktrees/{key}-brainstorm/ 不存在）
- [ ] GitHub main 有 games/{key}/{名}-game-design.md
- [ ] GitHub 有 brainstorm-{key}-v0 tag
- [ ] SSE 全程可见 agent.* + git.* 事件
- [ ] 若 refusal：project FAILED + git 未 finalize（属预期三态，非 bug）

- [ ] **Step 7: 记录验收结果到 doc**

在 plan 末尾追加验收记录（通过/失败 + 现象 + 任何 e2e 修复）。

- [ ] **Step 8: 提交（若 e2e 发现 fix）**

```bash
git add -A && git commit -m "test(e2e): Phase2 验收链路手动验证（clone→worktree→brainstorm→finalize→push→tag）"
```

---

## Self-Review 已执行

**1. Spec coverage:** 逐条对照 spec §1-13：
- §1.2 验收链路 ①-⑦ → Task 0(config)+7(create)+9(brainstorm)+10(finalize)+11(API)+13(e2e) 全覆盖。
- §2 D1-D10 → Global Constraints + 各 task（D7→GitService subprocess；D8→不改 GDD 命名；D9→Task 6 template；D10→测试策略）。
- §3 spike 证据 → Global Constraints 引用 + Task 0 Step 6 验真 clone。
- §4.1 物理布局 → File Structure + Task 0 .gitignore + GitService._worktree_dir。
- §4.2 模块清单 → File Structure 全覆盖。
- §4.3 数据流 → Task 9(brainstorm)+10(finalize) 逐步骤。
- §5.1 GitService 方法 → Task 3-5 逐方法（_git/ensure_clone/worktree_add/worktree_path/copy_template/commit/merge_to_main/worktree_remove/push/tag/current_sha）全覆盖。
- §5.2 template → Task 6。
- §5.3 project_repositories → Task 1（DDL 字段对齐）。
- §5.4 states → Task 2。
- §5.5 project_service → Task 7。
- §5.6 tasks → Task 9(run_brainstorm 改)+10(run_finalize)。
- §5.7 API → Task 11。
- §5.8 session → Task 8。
- §6 数据模型 → Task 1(表)+7(projects workspace_root)+9(agent_sessions working_directory 经 create)+Redis 键(Task 10 finalize lock)。
- §7 事件协议 git.* → Task 9(git.worktree.added)+10(全 git.*)+12(SSE 可见)全覆盖。
- §8 API → Task 11。
- §9 .env → Task 0。
- §10 测试 → 各 task 单测 + Task 13 e2e。
- §11 风险 → Global Constraints(空 repo main/PAT 不落盘/worktree 绝对路径)+Task 0 Step 6(验真)+Task 10(异常兜底)。

**2. Placeholder scan:** 无 TBD/TODO。Task 12 Step 1 标了「执行决策」（fixture 对齐既有 test_api_events_sse）——属接口钉死而非占位，执行者按既有 fixture 调整。Task 9 Step 5 标了「执行决策」（FakeGitService 放 conftest）——同理。其余各 step 含实际代码/命令。

**3. Type consistency:**
- `GitService.__init__(settings=None)` / `_git(args, cwd=None, use_pat=False) -> tuple[int,str,str]` / `ensure_clone(origin_url=None) -> Path` 跨 Task 3-10 一致。
- `worktree_add(project_key, branch) -> Path`（Task 4 定义，Task 9 调用传 `(key, "agent/{key}-brainstorm")` 一致）。
- `commit(worktree_path, message) -> str`（Task 4 定义 Path 入参，Task 10 FakeGitFinalize + 真调用一致）。
- `ProjectRepositoryRepo.create(project_id, owner, repository, sub_path, default_branch="main")`（Task 1 定义，Task 7 调用一致）。
- `run_finalize(ctx, project_id)` / `enqueue_finalize(project_id)` / `assert_can_finalize(status)` 跨 Task 10-11 一致。
- `ensure_template_pushed(git_service)`（Task 6 定义，Task 9 调用 `ensure_template_pushed(git)` 一致；FakeGitService.ensure_template_pushed 签名对齐）。

## 执行交接

计划已存 `doc/plans/2026-08-15-phase2-git-plan.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每个 task 派新 subagent，任务间 review，快速迭代。

**2. Inline Execution** — 本会话用 executing-plans 批量执行，带检查点。

**你选哪种？**
