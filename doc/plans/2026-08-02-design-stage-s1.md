# Design 阶段（S1）前后端 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「需求确认」（S1 design）阶段端到端可运行：后端用 `claude_agent_sdk` 跑 Design Agent（编码 obra/superpowers brainstorming 方法论），多轮问答 → 产出 `Games/<game-name>/docs/game-design.md`；前端展示 Markdown 编辑器 + 问答面板 + 实时进度流；阶段闸由前端用户通过/不通过，不通过带反馈重跑直到通过。

**Architecture:** 方案3 混合：Orchestrator（Python 状态机 + MySQL 持久化 + checkpoint）管阶段边界与闸；阶段内由 `claude_agent_sdk.query()` 跑 Design Agent 自循环，用自定义工具（`read_file`/`write_file`/`ask_user`）+ `can_use_tool` 权限沙箱 + `HookMatcher` 进度流。前端 React SPA。本计划只实现 S1 所需的最小骨架（orchestrator/persistence/api/agent-runner/frontend 的 S1 子集），其余阶段（Art 等）由后续计划扩展。

**Tech Stack:** Python 3.10（conda env `agent_env`）· `claude_agent_sdk` 0.2.125 · FastAPI · SQLAlchemy 2.0(async) · MySQL（生产）/ SQLite（测试）· React 18 · Vite · TypeScript · Vitest。

## Global Constraints

- **Python 环境**：所有后端命令在 `conda activate agent_env`（`D:/Anaconda3/envs/agent_env`）下运行；Python 3.10.19。运行后端用 `D:/Anaconda3/envs/agent_env/python.exe`。
- **已装依赖**：claude-agent-sdk 0.2.125、fastapi 0.139、SQLAlchemy 2.0.48、uvicorn 0.51、httpx、pillow、pytest 9.1、aiosqlite、anyio。**需补装**：`aiomysql`、`python-dotenv`、`pytest-asyncio`。
- **Node**：v20.20.1 / npm 10.8.2（前端用）。
- **平台**：Windows + Git Bash；路径用正斜杠；venv/conda 的 python 在 `Scripts/` 下。
- **语言/规范**：所有代码与 Agent 输出中文；每个后端文件顶部有简短中文功能说明注释；Design Agent 产物必须通过 `agents/contract.py` 的 `validate_game_design` 校验。
- **参考交付物**：顶层 `game-design-spec.md`（Farmer）是 S1 交付格式样例与测试夹具；Design Agent 的输出格式契约从它提炼。
- **SDK API（已内省确认，0.2.125）**：
  - `query(*, prompt: str|AsyncIterable, options: ClaudeAgentOptions) -> AsyncIterator[Message]`
  - `ClaudeAgentOptions(system_prompt=, tools=[str|preset], mcp_servers={name:McpSdkServerConfig}, can_use_tool=Callable[[str,dict,ToolPermissionContext],Awaitable[PermissionResultAllow|PermissionResultDeny]], hooks={event:[HookMatcher]}, permission_mode=, model=, cwd=, env=)`
  - `@tool(name=, description=, input_schema=<type|dict>)` 装饰 async fn `(args)->dict`；`create_sdk_mcp_server(name, version, tools=[SdkMcpTool]) -> McpSdkServerConfig`
  - `PermissionResultAllow()` / `PermissionResultDeny(message=, interrupt=)` / `ToolPermissionContext`
  - `HookMatcher(matcher=<str|None>, hooks=[async_cb], timeout=)`，`async_cb(input_dict, tool_use_id_str|None, ctx_dict) -> dict`（返回 `{}` 表示放行）
- **测试约定**：后端用 pytest + pytest-asyncio；DB 测试用 SQLite in-memory（`aiosqlite`），生产用 MySQL（`aiomysql`）；本计划含自动化测试用于自检，**用户不手动测试 S1**；接真实 LLM 的端到端冒烟为可选手动步骤。

---

## File Structure

**后端 `backend/`**
- `backend/pyproject.toml` — 依赖与 pytest 配置
- `backend/.env.example` — 配置模板（自部署端点、MySQL、模型）
- `backend/persistence/db.py` — 异步 engine/session 工厂 + `init_db()`
- `backend/persistence/models.py` — SQLAlchemy 模型（GameRun/StageState/PendingApproval/PendingQuestion）
- `backend/persistence/repo.py` — 仓储函数（create/get/update/list/审批/问答）
- `backend/orchestrator/states.py` — `Stage` / `StageStatus` 枚举
- `backend/orchestrator/machine.py` — 状态机纯逻辑（转移 + 闸）
- `backend/agents/contract.py` — `validate_game_design()` + 输出模板
- `backend/agents/prompts.py` — `DESIGN_SYSTEM_PROMPT`
- `backend/agents/tools.py` — `read_file`/`write_file`/`ask_user` 工具（plain fn + SDK 包装）
- `backend/agents/permissions.py` — `make_permission_handler(game_root)`
- `backend/agents/hooks.py` — `make_progress_hooks(on_progress)`
- `backend/agents/runner.py` — `run_design_agent()`（query 接线）
- `backend/api/broker.py` — WS 发布/订阅 + 问答 Future 中介
- `backend/api/runtime.py` — 后台 agent 任务管理
- `backend/api/routes.py` — REST 路由
- `backend/api/ws.py` — WS 端点
- `backend/api/main.py` — FastAPI app 装配 + lifespan
- `backend/tests/conftest.py` — SQLite fixture
- `backend/tests/test_machine.py` / `test_contract.py` / `test_permissions.py` / `test_tools.py` / `test_hooks.py` / `test_repo.py` / `test_routes.py` / `test_runner.py`

**前端 `frontend/`**
- `frontend/package.json` / `vite.config.ts` / `tsconfig.json` / `index.html`
- `frontend/src/main.tsx` / `App.tsx` / `types.ts`
- `frontend/src/api/client.ts` — REST + WS 客户端
- `frontend/src/components/ProgressBar.tsx` / `ProgressStream.tsx` / `MarkdownEditor.tsx` / `QAPanel.tsx`
- `frontend/src/stages/DesignWorkbench.tsx`
- `frontend/src/__tests__/*.test.tsx`

**产物 `Games/<game-name>/docs/game-design.md`**（由 Design Agent 写入）

---

## Task 1: 后端骨架 + 依赖 + 配置 + git

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/.gitignore`, `.gitignore`, `backend/persistence/__init__.py`, `backend/orchestrator/__init__.py`, `backend/agents/__init__.py`, `backend/api/__init__.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`
- Modify: 仓库根（`git init`）

**Interfaces:**
- Produces: `backend/tests/conftest.py` 暴露 `async_session` fixture（in-memory SQLite），供后续任务测试用；`pyproject.toml` 锁定依赖入口。

- [ ] **Step 1: 初始化 git 与目录**

```bash
cd "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game"
git init
mkdir -p backend/persistence backend/orchestrator backend/agents backend/api backend/tests
touch backend/persistence/__init__.py backend/orchestrator/__init__.py backend/agents/__init__.py backend/api/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: 写根 `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
node_modules/
dist/
.pytest_cache/
Games/
```

> `Games/` 是产物目录，不入库（但保留 `Games/.gitkeep` 在后续任务按需）。

- [ ] **Step 3: 写 `backend/pyproject.toml`**

```toml
[project]
name = "ai-cowork-game-backend"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "claude-agent-sdk==0.2.125",
  "fastapi>=0.139",
  "uvicorn>=0.51",
  "SQLAlchemy>=2.0.48",
  "aiomysql",
  "aiosqlite",
  "python-dotenv",
  "httpx",
  "pillow",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4: 写 `backend/.env.example`**

```env
# 自部署的 Claude 兼容端点
ANTHROPIC_BASE_URL=http://127.0.0.1:8080
ANTHROPIC_AUTH_TOKEN=replace-with-your-self-deployed-key
# Design Agent 用的模型名
DESIGN_MODEL=claude-sonnet-4-6
# 生产 MySQL；测试固定用 sqlite in-memory，不读此项
DATABASE_URL=mysql+aiomysql://root:root@localhost:3306/agent_game?charset=utf8mb4
# 后端监听
HOST=127.0.0.1
PORT=8000
```

- [ ] **Step 5: 补装缺失依赖**

```bash
D:/Anaconda3/envs/agent_env/python.exe -m pip install aiomysql python-dotenv pytest-asyncio
```
Expected: 三个包安装成功（已装依赖不重装）。

- [ ] **Step 6: 写 `backend/tests/conftest.py`**

```python
"""测试夹具：in-memory SQLite 异步会话，供所有后端单测使用。"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from persistence.models import Base


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    await engine.dispose()
```

- [ ] **Step 7: 写一个冒烟测试验证导入链**

`backend/tests/test_smoke.py`:
```python
"""验证核心第三方包可导入。"""

def test_imports():
    import fastapi  # noqa
    import sqlalchemy  # noqa
    import claude_agent_sdk  # noqa
    import aiomysql  # noqa
    import dotenv  # noqa
    assert True
```

- [ ] **Step 8: 运行冒烟测试**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_smoke.py -v
```
Expected: PASS（若 `persistence.models` 未建则下个任务补；此处只测第三方导入）。

> 注：Step 6 引用了 `persistence.models.Base`，将在 Task 2 创建。为让本步通过，可先在 `backend/persistence/models.py` 放最小 `Base`（见 Task 2 Step 1），或把 conftest 的 import 推迟到 Task 2 完成后再运行。**实现时先做 Task 2 的 `Base`，再回头跑本冒烟。**

- [ ] **Step 9: Commit**

```bash
git add backend/ .gitignore
git commit -m "chore: backend scaffold, deps, config, test fixtures"
```

---

## Task 2: 持久化模型 + 仓储

**Files:**
- Create: `backend/persistence/models.py`, `backend/persistence/db.py`, `backend/persistence/repo.py`
- Test: `backend/tests/test_repo.py`

**Interfaces:**
- Consumes: `orchestrator/states.Stage`（字符串值，Task 3）——为解耦，模型用 `String` 列存 stage 字符串，不直接 import 枚举。
- Produces: `persistence.models.Base`、`persistence.models.GameRun/StageState/PendingApproval/PendingQuestion`；`persistence.db.get_session_factory(url)`、`init_db(engine)`；`persistence.repo.create_run/get_run/list_runs/update_stage/create_approval/resolve_approval/get_pending_approval/create_question/answer_question`。

- [ ] **Step 1: 写 `backend/persistence/models.py`**

```python
"""SQLAlchemy 模型：游戏运行、阶段状态、待审批、待回答问答。"""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GameRun(Base):
    __tablename__ = "game_run"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="S0_init")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    stages: Mapped[list["StageState"]] = relationship(back_populates="run", cascade="all,delete-orphan")


class StageState(Base):
    __tablename__ = "stage_state"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("game_run.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run: Mapped["GameRun"] = relationship(back_populates="stages")


class PendingApproval(Base):
    __tablename__ = "pending_approval"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("game_run.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|approved|rejected
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PendingQuestion(Base):
    __tablename__ = "pending_question"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("game_run.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|answered
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: 写 `backend/persistence/db.py`**

```python
"""异步 engine/session 工厂 + 建表。"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base


def get_session_factory(url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(url, future=True)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 3: 写失败测试 `backend/tests/test_repo.py`**

```python
"""仓储函数 CRUD 测试（in-memory SQLite）。"""
import pytest
from persistence.repo import (
    create_run, get_run, list_runs, update_stage,
    create_approval, resolve_approval, get_pending_approval,
    create_question, answer_question,
)


@pytest.mark.asyncio
async def test_create_and_get_run(async_session):
    run = await create_run(async_session, game_name="我的农场", slug="my-farm")
    assert run.id and run.current_stage == "S0_init"
    got = await get_run(async_session, run.id)
    assert got.game_name == "我的农场"


@pytest.mark.asyncio
async def test_list_runs(async_session):
    await create_run(async_session, game_name="A", slug="a")
    await create_run(async_session, game_name="B", slug="b")
    runs = await list_runs(async_session)
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_update_stage(async_session):
    run = await create_run(async_session, game_name="A", slug="a")
    await update_stage(async_session, run.id, stage="S1_design", status="running")
    got = await get_run(async_session, run.id)
    assert got.current_stage == "S1_design" and got.status == "running"


@pytest.mark.asyncio
async def test_approval_flow(async_session):
    run = await create_run(async_session, game_name="A", slug="a")
    ap = await create_approval(async_session, run.id, stage="S1_design", payload={"doc": "game-design.md"})
    assert ap.status == "pending"
    await resolve_approval(async_session, ap.id, resolution="approved", feedback=None)
    pending = await get_pending_approval(async_session, run.id, stage="S1_design")
    assert pending.status == "approved"


@pytest.mark.asyncio
async def test_question_flow(async_session):
    run = await create_run(async_session, game_name="A", slug="a")
    q = await create_question(async_session, run.id, "q1", "游戏类型？", ["RPG", "模拟"])
    assert q.status == "pending"
    await answer_question(async_session, q.id, answer="模拟")
    assert q.status == "answered" and q.answer == "模拟"
```

- [ ] **Step 4: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_repo.py -v
```
Expected: FAIL（`persistence.repo` 不存在）。

- [ ] **Step 5: 写 `backend/persistence/repo.py`**

```python
"""仓储函数：对 GameRun/StageState/PendingApproval/PendingQuestion 的增查改。"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import GameRun, StageState, PendingApproval, PendingQuestion


async def create_run(session: AsyncSession, *, game_name: str, slug: str) -> GameRun:
    run = GameRun(id=slug, game_name=game_name, slug=slug, current_stage="S0_init", status="running")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: str) -> GameRun | None:
    return await session.get(GameRun, run_id)


async def list_runs(session: AsyncSession) -> list[GameRun]:
    res = await session.execute(select(GameRun).order_by(GameRun.created_at.desc()))
    return list(res.scalars().all())


async def update_stage(session: AsyncSession, run_id: str, *, stage: str, status: str) -> None:
    run = await session.get(GameRun, run_id)
    run.current_stage = stage
    run.status = status
    await session.commit()


async def create_approval(session: AsyncSession, run_id: str, *, stage: str, payload: dict) -> PendingApproval:
    ap = PendingApproval(run_id=run_id, stage=stage, payload=payload, status="pending")
    session.add(ap)
    await session.commit()
    await session.refresh(ap)
    return ap


async def resolve_approval(session: AsyncSession, approval_id: int, *, resolution: str, feedback: str | None) -> None:
    ap = await session.get(PendingApproval, approval_id)
    ap.status = resolution  # approved | rejected
    ap.feedback = feedback
    ap.resolved_at = datetime.utcnow()
    await session.commit()


async def get_pending_approval(session: AsyncSession, run_id: str, *, stage: str) -> PendingApproval | None:
    res = await session.execute(
        select(PendingApproval).where(PendingApproval.run_id == run_id, PendingApproval.stage == stage)
        .order_by(PendingApproval.created_at.desc())
    )
    return res.scalars().first()


async def create_question(session: AsyncSession, run_id: str, question_id: str, question_text: str, options: list) -> PendingQuestion:
    q = PendingQuestion(run_id=run_id, question_id=question_id, question_text=question_text, options=options, status="pending")
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q


async def answer_question(session: AsyncSession, question_id_pk: int, *, answer: str) -> None:
    q = await session.get(PendingQuestion, question_id_pk)
    q.answer = answer
    q.status = "answered"
    q.answered_at = datetime.utcnow()
    await session.commit()
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_repo.py -v
```
Expected: 5 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/persistence backend/tests/test_repo.py
git commit -m "feat(persistence): models + async repo with CRUD tests"
```

---

## Task 3: Orchestrator 状态机（纯逻辑）

**Files:**
- Create: `backend/orchestrator/states.py`, `backend/orchestrator/machine.py`
- Test: `backend/tests/test_machine.py`

**Interfaces:**
- Consumes: 无
- Produces: `Stage` 枚举（`S0_init/S1_design/S2_art_plan/S3_art_gen/S4_coding/S5_done`）、`StageStatus`（`running/awaiting_approval/approved/rejected/not_implemented/done`）；`RunState` 数据类；`StateMachine` 方法 `start_design/complete_design/approve/reject`，返回 `Transition(stage, status)`。调用方负责落库（repo）。

- [ ] **Step 1: 写失败测试 `backend/tests/test_machine.py`**

```python
"""状态机转移与闸逻辑测试。"""
from orchestrator.states import Stage, StageStatus
from orchestrator.machine import StateMachine, RunState


def test_start_design():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S0_init, status=StageStatus.running)
    t = sm.start_design(run)
    assert t.stage == Stage.S1_design and t.status == StageStatus.running


def test_complete_design_holds_gate():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S1_design, status=StageStatus.running)
    t = sm.complete_design(run)
    assert t.stage == Stage.S1_design and t.status == StageStatus.awaiting_approval


def test_approve_design_advances_to_art_plan_not_implemented():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S1_design, status=StageStatus.awaiting_approval)
    t = sm.approve(run, stage=Stage.S1_design)
    # S2 尚未实现，标记为 not_implemented
    assert t.stage == Stage.S2_art_plan and t.status == StageStatus.not_implemented


def test_reject_design_back_to_revising():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S1_design, status=StageStatus.awaiting_approval)
    t = sm.reject(run, stage=Stage.S1_design, feedback="再加一个钓鱼系统")
    assert t.stage == Stage.S1_design and t.status == StageStatus.running


def test_cannot_approve_wrong_stage():
    sm = StateMachine()
    run = RunState(id="a", stage=Stage.S0_init, status=StageStatus.running)
    t = sm.approve(run, stage=Stage.S1_design)
    assert t is None  # 状态不匹配，拒绝转移
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_machine.py -v
```
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写 `backend/orchestrator/states.py`**

```python
"""阶段与状态枚举。"""
from enum import Enum


class Stage(str, Enum):
    S0_init = "S0_init"
    S1_design = "S1_design"
    S2_art_plan = "S2_art_plan"
    S3_art_gen = "S3_art_gen"
    S4_coding = "S4_coding"
    S5_done = "S5_done"


class StageStatus(str, Enum):
    running = "running"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    not_implemented = "not_implemented"
    done = "done"
```

- [ ] **Step 4: 写 `backend/orchestrator/machine.py`**

```python
"""状态机纯逻辑：负责阶段转移与闸判定，不直接碰数据库。调用方据返回值落库。"""
from dataclasses import dataclass
from .states import Stage, StageStatus


@dataclass
class RunState:
    id: str
    stage: Stage
    status: StageStatus


@dataclass
class Transition:
    stage: Stage
    status: StageStatus


class StateMachine:
    """S1 阶段实现 start_design/complete_design/approve/reject；其余阶段由后续计划扩展。"""

    def start_design(self, run: RunState) -> Transition:
        return Transition(Stage.S1_design, StageStatus.running)

    def complete_design(self, run: RunState) -> Transition:
        # 设计产物就绪，停在阶段闸等用户确认
        return Transition(Stage.S1_design, StageStatus.awaiting_approval)

    def approve(self, run: RunState, *, stage: Stage) -> Transition | None:
        if run.stage != stage or run.status != StageStatus.awaiting_approval:
            return None
        if stage == Stage.S1_design:
            # Art 阶段尚未实现
            return Transition(Stage.S2_art_plan, StageStatus.not_implemented)
        return None

    def reject(self, run: RunState, *, stage: Stage, feedback: str) -> Transition | None:
        if run.stage != stage or run.status != StageStatus.awaiting_approval:
            return None
        # 不通过 → 回到 design 重新跑（带反馈）
        return Transition(Stage.S1_design, StageStatus.running)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_machine.py -v
```
Expected: 5 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator backend/tests/test_machine.py
git commit -m "feat(orchestrator): stage FSM with S1 gate logic"
```

---

## Task 4: Design 输出契约 + 校验器（从交付物提炼）

**Files:**
- Create: `backend/agents/contract.py`
- Test: `backend/tests/test_contract.py`
- 读取夹具：仓库根 `game-design-spec.md`

**Interfaces:**
- Produces: `validate_game_design(md: str) -> tuple[bool, list[str]]`；`GAME_DESIGN_TEMPLATE: str`（供 Design Agent 填充的骨架）。

- [ ] **Step 1: 写失败测试 `backend/tests/test_contract.py`**

```python
"""Design 输出契约校验器测试。"""
from pathlib import Path
from agents.contract import validate_game_design, GAME_DESIGN_TEMPLATE


def _valid_doc() -> str:
    return (
        "# 我的游戏 游戏设计规格书\n\n"
        "## 0. 设计总览\n核心循环：种田→赚钱。\n\n"
        "## 1. 玩法系统A\n机制说明。\n\n"
        "## 2. 玩法系统B\n机制说明。\n\n"
        "## 3. 玩法系统C\n机制说明。\n\n"
        "## 10. 存档持久化\n字段列表。\n\n"
        "## 11. 经济平衡结论\n基准假设。\n"
    )


def test_valid_doc_passes():
    ok, reasons = validate_game_design(_valid_doc())
    assert ok, reasons


def test_missing_overview_fails():
    doc = _valid_doc().replace("## 0. 设计总览\n核心循环：种田→赚钱。\n\n", "")
    ok, reasons = validate_game_design(doc)
    assert not ok and any("总览" in r for r in reasons)


def test_missing_persist_fails():
    doc = _valid_doc().replace("## 10. 存档持久化\n字段列表。\n\n", "")
    ok, reasons = validate_game_design(doc)
    assert not ok and any("存档" in r for r in reasons)


def test_missing_economy_fails():
    doc = _valid_doc().replace("## 11. 经济平衡结论\n基准假设。\n", "")
    ok, reasons = validate_game_design(doc)
    assert not ok and any("经济" in r or "平衡" in r for r in reasons)


def test_too_few_sections_fails():
    doc = "# X 游戏设计规格书\n\n## 0. 设计总览\na\n\n## 10. 存档持久化\nb\n\n## 11. 经济平衡结论\nc\n"
    ok, reasons = validate_game_design(doc)
    assert not ok and any("玩法系统" in r for r in reasons)


def test_reference_fixture_passes():
    """顶层 game-design-spec.md（Farmer）作为测试夹具，必须通过契约校验。"""
    fixture = Path(__file__).resolve().parents[2] / "game-design-spec.md"
    ok, reasons = validate_game_design(fixture.read_text(encoding="utf-8"))
    assert ok, f"参考交付物未通过契约校验: {reasons}"


def test_template_is_markdown_with_sections():
    assert "# " in GAME_DESIGN_TEMPLATE
    assert "设计总览" in GAME_DESIGN_TEMPLATE and "存档持久化" in GAME_DESIGN_TEMPLATE
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_contract.py -v
```
Expected: FAIL（`agents.contract` 不存在）。

- [ ] **Step 3: 写 `backend/agents/contract.py`**

```python
"""Design Agent 输出契约：从顶层 game-design-spec.md 提炼的 game-design.md 必备结构 + 校验器。"""
import re

# Design Agent 填充的骨架（通用，非 Farmer 专属）
GAME_DESIGN_TEMPLATE = """# <游戏名> 游戏设计规格书

> 技术栈：HTML + JavaScript + Phaser.js，浏览器可直接运行
> 中文撰写；每个系统给出机制/数值/解锁；每节有通俗易懂的功能说明

## 0. 设计总览
核心循环：___ → 终局目标：___
时间基准 / 节奏 / 高层设定。

## 1. <系统A名>
机制流程 / 体力消耗 / 数值表 / 解锁条件。

## 2. <系统B名>
...

## N. <系统…名>
...

## 存档持久化
玩家状态 / 时间 / 农场 / NPC / 进度 等待持久化字段。

## 经济平衡结论
基准假设 / 产能 / 结论。
"""


def validate_game_design(md: str) -> tuple[bool, list[str]]:
    """校验 game-design.md 是否满足 S1 交付契约。返回 (是否通过, 原因列表)。"""
    reasons: list[str] = []
    if not md or not md.strip():
        return False, ["内容为空"]
    if not md.lstrip().startswith("# "):
        reasons.append("缺少一级标题（游戏名）")
    # 二级标题
    h2 = re.findall(r"^##\s+(.+)$", md, flags=re.MULTILINE)
    h2_text = "\n".join(h2)
    if not re.search(r"设计总览", h2_text):
        reasons.append("缺少「设计总览」章节")
    if not re.search(r"存档", h2_text):
        reasons.append("缺少「存档持久化」章节")
    if not re.search(r"经济|平衡", h2_text):
        reasons.append("缺少「经济平衡结论」章节")
    # 玩法系统章节数：去掉总览/存档/经济后，至少 3 个
    system_headings = [h for h in h2 if not re.search(r"设计总览|存档|经济|平衡", h)]
    if len(system_headings) < 3:
        reasons.append(f"玩法系统章节不足 3 个（当前 {len(system_headings)}）")
    return (len(reasons) == 0, reasons)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_contract.py -v
```
Expected: 7 PASS（含参考夹具通过）。

> 若 `test_reference_fixture_passes` 失败：说明契约与参考交付物不符，应放宽契约（而非改夹具）。检查 Farmer 文档的实际标题措辞，调整 `validate_game_design` 的正则。

- [ ] **Step 5: Commit**

```bash
git add backend/agents/contract.py backend/tests/test_contract.py
git commit -m "feat(agents): design output contract + validator (fixture-backed)"
```

---

## Task 5: Design Agent 系统提示词（brainstorming 方法论 + 输出契约）

**Files:**
- Create: `backend/agents/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Interfaces:**
- Consumes: `agents.contract.GAME_DESIGN_TEMPLATE`
- Produces: `DESIGN_SYSTEM_PROMPT: str`

- [ ] **Step 1: 写失败测试 `backend/tests/test_prompts.py`**

```python
"""系统提示词必须编码 brainstorming 方法论与输出契约。"""
from agents.prompts import DESIGN_SYSTEM_PROMPT


def test_prompt_has_methodology_rules():
    for kw in ["一次只问一个", "2-3", "方案", "推荐", "分节", "确认"]:
        assert kw in DESIGN_SYSTEM_PROMPT, f"缺方法论语: {kw}"


def test_prompt_has_output_contract():
    for kw in ["game-design.md", "设计总览", "存档持久化", "经济平衡", "中文"]:
        assert kw in DESIGN_SYSTEM_PROMPT, f"缺输出契约语: {kw}"


def test_prompt_uses_ask_user_and_write_file():
    assert "ask_user" in DESIGN_SYSTEM_PROMPT and "write_file" in DESIGN_SYSTEM_PROMPT
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_prompts.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/agents/prompts.py`**

```python
"""Design Agent 系统提示词：编码 obra/superpowers brainstorming 方法论 + 输出契约。"""
from .contract import GAME_DESIGN_TEMPLATE

DESIGN_SYSTEM_PROMPT = f"""你是一名游戏设计 Agent，负责与用户多轮问答确认游戏需求，最终产出 game-design.md。

【工作方法（brainstorming）】
1. 一次只问一个问题；能用多选就用多选（给出 2-4 个选项）。
2. 在提具体设计前，先提出 2-3 个方案，说明权衡并给出推荐。
3. 分节呈现设计，每节后请用户确认再继续。
4. 主动引导用户补全：游戏类型、核心玩法、美术风格、胜利/终局条件、时间/节奏、关键系统。
5. 需求完整后，才写文件。

【可用工具】
- ask_user(question, options)：向用户提问并阻塞等待回答。options 为字符串列表（可空表示开放题）。
- read_file(path)：读取本项目文件（如查看已有设计）。
- write_file(path, content)：将最终 game-design.md 写盘。path 必须为 docs/game-design.md。

【输出契约】
最终用 write_file 写入 docs/game-design.md，必须为中文 Markdown，且满足以下结构（参考下方模板的深度与分节，但内容针对用户选择的游戏，不要照搬 Farmer）：
- 一级标题：`# <游戏名> 游戏设计规格书`（游戏名由你在问答中确定，写入标题）。
- `## 0. 设计总览`：核心循环、终局目标、时间基准、高层设定。
- 至少 3 个 `## <玩法系统名>` 章节：每个给出机制流程、体力/代价、数值表、解锁条件、通俗易懂的功能说明。
- `## 存档持久化`：列出待持久化字段（玩家状态/时间/农场/NPC/进度）。
- `## 经济平衡结论`：基准假设、产能、结论。

【模板】
{GAME_DESIGN_TEMPLATE}

【硬性要求】
- 全程中文。
- 每个系统都要有数值表或明确数值（成熟时间、价格、体力消耗等）。
- 不确定时用 ask_user 问，不要自行编造关键数值。
- 设计完整且通过你自检后，调用 write_file 写入 docs/game-design.md，然后停止。
"""
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_prompts.py -v
```
Expected: 3 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/agents/prompts.py backend/tests/test_prompts.py
git commit -m "feat(agents): design system prompt (brainstorming + output contract)"
```

---

## Task 6: Agent 工具（read_file / write_file / ask_user）

**Files:**
- Create: `backend/agents/tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `claude_agent_sdk.tool`、`create_sdk_mcp_server`
- Produces: 纯函数 `do_read_file`/`do_write_file`/`do_ask_user`（可单测）；`build_design_tools(game_root: Path, ask: Callable[[str,list[str]|None],Awaitable[str]]) -> McpSdkServerConfig`，返回用于 `ClaudeAgentOptions.mcp_servers` 的服务配置；工具名常量 `TOOL_READ_FILE`/`TOOL_WRITE_FILE`/`TOOL_ASK_USER`。

- [ ] **Step 1: 写失败测试 `backend/tests/test_tools.py`**

```python
"""Design Agent 工具：纯函数行为 + SDK 包装可构建。"""
import asyncio
from pathlib import Path
import pytest
from agents.tools import do_read_file, do_write_file, do_ask_user, build_design_tools, TOOL_ASK_USER


@pytest.mark.asyncio
async def test_do_write_and_read_file(tmp_path):
    target = tmp_path / "docs" / "game-design.md"
    res = await do_write_file(target, "# 标题\n正文")
    assert target.read_text(encoding="utf-8") == "# 标题\n正文"
    assert res["ok"] is True
    content = await do_read_file(target)
    assert content["content"].startswith("# 标题")


@pytest.mark.asyncio
async def test_do_read_file_missing(tmp_path):
    res = await do_read_file(tmp_path / "nope.md")
    assert res["ok"] is False and "不存在" in res["error"]


@pytest.mark.asyncio
async def test_do_ask_user_returns_answer():
    async def fake_ask(question, options):
        return "模拟"
    res = await do_ask_user("类型？", ["RPG", "模拟"], ask=fake_ask)
    assert res["answer"] == "模拟"


def test_build_design_tools_returns_mcp_config(tmp_path):
    async def ask(q, o):
        return "x"
    cfg = build_design_tools(tmp_path, ask)
    # McpSdkServerConfig 是 dict 子类
    assert isinstance(cfg, dict)
    assert "tools" in cfg or "name" in cfg


def test_tool_name_constant():
    assert TOOL_ASK_USER == "ask_user"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tools.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/agents/tools.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tools.py -v
```
Expected: 5 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/agents/tools.py backend/tests/test_tools.py
git commit -m "feat(agents): design tools (read/write/ask) with SDK wrapping"
```

---

## Task 7: 权限沙箱（can_use_tool）

**Files:**
- Create: `backend/agents/permissions.py`
- Test: `backend/tests/test_permissions.py`

**Interfaces:**
- Consumes: `claude_agent_sdk.PermissionResultAllow/Deny/ToolPermissionContext`
- Produces: `make_permission_handler(game_root: Path) -> Callable[[str,dict,ToolPermissionContext],Awaitable[PermissionResultAllow|PermissionResultDeny]]`。规则：允许 `read_file`（限 game_root 内）、`ask_user`；仅允许 `write_file` 写 `game_root/docs/game-design.md`；其余 Deny。

- [ ] **Step 1: 写失败测试 `backend/tests/test_permissions.py`**

```python
"""权限沙箱：按工具与路径放行/拒绝。"""
from pathlib import Path
import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
from agents.permissions import make_permission_handler


@pytest.mark.asyncio
async def test_allow_write_game_design(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("write_file", {"path": "docs/game-design.md", "content": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultAllow)


@pytest.mark.asyncio
async def test_deny_write_outside_game_design(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("write_file", {"path": "src/main.js", "content": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)


@pytest.mark.asyncio
async def test_deny_absolute_escape(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("write_file", {"path": "../../etc/evil.md", "content": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)


@pytest.mark.asyncio
async def test_allow_read_inside(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("read_file", {"path": "docs/game-design.md"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultAllow)


@pytest.mark.asyncio
async def test_deny_read_outside(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("read_file", {"path": "../../etc/passwd"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)


@pytest.mark.asyncio
async def test_allow_ask_user(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("ask_user", {"question": "x"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultAllow)


@pytest.mark.asyncio
async def test_deny_unknown_tool(tmp_path):
    h = make_permission_handler(tmp_path)
    res = await h("bash", {"command": "rm -rf /"}, ToolPermissionContext())
    assert isinstance(res, PermissionResultDeny)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_permissions.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/agents/permissions.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_permissions.py -v
```
Expected: 7 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/agents/permissions.py backend/tests/test_permissions.py
git commit -m "feat(agents): permission sandbox for design tools"
```

---

## Task 8: 进度流 Hook（HookMatcher）

**Files:**
- Create: `backend/agents/hooks.py`
- Test: `backend/tests/test_hooks.py`

**Interfaces:**
- Consumes: `claude_agent_sdk.HookMatcher`
- Produces: `make_progress_hooks(on_progress: Callable[[dict],Awaitable[None]]) -> dict`，返回 `{"PreToolUse":[...], "PostToolUse":[...]}`，每个 hook 调用 `on_progress` 推 `{event, tool, input}`，返回 `{}` 放行。

- [ ] **Step 1: 写失败测试 `backend/tests/test_hooks.py`**

```python
"""进度流 hook：工具调用前后回调 on_progress。"""
import asyncio
import pytest
from agents.hooks import make_progress_hooks


@pytest.mark.asyncio
async def test_pre_and_post_fire():
    events = []
    async def on_progress(msg):
        events.append(msg)
    hooks = make_progress_hooks(on_progress)
    pre = hooks["PreToolUse"][0]
    post = hooks["PostToolUse"][0]
    # hook 回调签名: (input_dict, tool_use_id, ctx_dict)
    out_pre = await pre.hooks[0]({"tool_name": "write_file", "tool_input": {"path": "docs/game-design.md"}}, "tu1", {})
    out_post = await post.hooks[0]({"tool_name": "write_file", "tool_input": {}}, "tu1", {})
    assert out_pre == {} and out_post == {}
    assert events[0]["event"] == "pre" and events[0]["tool"] == "write_file"
    assert events[1]["event"] == "post" and events[1]["tool"] == "write_file"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_hooks.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/agents/hooks.py`**

```python
"""进度流 hook：把工具调用前后事件推给前端，不干预放行。"""
from typing import Awaitable, Callable
from claude_agent_sdk import HookMatcher

ProgressFn = Callable[[dict], Awaitable[None]]


def make_progress_hooks(on_progress: ProgressFn) -> dict:
    async def pre(input_dict, tool_use_id, ctx):
        await on_progress({
            "event": "pre",
            "tool": input_dict.get("tool_name"),
            "input": input_dict.get("tool_input", {}),
        })
        return {}

    async def post(input_dict, tool_use_id, ctx):
        await on_progress({
            "event": "post",
            "tool": input_dict.get("tool_name"),
        })
        return {}

    return {
        "PreToolUse": [HookMatcher(hooks=[pre])],
        "PostToolUse": [HookMatcher(hooks=[post])],
    }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_hooks.py -v
```
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/agents/hooks.py backend/tests/test_hooks.py
git commit -m "feat(agents): progress hooks via HookMatcher"
```

---

## Task 9: Design Agent 运行器（query 接线，mock 测试）

**Files:**
- Create: `backend/agents/runner.py`
- Test: `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: `claude_agent_sdk.query/ClaudeAgentOptions`、`agents.prompts`、`agents.tools.build_design_tools`、`agents.permissions.make_permission_handler`、`agents.hooks.make_progress_hooks`
- Produces: `async def run_design_agent(game_root: Path, *, ask: AskFn, on_progress: Callable[[dict],Awaitable[None]], model: str, base_url: str|None, auth_token: str|None, prompt: str) -> Path`。返回写入的 `game-design.md` 路径。

- [ ] **Step 1: 写失败测试 `backend/tests/test_runner.py`**

```python
"""Design Agent 运行器：用假 query 验证接线（不接真实 LLM）。"""
import asyncio
from pathlib import Path
import pytest
from claude_agent_sdk import ResultMessage
from agents.tools import do_write_file


@pytest.mark.asyncio
async def test_runner_writes_design_and_emits_progress(tmp_path, monkeypatch):
    import agents.runner as runner_mod

    progress = []

    async def fake_query(*, prompt, options):
        # 模拟 agent 一次完整工具往返：先 ask_user（验权限），再 write_file（验权限 + 真正落盘），
        # 再触发 Pre/Post hook 验进度流。真实 SDK 会驱动这些；fake 里手动模拟。
        await options.can_use_tool("ask_user", {"question": "类型?", "options": ["模拟"]}, None)
        write_input = {"path": "docs/game-design.md", "content": "OK"}
        await options.can_use_tool("write_file", write_input, None)
        # 模拟 MCP write_file 工具实际执行（runner 已建好 game_root/docs）
        await do_write_file(tmp_path / "docs" / "game-design.md", "OK")
        for hm in options.hooks["PreToolUse"]:
            await hm.hooks[0]({"tool_name": "write_file", "tool_input": write_input}, "tu1", {})
        for hm in options.hooks["PostToolUse"]:
            await hm.hooks[0]({"tool_name": "write_file", "tool_input": {}}, "tu1", {})
        yield ResultMessage()

    monkeypatch.setattr(runner_mod, "query", fake_query)

    async def ask(q, o):
        return "模拟"
    async def on_progress(m):
        progress.append(m)

    path = await runner_mod.run_design_agent(
        game_root=tmp_path, ask=ask, on_progress=on_progress,
        model="claude-sonnet-4-6", base_url=None, auth_token=None,
        prompt="设计一款农场游戏",
    )
    assert path.read_text(encoding="utf-8") == "OK"
    assert any(m["event"] == "pre" for m in progress)
```

> 注：真实 `query` 在 SDK 内部驱动工具循环；此处用假 async generator 触发 `can_use_tool`/hooks 以验证我们接线正确。生产路径在 Task 17 手动冒烟验证。

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runner.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/agents/runner.py`**

```python
"""Design Agent 运行器：装配 options 并驱动 claude_agent_sdk.query。"""
from pathlib import Path
from typing import Awaitable, Callable
from claude_agent_sdk import query, ClaudeAgentOptions

from .prompts import DESIGN_SYSTEM_PROMPT
from .tools import build_design_tools, TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_ASK_USER
from .permissions import make_permission_handler
from .hooks import make_progress_hooks

AskFn = Callable[[str, list[str] | None], Awaitable[str]]
ProgressFn = Callable[[dict], Awaitable[None]]


async def run_design_agent(
    game_root: Path,
    *,
    ask: AskFn,
    on_progress: ProgressFn,
    model: str,
    base_url: str | None,
    auth_token: str | None,
    prompt: str,
) -> Path:
    """运行 Design Agent，返回写入的 game-design.md 路径。"""
    game_root.mkdir(parents=True, exist_ok=True)
    (game_root / "docs").mkdir(exist_ok=True)

    mcp_server = build_design_tools(game_root, ask)
    options = ClaudeAgentOptions(
        system_prompt=DESIGN_SYSTEM_PROMPT,
        tools=[TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_ASK_USER],
        mcp_servers={"design-tools": mcp_server},
        can_use_tool=make_permission_handler(game_root),
        hooks=make_progress_hooks(on_progress),
        permission_mode="default",
        model=model,
        cwd=str(game_root),
        env={} if (base_url is None or auth_token is None) else {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": auth_token,
        },
    )

    final_path = game_root / "docs" / "game-design.md"
    async for _msg in query(prompt=prompt, options=options):
        # SDK 内部驱动工具循环；此处仅消费消息流（可在此追加 on_progress 文本推送）
        pass
    return final_path
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runner.py -v
```
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/agents/runner.py backend/tests/test_runner.py
git commit -m "feat(agents): design runner wiring claude_agent_sdk.query"
```

---

## Task 10: WS 中介（发布/订阅 + 问答 Future）

**Files:**
- Create: `backend/api/broker.py`
- Test: `backend/tests/test_broker.py`

**Interfaces:**
- Produces: `class Broker`：`subscribe(run_id) -> AsyncIterator[dict]`、`publish(run_id, msg)`、`register_question(run_id, question_id, question, options) -> asyncio.Future`、`deliver_answer(run_id, answer)`、`pending_question(run_id)`。单例 `broker`。

- [ ] **Step 1: 写失败测试 `backend/tests/test_broker.py`**

```python
"""WS 中介：订阅发布与问答 Future。"""
import asyncio
import pytest
from api.broker import Broker


@pytest.mark.asyncio
async def test_publish_subscribe():
    b = Broker()
    async def consumer():
        async for msg in b.subscribe("r1"):
            return msg
    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)  # 让订阅就绪
    b.publish("r1", {"type": "progress", "event": "pre"})
    msg = await asyncio.wait_for(task, timeout=1)
    assert msg["event"] == "pre"


@pytest.mark.asyncio
async def test_question_future_flow():
    b = Broker()
    fut = b.register_question("r1", "q1", "类型？", ["模拟"])
    assert b.pending_question("r1").question == "类型？"
    b.deliver_answer("r1", "模拟")
    answer = await asyncio.wait_for(fut, timeout=1)
    assert answer == "模拟"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_broker.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/api/broker.py`**

```python
"""WS 中介：每个 run 一个广播队列；问答用 asyncio.Future 阻塞 agent 工具直到前端回答。"""
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class Q:
    question_id: str
    question: str
    options: list


class Broker:
    def __init__(self):
        self._queues: dict[str, deque] = defaultdict(deque)
        self._waiters: dict[str, list[asyncio.Future]] = defaultdict(list)
        self._questions: dict[str, Q] = {}
        self._futures: dict[str, asyncio.Future] = {}

    async def subscribe(self, run_id: str):
        q = self._queues[run_id]
        while True:
            if q:
                yield q.popleft()
            else:
                fut: asyncio.Future = asyncio.get_event_loop().create_future()
                self._waiters[run_id].append(fut)
                await fut

    def publish(self, run_id: str, msg: dict) -> None:
        waiters = self._waiters.get(run_id, [])
        if waiters:
            waiters.pop(0).set_result(None)
        else:
            self._queues[run_id].append(msg)

    def register_question(self, run_id: str, question_id: str, question: str, options: list) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._questions[run_id] = Q(question_id, question, options)
        self._futures[run_id] = fut
        self.publish(run_id, {"type": "ask_user", "question_id": question_id, "question": question, "options": options})
        return fut

    def pending_question(self, run_id: str) -> Q | None:
        return self._questions.get(run_id)

    def deliver_answer(self, run_id: str, answer: str) -> None:
        fut = self._futures.pop(run_id, None)
        self._questions.pop(run_id, None)
        if fut is not None:
            fut.set_result(answer)


broker = Broker()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_broker.py -v
```
Expected: 2 PASS。

> 若 subscribe 测试时序抖动：在 `consumer` 前加 `await asyncio.sleep(0.01)` 确保 waiter 已注册。

- [ ] **Step 5: Commit**

```bash
git add backend/api/broker.py backend/tests/test_broker.py
git commit -m "feat(api): WS broker with pub/sub + ask_user futures"
```

---

## Task 11: FastAPI REST 路由

**Files:**
- Create: `backend/api/routes.py`, `backend/api/runtime.py`, `backend/api/deps.py`
- Test: `backend/tests/test_routes.py`

**Interfaces:**
- Consumes: `persistence`、`orchestrator.machine`、`agents.runner`、`api.broker`
- Produces: `router`（APIRouter）；`runtime.start_design(run_id, game_name, feedback=None)` 后台任务。端点：
  - `POST /api/runs` {game_name} → 建 run + 启动 design
  - `GET /api/runs` → 列表
  - `GET /api/runs/{id}` → 状态
  - `GET /api/runs/{id}/design.md` → 文件内容
  - `PUT /api/runs/{id}/design.md` {content} → 保存用户编辑
  - `POST /api/runs/{id}/approve` → 通过 S1 闸
  - `POST /api/runs/{id}/reject` {feedback} → 不通过 + 带反馈重跑
  - `POST /api/runs/{id}/answer` {answer} → 回答 ask_user

- [ ] **Step 1: 写失败测试 `backend/tests/test_routes.py`**

```python
"""REST 路由集成测试（异步 httpx + ASGITransport + sqlite，runner 被 mock）。

用异步客户端而非同步 TestClient：design agent 作为 asyncio.create_task 后台任务
运行，需要在同一事件循环里 await 让出控制权才能推进；同步 TestClient 会阻塞。
"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
import api.runtime as runtime_mod


async def _fake_run_design_agent(game_root, **kw):
    (game_root / "docs").mkdir(parents=True, exist_ok=True)
    (game_root / "docs" / "game-design.md").write_text(
        "# G 游戏设计规格书\n\n## 0. 设计总览\nx\n\n## 1. A\nx\n\n## 2. B\nx\n\n## 3. C\nx\n\n## 存档持久化\nx\n\n## 经济平衡结论\nx\n",
        encoding="utf-8",
    )
    return game_root / "docs" / "game-design.md"


async def _wait_status(c, rid, status, stage=None, timeout=50):
    for _ in range(timeout):
        st = (await c.get(f"/api/runs/{rid}")).json()
        if st["status"] == status and (stage is None or st["current_stage"] == stage):
            return st
        await asyncio.sleep(0.1)
    raise AssertionError(f"未等到 status={status}: {st}")


@pytest.mark.asyncio
async def test_create_run_and_get_design(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "run_design_agent", _fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "测试游戏"})).json()
        assert r["game_name"] == "测试游戏"
        await _wait_status(c, r["id"], "awaiting_approval", stage="S1_design")
        doc = (await c.get(f"/api/runs/{r['id']}/design.md")).json()
        assert "设计总览" in doc["content"]


@pytest.mark.asyncio
async def test_approve_advances(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "run_design_agent", _fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "G2"})).json()
        await _wait_status(c, r["id"], "awaiting_approval")
        ap = await c.post(f"/api/runs/{r['id']}/approve")
        assert ap.status_code == 200
        st = (await c.get(f"/api/runs/{r['id']}")).json()
        assert st["current_stage"] == "S2_art_plan" and st["status"] == "not_implemented"


@pytest.mark.asyncio
async def test_reject_reruns(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_mod, "run_design_agent", _fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "G3"})).json()
        await _wait_status(c, r["id"], "awaiting_approval")
        rj = await c.post(f"/api/runs/{r['id']}/reject", json={"feedback": "加钓鱼"})
        assert rj.status_code == 200
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_routes.py -v
```
Expected: FAIL（`api.main`/`api.routes` 未创建）。

- [ ] **Step 3: 写 `backend/api/deps.py`**

```python
"""依赖注入：DB 会话工厂、Games 根目录、配置。"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
DESIGN_MODEL = os.getenv("DESIGN_MODEL", "claude-sonnet-4-6")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN")

_games_root: Path = Path(os.getenv("GAMES_ROOT", "../Games")).resolve()


def set_games_root(p: Path) -> None:
    global _games_root
    _games_root = p.resolve()


def games_root() -> Path:
    return _games_root


# in-memory sqlite 需 StaticPool 让多连接共享同一库（测试稳定）
if DATABASE_URL.startswith("sqlite"):
    _engine = create_async_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
else:
    _engine = create_async_engine(DATABASE_URL, future=True)

_session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with _session_factory() as session:
        yield session
```

- [ ] **Step 4: 写 `backend/api/runtime.py`**

```python
"""后台 agent 任务管理：启动 Design Agent 并把进度/问答接到 broker。"""
import re
from api.broker import broker
from api.deps import DESIGN_MODEL, BASE_URL, AUTH_TOKEN, games_root, _session_factory
from persistence.repo import update_stage, create_approval
from orchestrator.states import Stage, StageStatus
from agents.runner import run_design_agent

__all__ = ["start_design"]


def _slug(name: str) -> str:
    s = re.sub(r"[^\w一-龥]+", "-", name.strip().lower()).strip("-")
    return s or "game"


async def start_design(run_id: str, game_name: str, *, feedback: str | None = None) -> None:
    """启动 Design Agent；完成后把阶段置为 awaiting_approval 并创建待审批。"""
    game_root = games_root() / _slug(game_name)
    prompt = f"请为游戏《{game_name}》进行需求确认。" + (
        f"\n用户对上一版设计的反馈：{feedback}\n请据此修改。" if feedback else ""
    )

    async def ask(question, options):
        return await broker.register_question(run_id, "q", question, options or [])

    async def on_progress(msg):
        broker.publish(run_id, {"type": "progress", **msg})

    try:
        await run_design_agent(
            game_root, ask=ask, on_progress=on_progress,
            model=DESIGN_MODEL, base_url=BASE_URL, auth_token=AUTH_TOKEN, prompt=prompt,
        )
        async with _session_factory() as session:
            await update_stage(session, run_id, stage=Stage.S1_design.value, status=StageStatus.awaiting_approval.value)
            await create_approval(session, run_id, stage=Stage.S1_design.value, payload={"doc": "docs/game-design.md"})
        broker.publish(run_id, {"type": "gate", "stage": "S1_design", "status": "awaiting_approval"})
    except Exception as e:
        broker.publish(run_id, {"type": "error", "message": str(e)})
        raise
```

> 注：`run_design_agent` 是模块级 import，测试用 `monkeypatch.setattr(runtime_mod, "run_design_agent", ...)` 替换即可，无需接真实 LLM。

- [ ] **Step 5: 写 `backend/api/routes.py`**

```python
"""REST 路由：run 管理、设计文档读写、阶段闸、问答回答。"""
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, games_root, _session_factory
from api.broker import broker
from api.runtime import start_design
from persistence.repo import create_run, get_run, list_runs, update_stage, get_pending_approval, resolve_approval
from orchestrator.states import Stage, StageStatus
from orchestrator.machine import StateMachine, RunState

router = APIRouter(prefix="/api")
sm = StateMachine()


def _slug(name: str) -> str:
    import re
    s = re.sub(r"[^\w一-龥]+", "-", name.strip().lower()).strip("-")
    return s or "game"


@router.post("/runs")
async def create_run_endpoint(payload: dict, session: AsyncSession = Depends(get_session)):
    game_name = payload["game_name"]
    slug = _slug(game_name)
    run = await create_run(session, game_name=game_name, slug=slug)
    # 启动 design agent 后台任务
    asyncio.create_task(start_design(run.id, game_name))
    return {"id": run.id, "game_name": run.game_name, "current_stage": run.current_stage, "status": run.status}


@router.get("/runs")
async def list_runs_endpoint(session: AsyncSession = Depends(get_session)):
    runs = await list_runs(session)
    return [{"id": r.id, "game_name": r.game_name, "current_stage": r.current_stage, "status": r.status} for r in runs]


@router.get("/runs/{run_id}")
async def get_run_endpoint(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {"id": run.id, "game_name": run.game_name, "current_stage": run.current_stage, "status": run.status}


@router.get("/runs/{run_id}/design.md")
async def get_design(run_id: str):
    run = await _load_run(run_id)
    p = games_root() / run.slug / "docs" / "game-design.md"
    if not p.exists():
        raise HTTPException(404, "design not ready")
    return {"content": p.read_text(encoding="utf-8")}


@router.put("/runs/{run_id}/design.md")
async def put_design(run_id: str, payload: dict):
    run = await _load_run(run_id)
    p = games_root() / run.slug / "docs" / "game-design.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(payload["content"], encoding="utf-8")
    return {"ok": True}


@router.post("/runs/{run_id}/approve")
async def approve(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    t = sm.approve(RunState(run.id, Stage(run.current_stage), StageStatus(run.status)), stage=Stage.S1_design)
    if t is None:
        raise HTTPException(409, "当前状态不可通过")
    await update_stage(session, run_id, stage=t.stage.value, status=t.status.value)
    ap = await get_pending_approval(session, run_id, stage=Stage.S1_design.value)
    if ap:
        await resolve_approval(session, ap.id, resolution="approved", feedback=None)
    broker.publish(run_id, {"type": "gate", "stage": t.stage.value, "status": "approved"})
    return {"ok": True, "current_stage": t.stage.value, "status": t.status.value}


@router.post("/runs/{run_id}/reject")
async def reject(run_id: str, payload: dict):
    feedback = payload.get("feedback", "")
    run = await _load_run(run_id)
    # 状态回到 design running，带反馈重跑
    async with _session_factory() as session:
        await update_stage(session, run_id, stage=Stage.S1_design.value, status=StageStatus.running.value)
        ap = await get_pending_approval(session, run_id, stage=Stage.S1_design.value)
        if ap:
            await resolve_approval(session, ap.id, resolution="rejected", feedback=feedback)
    asyncio.create_task(start_design(run.id, run.game_name, feedback=feedback))
    return {"ok": True}


@router.post("/runs/{run_id}/answer")
async def answer(run_id: str, payload: dict):
    broker.deliver_answer(run_id, payload["answer"])
    return {"ok": True}


async def _load_run(run_id: str):
    async with _session_factory() as session:
        run = await get_run(session, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_routes.py -v
```
Expected: 3 PASS。

> 若 `_wait_status` 超时：确认 `_fake_run_design_agent` 已被 monkeypatch 命中、`set_games_root(tmp_path)` 已调用、sqlite 用了 StaticPool（Task 11 Step 3）使建 run 与后台任务读写同一库。

- [ ] **Step 7: Commit**

```bash
git add backend/api/routes.py backend/api/runtime.py backend/api/deps.py backend/tests/test_routes.py
git commit -m "feat(api): REST routes for runs, design doc, gate, answers"
```

---

## Task 12: FastAPI WS 端点 + app 装配

**Files:**
- Create: `backend/api/ws.py`, `backend/api/main.py`
- Test: `backend/tests/test_ws.py`

**Interfaces:**
- Produces: `app`（FastAPI，含 lifespan 建表、CORS、挂载 router 与 ws）、`set_games_root(p)`。

- [ ] **Step 1: 写失败测试 `backend/tests/test_ws.py`**

```python
"""WS 端点：订阅进度流。"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from api.broker import broker


@pytest.mark.asyncio
async def test_ws_receives_published_message(monkeypatch, tmp_path):
    async def fake_run_design_agent(game_root, **kw):
        await asyncio.sleep(0)  # 不做实事，仅占位
        return game_root / "docs" / "game-design.md"
    import api.runtime as runtime_mod
    monkeypatch.setattr(runtime_mod, "run_design_agent", fake_run_design_agent)
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        with c.websocket_connect("/api/ws/test-run") as ws:
            broker.publish("test-run", {"type": "progress", "event": "pre"})
            msg = ws.receive_json()
            assert msg["type"] == "progress"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_ws.py -v
```
Expected: FAIL。

- [ ] **Step 3: 写 `backend/api/ws.py`**

```python
"""WebSocket 端点：把 broker 的进度流转发给前端。"""
import asyncio
from fastapi import APIRouter, WebSocket
from api.broker import broker

router = APIRouter()


@router.websocket("/api/ws/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    try:
        async for msg in broker.subscribe(run_id):
            await websocket.send_json(msg)
    except Exception:
        pass
    finally:
        await websocket.close()
```

- [ ] **Step 4: 写 `backend/api/main.py`**

```python
"""FastAPI 装配：lifespan 建表、CORS、挂 REST 与 WS。"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import _engine
from persistence.db import init_db
from api.routes import router as rest_router
from api.ws import router as ws_router


def set_games_root(p: Path) -> None:
    from api import deps
    deps.set_games_root(p)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(_engine)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(rest_router)
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"ok": True}
```

> 注：`deps.py` 已在 import 时用 StaticPool 构造 `_engine`/`_session_factory`（见 Task 11 Step 3），`main` 在 lifespan 调 `init_db(_engine)` 建表即可。测试默认用 in-memory sqlite，StaticPool 保证多连接共享同一库。

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_ws.py tests/test_routes.py -v
```
Expected: PASS。

- [ ] **Step 6: 全量后端测试**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -v
```
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add backend/api/ws.py backend/api/main.py backend/api/deps.py backend/tests/test_ws.py
git commit -m "feat(api): websocket endpoint + app assembly + db lifespan"
```

---

## Task 13: 前端骨架 + 类型 + API/WS 客户端

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/types.ts`, `frontend/src/api/client.ts`
- Test: `frontend/src/__tests__/client.test.ts`

**Interfaces:**
- Produces: `client.ts` 导出 `createRun/getRun/listRuns/getDesign/putDesign/approveRun/rejectRun/answerQuestion` 与 `connectWS(runId, onMsg)`。

- [ ] **Step 1: 初始化前端**

```bash
cd "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-markdown remark-gfm
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @vitest/ui
```

- [ ] **Step 2: 写 `frontend/vite.config.ts`**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/setup.ts'] },
})
```

- [ ] **Step 3: 写 `frontend/src/setup.ts`**

```ts
import '@testing-library/jest-dom'
```

- [ ] **Step 4: 写 `frontend/src/types.ts`**

```ts
export interface Run { id: string; game_name: string; current_stage: string; status: string }
export interface ProgressMsg { type: 'progress' | 'gate' | 'ask_user' | 'error'; [k: string]: any }
```

- [ ] **Step 5: 写失败测试 `frontend/src/__tests__/client.test.ts`**

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRun, getDesign, approveRun } from '../api/client'

describe('api client', () => {
  beforeEach(() => { (global as any).fetch = vi.fn() })

  it('createRun posts and returns run', async () => {
    ;(global as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ id: 'r1', game_name: 'G', current_stage: 'S1_design', status: 'running' }) })
    const r = await createRun('G')
    expect(r.id).toBe('r1')
  })

  it('getDesign returns content', async () => {
    ;(global as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ content: '# hi' }) })
    const d = await getDesign('r1')
    expect(d).toBe('# hi')
  })

  it('approveRun posts', async () => {
    ;(global as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const r = await approveRun('r1')
    expect(r.ok).toBe(true)
  })
})
```

- [ ] **Step 6: 运行测试，确认失败**

```bash
cd frontend && npx vitest run src/__tests__/client.test.ts
```
Expected: FAIL。

- [ ] **Step 7: 写 `frontend/src/api/client.ts`**

```ts
import type { Run, ProgressMsg } from '../types'

const BASE = '/api'

async function j(r: Response) { if (!r.ok) throw new Error(await r.text()); return r.json() }

export async function createRun(gameName: string): Promise<Run> {
  return j(await fetch(`${BASE}/runs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ game_name: gameName }) }))
}
export async function listRuns(): Promise<Run[]> { return j(await fetch(`${BASE}/runs`)) }
export async function getRun(id: string): Promise<Run> { return j(await fetch(`${BASE}/runs/${id}`)) }
export async function getDesign(id: string): Promise<string> { return (await j(await fetch(`${BASE}/runs/${id}/design.md`))).content }
export async function putDesign(id: string, content: string): Promise<void> { await j(await fetch(`${BASE}/runs/${id}/design.md`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) })) }
export async function approveRun(id: string) { return j(await fetch(`${BASE}/runs/${id}/approve`, { method: 'POST' })) }
export async function rejectRun(id: string, feedback: string) { return j(await fetch(`${BASE}/runs/${id}/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ feedback }) })) }
export async function answerQuestion(id: string, answer: string) { return j(await fetch(`${BASE}/runs/${id}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer }) })) }

export function connectWS(runId: string, onMsg: (m: ProgressMsg) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}${BASE}/ws/${runId}`)
  ws.onmessage = (e) => onMsg(JSON.parse(e.data))
  return ws
}
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
cd frontend && npx vitest run src/__tests__/client.test.ts
```
Expected: PASS。

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold + types + api/ws client"
```

---

## Task 14: ProgressBar + ProgressStream 组件

**Files:**
- Create: `frontend/src/components/ProgressBar.tsx`, `frontend/src/components/ProgressStream.tsx`
- Test: `frontend/src/__tests__/components.test.tsx`

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/components.test.tsx`:
```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressBar } from '../components/ProgressBar'
import { ProgressStream } from '../components/ProgressStream'

describe('ProgressBar', () => {
  it('highlights current stage', () => {
    render(<ProgressBar current="S1_design" />)
    expect(screen.getByText('设计')).toHaveClass('active')
    expect(screen.getByText('美术清单')).not.toHaveClass('active')
  })
})

describe('ProgressStream', () => {
  it('lists messages', () => {
    render(<ProgressStream messages={[{ type: 'progress', event: 'pre', tool: 'write_file' }]} />)
    expect(screen.getByText(/write_file/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && npx vitest run src/__tests__/components.test.tsx
```
Expected: FAIL。

- [ ] **Step 3: 写 `frontend/src/components/ProgressBar.tsx`**

```tsx
const STAGES = [
  { id: 'S1_design', label: '设计' },
  { id: 'S2_art_plan', label: '美术清单' },
  { id: 'S3_art_gen', label: '素材生成' },
  { id: 'S4_coding', label: '代码' },
  { id: 'S5_done', label: '完成' },
]

export function ProgressBar({ current }: { current: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: 8 }}>
      {STAGES.map(s => (
        <div key={s.id} className={s.id === current ? 'active' : ''} style={{ padding: '4px 10px', border: '1px solid #ccc', borderRadius: 4, background: s.id === current ? '#def' : '#fff' }}>
          {s.label}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: 写 `frontend/src/components/ProgressStream.tsx`**

```tsx
import type { ProgressMsg } from '../types'

export function ProgressStream({ messages }: { messages: ProgressMsg[] }) {
  return (
    <div style={{ height: 160, overflow: 'auto', border: '1px solid #eee', padding: 8, fontFamily: 'monospace', fontSize: 12 }}>
      {messages.map((m, i) => (
        <div key={i}>{m.type === 'progress' ? `[${m.event}] ${m.tool}` : JSON.stringify(m)}</div>
      ))}
    </div>
  )
}
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd frontend && npx vitest run src/__tests__/components.test.tsx
```
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components frontend/src/__tests__/components.test.tsx
git commit -m "feat(frontend): ProgressBar + ProgressStream"
```

---

## Task 15: MarkdownEditor + QAPanel 组件

**Files:**
- Create: `frontend/src/components/MarkdownEditor.tsx`, `frontend/src/components/QAPanel.tsx`
- Test: `frontend/src/__tests__/editor_qa.test.tsx`

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/editor_qa.test.tsx`:
```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MarkdownEditor } from '../components/MarkdownEditor'
import { QAPanel } from '../components/QAPanel'

describe('MarkdownEditor', () => {
  it('edits and saves', () => {
    const onSave = vi.fn()
    render(<MarkdownEditor content="# hi" onSave={onSave} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '# bye' } })
    fireEvent.click(screen.getByText('保存'))
    expect(onSave).toHaveBeenCalledWith('# bye')
  })
})

describe('QAPanel', () => {
  it('renders question and submits answer', () => {
    const onAnswer = vi.fn()
    render(<QAPanel question="游戏类型？" options={['RPG', '模拟']} onAnswer={onAnswer} />)
    fireEvent.click(screen.getByText('模拟'))
    expect(onAnswer).toHaveBeenCalledWith('模拟')
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && npx vitest run src/__tests__/editor_qa.test.tsx
```
Expected: FAIL。

- [ ] **Step 3: 写 `frontend/src/components/MarkdownEditor.tsx`**

```tsx
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function MarkdownEditor({ content, onSave }: { content: string; onSave: (c: string) => void }) {
  const [text, setText] = useState(content)
  return (
    <div style={{ display: 'flex', gap: 8, height: 400 }}>
      <textarea role="textbox" value={text} onChange={e => setText(e.target.value)} style={{ flex: 1 }} />
      <div style={{ flex: 1, overflow: 'auto', border: '1px solid #eee', padding: 8 }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      </div>
      <button onClick={() => onSave(text)}>保存</button>
    </div>
  )
}
```

- [ ] **Step 4: 写 `frontend/src/components/QAPanel.tsx`**

```tsx
export function QAPanel({ question, options, onAnswer }: { question: string; options: string[]; onAnswer: (a: string) => void }) {
  return (
    <div style={{ border: '1px solid #ccf', padding: 12, margin: '8px 0' }}>
      <div style={{ fontWeight: 600 }}>{question}</div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        {options.map(o => (
          <button key={o} onClick={() => onAnswer(o)}>{o}</button>
        ))}
        {options.length === 0 && <input placeholder="输入回答" onKeyDown={e => { if (e.key === 'Enter') onAnswer((e.target as HTMLInputElement).value) }} />}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd frontend && npx vitest run src/__tests__/editor_qa.test.tsx
```
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components frontend/src/__tests__/editor_qa.test.tsx
git commit -m "feat(frontend): MarkdownEditor + QAPanel"
```

---

## Task 16: DesignWorkbench + App 装配

**Files:**
- Create: `frontend/src/stages/DesignWorkbench.tsx`, modify `frontend/src/App.tsx`, `frontend/src/main.tsx`
- Test: `frontend/src/__tests__/design_workbench.test.tsx`

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/design_workbench.test.tsx`:
```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DesignWorkbench } from '../stages/DesignWorkbench'

vi.mock('../api/client', () => ({
  getDesign: vi.fn().mockResolvedValue('# 设计\n## 0. 设计总览\nx'),
  putDesign: vi.fn().mockResolvedValue(undefined),
  approveRun: vi.fn().mockResolvedValue({ ok: true }),
  rejectRun: vi.fn().mockResolvedValue({ ok: true }),
  answerQuestion: vi.fn().mockResolvedValue({ ok: true }),
  connectWS: vi.fn(() => ({ close: vi.fn(), onmessage: null })),
}))

describe('DesignWorkbench', () => {
  it('loads design and shows approve/reject', async () => {
    render(<DesignWorkbench runId="r1" status="awaiting_approval" />)
    await waitFor(() => expect(screen.getByText(/设计总览/)).toBeInTheDocument())
    expect(screen.getByText('通过')).toBeInTheDocument()
    expect(screen.getByText('不通过')).toBeInTheDocument()
  })

  it('clicking approve calls approveRun', async () => {
    const { approveRun } = await import('../api/client')
    render(<DesignWorkbench runId="r1" status="awaiting_approval" />)
    await waitFor(() => screen.getByText('通过'))
    fireEvent.click(screen.getByText('通过'))
    await waitFor(() => expect(approveRun).toHaveBeenCalledWith('r1'))
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && npx vitest run src/__tests__/design_workbench.test.tsx
```
Expected: FAIL。

- [ ] **Step 3: 写 `frontend/src/stages/DesignWorkbench.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { getDesign, putDesign, approveRun, rejectRun, answerQuestion, connectWS } from '../api/client'
import { MarkdownEditor } from '../components/MarkdownEditor'
import { QAPanel } from '../components/QAPanel'
import type { ProgressMsg } from '../types'

export function DesignWorkbench({ runId, status }: { runId: string; status: string }) {
  const [content, setContent] = useState('')
  const [messages, setMessages] = useState<ProgressMsg[]>([])
  const [question, setQuestion] = useState<{ question: string; options: string[] } | null>(null)

  useEffect(() => {
    getDesign(runId).then(setContent).catch(() => {})
    const ws = connectWS(runId, (m) => {
      setMessages(prev => [...prev, m])
      if (m.type === 'ask_user') setQuestion({ question: m.question, options: m.options || [] })
    })
    return () => ws.close()
  }, [runId])

  return (
    <div style={{ padding: 12 }}>
      {question && (
        <QAPanel question={question.question} options={question.options}
          onAnswer={(a) => { answerQuestion(runId, a); setQuestion(null) }} />
      )}
      <MarkdownEditor content={content} onSave={(c) => { setContent(c); putDesign(runId, c) }} />
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

- [ ] **Step 4: 写 `frontend/src/App.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { ProgressBar } from './components/ProgressBar'
import { ProgressStream } from './components/ProgressStream'
import { DesignWorkbench } from './stages/DesignWorkbench'
import { createRun, getRun, listRuns } from './api/client'
import type { Run, ProgressMsg } from './types'

export default function App() {
  const [run, setRun] = useState<Run | null>(null)
  const [name, setName] = useState('')
  const [messages, setMessages] = useState<ProgressMsg[]>([])

  return (
    <div style={{ fontFamily: 'sans-serif' }}>
      <ProgressBar current={run?.current_stage || 'S1_design'} />
      {!run ? (
        <div style={{ padding: 12 }}>
          <input placeholder="游戏名" value={name} onChange={e => setName(e.target.value)} />
          <button onClick={async () => { const r = await createRun(name); setRun(r) }}>开始设计</button>
        </div>
      ) : (
        <DesignWorkbench runId={run.id} status={run.status} />
      )}
      <ProgressStream messages={messages} />
    </div>
  )
}
```

- [ ] **Step 5: 写 `frontend/src/main.tsx`**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
cd frontend && npx vitest run src/__tests__/design_workbench.test.tsx
```
Expected: PASS。

- [ ] **Step 7: 构建冒烟**

```bash
cd frontend && npm run build
```
Expected: 构建成功（`dist/` 生成）。

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): DesignWorkbench + App assembly"
```

---

## Task 17: 端到端 S1 冒烟 + 自检清单

**Files:**
- Modify: 无（验证为主）
- Create: `backend/tests/test_e2e_s1.py`（mock LLM 的全链路集成测试）

- [ ] **Step 1: 写端到端集成测试 `backend/tests/test_e2e_s1.py`**

```python
"""S1 端到端：mock LLM（假 query），验证 建run→问答→写设计→闸→通过→S2。"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_s1_full_flow(monkeypatch, tmp_path):
    from claude_agent_sdk import ResultMessage
    from agents.tools import do_write_file
    from api.runtime import _slug
    import agents.runner as runner_mod

    game_root = tmp_path / _slug("测试游戏")

    async def fake_query(*, prompt, options):
        # 1) agent 问一个问题（仅走权限校验；真实问答环路见 Task 10/11 的 broker 测试）
        await options.can_use_tool("ask_user", {"question": "类型?", "options": ["模拟"]}, None)
        # 2) agent 写设计文件：先过权限沙箱，再真正落盘（runner 已建好 game_root/docs）
        md = ("# 测试游戏 游戏设计规格书\n\n## 0. 设计总览\n核心循环。\n\n"
              "## 1. 系统A\n机制。\n\n## 2. 系统B\n机制。\n\n## 3. 系统C\n机制。\n\n"
              "## 存档持久化\n字段。\n\n## 经济平衡结论\n结论。\n")
        await options.can_use_tool("write_file", {"path": "docs/game-design.md", "content": md}, None)
        await do_write_file(game_root / "docs" / "game-design.md", md)
        # SDK 0.2.125 的 ResultMessage 需要 6 个位置参数；runner 忽略 yield 的消息
        yield ResultMessage("result", 0, 0, False, 1, "test-session")

    monkeypatch.setattr(runner_mod, "query", fake_query)

    from api.main import app, set_games_root
    set_games_root(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.post("/api/runs", json={"game_name": "测试游戏"})).json()
        rid = r["id"]
        # 等到闸
        for _ in range(50):
            st = (await c.get(f"/api/runs/{rid}")).json()
            if st["status"] == "awaiting_approval":
                break
            await asyncio.sleep(0.1)
        assert st["status"] == "awaiting_approval"
        doc = (await c.get(f"/api/runs/{rid}/design.md")).json()["content"]
        assert "设计总览" in doc and "存档持久化" in doc
        # 通过闸 → S2 not_implemented
        await c.post(f"/api/runs/{rid}/approve")
        st2 = (await c.get(f"/api/runs/{rid}")).json()
        assert st2["current_stage"] == "S2_art_plan" and st2["status"] == "not_implemented"
```

- [ ] **Step 2: 运行全量测试**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -v
cd ../frontend && npx vitest run
```
Expected: 全绿（后端 + 前端）。

- [ ] **Step 3: 手动冒烟（可选，接真实自部署端点）**

> 用户已声明不手动测试 S1；此步仅当需要验证真实 LLM 链路时执行。

```bash
# 1) 配置 backend/.env（填 ANTHROPIC_BASE_URL/AUTH_TOKEN、DATABASE_URL）
# 2) 建库：CREATE DATABASE agent_game CHARACTER SET utf8mb4;
# 3) 启后端
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m uvicorn api.main:app --reload --port 8000
# 4) 启前端
cd frontend && npm run dev
# 5) 浏览器 http://127.0.0.1:5173 → 输入游戏名 → 在问答面板回答 → 等 design.md → 通过
```

- [ ] **Step 4: 自检清单（verification-before-completion）**

- [ ] 后端全量 pytest 通过
- [ ] 前端 vitest 全通过 + `npm run build` 成功
- [ ] `test_reference_fixture_passes` 通过（契约与顶层 game-design-spec.md 一致）
- [ ] 权限沙箱：write_file 仅允许 docs/game-design.md（7 个用例）
- [ ] 状态机：S1 闸 approve→S2 not_implemented、reject→revising
- [ ] WS 进度流 + ask_user 问答闭环
- [ ] 无占位符/TODO；所有 SDK 调用用已内省确认的 0.2.125 API

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_e2e_s1.py
git commit -m "test: S1 end-to-end flow with mocked LLM"
```

---

## Self-Review（plan 作者自检）

**1. Spec 覆盖**：本计划覆盖 S1 design 阶段的全部后端（orchestrator+persistence+agent runner+api+ws）与前端（S1 工作台）——即 `agent-system-design.md` §0.2 的 S1、§1 的 Design Agent 角色+权限、§2 checkpoint（MySQL）、§3 前端 S1 工作台。Art/S3/Coding 不在本计划（后续计划）。✔

**2. 占位符扫描**：无 TBD/TODO。`runtime.py`/`deps.py` 各为单一干净版本（已消除早期草稿与占位）。✔

**3. 类型一致性**：`Stage`/`StageStatus`、`RunState`/`Transition`、`AskFn`/`ProgressFn`、broker 接口、REST 路径在跨任务中一致。✔

**4. 已知实现注意点**：
- `deps.py` 的 sqlite 用 `StaticPool` 共享库（Task 11 Step 3），保证 in-memory 测试多连接一致。
- 后台 design agent 用 `asyncio.create_task`；集成测试统一用 `httpx.AsyncClient` + `ASGITransport`（Task 11/17），让 `await` 让出控制权使后台任务推进——不要用同步 `TestClient`。
- 真实 `query` 的消息块（TextBlock/ToolUseBlock）访问器在 Task 9 不依赖（SDK 内部驱动工具循环）；如需向前端推文本，可在 runner 的 `async for` 里按 `getattr(msg,'content',None)` 解析——此为可选增强，不阻塞 S1。
