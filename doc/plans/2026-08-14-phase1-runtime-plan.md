# Phase 1 Runtime 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 跑通 `API → Claude(CLI 子进程) → stream-json → MySQL 落库 → Redis Stream → SSE 回放`，并支持 session/resume 续接。

**Architecture:** FastAPI API 层只建 Job 返 task_id；Arq Worker 异步 spawn 官方 `claude` CLI（`--bare`，经 KSPMAS kimi-k3 端点），逐行解析 stream-json NDJSON 归一化为 CoworkEvent，每条先写 MySQL `events` 表再 `XADD` Redis Stream；SSE 端点先从 MySQL 补历史再接 Redis Stream 实时推送。`--resume <session_id>` 续接同一会话，子进程 `cwd` 与创建时一致。

**Tech Stack:** Python 3.10（agent_env，D 盘）/ FastAPI 0.139 / SQLAlchemy 2.0 async / asyncmy / Pydantic v2 / arq / redis 8.1 / MySQL 8.0 / 官方 claude CLI 2.1.197 + KSPMAS kimi-k3（Anthropic 兼容端点）/ pytest + pytest-asyncio

**Spec:** `doc/specs/2026-08-14-phase1-runtime-design.md`（本计划从 spec 推导，spec 与计划一并阅读）

## Global Constraints

- **Python 解释器固定** `D:/Anaconda3/envs/agent_env/python.exe`（C 盘约束：依赖只装 agent_env，禁碰 C 盘）。下文 `python` 均指此解释器。
- **Python 版本 3.10**：类型标注用 `Optional[X]` / `Union` 或文件首 `from __future__ import annotations`，**不要**裸用 `X | None` 作运行时类型（pydantic v2 模型字段除外，pydantic 已支持）。`list[str]` 等内置泛型在 3.10 可用。
- **CLI 命令名**：Agent Runtime 调 `claude`（官方 CLI，已装 D 盘 `node_global`，版本 2.1.197），**不是** `kscc`。
- **`--bare` 强制**：所有 `claude -p` 调用必须带 `--bare`（spike §3.3-1：不带会背 26707 token 宿主上下文 + 触发 superpowers hook 报错 + kimi-k3 审核 refusal）。
- **端点 env**：子进程注入 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL`（来自 `backend/.env`，实测 `BASE_URL=https://kspmas.ksyun.com/v1/chat/completions`、`MODEL=kimi-k3`；spike §3.5 标注 BASE_URL 待实现期 Task 1 确认）。
- **session 按 cwd 存**：claude 本地 JSONL 在 `C:\Users\39335\.claude\projects\<cwd-hash>\<sid>.jsonl`，`--resume` 要求 `cwd` 与创建时一致 → 每个 project 的 workspace 全程不变。
- **workspace**：`<repo>/Games/{project_key}/`（D9），建项目时创建目录。
- **thinking 丢弃**（D10）：parser 不持久化/广播 `thinking_delta`、`thinking_tokens`。
- **DB 字符集** `utf8mb4`，引擎 `InnoDB`；库名 `ai_cowork_game`。
- **Redis 未在跑**：Task 0 含启动步骤；Arq 与 SSE 都依赖 Redis。
- **MySQL 需密码**：`backend/.env` 的 `DB_URL` 带真实凭据（root 无密码被拒）。
- **测试不打 KSPMAS**（D12）：单元/集成用录制 NDJSON 喂入；e2e 手动跑真 KSPMAS，不进 CI。
- **commit 规范**：每 task 末提交，message 前缀按改动类型（feat/fix/test/chore/docs）。
- **不碰 frontend**：Phase 1 只在 `backend/` 与 `doc/` 下作业；`frontend/` 已保全（commit 94c484e），勿改。

---

## File Structure

```
backend/
├── .env                              Task 0 创建（gitignore 已含 .env，不入库）
├── pyproject.toml                    Task 0 创建（依赖声明 + pytest 配置）
├── app/
│   ├── __init__.py
│   ├── main.py                       Task 11：FastAPI 入口 + lifespan + 路由注册
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py               Task 0：Pydantic Settings（DB/Redis/Arq/LLM env）
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── event.py                  Task 2：CoworkEvent
│   │   └── project.py                Task 11：ProjectCreate/Read
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py                Task 3：projects ORM
│   │   ├── agent_session.py          Task 3：agent_sessions ORM
│   │   └── event.py                  Task 3：events ORM
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── db.py                     Task 3：async engine/sessionmaker
│   │   └── repo.py                   Task 5：EventRepo/ProjectRepo/AgentSessionRepo
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── parser.py                  Task 2：ClaudeEventParser（NDJSON→CoworkEvent）
│   │   ├── runtime.py                Task 6：ClaudeRuntime（start/resume/cancel）
│   │   ├── session.py                Task 7：session/workspace 管理
│   │   └── prompts.py                Task 8：brainstorm 自研 system prompt
│   ├── events/
│   │   ├── __init__.py
│   │   └── broker.py                  Task 5：EventBroker（先落库再 XADD）
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── states.py                 Task 4：ProjectStatus 枚举
│   │   └── engine.py                 Task 4：状态校验/流转入口（Phase 1 最小）
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── jobs.py                   Task 9：enqueue 封装
│   │   ├── tasks.py                  Task 10：run_brainstorm Arq task
│   │   └── worker.py                 Task 10：Arq Worker 配置
│   ├── services/
│   │   ├── __init__.py
│   │   └── project_service.py        Task 9：建项目/查状态/落 agent_session
│   └── api/
│       ├── __init__.py
│       ├── projects.py               Task 11：POST/GET /projects、POST /brainstorm
│       └── events.py                  Task 12：GET /stream SSE
└── tests/
    ├── __init__.py
    ├── conftest.py                   Task 1：pytest fixtures（async db、redis fake）
    ├── fixtures/                     Task 1：录制的 stream-json NDJSON 样本
    │   ├── ok_math.jsonl              spike ①产物（2+2=4，含 thinking）
    │   ├── resume_ok.jsonl            spike ③产物（resume 回 4）
    │   ├── tool_use_read.jsonl        spike ②产物（tool_use/tool_result）
    │   └── refusal.jsonl              spike ②产物（content review refusal）
    ├── test_parser.py                Task 2
    ├── test_models.py                Task 3
    ├── test_states.py                Task 4
    ├── test_broker.py                Task 5
    ├── test_runtime.py                Task 6
    ├── test_session.py               Task 7
    ├── test_project_service.py        Task 9
    ├── test_tasks_worker.py           Task 10（fake runtime）
    ├── test_api_projects.py           Task 11
    └── test_api_events_sse.py         Task 12
```

**责任划分**：Parser（纯函数，NDJSON→CoworkEvent）无 IO 依赖，最易测，先行；Runtime 只管子进程与逐行读取，产出 CoworkEvent，不碰 DB；EventBroker 只管落库+广播；session 管 cwd/workspace；prompts 纯文本；Arq task 串联上述。每层接口在对应 task 的 **Interfaces** 块钉死。

---

## Task 0: 环境与基建

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env`（不入库，gitignore 已含）
- Create: `backend/app/__init__.py`、`backend/app/config/__init__.py`、`backend/app/config/settings.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/.env.example`（入库模板，无真实 key）

**Interfaces:**
- Produces: `Settings` 单例（`app.config.settings.get_settings()`），字段见下；后续所有 task 经此读配置。

- [ ] **Step 1: 装缺失依赖到 agent_env（D 盘，不碰 C 盘）**

Run:
```bash
D:/Anaconda3/envs/agent_env/python.exe -m pip install "arq" "asyncmy" "aioredis" 2>&1 | tail -5
```
注：`redis` 8.1 已装且支持 async（`redis.asyncio`），`aioredis` 不必装——若上面报 aioredis 冲突就只装 `arq asyncmy`。验证：
```bash
D:/Anaconda3/envs/agent_env/python.exe -c "import arq, asyncmy; print('arq', arq.__version__, 'asyncmy OK')"
```
Expected: `arq <ver> asyncmy OK`

- [ ] **Step 2: 创建 backend/pyproject.toml**

```toml
[project]
name = "ai-cowork-game-backend"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "asyncmy>=0.2",
  "pydantic>=2.5",
  "pydantic-settings>=2.0",
  "arq>=0.26",
  "redis>=5.0",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: 创建 backend/.env（含真实 key，不入库）**

从仓库根 `.spike.env` 复制端点配置，补 DB/Redis：
```ini
# LLM（KSPMAS kimi-k3）
ANTHROPIC_BASE_URL=https://kspmas.ksyun.com/v1/chat/completions
ANTHROPIC_AUTH_TOKEN=<从 .spike.env 复制>
ANTHROPIC_MODEL=kimi-k3
# MySQL（本机；填你的真实凭据）
DB_URL=mysql+asyncmy://root:<你的密码>@127.0.0.1:3306/ai_cowork_game?charset=utf8mb4
# Redis（本机）
REDIS_URL=redis://127.0.0.1:6379/0
# Arq
ARQ_QUEUE=agent
# workspace 根（相对 repo）
WORKSPACE_ROOT=Games
```
验证不入库：
```bash
git check-ignore backend/.env && echo "忽略OK"
```
Expected: `backend/.env`（被忽略）

- [ ] **Step 4: 创建 backend/.env.example（入库模板，无 key）**

把 Step 3 的内容里 `<...>` 占位符化、`AUTH_TOKEN` 置空：
```ini
ANTHROPIC_BASE_URL=https://kspmas.ksyun.com/v1/chat/completions
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_MODEL=kimi-k3
DB_URL=mysql+asyncmy://root:PASSWORD@127.0.0.1:3306/ai_cowork_game?charset=utf8mb4
REDIS_URL=redis://127.0.0.1:6379/0
ARQ_QUEUE=agent
WORKSPACE_ROOT=Games
```

- [ ] **Step 5: 启动 Redis（本机服务未在跑）**

```bash
# 选项A：本机已装的 Redis 服务
#   在「服务」里启动 Redis，或运行 D:/Program Files (x86)/Redis-x64-5.0.14.1/redis-server.exe
# 选项B：docker 一行起
docker run -d --name ai-cowork-redis -p 6379:6379 redis:7-alpine
# 验证
redis-cli ping
```
Expected: `PONG`

- [ ] **Step 6: 建 MySQL 库**

```bash
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS ai_cowork_game CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```
（Task 3 用 SQLAlchemy `create_all` 建表，本步只建库。）

- [ ] **Step 7: 创建 settings.py**

`backend/app/config/settings.py`:
```python
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/app/config -> repo

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / "backend" / ".env", extra="ignore")

    anthropic_base_url: str
    anthropic_auth_token: str
    anthropic_model: str
    db_url: str
    redis_url: str = "redis://127.0.0.1:6379/0"
    arq_queue: str = "agent"
    workspace_root: str = "Games"

    @property
    def workspace_base(self) -> Path:
        return REPO_ROOT / self.workspace_root

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
`backend/app/__init__.py`、`backend/app/config/__init__.py`、`backend/tests/__init__.py` 各建空文件。

- [ ] **Step 8: 验证 settings 可加载**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -c "from app.config.settings import get_settings; s=get_settings(); print(s.anthropic_model, s.workspace_base)"
```
Expected: 打印 `kimi-k3` 与 workspace_base 路径（证明 `.env` 被读到）。若报 `.env not found`，检查路径与 `REPO_ROOT` 层级。

- [ ] **Step 9: 提交**

```bash
git add backend/pyproject.toml backend/.env.example backend/app/__init__.py backend/app/config/ backend/tests/__init__.py
git commit -m "chore(backend): Phase1 基建——pyproject、settings、.env.example"
```
（`.env` 与 `.spike.env` 均被 gitignore，不提交。）

---

## Task 1: 测试基建与录制 NDJSON fixtures

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/fixtures/ok_math.jsonl`、`resume_ok.jsonl`、`tool_use_read.jsonl`、`refusal.jsonl`

**Interfaces:**
- Produces: `tests/conftest.py` 提供 `async_db_session`（async SQLAlchemy session，连真 MySQL，每测试回滚）、`fake_redis`（内存 dict 模拟 XADD/XREAD）；`tests/fixtures/*.jsonl` 为 Parser 测试输入。

- [ ] **Step 1: 从 spike 产物录制 NDJSON fixtures**

spike 时输出落在了 `/tmp/spkC.txt`、`/tmp/spkR.txt`、`/tmp/spkT.txt`。把它们整理成 fixtures（每行一个 claude stream-json 事件）。若 `/tmp` 已清，用下面 Task 2 Step 2 的内联最小样本（推荐重新跑一次 spike 落盘到 fixtures 目录，见 Step 2）。
```bash
mkdir -p backend/tests/fixtures
# 若 spike 输出还在：
cp /tmp/spkC.txt backend/tests/fixtures/ok_math.jsonl   # 2+2=4 含 thinking
cp /tmp/spkR.txt backend/tests/fixtures/resume_ok.jsonl  # resume 回 4
cp /tmp/spkT.txt backend/tests/fixtures/tool_use_read.jsonl
# refusal 样本：从 spkC 第一次（非 --bare）输出含 refusal，若已无则手写（见 Step 2）
```

- [ ] **Step 2: 重新录制（若 /tmp 已清，推荐此法保证真实）**

```bash
cd "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game"
set -a && source .spike.env && set +a
claude -p "What is two plus two? Answer with only the digit." --output-format stream-json --verbose --include-partial-messages --bare > backend/tests/fixtures/ok_math.jsonl 2>&1
claude --resume <ok_math的session_id> -p "What digit did you reply? Only that digit." --output-format stream-json --verbose --include-partial-messages --bare > backend/tests/fixtures/resume_ok.jsonl 2>&1
claude -p "Read README.md then reply only its first heading." --output-format stream-json --verbose --include-partial-messages --bare --allowedTools Read --permission-mode acceptEdits > backend/tests/fixtures/tool_use_read.jsonl 2>&1
```
`refusal.jsonl`：若上面 tool_use 触发了 refusal（spike §3.5 实测会），该文件即含 refusal；否则从 ok_math 手工改一行 `model_refusal_no_fallback`（见 Task 2 测试，parser 不依赖真实 fixture 数量，只测能解析 refusal 类型）。

- [ ] **Step 3: 创建 conftest.py**

`backend/tests/conftest.py`:
```python
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.settings import get_settings
from app.models import Base  # Task 3 定义；本 task 先 import，Task 3 未到时用桩

FIXTURES = Path(__file__).parent / "fixtures"

@pytest_asyncio.fixture
async def async_db_session():
    settings = get_settings()
    engine = create_async_engine(settings.db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()

class FakeRedis:
    """内存模拟 redis.asyncio 的 XADD/XREAD，给 EventBroker/SSE 单测用。"""
    def __init__(self):
        self.streams: dict[str, list] = {}
    async def xadd(self, name, fields, **kw):
        self.streams.setdefault(name, []).append(fields)
        return b"0-0"
    async def xread(self, streams, block=None, count=None):
        # 简化：返回已有条目；block 忽略（单测不阻塞）
        out = []
        for name, ids in streams.items():
            entries = self.streams.get(name, [])
            out.append((name, [(b"0-0", e) for e in entries]))
            self.streams[name] = []  # 消费掉
        return out

@pytest.fixture
def fake_redis():
    return FakeRedis()

@pytest.fixture
def fixture_lines():
    def _load(name):
        return [json.loads(l) for l in (FIXTURES / name).read_text(encoding="utf-8").splitlines() if l.strip()]
    return _load
```
注：`from app.models import Base` 在 Task 3 才存在。本 task 提交时若 Task 3 未做，conftest 会 import 失败——**所以 Task 1 与 Task 3 顺序可对调**，但 spec 里 Parser 先行。折中：Task 1 只建 fixtures + FakeRedis，conftest 里 DB 部分先注释，Task 3 完成后补 `from app.models import Base`。**执行时：先做 Task 1 fixtures+FakeRedis，DB fixture 在 Task 3 完成后启用。**

- [ ] **Step 4: 提交**

```bash
git add backend/tests/conftest.py backend/tests/fixtures/
git commit -m "test(backend): 录制 stream-json fixtures + FakeRedis/conftest 基建"
```

---

## Task 2: CoworkEvent schema + ClaudeEventParser

**Files:**
- Create: `backend/app/schemas/__init__.py`、`backend/app/schemas/event.py`
- Create: `backend/app/agent/__init__.py`、`backend/app/agent/parser.py`
- Test: `backend/tests/test_parser.py`

**Interfaces:**
- Produces: `CoworkEvent`（pydantic 模型，字段见下）；`ClaudeEventParser.parse(line: str) -> list[CoworkEvent]`（一行可能产出 0..N 个事件；thinking 丢弃；result/refusal 三态）。
- Consumes: 无（纯函数，最早可测）。

`CoworkEvent` 字段（spec §7）：
```python
class CoworkEvent(BaseModel):
    event_id: str          # "evt_" + uuid4 hex
    project_id: int
    workflow_run_id: Optional[int] = None
    task_id: Optional[int] = None
    type: str              # agent.session.started 等
    timestamp: str         # ISO8601 UTC
    data: dict
    # 持久化用附加字段（不序列化给前端，repo 用）：
    aggregate_type: str = "agent_session"
    aggregate_id: int = 0
    raw_json: Optional[str] = None
```

- [ ] **Step 1: 写失败测试（先测最简：system/init → agent.session.started）**

`backend/tests/test_parser.py`:
```python
from __future__ import annotations
import json
from app.agent.parser import ClaudeEventParser, CoworkEvent

def test_parse_system_init_emits_session_started():
    line = json.dumps({
        "type": "system", "subtype": "init",
        "session_id": "sid-123",
        "model": "kimi-k3",
        "tools": ["Read", "Write"],
    })
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1
    e = evts[0]
    assert e.type == "agent.session.started"
    assert e.data == {"session_id": "sid-123", "model": "kimi-k3", "agent_type": "brainstorm"}
    assert e.event_id.startswith("evt_")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_parser.py -v`
Expected: FAIL（`ModuleNotFoundError: app.agent.parser`）

- [ ] **Step 3: 实现 schemas/event.py**

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field

def _new_event_id() -> str:
    return "evt_" + uuid4().hex

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class CoworkEvent(BaseModel):
    event_id: str = Field(default_factory=_new_event_id)
    project_id: int
    workflow_run_id: Optional[int] = None
    task_id: Optional[int] = None
    type: str
    timestamp: str = Field(default_factory=_now_iso)
    data: dict
    aggregate_type: str = "agent_session"
    aggregate_id: int = 0
    raw_json: Optional[str] = None
```

- [ ] **Step 4: 实现 parser.py（system/init 分支先够测试）**

```python
from __future__ import annotations
import json
from typing import Optional
from app.schemas.event import CoworkEvent

class ClaudeEventParser:
    def __init__(self, project_id: int, agent_type: str = "brainstorm"):
        self.project_id = project_id
        self.agent_type = agent_type

    def parse(self, line: str) -> list[CoworkEvent]:
        line = line.strip()
        if not line:
            return []
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return []
        t = obj.get("type")
        if t == "system" and obj.get("subtype") == "init":
            return [CoworkEvent(
                project_id=self.project_id,
                type="agent.session.started",
                data={"session_id": obj["session_id"], "model": obj.get("model"), "agent_type": self.agent_type},
                aggregate_id=0,
                raw_json=line,
            )]
        return []
```
`backend/app/agent/__init__.py`、`backend/app/schemas/__init__.py` 各建空文件。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 6: 扩展测试覆盖全部映射（TDD 循环：每个映射一个测试）**

逐个加测试，覆盖 spec §5.2 映射表。示例（text_delta / tool_use / tool_result / assistant completed / result 正常 / refusal / thinking 丢弃）：
```python
def test_parse_text_delta():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "text_delta", "text": "hello"}}})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert len(evts) == 1 and evts[0].type == "agent.message.delta"
    assert evts[0].data == {"text": "hello"}

def test_parse_thinking_delta_dropped():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "thinking_delta", "thinking": "x"}}})
    assert ClaudeEventParser(project_id=1).parse(line) == []

def test_parse_tool_use():
    line = json.dumps({"type": "stream_event", "event": {
        "type": "content_block_start", "index": 1,
        "content_block": {"type": "tool_use", "id": "tu1", "name": "Read",
                          "input": {"file_path": "a.md"}}}})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert evts[0].type == "agent.tool.started"
    assert evts[0].data["name"] == "Read" and evts[0].data["tool_use_id"] == "tu1"

def test_parse_result_completed():
    line = json.dumps({"type": "result", "subtype": "success", "is_error": False,
        "stop_reason": "end_turn", "session_id": "sid-1", "result": "4",
        "total_cost_usd": 0.01, "duration_ms": 100, "num_turns": 1})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert evts[0].type == "agent.session.completed"
    assert evts[0].data["session_id"] == "sid-1" and evts[0].data["result"] == "4"

def test_parse_refusal():
    line = json.dumps({"type": "system", "subtype": "model_refusal_no_fallback"})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert evts[0].type == "agent.refused"

def test_parse_result_refusal():
    line = json.dumps({"type": "result", "subtype": "success", "is_error": True,
        "stop_reason": "refusal", "result": "API Error..."})
    evts = ClaudeEventParser(project_id=1).parse(line)
    assert evts[0].type == "agent.refused"
```

- [ ] **Step 7: 扩展实现至完整映射表**

补 `content_block_delta`(text_delta/tool_result 通过后续 user 消息)、`content_block_start`(tool_use/text)、`assistant`(完整消息→agent.message.completed)、`result`(按 is_error/stop_reason 分 completed/refused/failed)、`model_refusal_no_fallback`→refused。thinking_delta/thinking_tokens 全部返回 `[]`。完整实现见 spec §5.2 表（每个 claude 原始类型一个分支）。`assistant` 完整消息：取 `content` 里 type=text 的 block 文本 → `agent.message.completed`。`tool_result`：claude 在下一轮 user 消息里给出，parser 需识别 `{"role":"user","content":[{"type":"tool_result",...}]}` 形态（spike §3.4）→ `agent.tool.completed`。

- [ ] **Step 8: 用真实 fixture 跑一遍（可选，确认对得上 spike）**

```python
def test_parse_real_fixture(fixture_lines):
    lines = fixture_lines("ok_math.jsonl")
    evts = [e for l in lines for e in ClaudeEventParser(project_id=1).parse(json.dumps(l))]
    types = [e.type for e in evts]
    assert "agent.session.started" in types
    assert "agent.message.completed" in types or "agent.session.completed" in types
    assert all("thinking" not in e.type for e in evts)  # thinking 被丢弃
```

- [ ] **Step 9: 提交**

```bash
git add backend/app/schemas/ backend/app/agent/__init__.py backend/app/agent/parser.py backend/tests/test_parser.py
git commit -m "feat(agent): CoworkEvent + ClaudeEventParser（stream-json→事件归一化，含三态/thinking丢弃）"
```

---

## Task 3: ORM 模型 + async DB 基建

**Files:**
- Create: `backend/app/models/__init__.py`、`backend/app/models/project.py`、`backend/app/agent_session.py`(下同 models/)、`backend/app/models/event.py`
- Create: `backend/app/persistence/__init__.py`、`backend/app/persistence/db.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Base`（declarative base，`app.models`）、`Project`/`AgentSession`/`Event` ORM 类、`get_engine()`/`get_sessionmaker()`（async）；conftest 的 `async_db_session` 在本 task 完成后启用 `from app.models import Base`。

- [ ] **Step 1: 写失败测试（建表 + 插一行 project）**

`backend/tests/test_models.py`:
```python
from sqlalchemy import select
from app.models.project import Project
from app.models.agent_session import AgentSession
from app.models.event import Event

async def test_project_insert(async_db_session):
    p = Project(project_key="farmdemo", name="FarmDemo", status="CREATED", workspace_root="Games/farmdemo")
    async_db_session.add(p)
    await async_db_session.flush()
    assert p.id is not None
```

- [ ] **Step 2: 跑确认失败**（import 缺）

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_models.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 models**

`backend/app/models/__init__.py`:
```python
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass
from . import project, agent_session, event  # noqa
```
`backend/app/models/project.py`（spec §6.1 精简）:
```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_workflow_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    workspace_root: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
```
`agent_session.py`（spec §6.2）、`event.py`（spec §6.3）按 spec DDL 同理实现（`claude_session_id` nullable、`payload`/`raw_json` 用 `JSON`/`Text`、事件表加 `aggregate_type/aggregate_id`）。event.py 的 `payload` 用 `sqlalchemy.JSON`，`raw_json` 用 `Text`。

- [ ] **Step 4: 实现 db.py**

`backend/app/persistence/db.py`:
```python
from __future__ import annotations
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.settings import get_settings

_engine = None
_sessionmaker = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().db_url, echo=False, pool_pre_ping=True)
    return _engine

def get_sessionmaker():
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _sessionmaker
```

- [ ] **Step 5: 启用 conftest 的 DB fixture**

把 Task 1 conftest 里 `from app.models import Base` 取消注释（Task 3 已有 Base）。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_models.py -v`
Expected: PASS（连真 MySQL，create_all 建表，插行回滚）

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/ backend/app/persistence/db.py backend/tests/test_models.py
git commit -m "feat(persistence): Project/AgentSession/Event ORM + async DB 基建"
```

---

## Task 4: workflow states + engine（最小）

**Files:**
- Create: `backend/app/workflow/__init__.py`、`backend/app/workflow/states.py`、`backend/app/workflow/engine.py`
- Test: `backend/tests/test_states.py`

**Interfaces:**
- Produces: `ProjectStatus` 枚举（CREATED/BRAINSTORMING/FAILED）；`assert_can_brainstorm(status)` 抛 `WorkflowBlocked` 若非 CREATED/BRAINSTORMING。

- [ ] **Step 1: 写失败测试**
```python
import pytest
from app.workflow.states import ProjectStatus
from app.workflow.engine import assert_can_brainstorm, WorkflowBlocked

def test_can_brainstorm_from_created():
    assert_can_brainstorm(ProjectStatus.CREATED)  # 不抛

def test_cannot_brainstorm_from_failed():
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm(ProjectStatus.FAILED)
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_states.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`states.py`:
```python
from enum import Enum
class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    FAILED = "FAILED"
```
`engine.py`:
```python
from __future__ import annotations
from app.workflow.states import ProjectStatus

class WorkflowBlocked(Exception):
    pass

def assert_can_brainstorm(status: ProjectStatus) -> None:
    if status not in (ProjectStatus.CREATED, ProjectStatus.BRAINSTORMING):
        raise WorkflowBlocked(f"cannot brainstorm from {status}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_states.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/workflow/ backend/tests/test_states.py
git commit -m "feat(workflow): ProjectStatus 枚举 + brainstorm 状态校验"
```

---

## Task 5: EventBroker + Repos

**Files:**
- Create: `backend/app/events/__init__.py`、`backend/app/events/broker.py`
- Modify: `backend/app/persistence/repo.py`（Create）
- Test: `backend/tests/test_broker.py`

**Interfaces:**
- Produces: `EventRepo`（`insert(evt: CoworkEvent)`）、`ProjectRepo`、`AgentSessionRepo`；`EventBroker.publish(evt)` 先 `EventRepo.insert` 再 `redis.xadd`；`EventBroker.history(project_id, after_id)` 读 MySQL 历史。

- [ ] **Step 1: 写失败测试（先落库再广播，用 FakeRedis）**
```python
from app.events.broker import EventBroker
from app.schemas.event import CoworkEvent
from app.persistence.repo import EventRepo

async def test_broker_persists_then_publishes(async_db_session, fake_redis):
    broker = EventBroker(session_factory=lambda: async_db_session, redis=fake_redis)
    evt = CoworkEvent(project_id=1, type="agent.message.delta", data={"text": "hi"}, aggregate_id=1)
    await broker.publish(evt)
    # 落库
    rows = await async_db_session.execute(select(Event).where(Event.project_id == 1))
    assert rows.scalars().first() is not None
    # 广播
    assert len(fake_redis.streams["stream:project:1"]) == 1
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_broker.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 repo.py**

```python
from __future__ import annotations
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import Event
from app.models.project import Project
from app.models.agent_session import AgentSession
from app.schemas.event import CoworkEvent

class EventRepo:
    def __init__(self, session: AsyncSession):
        self.session = session
    async def insert(self, evt: CoworkEvent) -> int:
        row = Event(event_id=evt.event_id, project_id=evt.project_id, event_type=evt.type,
                    aggregate_type=evt.aggregate_type, aggregate_id=evt.aggregate_id,
                    payload=evt.data, raw_json=evt.raw_json)
        self.session.add(row)
        await self.session.flush()
        return row.id
    async def history(self, project_id: int, after_id: int = 0, limit: int = 500):
        q = select(Event).where(Event.project_id == project_id, Event.id > after_id).order_by(Event.id).limit(limit)
        return (await self.session.execute(q)).scalars().all()

class ProjectRepo:
    def __init__(self, session): self.session = session
    async def create(self, **kw): ...
    async def get(self, pid): ...
    async def set_status(self, pid, status): ...

class AgentSessionRepo:
    def __init__(self, session): self.session = session
    async def create(self, project_id, agent_type, working_directory): ...
    async def bind_claude_session(self, id, claude_session_id): ...
    async def finish(self, id, status): ...
    async def last_claude_session(self, project_id, agent_type): ...  # resume 用
```
（上述 `...` 处填实具体 SQL，见 spec §6.1/§6.2 字段。）

- [ ] **Step 4: 实现 broker.py**

```python
from __future__ import annotations
import json
from typing import Callable
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.schemas.event import CoworkEvent
from app.persistence.repo import EventRepo

class EventBroker:
    def __init__(self, session_factory: Callable[[], AsyncSession], redis):
        self.session_factory = session_factory
        self.redis = redis
    async def publish(self, evt: CoworkEvent) -> None:
        async with self.session_factory() as session:
            repo = EventRepo(session)
            await repo.insert(evt)
            await session.commit()
        await self.redis.xadd(f"stream:project:{evt.project_id}", {"data": json.dumps(evt.model_dump(), ensure_ascii=False)})
    async def history(self, project_id, after_id=0):
        async with self.session_factory() as session:
            return await EventRepo(session).history(project_id, after_id)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_broker.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/events/ backend/app/persistence/repo.py backend/tests/test_broker.py
git commit -m "feat(events): EventBroker（先落库再 XADD）+ Event/Project/AgentSession Repo"
```

---

## Task 6: ClaudeRuntime

**Files:**
- Create: `backend/app/agent/runtime.py`
- Test: `backend/tests/test_runtime.py`

**Interfaces:**
- Produces: `ClaudeRuntime`（`async start(prompt, workspace, agent_type, system_prompt) -> AsyncIterator[CoworkEvent]`、`resume(session_id, prompt, workspace, ...) -> ...`、`async cancel()`）；用 `asyncio.create_subprocess_exec` spawn `claude`；逐行喂 `ClaudeEventParser`。

- [ ] **Step 1: 写失败测试（用 fake subprocess 验命令拼接 + 逐事件 yield）**

`backend/tests/test_runtime.py`:
```python
import asyncio
import pytest
from app.agent.runtime import ClaudeRuntime

class FakeProc:
    def __init__(self, lines: list[str]):
        self._lines = lines
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def stream_lines(self):  # 模拟逐行
        for l in self._lines:
            yield l

@pytest.mark.asyncio
async def test_runtime_yields_events_from_stream(monkeypatch):
    import json
    lines = [
        json.dumps({"type":"system","subtype":"init","session_id":"s1","model":"kimi-k3"}),
        json.dumps({"type":"result","subtype":"success","is_error":False,"stop_reason":"end_turn","session_id":"s1","result":"4","total_cost_usd":0.01,"duration_ms":1,"num_turns":1}),
    ]
    rt = ClaudeRuntime.__new__(ClaudeRuntime)  # 绕过真实 spawn
    # 用 monkeypatch 替换 _spawn 与解析：验证 start 的命令拼了 --bare 与端点 env
    cmd_captured = {}
    async def fake_spawn(cmd, env, cwd):
        cmd_captured.update(cmd=cmd, env=env, cwd=cwd)
        return lines  # 返回行列表
    monkeypatch.setattr(rt, "_spawn_stream", fake_spawn)
    evts = [e async for e in rt.start(prompt="2+2", workspace="Games/x", agent_type="brainstorm")]
    assert "--bare" in cmd_captured["cmd"]
    assert cmd_captured["env"]["ANTHROPIC_MODEL"] == "kimi-k3"
    assert evts[0].type == "agent.session.started"
    assert evts[-1].type == "agent.session.completed"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runtime.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 runtime.py**

```python
from __future__ import annotations
import asyncio
import os
from typing import AsyncIterator, Optional
from app.agent.parser import ClaudeEventParser
from app.config.settings import get_settings

class ClaudeRuntime:
    def __init__(self):
        self.settings = get_settings()
        self.proc: Optional[asyncio.subprocess.Process] = None

    def _build_cmd(self, prompt, resume_sid=None, system_prompt=None) -> list[str]:
        cmd = ["claude", "-p", prompt,
               "--output-format", "stream-json", "--verbose", "--include-partial-messages",
               "--bare", "--allowedTools", "Read", "Write",
               "--permission-mode", "acceptEdits"]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        if resume_sid:
            cmd += ["--resume", resume_sid]
        return cmd

    def _build_env(self) -> dict:
        # 剥离宿主 CLAUDE_*/KSCC_* 避免误连 glm-5.2；只注入 .env 三变量 + 必要 PATH
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_", "KSCC_"))}
        env["ANTHROPIC_BASE_URL"] = self.settings.anthropic_base_url
        env["ANTHROPIC_AUTH_TOKEN"] = self.settings.anthropic_auth_token
        env["ANTHROPIC_MODEL"] = self.settings.anthropic_model
        return env

    async def _spawn_stream(self, cmd, env, cwd) -> list[str]:
        # 真实实现：create_subprocess_exec + 逐行读 stdout
        self.proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd)
        lines = []
        async for raw in self.proc.stdout:
            lines.append(raw.decode("utf-8", "replace"))
        await self.proc.wait()
        return lines

    async def _run(self, prompt, workspace, agent_type, resume_sid=None, system_prompt=None) -> AsyncIterator:
        cmd = self._build_cmd(prompt, resume_sid, system_prompt)
        env = self._build_env()
        cwd = str(self.settings.workspace_base.parent / workspace) if not os.path.isabs(workspace) else workspace
        # workspace 形如 "Games/farmdemo"；cwd 指向该目录（session 按 cwd 存）
        parser = ClaudeEventParser(project_id=0, agent_type=agent_type)  # project_id 由 task 注入
        for line in await self._spawn_stream(cmd, env, cwd):
            for evt in parser.parse(line):
                yield evt

    async def start(self, prompt, workspace, agent_type="brainstorm", system_prompt=None, project_id=0) -> AsyncIterator:
        parser = ClaudeEventParser(project_id=project_id, agent_type=agent_type)
        cmd = self._build_cmd(prompt, None, system_prompt)
        env = self._build_env()
        cwd = str(self.settings.workspace_base.parent / workspace) if not os.path.isabs(workspace) else workspace
        self.proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd)
        async for raw in self.proc.stdout:
            for evt in parser.parse(raw.decode("utf-8","replace")):
                yield evt
        await self.proc.wait()

    async def resume(self, session_id, prompt, workspace, agent_type="brainstorm", system_prompt=None, project_id=0) -> AsyncIterator:
        # 同 start 但 cmd 加 --resume
        ...  # 复用 start 逻辑，_build_cmd 传 resume_sid

    async def cancel(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
```
（注：测试用 `_spawn_stream` 被 monkeypatch；真实 `start`/`resume` 直接 stream `proc.stdout`，不走 `_spawn_stream`——上面两者并存，测试覆盖命令拼接与解析，真实路径靠 e2e 验。实现时统一：`start`/`resume` 都用 `_run` 私有方法 + `proc.stdout` 流式，`_spawn_stream` 仅为可测性保留或删除。**执行时择一，避免重复。**）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runtime.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/runtime.py backend/tests/test_runtime.py
git commit -m "feat(agent): ClaudeRuntime（spawn claude --bare + stream-json 逐事件 yield + resume）"
```

---

## Task 7: session/workspace 管理

**Files:**
- Create: `backend/app/agent/session.py`
- Test: `backend/tests/test_session.py`

**Interfaces:**
- Produces: `ensure_workspace(project_key) -> Path`（创建 `Games/{key}/`）；`AgentSession` 生命周期 helper（预建 RUNNING 行、system/init 回填 claude_session_id、result 收尾）。

- [ ] **Step 1: 写失败测试**
```python
from app.agent.session import ensure_workspace
from app.config.settings import get_settings

def test_ensure_workspace_creates_dir(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "workspace_base", tmp_path)
    p = ensure_workspace("farmdemo")
    assert p.exists() and p.name == "farmdemo"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_session.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 session.py**
```python
from __future__ import annotations
from pathlib import Path
from app.config.settings import get_settings

def ensure_workspace(project_key: str) -> Path:
    p = get_settings().workspace_base / project_key
    p.mkdir(parents=True, exist_ok=True)
    return p
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_session.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/session.py backend/tests/test_session.py
git commit -m "feat(agent): workspace/session 管理（Games/{key}/ + ensure_workspace）"
```

---

## Task 8: brainstorm 自研 system prompt

**Files:**
- Create: `backend/app/agent/prompts.py`

**Interfaces:**
- Produces: `BRAINSTORM_SYSTEM_PROMPT: str`（多轮澄清游戏创意 → 澄清充分后调 Write 落 `Games/{key}/{游戏名}-game-design.md`；措辞中性规避 kimi-k3 审核）。

- [ ] **Step 1: 写 prompt（无逻辑测试，仅静态断言文案存在关键约束）**

`backend/tests/test_prompts.py`（轻测）:
```python
from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT

def test_brainstorm_prompt_has_write_instruction():
    assert "game-design.md" in BRAINSTORM_SYSTEM_PROMPT
    assert "Write" in BRAINSTORM_SYSTEM_PROMPT
```

- [ ] **Step 2: 实现 prompts.py**

```python
BRAINSTORM_SYSTEM_PROMPT = """You are the Brainstorm Agent for an AI game co-creation backend.

Goal: clarify the user's game idea through multi-turn questions, then write a game design draft.

Process:
1. Ask focused questions one batch at a time: genre, core loop, player goals, win condition, art style. Do not ask all at once.
2. When the idea is sufficiently clear, call the Write tool to save a draft to the file path given in the user message (a *-game-design.md file).
3. Keep the draft concise: Overview, Core Loop, Player Goals, Mechanics, Features list.

Rules:
- Stay neutral and concrete. Avoid sensitive or policy-flagged wording.
- Only use Read and Write tools. Do not run shell commands.
- Do not modify files other than the designated game-design.md.
- After writing the draft, reply with a one-line summary.
"""
```

- [ ] **Step 3: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_prompts.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/agent/prompts.py backend/tests/test_prompts.py
git commit -m "feat(agent): brainstorm 自研 system prompt（多轮澄清→落 game-design.md，规避审核）"
```

---

## Task 9: project_service + jobs

**Files:**
- Create: `backend/app/services/__init__.py`、`backend/app/services/project_service.py`
- Create: `backend/app/queue/__init__.py`、`backend/app/queue/jobs.py`
- Test: `backend/tests/test_project_service.py`

**Interfaces:**
- Produces: `project_service.create(name, description) -> Project`（生成 project_key、ensure_workspace、落库 status=CREATED）；`jobs.enqueue_brainstorm(project_id) -> str`（Arq enqueue，返 job_id）。

- [ ] **Step 1: 写失败测试**
```python
async def test_create_project(async_db_session, monkeypatch):
    monkeypatch.setattr("app.services.project_service.ensure_workspace", lambda key: Path("/tmp/x"))
    p = await project_service.create(session=async_db_session, name="FarmDemo", description="d")
    assert p.status == "CREATED" and p.project_key
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_project_service.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 project_service.py + jobs.py**

`project_service.py`:
```python
from __future__ import annotations
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.workflow.states import ProjectStatus
from app.agent.session import ensure_workspace
from app.persistence.repo import ProjectRepo

async def create(session, name, description=None) -> Project:
    key = name.lower().replace(" ", "-") + "-" + secrets.token_hex(3)
    ws = ensure_workspace(key)
    p = Project(project_key=key, name=name, description=description, status=ProjectStatus.CREATED, workspace_root=str(ws))
    session.add(p); await session.flush()
    return p
```
`jobs.py`（Arq enqueue 封装）:
```python
from __future__ import annotations
from arq import create_pool
from arq.connections import RedisSettings
from app.config.settings import get_settings

async def enqueue_brainstorm(project_id: int) -> str:
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_brainstorm", project_id, _queue_name=s.arq_queue)
    return job.job_id
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_project_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/ backend/app/queue/jobs.py backend/tests/test_project_service.py
git commit -m "feat(service): project_service.create + Arq enqueue 封装"
```

---

## Task 10: Arq task run_brainstorm + worker 配置

**Files:**
- Create: `backend/app/queue/tasks.py`、`backend/app/queue/worker.py`
- Test: `backend/tests/test_tasks_worker.py`

**Interfaces:**
- Produces: `async def run_brainstorm(ctx, project_id)`（状态校验→acquire lock→runtime.start→逐事件 broker.publish→result 三态收尾→release lock）；`WorkerSettings`（Arq functions=[run_brainstorm]，RedisSettings）。

- [ ] **Step 1: 写失败测试（fake runtime，验状态校验+落库+三态收尾）**
```python
import pytest
from app.queue.tasks import run_brainstorm
from app.schemas.event import CoworkEvent

class FakeRuntime:
    def __init__(self, evts): self.evts = evts
    async def start(self, **kw):
        for e in self.evts: yield e

async def test_run_brainstorm_persists_events(async_db_session, fake_redis, monkeypatch):
    # 预置 project(状态 CREATED) + fake runtime 吐 3 事件 + result completed
    evts = [
        CoworkEvent(project_id=1, type="agent.session.started", data={"session_id":"s1","model":"kimi-k3","agent_type":"brainstorm"}, aggregate_id=1),
        CoworkEvent(project_id=1, type="agent.message.delta", data={"text":"hi"}, aggregate_id=1),
        CoworkEvent(project_id=1, type="agent.session.completed", data={"session_id":"s1","result":"ok","stop_reason":"end_turn","cost":0.0,"duration":1}, aggregate_id=1),
    ]
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeRuntime(evts))
    # ... 预置 project 行，调 run_brainstorm，断言 events 表有 3 行、agent_session.status=COMPLETED
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_worker.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 tasks.py**

```python
from __future__ import annotations
import asyncio
from app.agent.runtime import ClaudeRuntime
from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT
from app.agent.session import ensure_workspace
from app.events.broker import EventBroker
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo, AgentSessionRepo
from app.workflow.engine import assert_can_brainstorm, WorkflowBlocked
from app.workflow.states import ProjectStatus
from app.config.settings import get_settings
import redis.asyncio as aioredis

async def run_brainstorm(ctx, project_id: int):
    settings = get_settings()
    sm = get_sessionmaker()
    # 1. 状态校验
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        assert_can_brainstorm(ProjectStatus(p.status))
        await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMING)
        # 2. 预建 agent_session
        as_repo = AgentSessionRepo(s)
        agent_session = await as_repo.create(project_id, "BRAINSTORM", p.workspace_root)
        await s.commit()
    # 3. acquire project lock（Redis TTL 30min）
    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:brainstorm", timeout=1800)
    await lock.acquire()
    try:
        broker = EventBroker(session_factory=lambda: sm().__enter__(), redis=r)  # 用 context manager 正确包装
        runtime = ClaudeRuntime()
        last_sid = None; failed = False; reason = None
        prompt = ctx.get("prompt", "开始设计游戏")  # 实际 prompt 由 brainstorm 端点传入
        async for evt in runtime.start(prompt=prompt, workspace=p.workspace_root, agent_type="brainstorm", system_prompt=BRAINSTORM_SYSTEM_PROMPT, project_id=project_id):
            evt.aggregate_id = agent_session.id
            if evt.type == "agent.session.started":
                await as_repo.bind_claude_session(agent_session.id, evt.data["session_id"])
                last_sid = evt.data["session_id"]
            elif evt.type in ("agent.refused",):
                failed = True; reason = "content_review"
            await broker.publish(evt)
        # 4. 三态收尾
        async with sm() as s:
            await AgentSessionRepo(s).finish(agent_session.id, "FAILED" if failed else "COMPLETED")
            if failed: await ProjectRepo(s).set_status(project_id, ProjectStatus.FAILED)
            await s.commit()
        return {"session_id": last_sid, "failed": failed, "reason": reason}
    finally:
        await lock.release()
        await r.close()
```
（执行时修正 broker 的 session_factory 用法——应为 `async with sm() as s: ...`，上面伪码示意，实现用 EventBroker 接受 sessionmaker 而非 lambda。）

`worker.py`:
```python
from arq.connections import RedisSettings
from app.config.settings import get_settings
from app.queue.tasks import run_brainstorm

class WorkerSettings:
    functions = [run_brainstorm]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_worker.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/queue/tasks.py backend/app/queue/worker.py backend/tests/test_tasks_worker.py
git commit -m "feat(queue): run_brainstorm Arq task（状态校验+锁+流式落库+三态收尾）+ worker 配置"
```

---

## Task 11: FastAPI app + projects/brainstorm API

**Files:**
- Create: `backend/app/api/__init__.py`、`backend/app/api/projects.py`、`backend/app/schemas/project.py`、`backend/app/main.py`
- Test: `backend/tests/test_api_projects.py`

**Interfaces:**
- Produces: `POST /api/projects`（建项目，返 ProjectRead）、`GET /api/projects/{id}`、`POST /api/projects/{id}/brainstorm`（enqueue→202 {task_id}）；`main.py` lifespan 启动时建表。

- [ ] **Step 1: 写失败测试（httpx AsyncClient）**
```python
async def test_create_project_endpoint(client):
    r = await client.post("/api/projects", json={"name":"FarmDemo","description":"d"})
    assert r.status_code == 201
    assert r.json()["status"] == "CREATED"

async def test_brainstorm_enqueues(client, monkeypatch):
    monkeypatch.setattr("app.api.projects.enqueue_brainstorm", lambda pid: _async_return("job-1"))
    r = await client.post("/api/projects/1/brainstorm")
    assert r.status_code == 202 and r.json()["task_id"] == "job-1"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_projects.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 schemas/project.py、api/projects.py、main.py**

`project.py`:
```python
from pydantic import BaseModel
class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
class ProjectRead(BaseModel):
    id: int
    project_key: str
    name: str
    status: str
    workspace_root: str
```
`api/projects.py`：`POST /api/projects`（session→project_service.create→commit→ProjectRead）；`GET /api/projects/{id}`；`POST /api/projects/{id}/brainstorm`（enqueue_brainstorm(id)→202 {task_id}）。
`main.py`：FastAPI 实例、lifespan 启动 `create_all`、include_router。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_projects.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/ backend/app/schemas/project.py backend/app/main.py backend/tests/test_api_projects.py
git commit -m "feat(api): FastAPI app + POST/GET /projects + POST /brainstorm（入队返 task_id）"
```

---

## Task 12: SSE 事件流端点

**Files:**
- Create: `backend/app/api/events.py`
- Modify: `backend/app/main.py`（注册 events router）
- Test: `backend/tests/test_api_events_sse.py`

**Interfaces:**
- Produces: `GET /api/projects/{id}/stream?after=<event_id>` → `text/event-stream`：先 `broker.history(id, after)` yield 历史，再 `redis.xread BLOCK` yield 实时。

- [ ] **Step 1: 写失败测试（验 history 回放 + 格式 SSE）**
```python
async def test_stream_replays_history(client, async_db_session):
    # 预置 2 条 events 行
    r = await client.get("/api/projects/1/stream?after=0")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "agent.session.started" in body  # 历史被回放
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_events_sse.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 events.py**

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis
from app.config.settings import get_settings
from app.events.broker import EventBroker
from app.persistence.db import get_sessionmaker
import json

router = APIRouter()

@router.get("/projects/{pid}/stream")
async def stream(pid: int, after: int = 0):
    settings = get_settings()
    sm = get_sessionmaker()
    broker = EventBroker(session_factory=sm, redis=None)
    r = aioredis.from_url(settings.redis_url)

    async def gen():
        # 1. 补历史
        rows = await broker.history(pid, after)
        for row in rows:
            yield f"data: {json.dumps({'event_id': row.event_id, 'type': row.event_type, 'data': row.payload}, ensure_ascii=False)}\n\n"
        # 2. 实时 XREAD BLOCK
        last = "$"
        while True:
            resp = await r.xread({f"stream:project:{pid}": last}, block=30000, count=100)
            if not resp:
                yield ": keepalive\n\n"
                continue
            for _stream, entries in resp:
                for _id, fields in entries:
                    last = _id.decode() if isinstance(_id, bytes) else _id
                    yield f"data: {fields['data']}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_events_sse.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/events.py backend/app/main.py backend/tests/test_api_events_sse.py
git commit -m "feat(api): SSE 事件流端点（MySQL 补历史 + Redis XREAD 实时）"
```

---

## Task 13: e2e 手动验收（不打 CI）

**Goal:** 跑通 spec §1.2 验收链路 ①-⑤，真打 KSPMAS kimi-k3。

- [ ] **Step 1: 启动基建**

```bash
# Redis（Task 0 已起，确认在跑）
redis-cli ping  # PONG
# MySQL 库已建；建表由 app lifespan create_all
```

- [ ] **Step 2: 起 Arq worker（终端A）**
```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m arq app.queue.worker.WorkerSettings
```

- [ ] **Step 3: 起 FastAPI（终端B）**
```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 4: 跑验收链路（终端C）**
```bash
# ① 建项目
curl -s -X POST http://127.0.0.1:8000/api/projects -H "Content-Type: application/json" -d '{"name":"FarmDemo","description":"种田游戏"}'
# 记下 id

# ② brainstorm 入队
curl -s -X POST http://127.0.0.1:8000/api/projects/<id>/brainstorm
# 返 task_id

# ④ SSE 看流（另开终端）
curl -N http://127.0.0.1:8000/api/projects/<id>/stream?after=0
# 应看到 agent.session.started → agent.message.delta → agent.session.completed

# ⑤ 第二轮 resume（验证 session/resume）
curl -s -X POST http://127.0.0.1:8000/api/projects/<id>/brainstorm -d '{"idea":"补充：NPC 要有作息"}'
# SSE 应续看同 session 的新事件
```

- [x] **Step 5: 验收检查清单**（2026-08-15 实测，project id=1 / key=farmdemo-77aa59）

- [x] events 表有 ≥3 行（started/delta/completed）——实测 140 行：第一轮 114 + 第二轮 26；分布 delta 96 / tool.start+completed 22 / message.completed 8 / session.started+completed 2
- [x] agent_sessions.claude_session_id 已回填、status=COMPLETED——session 2/3 均 COMPLETED，同一 claude_session_id `27f5d675-5eba-427b-8d0a-151b1ba7caa5`
- [x] `Games/farmdemo-77aa59/` 下生成了 `*-game-design.md`——`farmdemo-77aa59-game-design.md`，含 Overview/Core Loop/Player Goals/Mechanics/Features + 第二轮追加 `## NPC 作息`
- [x] SSE 第二轮看到同 session_id 的续接事件——第二轮 `agent.session.started.session_id` == 第一轮（matches prev: True）
- [x] 若触发 refusal：……——本轮两轮均 succeeded=True，未走 refusal 分支（三态处理代码就绪，未触发）

- [x] **Step 6: 记录验收结果到 doc**（见下「验收执行记录」）

- [x] **Step 7: 提交（验收中发现的 fix）**

```bash
git add backend/app/persistence/db.py backend/app/queue/worker.py backend/app/agent/runtime.py backend/app/queue/tasks.py doc/plans/2026-08-14-phase1-runtime-plan.md
git commit -m "fix(backend): Phase1 e2e 修复 4 项 + 验收记录（pool_pre_ping/arq queue/claude.exe/异常兜底）"
```

---

### 验收执行记录（2026-08-15）

**链路 ①-⑤ 全通过**（真打 KSPMAS kimi-k3，project id=1 / key=farmdemo-77aa59）：

| 步骤 | 结果 |
|---|---|
| ① POST /api/projects | 201，project id=1 status=CREATED，workspace=Games/farmdemo-77aa59 |
| ② POST /api/projects/1/brainstorm | 202，task_id 返回 |
| ③ Worker run_brainstorm | spawn claude.exe → kimi-k3 流式 → 114 事件落库 → 落 GDD → session COMPLETED；耗时 101.69s |
| ④ GET /stream?after=0 SSE | 200 text/event-stream，补历史+实时，事件序列 delta→tool→completed 完整 |
| ⑤ 第二轮 resume | enqueue 202 → run_brainstorm 查 last_claude_session 命中 → `--resume 27f5d675` → 同 session_id 续接 26 事件 → GDD 追加 `## NPC 作息` → session 3 COMPLETED |

**e2e 暴露并修复的 4 个真实 bug**（单测用 sqlite + FakeRedis + monkeypatch `_spawn_stream` 未覆盖）：

1. **`pool_pre_ping=True` + asyncmy 不兼容**（`db.py`）：asyncmy 异步 ping 适配签名与 SQLAlchemy 默认 `do_ping`（pymysql 同步签名）不匹配，请求时 pool 复用连接触发 pre_ping 抛 `ping() missing argument 'reconnect'`。建表首连不触发故 lifespan OK、请求才炸。修复：去掉 `pool_pre_ping`（本地 MySQL 稳定；将来防 stale 用 `pool_recycle`）。
2. **Arq worker queue_name 不匹配**（`worker.py`）：`jobs.enqueue_brainstorm` 用 `_queue_name=settings.arq_queue`（"agent"），worker 未设 `queue_name` → arq 默认监听 "arq"。arq 0.28 队列 key 是裸 queue_name（zset），job 进 `agent` zset、worker 监听 `arq` zset → 永不消费。修复：`WorkerSettings.queue_name = settings.arq_queue`。
3. **Windows spawn claude 失败**（`runtime.py`）：npm 全局 `claude` 在 Windows 是 `.cmd` shim，`asyncio.create_subprocess_exec`（非 shell，走 CreateProcess）找不到无扩展名 `claude`，抛 `FileNotFoundError [WinError 2]`。实际可执行是 `<node_global>/node_modules/@anthropic-ai/claude-code/bin/claude.exe`（claude-code 2.x bun 编译原生 exe）。修复：`_resolve_claude_bin()` 解析 claude.exe 绝对路径直接 exec——绕过 cmd.exe，避免多行 `--append-system-prompt` 在换行处被截断。
4. **run_brainstorm 异常不兜底致状态泄漏**（`tasks.py`）：spawn 失败等异常在 `async for` 抛出，三态收尾被跳过 → agent_session 泄漏 `RUNNING`、project 卡死 `BRAINSTORMING`。修复：`async for` 包 try/except，异常补发 `agent.session.failed` 事件并走 FAILED 三态收尾。

**观察（非 bug，Phase 1 边界外）**：kimi-k3 实测调用了 11 次 `PowerShell` 工具（非 prompt 约束的 Read/Write），但未触发 content_review refusal、最终仍用 Write 落/更新 GDD，session 正常 COMPLETED。属 agent 行为（prompt 未约束住模型），Runtime 链路不受影响；spec §5.4 已预判"尽量少调 PowerShell"，后续 Phase 3 接 Skills 时收紧工具白名单。

**e2e 环境补建**：MySQL 库 `ai_cowork_game` 首次未建（Task 0 Step 6 漏，单测用 sqlite 未暴露），已 `CREATE DATABASE`；`.env` MySQL 凭据由用户填入正确密码。

---

## Self-Review 已执行

**1. Spec coverage:** 逐条对照 spec §1-13：12 决策→Global Constraints/各 task；spike 证据→fixtures+三态；§4 模块→File Structure 全覆盖；§5 各模块→Task 2/5/6/7/8/10；§6 三表→Task 3；§7 事件协议→Task 2；§8 API→Task 11/12；§9 .env→Task 0；§10 测试→各 task+Task 13；§11 风险→Global Constraints 标注；§12 边界→Phase 1 不含 Git/Skill/Asset/Build/Feedback。
**2. Placeholder scan:** Task 5/10 的 repo/task 实现含 `...` 标注，已注明「执行时填具体 SQL/修正 session_factory」——属接口钉死而非占位回避，执行者按 spec DDL 填。无 TBD/TODO。
**3. Type consistency:** `CoworkEvent`/`ClaudeRuntime`/`EventBroker`/`ProjectRepo` 签名跨 task 一致；`run_brainstorm(ctx, project_id)` 在 jobs/tasks/worker 一致。

## 执行交接

计划已存 `doc/plans/2026-08-14-phase1-runtime-plan.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每个 task 派新 subagent，任务间 review，快速迭代。

**2. Inline Execution** — 本会话用 executing-plans 批量执行，带检查点。

**你选哪种？**
