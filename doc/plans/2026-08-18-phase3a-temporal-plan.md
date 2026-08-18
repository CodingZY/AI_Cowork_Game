# 阶段1 Temporal 重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 把阶段1从 Arq 编排重构为 Temporal Workflow——`GameDesignWorkflow`（Activity/Signal/Query/wait_condition）实现可暂停 Human-in-the-Loop；02 产出 QuestionPlan JSON 决策树；用户逐题 Signal 答题；Requirements Snapshot SSOT；GDD Check 三态。保留 ClaudeRuntime/GitService。

**Architecture:** 新增 `temporal/` 模块（workflows/activities/worker/client），`GameDesignWorkflow` 用 `await workflow.wait_condition` 逐题暂停等 Signal；Activity 调 ClaudeRuntime spawn claude（02/03/04）或纯 Python 合成（requirements）；FastAPI 端点经 Temporal Client start/signal/query；前端 Query 轮询 `/state` + SSE 看 Activity 流。

**Tech Stack:** Python 3.10（agent_env D 盘）/ temporalio 1.31.0（Docker Temporal Server + TestWorkflowEnvironment 单测）/ FastAPI / SQLAlchemy async / ClaudeRuntime（`--bare --plugin-dir`）+ KSPMAS kimi-k3 / GitService / React 18 + Vite

**Spec:** `doc/specs/2026-08-18-phase3a-temporal-design.md`（本计划从 spec 推导，spec 与计划一并阅读）

## Global Constraints

- **Python 解释器固定** `D:/Anaconda3/envs/agent_env/python.exe`（C 盘约束：禁碰 C 盘）。Python 3.10，类型用 `Optional[X]`/`from __future__ import annotations`。
- **temporalio 1.31.0 已装**（agent_env）。测试用 `WorkflowEnvironment.start_time_skipping()`（内嵌，不需真 Server）；e2e 用真 Temporal Server（Docker）。
- **Docker Temporal Server**：实现期 Task 0 用户启动 Docker Desktop 后 `docker run temporalio/auto-setup`。e2e 依赖它。
- **演进式重构**（D2）：保留 `ClaudeRuntime`（`start(prompt,cwd,project_id,agent_type,system_prompt,plugin_dir)`）、`GitService`（worktree/commit/merge/push/tag）、SSE 端点（`/stream`）、前端骨架（`api/backend.ts`/`useSSE`/store）。替换 Arq→Temporal；重写 4 SKILL。
- **测试不打 KSPMAS/github**（D10）：Workflow/Activity 单测用 TestWorkflowEnvironment + FakeRuntime（mock ClaudeRuntime）+ sqlite；e2e 手动真打，不进 CI。
- **Subagent 并行教训**：并行 subagent 指示**只跑自己测试文件、只 git add 自己文件、commit 带 pathspec**（`git commit -m "..." -- <文件>`）；同文件链（tasks.py/api 等）串行派；主控统一跑全量 + 跨文件回归。
- **QuestionPlan JSON schema**（文档 §9）：`{id, category, question, type:single_choice|multi_choice|text, options:[{id,label,impact?,description?}], required, priority:blocking|important|optional, depends_on?:[{question_id, operator:equals|not_equals, value}], default_option?, allow_custom?}`。
- **Requirements Snapshot**（文档 §20）：`{game:{genre,camera,platform,engine}, core_loop:[], v1:{}, decisions:[{id,value,source}], assumptions:[{id,value,source}]}`。game-requirements **不调 LLM**（纯 Python 合成）。
- **GDD Check 三态**（D7）：`{status: PASS|WARNING|BLOCKING, blocking:[], warnings:[]}`。PASS/WARNING→COMPLETED；BLOCKING→回 WAITING_USER。
- **6 状态**（D12）：`CREATED/ANALYZING/WAITING_USER/GENERATING_GDD/CHECKING_GDD/COMPLETED`。
- **commit 规范**：每 task 末提交，前缀按改动类型，结尾 `Co-Authored-By: Kscc <noreply@owtffssent.com>`。
- **不碰阶段 2-5 前端 mock**（沿用前端连接 spec）。

---

## File Structure

```
backend/
├── temporal/                           新增
│   ├── __init__.py
│   ├── client.py                        Task 1：Temporal Client（connect/start/signal/query 封装）
│   ├── workflows.py                     Task 2：GameDesignWorkflow（@defn/run/signal/query/wait_condition）
│   ├── activities.py                    Task 3：analyze_idea/synthesize_requirements/generate_gdd/check_gdd
│   └── worker.py                        Task 7：Temporal Worker（注册 workflow+activities）
├── app/
│   ├── agent/runtime.py                 保留（ClaudeRuntime，Activity 底层）
│   ├── git/service.py                   保留（GitService，finalize）
│   ├── api/projects.py                 改 Task 8：POST /projects 起 Workflow + GET /state + POST /answer/skip/change
│   ├── config/settings.py              改 Task 1：+temporal_host/port/namespace
│   ├── workflow/states.py              改 Task 8：6 状态
│   ├── persistence/repo.py              保留（ProjectRepo/QuestionRepo）
│   └── events/events.py                保留 SSE
├── game-skills/skills/
│   ├── game-brainstorm/SKILL.md         重写 Task 4：产 QuestionPlan JSON
│   ├── game-requirements/SKILL.md       新增 Task 5：纯 Python 合成 Snapshot（SKILL 文档，Activity 不 spawn）
│   ├── gdd-generator/SKILL.md          重写 Task 6：读 Snapshot 生成 GDD
│   └── gdd-check/SKILL.md              重写 Task 6：三态
├── app/agent/prompts.py                 改 Task 4/6：新 system prompts
└── （app/queue/tasks.py/jobs.py/worker.py Arq 版废弃 Task 9）
frontend/
├── api/backend.ts                       改 Task 10：+getState/submitAnswer/skipQuestion/changeAnswer
├── features/1-brainstorm/
│   ├── QuestionCard.tsx                 新增 Task 10：单题（选项+影响+推荐+帮我决定）
│   ├── ProgressStepper.tsx             新增 Task 10：✓/●/○ 进度
│   └── SuperpowerChat.tsx              改 Task 11：逐题驱动（Query 轮询 + SSE）
```

**责任划分**：temporal/client（连接）→ workflows（编排逻辑，最易测用 TestWorkflowEnvironment）→ activities（执行，FakeRuntime mock）→ 4 SKILL（文本）→ worker（注册）→ API（端点）→ 前端。每层接口在 **Interfaces** 块钉死。

---

## Task 0: Docker Temporal Server + temporalio 连通（e2e 前置 spike）

**Files:** 无代码（基建 spike + settings）

**Interfaces:**
- Produces: 运行中的 Temporal Server（Docker）+ 确认 temporalio Python SDK 能连真 Server。

- [ ] **Step 1: 用户启动 Docker Desktop**

用户手动启动 Docker Desktop（GUI），确认 daemon 跑：
```bash
docker info 2>&1 | head -3  # 应有 Server 信息，非 "cannot connect"
```

- [ ] **Step 2: Docker 起 Temporal Server**

```bash
docker run -d --name temporal-dev -p 7233:7233 -p 8233:8233 temporalio/auto-setup:latest
sleep 15
docker ps --filter name=temporal-dev --format "{{.Status}}"  # 应 Up
```

- [ ] **Step 3: Python 连 Temporal + 跑最小 Workflow 验通**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -c "
import asyncio
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return f'hello {name}'

async def main():
    client = await Client.connect('localhost:7233', namespace='default')
    worker = Worker(client, task_queue='test', workflows=[HelloWorkflow])
    await worker.start()
    handle = await client.start_workflow(HelloWorkflow.run, 'temporal', id='hello-1', task_queue='test')
    print(await handle.result())
    await worker.shutdown()
asyncio.run(main())
"
```
Expected: 打印 `hello temporal`。若超时/连不上，检查 Temporal 容器日志 + 端口。

- [ ] **Step 4: 改 settings.py 加 Temporal 配置**

`backend/app/config/settings.py` 加字段：
```python
    temporal_host: str = "localhost"
    temporal_port: int = 7233
    temporal_namespace: str = "default"
    temporal_task_queue: str = "game-design"
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/config/settings.py
git commit -m "chore(temporal): Task0 Docker Temporal Server + settings 配置

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/app/config/settings.py
```

---

## Task 1: temporal/client.py（Temporal Client 封装）

**Files:**
- Create: `backend/temporal/__init__.py`, `backend/temporal/client.py`
- Test: `backend/tests/test_temporal_client.py`

**Interfaces:**
- Consumes: `settings.temporal_host/port/namespace/task_queue`（Task 0）。
- Produces: `get_client() -> Client`（单例）；`start_design_workflow(project_id, idea) -> str`（返 workflow_id）；`send_signal(project_id, sig) -> None`；`query_state(project_id) -> dict`。Task 8 API 用。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_temporal_client.py`:
```python
from __future__ import annotations

import pytest
from temporalio.client import Client


async def test_get_client_returns_client(monkeypatch):
    """get_client 返回 Temporal Client 单例。"""
    from temporal import client as tclient
    # mock Client.connect 避免真连
    captured = {}
    async def fake_connect(target, **kw):
        captured["target"] = target
        return object()  # 假 Client
    monkeypatch.setattr(Client, "connect", fake_connect)
    c = await tclient.get_client()
    assert c is not None
    assert "localhost" in captured["target"] or "7233" in str(captured["target"])
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_client.py -v`
Expected: FAIL（`temporal.client` 未定义）

- [ ] **Step 3: 实现 client.py**

`backend/temporal/__init__.py`：空文件。

`backend/temporal/client.py`:
```python
from __future__ import annotations

from typing import Optional
from temporalio.client import Client

from app.config.settings import get_settings

_client: Optional[Client] = None


async def get_client() -> Client:
    """单例 Temporal Client（连 settings.temporal_host:port）。"""
    global _client
    if _client is None:
        s = get_settings()
        _client = await Client.connect(f"{s.temporal_host}:{s.temporal_port}", namespace=s.temporal_namespace)
    return _client


async def start_design_workflow(project_id: int, idea: str) -> str:
    """起 GameDesignWorkflow，返 workflow_id。"""
    from .workflows import GameDesignWorkflow
    s = get_settings()
    client = await get_client()
    handle = await client.start_workflow(
        GameDesignWorkflow.run, idea,
        id=f"game-{project_id}", task_queue=s.temporal_task_queue,
    )
    return handle.id


async def send_signal(project_id: int, signal_name: str, signal_arg) -> None:
    """发 Signal 到 Workflow。"""
    from .workflows import GameDesignWorkflow
    client = await get_client()
    handle = client.get_workflow_handle(f"game-{project_id}")
    await handle.signal(getattr(GameDesignWorkflow, signal_name), signal_arg)


async def query_state(project_id: int) -> dict:
    """Query get_design_state。"""
    from .workflows import GameDesignWorkflow
    client = await get_client()
    handle = client.get_workflow_handle(f"game-{project_id}")
    return await handle.query(GameDesignWorkflow.get_design_state)
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_client.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/temporal/__init__.py backend/temporal/client.py backend/tests/test_temporal_client.py
git commit -m "feat(temporal): client.py Temporal Client 封装（get_client/start/signal/query）

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/temporal/__init__.py backend/temporal/client.py backend/tests/test_temporal_client.py
```

---

## Task 2: temporal/workflows.py GameDesignWorkflow（核心编排）

**Files:**
- Create: `backend/temporal/workflows.py`
- Test: `backend/tests/test_temporal_workflows.py`

**Interfaces:**
- Consumes: `analyze_idea`/`synthesize_requirements`/`generate_gdd`/`check_gdd` Activity（Task 3，单测用 mock）。
- Produces: `GameDesignWorkflow`（`@workflow.run run(idea) -> dict`、`@workflow.signal submit_answer(sig)`、`@workflow.query get_design_state() -> dict`、`@workflow.signal skip_question(qid)`、`@workflow.signal change_answer(sig)`）；`AnswerSignal` dataclass（`question_id/answer/action`）。Task 1 client / Task 7 worker / Task 8 API 用。

- [ ] **Step 1: 写失败测试（TestWorkflowEnvironment）**

`backend/tests/test_temporal_workflows.py`:
```python
from __future__ import annotations

import asyncio
import pytest
from dataclasses import dataclass
from temporalio import workflow, activity
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

from temporal.workflows import GameDesignWorkflow, AnswerSignal


# Mock activities（单测不真 spawn claude）
@activity.defn
async def mock_analyze_idea(idea: str) -> list[dict]:
    return [
        {"id": "camera", "category": "camera", "question": "视角？", "type": "single_choice",
         "options": [{"id": "top_down", "label": "俯视"}, {"id": "side", "label": "横版"}],
         "required": True, "priority": "blocking"},
        {"id": "core_loop", "category": "core_loop", "question": "核心玩法？", "type": "single_choice",
         "options": [{"id": "farming", "label": "种田"}], "required": True, "priority": "blocking"},
    ]

@activity.defn
async def mock_synthesize_requirements(qp, answers) -> dict:
    return {"game": {"camera": answers.get("camera", "top_down")}, "core_loop": ["plant","harvest"], "v1": {}, "decisions": [], "assumptions": []}

@activity.defn
async def mock_generate_gdd(req) -> str:
    return "# GDD\n"

@activity.defn
async def mock_check_gdd(gdd) -> dict:
    return {"status": "PASS", "blocking": [], "warnings": []}


async def test_workflow_signal_advances_questions():
    """Signal submit_answer 推进逐题，答完→synthesize→gdd→check→COMPLETED。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        worker = Worker(env.client, "test-queue", [
            GameDesignWorkflow, mock_analyze_idea, mock_synthesize_requirements, mock_generate_gdd, mock_check_gdd,
        ])
        await worker.start()
        handle = await env.client.start_workflow(
            GameDesignWorkflow.run, "种田游戏", id="game-test-1", task_queue="test-queue",
        )
        # 初始：WAITING_USER，0/2
        state = await handle.query(GameDesignWorkflow.get_design_state)
        assert state["phase"] == "WAITING_USER"
        assert state["progress"]["answered"] == 0
        # 答 camera
        await handle.signal(GameDesignWorkflow.submit_answer, AnswerSignal("camera", "top_down"))
        await asyncio.sleep(0.3)
        state = await handle.query(GameDesignWorkflow.get_design_state)
        assert state["progress"]["answered"] == 1
        # 答 core_loop
        await handle.signal(GameDesignWorkflow.submit_answer, AnswerSignal("core_loop", "farming"))
        result = await handle.result()
        assert result["check"]["status"] == "PASS"
        final = await handle.query(GameDesignWorkflow.get_design_state)
        assert final["phase"] == "COMPLETED"
    finally:
        await env.shutdown()


async def test_workflow_skip_uses_default():
    """skip_question 跳过题（用 default_option 或留空）。"""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        worker = Worker(env.client, "test-queue", [GameDesignWorkflow, mock_analyze_idea, mock_synthesize_requirements, mock_generate_gdd, mock_check_gdd])
        await worker.start()
        handle = await env.client.start_workflow(GameDesignWorkflow.run, "test", id="game-skip-1", task_queue="test-queue")
        await handle.signal(GameDesignWorkflow.skip_question, "camera")
        await handle.signal(GameDesignWorkflow.submit_answer, AnswerSignal("core_loop", "farming"))
        result = await handle.result()
        assert result["check"]["status"] == "PASS"
    finally:
        await env.shutdown()
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_workflows.py -v`
Expected: FAIL（`temporal.workflows` 未定义）

- [ ] **Step 3: 实现 workflows.py**

`backend/temporal/workflows.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from temporalio import workflow


@dataclass
class AnswerSignal:
    question_id: str
    answer: str | None = None
    action: str = "answer"  # answer / change


@workflow.defn
class GameDesignWorkflow:
    """阶段1 GameDesignWorkflow（Temporal Human-in-the-Loop）。

    流程：analyze_idea（产 QuestionPlan）→ 逐题 wait_condition（Signal 推进）
    → synthesize_requirements → generate_gdd → check_gdd → PASS/WARNING=COMPLETED / BLOCKING=回 WAITING_USER。
    """

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
        # 逐题等待
        await self._ask_questions()
        self.phase = "GENERATING_GDD"
        self.requirements = await workflow.execute_activity(
            "synthesize_requirements", args=[self.question_plan, self.answers],
            start_to_close_timeout=timedelta(minutes=5),
        )
        self.gdd = await workflow.execute_activity(
            "generate_gdd", args=[self.requirements], start_to_close_timeout=timedelta(minutes=15),
        )
        self.phase = "CHECKING_GDD"
        check = await workflow.execute_activity(
            "check_gdd", args=[self.gdd], start_to_close_timeout=timedelta(minutes=15),
        )
        if check["status"] in ("PASS", "WARNING"):
            self.phase = "COMPLETED"
            return {"gdd": self.gdd, "check": check, "requirements": self.requirements}
        # BLOCKING → 回 WAITING_USER 补充
        self.phase = "WAITING_USER"
        clarification = await workflow.execute_activity(
            "generate_clarification", args=[check], start_to_close_timeout=timedelta(minutes=10),
        )
        self.question_plan.extend(clarification.get("questions", []))
        await self._ask_questions()  # 再答补充题
        # 简化：BLOCKING 补答后直接重生成 GDD（不再 check 循环，e2e 看效果定）
        self.requirements = await workflow.execute_activity(
            "synthesize_requirements", args=[self.question_plan, self.answers], start_to_close_timeout=timedelta(minutes=5))
        self.gdd = await workflow.execute_activity("generate_gdd", args=[self.requirements], start_to_close_timeout=timedelta(minutes=15))
        self.phase = "COMPLETED"
        return {"gdd": self.gdd, "check": check, "requirements": self.requirements}

    async def _ask_questions(self):
        """逐题 wait_condition，跳过 optional + 不满足 depends_on 的题。"""
        for q in self.question_plan:
            qid = q["id"]
            if q.get("priority") == "optional":
                continue
            if not self._should_ask(q):
                continue
            self.phase = "WAITING_USER"
            await workflow.wait_condition(lambda qid=qid: qid in self.answers or qid in self.skipped)

    def _should_ask(self, q: dict) -> bool:
        """depends_on 检查：所有依赖条件满足才问。"""
        for dep in q.get("depends_on", []):
            ans = self.answers.get(dep["question_id"])
            if ans is None:
                return False
            if dep.get("operator", "equals") == "equals" and ans != dep["value"]:
                return False
        return True

    @workflow.signal
    async def submit_answer(self, sig: AnswerSignal):
        self.answers[sig.question_id] = sig.answer or ""

    @workflow.signal
    async def skip_question(self, question_id: str):
        self.skipped.add(question_id)
        # 若有 default_option 填入（Activity synthesize 会用）
        for q in self.question_plan:
            if q["id"] == question_id and q.get("default_option"):
                self.answers[question_id] = q["default_option"]

    @workflow.signal
    async def change_answer(self, sig: AnswerSignal):
        self.answers[sig.question_id] = sig.answer or ""
        # 改答案后清空后续依赖该题的答案（重算依赖会重新问）
        # 简化：不清空，让用户重新答（e2e 看效果定）

    @workflow.query
    def get_design_state(self) -> dict:
        """Query：返回可观察状态（phase/progress/currentQuestion/decisions）。"""
        current = None
        for q in self.question_plan:
            if q.get("priority") == "optional":
                continue
            if q["id"] not in self.answers and q["id"] not in self.skipped and self._should_ask(q):
                current = {"id": q["id"], "category": q.get("category"), "question": q["question"],
                           "options": q.get("options", []), "priority": q.get("priority")}
                break
        return {
            "phase": self.phase,
            "progress": {"answered": len(self.answers), "total": len([q for q in self.question_plan if q.get("priority") != "optional"])},
            "currentQuestion": current,
            "decisions": [{"id": k, "answer": v} for k, v in self.answers.items()],
        }
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_workflows.py -v`
Expected: PASS（2 测试：signal 推进 / skip 用 default）

- [ ] **Step 5: 提交**

```bash
git add backend/temporal/workflows.py backend/tests/test_temporal_workflows.py
git commit -m "feat(temporal): GameDesignWorkflow（@run/signal/query/wait_condition 逐题+三态）

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/temporal/workflows.py backend/tests/test_temporal_workflows.py
```

---

## Task 3: temporal/activities.py（Activity 执行层）

**Files:**
- Create: `backend/temporal/activities.py`
- Test: `backend/tests/test_temporal_activities.py`

**Interfaces:**
- Consumes: `ClaudeRuntime`（`start(prompt,cwd,project_id,agent_type,system_prompt,plugin_dir)`，保留）；prompts（Task 4/6）；`get_settings`（game_skills_dir/REPO_ROOT）。
- Produces: `analyze_idea(idea) -> list[dict]`（spawn 02 产 QuestionPlan JSON）；`synthesize_requirements(qp, answers) -> dict`（纯 Python，不调 LLM）；`generate_gdd(requirements) -> str`（spawn 03）；`check_gdd(gdd) -> dict`（spawn 04 三态）；`generate_clarification(check) -> dict`。Task 2 Workflow 调。

- [ ] **Step 1: 写失败测试（FakeRuntime + 纯 Python synthesize）**

`backend/tests/test_temporal_activities.py`:
```python
from __future__ import annotations

import json
import pytest
from temporal import activities


class FakeRuntime:
    """Fake ClaudeRuntime：spawn 返预设 result。"""
    def __init__(self, result_text):
        self.result = result_text
    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
        from app.schemas.event import CoworkEvent
        yield CoworkEvent(project_id=project_id, type="agent.session.started", data={"session_id": "s1"})
        yield CoworkEvent(project_id=project_id, type="agent.session.completed",
                          data={"session_id": "s1", "result": self.result, "stop_reason": "end_turn"})


QUESTION_PLAN_JSON = json.dumps({"questions": [
    {"id": "camera", "category": "camera", "question": "视角？", "type": "single_choice",
     "options": [{"id": "top_down", "label": "俯视"}], "required": True, "priority": "blocking"}
]})


async def test_analyze_idea_parses_json(monkeypatch):
    """analyze_idea spawn 02，解析 QuestionPlan JSON。"""
    monkeypatch.setattr(activities, "ClaudeRuntime", lambda: FakeRuntime(QUESTION_PLAN_JSON))
    monkeypatch.setattr(activities, "_worktree_cwd", lambda pid: "/fake/cwd")
    qp = await activities.analyze_idea("种田游戏")
    assert isinstance(qp, list)
    assert qp[0]["id"] == "camera"
    assert qp[0]["options"][0]["label"] == "俯视"


async def test_synthesize_requirements_pure_python():
    """synthesize_requirements 纯 Python（不调 LLM）：QuestionPlan+Answers→Snapshot。"""
    qp = [{"id": "camera", "category": "camera", "default_option": "top_down", "priority": "blocking"}]
    answers = {"camera": "top_down"}
    snap = await activities.synthesize_requirements(qp, answers)
    assert snap["game"]["camera"] == "top_down"
    assert {"id": "camera", "value": "top_down", "source": "user"} in snap["decisions"]


async def test_check_gdd_parses_three_state(monkeypatch):
    """check_gdd spawn 04，解析三态 JSON。"""
    monkeypatch.setattr(activities, "ClaudeRuntime", lambda: FakeRuntime(
        json.dumps({"status": "PASS", "blocking": [], "warnings": ["economy provisional"]})))
    monkeypatch.setattr(activities, "_worktree_cwd", lambda pid: "/fake/cwd")
    result = await activities.check_gdd("# GDD\n")
    assert result["status"] == "PASS"
    assert "economy provisional" in result["warnings"][0]
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_activities.py -v`
Expected: FAIL（`temporal.activities` 未定义）

- [ ] **Step 3: 实现 activities.py**

`backend/temporal/activities.py`:
```python
from __future__ import annotations

import json
import os
from pathlib import Path

from temporalio import activity

from app.agent.runtime import ClaudeRuntime
from app.agent.prompts import (
    GAME_BRAINSTORM_PROMPT, GDD_GEN_PROMPT, GDD_CHECK_PROMPT,
)
from app.config.settings import get_settings, REPO_ROOT


def _worktree_cwd(project_id: int) -> str:
    """查 project 的 worktree/games/{key} 路径。Activity 内不真查 DB（Workflow 传 cwd）。
    简化：Activity 接收 cwd 参数（实现期调整 run/Activity 签名传 cwd）。单测 monkeypatch 此函数。"""
    s = get_settings()
    # 实现期：从 project_key 推导，或 Workflow 传入。先占位。
    return "/fake/cwd"


async def _spawn_skill(skill_prompt: str, system_prompt: str, project_id: int) -> str:
    """spawn claude（--bare --plugin-dir），抓 session.completed.result 返回。"""
    runtime = ClaudeRuntime()
    cwd = _worktree_cwd(project_id)
    s = get_settings()
    plugin_dir = str(REPO_ROOT / s.game_skills_dir)
    result = ""
    async for evt in runtime.start(
        skill_prompt, cwd, project_id, agent_type="temporal-activity",
        system_prompt=system_prompt, plugin_dir=plugin_dir,
    ):
        if evt.type == "agent.session.completed":
            result = evt.data.get("result", "")
    return result


def _parse_json(text: str) -> dict | list:
    """容错解析 JSON（kimi-k3 可能含 ```json 包裹或前言）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text
        if text.startswith("json"):
            text = text[4:]
    # 找首个 { 或 [
    for i, ch in enumerate(text):
        if ch in "{[":
            text = text[i:]
            break
    for i in range(len(text) - 1, -1, -1):
        if text[i] in "}]":
            text = text[:i+1]
            break
    return json.loads(text)


@activity.defn
async def analyze_idea(idea: str) -> list[dict]:
    """Activity: spawn 02 game-brainstorm 产 QuestionPlan JSON。"""
    result = await _spawn_skill(
        f"用户游戏创意：{idea}\n请调用 /game-brainstorm 产出 QuestionPlan JSON。",
        GAME_BRAINSTORM_PROMPT, project_id=0,  # 实现期：Workflow 传 project_id（或从 idea 推）
    )
    parsed = _parse_json(result)
    return parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed


@activity.defn
async def synthesize_requirements(question_plan: list[dict], answers: dict[str, str]) -> dict:
    """Activity: 纯 Python 合成 Requirements Snapshot（不调 LLM，D6）。"""
    snapshot = {"game": {}, "core_loop": [], "v1": {}, "decisions": [], "assumptions": []}
    cat_map = {"camera": "camera", "core_loop": "genre", "platform": "platform"}  # category→snapshot 字段
    for q in question_plan:
        qid = q["id"]
        ans = answers.get(qid, q.get("default_option", ""))
        cat = q.get("category", qid)
        if cat in cat_map:
            snapshot["game"][cat_map[cat]] = ans
        elif cat == "core_loop":
            snapshot["core_loop"] = [ans] if ans else []
        else:
            snapshot["v1"][cat] = ans
        snapshot["decisions"].append({"id": qid, "value": ans, "source": "user" if qid in answers else "default"})
    return snapshot


@activity.defn
async def generate_gdd(requirements: dict) -> str:
    """Activity: spawn 03 gdd-generator 读 Requirements Snapshot 生成 GDD.md。"""
    result = await _spawn_skill(
        f"Requirements Snapshot（JSON）：{json.dumps(requirements, ensure_ascii=False)}\n请调用 /gdd-generator 生成 GDD.md。",
        GDD_GEN_PROMPT, project_id=0,
    )
    return result


@activity.defn
async def check_gdd(gdd: str) -> dict:
    """Activity: spawn 04 gdd-check → 三态 JSON。"""
    result = await _spawn_skill(
        f"请检查以下 GDD 是否能让 Code Agent 做 V1：\n{gdd}\n请调用 /gdd-check 输出三态 JSON。",
        GDD_CHECK_PROMPT, project_id=0,
    )
    return _parse_json(result)


@activity.defn
async def generate_clarification(check: dict) -> dict:
    """Activity: BLOCKING 时生成补充问题（spawn claude 或纯 Python）。简化：纯 Python 返回空。"""
    return {"questions": []}
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_activities.py -v`
Expected: PASS（3 测试）

- [ ] **Step 5: 提交**

```bash
git add backend/temporal/activities.py backend/tests/test_temporal_activities.py
git commit -m "feat(temporal): activities（analyze_idea/synthesize纯Python/generate_gdd/check_gdd三态）

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/temporal/activities.py backend/tests/test_temporal_activities.py
```

---

## Task 4: game-brainstorm SKILL 重写（QuestionPlan JSON）+ prompts

**Files:**
- Modify: `backend/game-skills/skills/game-brainstorm/SKILL.md`（若旧名 02-game-brainstorm 则改名/新建）
- Modify: `backend/app/agent/prompts.py`
- Test: `backend/tests/test_skills.py`（改断言）

**Interfaces:**
- Produces: game-brainstorm SKILL 输出 QuestionPlan JSON（文档 §9 schema，选项带 impact）；`GAME_BRAINSTORM_PROMPT`（指示产 JSON）。

- [ ] **Step 1: 重写 game-brainstorm/SKILL.md**

```markdown
---
name: game-brainstorm
description: 输入用户游戏创意，产出结构化 QuestionPlan JSON（决策树+依赖+优先级+影响），供 Temporal 逐题询问
---

You are the Game Brainstorm skill. Given the user's game idea, output a **QuestionPlan JSON** identifying the design decisions that need clarification. Do NOT ask the user directly; do NOT write files.

## Output format (STRICT JSON)
\`\`\`json
{
  "questions": [
    {
      "id": "camera",
      "category": "camera",
      "question": "你希望采用什么视角？",
      "type": "single_choice",
      "options": [
        {"id": "top_down", "label": "俯视角", "impact": "适合牧场/经营类2D游戏"},
        {"id": "side", "label": "横版", "impact": "更适合平台跳跃/横向探索"}
      ],
      "required": true,
      "priority": "blocking",
      "default_option": "top_down",
      "allow_custom": true
    }
  ]
}
\`\`\`

## Rules
- 4-6 questions. Only `blocking` + `important` priority (no `optional`).
- Every option MUST have `impact` (设计后果说明).
- Use `depends_on` for conditional questions (e.g. NPC relationship depends on npc=social).
- Cover: camera, core_loop, v1_scope, npc, progression as relevant to the idea.
- Output ONLY the JSON (no preamble, no ``` fences in content).
- Stay neutral (avoid policy-flagged wording).
```

- [ ] **Step 2: 改 prompts.py 加 GAME_BRAINSTORM_PROMPT**

`backend/app/agent/prompts.py` 末尾加：
```python
# Temporal 重构版 prompts
GAME_BRAINSTORM_PROMPT = """You are running the game-brainstorm skill to produce a QuestionPlan JSON.

Steps:
1. Invoke /game-brainstorm.
2. It outputs a JSON with 4-6 questions (blocking+important priority, options with impact, depends_on).
3. Your reply's content IS the JSON (strict, no preamble, no code fences).

Rules: do not call Write; do not generate GDD; keep JSON strict (backend parses it).
"""

GDD_GEN_PROMPT = """You are running the gdd-generator skill to produce GDD.md from a Requirements Snapshot.

Steps:
1. Invoke /gdd-generator.
2. It reads the Requirements Snapshot (provided in the prompt) and calls Write to produce GDD.md in the cwd.
3. Reply with a one-line summary.

Rules: only use Read/Write; do not re-interpret the game (read from Snapshot, do not add systems not in Snapshot).
"""

GDD_CHECK_PROMPT = """You are running the gdd-check skill — a hard gate.

Steps:
1. Invoke /gdd-check.
2. It checks if a Code Agent can build V1 from this GDD.
3. Output JSON: {status: PASS|WARNING|BLOCKING, blocking: [...], warnings: [...]}

Rules: only use Read; output strict JSON.
"""
```

- [ ] **Step 3: 改 test_skills.py 断言**

```python
def test_brainstorm_skill_constraints():
    s = _read("game-brainstorm")  # 新名
    assert "QuestionPlan" in s or "question" in s.lower()
    assert "impact" in s  # 选项带影响
    assert "priority" in s
    assert "JSON" in s or "json" in s
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_skills.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/game-skills/skills/game-brainstorm/ backend/app/agent/prompts.py backend/tests/test_skills.py
git commit -m "feat(skills): game-brainstorm 重写产 QuestionPlan JSON + prompts

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/game-skills/skills/game-brainstorm/ backend/app/agent/prompts.py backend/tests/test_skills.py
```

---

## Task 5: game-requirements SKILL 文档（纯 Python 合成，Activity 不 spawn）

**Files:**
- Create: `backend/game-skills/skills/game-requirements/SKILL.md`（文档，Activity 内纯 Python，不 spawn）
- Test: `backend/tests/test_synthesize.py`（测 synthesize_requirements 纯 Python 逻辑，Task 3 已有部分）

**Interfaces:**
- Produces: game-requirements SKILL 文档（说明合成规则，供人读；Activity `synthesize_requirements` 纯 Python 实现已 Task 3 完成）。

- [ ] **Step 1: 建 game-requirements/SKILL.md**

```markdown
---
name: game-requirements
description: QuestionPlan + Answers + Defaults → Requirements Snapshot（SSOT）。纯合成，不调 LLM。
---

## 作用
把 game-brainstorm 的 QuestionPlan + 用户答案 + 默认值合成为 **Requirements Snapshot**（单一事实来源 SSOT）。

## 实现
**不 spawn claude、不调 LLM**——后端 `synthesize_requirements` Activity 内纯 Python 合成：
- 按 question 的 `category` 填 snapshot 字段（camera→game.camera, core_loop→game.genre）
- 未答的题用 `default_option`
- 每个决策记入 `decisions`（source: user/default）

## Snapshot schema（文档 §20）
\`\`\`json
{
  "game": {"genre", "camera", "platform", "engine"},
  "core_loop": ["plant", "grow", "harvest", "sell"],
  "v1": {"map", "crops", "npc", "shop"},
  "decisions": [{"id", "value", "source"}],
  "assumptions": [{"id", "value", "source": "system_default"}]
}
\`\`\`

后续 gdd-generator / Asset / Code 都从此 Snapshot 派生。
```

- [ ] **Step 2: 跑 test_synthesize（Task 3 已有 test_synthesize_requirements_pure_python）**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_temporal_activities.py::test_synthesize_requirements_pure_python -v`
Expected: PASS（验证纯 Python 合成）

- [ ] **Step 3: 提交**

```bash
git add backend/game-skills/skills/game-requirements/
git commit -m "feat(skills): game-requirements SKILL 文档（纯 Python 合成 Snapshot，不调 LLM）

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/game-skills/skills/game-requirements/
```

---

## Task 6: gdd-generator + gdd-check SKILL 重写

**Files:**
- Modify: `backend/game-skills/skills/gdd-generator/SKILL.md`
- Modify: `backend/game-skills/skills/gdd-check/SKILL.md`
- Test: `backend/tests/test_skills.py`（改断言）

**Interfaces:**
- Produces: gdd-generator 读 Requirements Snapshot 生成 GDD.md（不重新理解游戏）；gdd-check 输出三态 JSON。

- [ ] **Step 1: 重写 gdd-generator/SKILL.md**

```markdown
---
name: gdd-generator
description: 读 Requirements Snapshot 生成 GDD.md（不重新理解游戏，从 SSOT 派生）
---

You are the GDD Generator skill. Input: **Requirements Snapshot** (JSON, provided in the prompt). Output: `GDD.md` via Write.

## Critical rule
**Do NOT re-interpret the game.** Read decisions strictly from the Snapshot. If Snapshot says `npc: false`, do NOT add NPC systems.

## GDD.md — 12 sections（文档 §14）
1. Game Goal  2. Core Loop  3. Player  4. Core Systems  5. Game Entities  6. Scenes/Maps
7. Input  8. UI  9. Assets  10. Progression  11. V1 Scope  12. Acceptance Criteria

## Rules
- Only use Read/Write. Write GDD.md in cwd.
- Stay neutral (avoid policy-flagged wording).
- After writing, reply one-line summary.
```

- [ ] **Step 2: 重写 gdd-check/SKILL.md**

```markdown
---
name: gdd-check
description: 检查 GDD 能否让 Code Agent 做 V1，输出三态 JSON（PASS/WARNING/BLOCKING）
---

You are the GDD Check skill — a hard gate. Input: `GDD.md`. Output: **three-state JSON**.

## Check criteria
- **BLOCKING**: core loop unclear / no V1 goal / core system rules missing / no playable loop → cannot build V1.
- **WARNING**: NPC values unbalanced / prices undecided / audio undecided → doesn't block V1.
- **PASS**: core loop + V1 scope + systems + input + acceptance criteria all clear.

## Output format (STRICT JSON)
\`\`\`json
{"status": "PASS", "blocking": [], "warnings": ["economy provisional"]}
\`\`\`

## Rules
- Only use Read; do not modify files.
- Output ONLY the JSON.
```

- [ ] **Step 3: 改 test_skills.py 断言**

```python
def test_gdd_generator_skill_constraints():
    s = _read("gdd-generator")
    assert "Snapshot" in s or "Requirements" in s
    assert "GDD.md" in s
    assert "Do NOT re-interpret" in s or "不重新" in s

def test_gdd_check_skill_constraints():
    s = _read("gdd-check")
    assert "PASS" in s and "WARNING" in s and "BLOCKING" in s
    assert "JSON" in s or "json" in s
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_skills.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/game-skills/skills/gdd-generator/SKILL.md backend/game-skills/skills/gdd-check/SKILL.md backend/tests/test_skills.py
git commit -m "feat(skills): gdd-generator 读 Snapshot + gdd-check 三态 JSON

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/game-skills/skills/gdd-generator/SKILL.md backend/game-skills/skills/gdd-check/SKILL.md backend/tests/test_skills.py
```

---

## Task 7: temporal/worker.py（Temporal Worker）

**Files:**
- Create: `backend/temporal/worker.py`
- Test: 无单测（worker 注册，e2e 验）

**Interfaces:**
- Produces: `run_worker()` async 函数（连 Temporal Server + 注册 GameDesignWorkflow + 4 activities + run）；可 `python -m temporal.worker` 起。

- [ ] **Step 1: 实现 worker.py**

`backend/temporal/worker.py`:
```python
from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from temporal.client import get_client
from temporal.workflows import GameDesignWorkflow
from temporal.activities import (
    analyze_idea, synthesize_requirements, generate_gdd, check_gdd, generate_clarification,
)
from app.config.settings import get_settings


async def run_worker():
    """起 Temporal Worker：注册 GameDesignWorkflow + activities。"""
    s = get_settings()
    client = await get_client()
    worker = Worker(
        client, task_queue=s.temporal_task_queue,
        workflows=[GameDesignWorkflow],
        activities=[analyze_idea, synthesize_requirements, generate_gdd, check_gdd, generate_clarification],
    )
    print(f"Temporal Worker started on queue={s.temporal_task_queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
```

- [ ] **Step 2: 起 worker 验不崩（连真 Temporal Server，Task 0 已起）**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m temporal.worker 2>&1 | head -5
```
Expected: 打印 `Temporal Worker started`（连不上 Temporal 会报错——确保 Task 0 的 Docker Temporal 在跑）。

- [ ] **Step 3: 提交**

```bash
git add backend/temporal/worker.py
git commit -m "feat(temporal): worker.py 注册 GameDesignWorkflow + activities

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/temporal/worker.py
```

---

## Task 8: API 改（POST /projects 起 Workflow + GET /state + POST /answer/skip/change）

**Files:**
- Modify: `backend/app/api/projects.py`
- Modify: `backend/app/workflow/states.py`（6 状态）
- Modify: `backend/app/services/project_service.py`（create 起 Workflow）
- Test: `backend/tests/test_api_temporal.py`

**Interfaces:**
- Consumes: `temporal.client.start_design_workflow/send_signal/query_state`（Task 1）。
- Produces: `POST /api/projects` 起 Workflow；`GET /api/projects/{id}/state` Query；`POST /api/projects/{id}/answer` Signal；`POST /skip`；`POST /change`；`POST /finalize`（保留 GitService）。

- [ ] **Step 1: 改 states.py 6 状态**

```python
class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    WAITING_USER = "WAITING_USER"
    GENERATING_GDD = "GENERATING_GDD"
    CHECKING_GDD = "CHECKING_GDD"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_api_temporal.py`:
```python
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base


@pytest_asyncio.fixture
async def client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override():
        async with sm() as s:
            yield s
    app.dependency_overrides[get_session] = override
    # mock Temporal client
    async def fake_start(pid, idea): return f"game-{pid}"
    async def fake_query(pid): return {"phase": "WAITING_USER", "progress": {"answered": 0, "total": 2}, "currentQuestion": {"id": "camera"}, "decisions": []}
    async def fake_signal(pid, name, arg): pass
    monkeypatch.setattr("app.api.projects.start_design_workflow", fake_start)
    monkeypatch.setattr("app.api.projects.query_state", fake_query)
    monkeypatch.setattr("app.api.projects.send_signal", fake_signal)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_create_project_starts_workflow(client):
    r = await client.post("/api/projects", json={"name": "Test", "description": "种田"})
    assert r.status_code == 201
    # 应起 Workflow（mock fake_start 返 game-{id}）


async def test_get_state(client):
    # 先建 project（mock），再 GET state
    await client.post("/api/projects", json={"name": "T", "description": "idea"})
    r = await client.get("/api/projects/1/state")
    assert r.status_code == 200
    data = r.json()
    assert data["phase"] == "WAITING_USER"
    assert data["currentQuestion"]["id"] == "camera"


async def test_submit_answer(client):
    await client.post("/api/projects", json={"name": "T", "description": "idea"})
    r = await client.post("/api/projects/1/answer", json={"question_id": "camera", "answer": "top_down"})
    assert r.status_code == 202
```

- [ ] **Step 3: 改 api/projects.py**

import 改：删 Arq jobs import，加 `from temporal.client import start_design_workflow, send_signal, query_state`。保留 `enqueue_finalize`（或迁 Temporal）。改端点：
```python
@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_project(body, session=Depends(get_session)):
    p = await project_service.create(session, name=body.name, description=body.description)
    await session.commit()
    await start_design_workflow(p.id, body.description or body.name)  # 起 Workflow
    return ProjectRead(...)

@router.get("/projects/{pid}/state")
async def get_state(pid: int):
    return await query_state(pid)

@router.post("/projects/{pid}/answer", status_code=202)
async def submit_answer(pid: int, body: AnswerBody):
    from temporal.workflows import AnswerSignal
    await send_signal(pid, "submit_answer", AnswerSignal(body.answers[0]["question_id"], body.answers[0]["answer"]))
    return {"ok": True}

@router.post("/projects/{pid}/skip", status_code=202)
async def skip_question(pid: int, body: dict):
    await send_signal(pid, "skip_question", body["question_id"])
    return {"ok": True}
```
（answer/skip/change 端点视 schema 简化）

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_temporal.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/projects.py backend/app/workflow/states.py backend/app/services/project_service.py backend/tests/test_api_temporal.py
git commit -m "feat(api): POST /projects 起 Workflow + GET /state Query + POST /answer Signal

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/app/api/projects.py backend/app/workflow/states.py backend/app/services/project_service.py backend/tests/test_api_temporal.py
```

---

## Task 9: 旧 Arq 代码废弃 + 既有测试回归

**Files:**
- Modify: `backend/app/queue/tasks.py`（删 run_brainstorm_questions/generate，保留 run_finalize）
- Modify: `backend/app/queue/jobs.py`（删 enqueue_brainstorm_*）
- Modify: `backend/app/queue/worker.py`（删 run_brainstorm_*，仅留 run_finalize 或全删）
- 改/删相关测试

**Interfaces:**
- Produces: Arq 编排代码清理（run_brainstorm_questions/generate 废弃），Temporal 替代。

- [ ] **Step 1: 删 run_brainstorm_questions/generate（tasks.py）**

保留 `run_finalize`（GitService 落 git，Phase 2 既有）+ `run_gdd_check`（若 finalize 不用则删）。删 `run_brainstorm_questions`/`run_brainstorm_generate`。

- [ ] **Step 2: 删 enqueue_brainstorm_questions/generate（jobs.py）**

保留 `enqueue_finalize`。

- [ ] **Step 3: 改 worker.py（Arq）**

若 run_finalize 仍用 Arq：`functions=[run_finalize]`；否则删 worker.py（全迁 Temporal）。简化：保留 Arq 仅 finalize，`functions=[run_finalize]`。

- [ ] **Step 4: 删/改测试**

删 `test_tasks_brainstorm_questions.py`/`test_tasks_brainstorm_generate.py`/`test_api_brainstorm_answer.py`（Arq 版）。改 `test_tasks_worker.py`（删 run_brainstorm 引用，保留 fake 共享）。跑全量确认。

- [ ] **Step 5: 提交**

```bash
git add -A backend/app/queue/ backend/tests/
git commit -m "refactor(queue): 废弃 Arq run_brainstorm_*，Temporal 替代（保留 run_finalize）

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- backend/app/queue/ backend/tests/
```

---

## Task 10: 前端 api/backend.ts + QuestionCard/ProgressStepper 组件

**Files:**
- Modify: `frontend/src/api/backend.ts`（+getState/submitAnswer/skipQuestion）
- Create: `frontend/src/features/1-brainstorm/QuestionCard.tsx`
- Create: `frontend/src/features/1-brainstorm/ProgressStepper.tsx`

**Interfaces:**
- Produces: `getState(id)`/`submitAnswer(id,qid,answer)`/`skipQuestion(id,qid)`；QuestionCard（单题+选项+影响+推荐+帮我决定）；ProgressStepper（✓/●/○）。

- [ ] **Step 1: 改 api/backend.ts 加 getState/submitAnswer/skipQuestion**

```typescript
export interface DesignState { phase: string; progress: {answered: number; total: number}; currentQuestion: {id:string; question:string; options:{id:string;label:string;impact?:string}[]; priority?:string} | null; decisions: {id:string;answer:string}[] }
export async function getState(id: number): Promise<DesignState> { return j(await fetch(`${BASE}/projects/${id}/state`)) }
export async function submitAnswer(id: number, questionId: string, answer: string): Promise<void> { await j(await fetch(`${BASE}/projects/${id}/answer`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question_id:questionId,answer})})) }
export async function skipQuestion(id: number, questionId: string): Promise<void> { await j(await fetch(`${BASE}/projects/${id}/skip`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question_id:questionId})})) }
```

- [ ] **Step 2: 建 QuestionCard.tsx**

```tsx
import { useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'

export function QuestionCard() {
  const state = useGameStore((s) => s.designState)
  const submit = useGameStore((s) => s.submitAnswer)
  const skip = useGameStore((s) => s.skipQuestion)
  const q = state?.currentQuestion
  if (!q) return <div className="p-4 text-sm text-ink-3">等待中…</div>
  return (
    <div className="space-y-3 p-4">
      <div className="text-base font-medium text-ink">{q.question}</div>
      {q.options.map((o) => (
        <button key={o.id} onClick={() => submit(q.id, o.id)} className="block w-full rounded-lg border border-line/70 p-3 text-left text-sm hover:bg-surface-2">
          <span className="font-medium">{o.label}</span>
          {o.impact && <span className="ml-2 text-xs text-ink-3">→ {o.impact}</span>}
        </button>
      ))}
      <Button variant="ghost" onClick={() => skip(q.id)}>帮我决定</Button>
    </div>
  )
}
```

- [ ] **Step 3: 建 ProgressStepper.tsx**

```tsx
import { useGameStore } from '@/store/useGameStore'

export function ProgressStepper() {
  const state = useGameStore((s) => s.designState)
  if (!state) return null
  const { answered, total } = state.progress
  return (
    <div className="px-4 py-2 text-xs text-ink-2">
      需求确认 {answered} / {total}
      <div className="mt-1 flex gap-1">
        {Array.from({length: total}).map((_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded ${i < answered ? 'bg-accent' : 'bg-line'}`} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 验 tsc**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -E "QuestionCard|ProgressStepper|backend.ts" | wc -l`
Expected: 0（新文件无错）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/backend.ts frontend/src/features/1-brainstorm/QuestionCard.tsx frontend/src/features/1-brainstorm/ProgressStepper.tsx
git commit -m "feat(frontend): QuestionCard + ProgressStepper + getState/submitAnswer API

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- frontend/src/api/backend.ts frontend/src/features/1-brainstorm/QuestionCard.tsx frontend/src/features/1-brainstorm/ProgressStepper.tsx
```

---

## Task 11: 前端 SuperpowerChat 改逐题驱动（Query 轮询）

**Files:**
- Modify: `frontend/src/store/useGameStore.ts`（+designState + 轮询 getState + submitAnswer/skipQuestion actions）
- Modify: `frontend/src/features/1-brainstorm/SuperpowerChat.tsx`（Query 轮询 + QuestionCard + ProgressStepper）

**Interfaces:**
- Produces: store `designState` + `pollState()`（轮询 getState 每 2s）+ `submitAnswer/skipQuestion`；SuperpowerChat 按 designState.phase 渲染。

- [ ] **Step 1: 改 useGameStore**

加 `designState: DesignState | null` + actions `pollState/startDesign/pollSubmit/pollSkip`。轮询 getState（setInterval 2s），WAITING_USER 渲染 QuestionCard，COMPLETED 显示定稿。

- [ ] **Step 2: 改 SuperpowerChat**

按 `designState.phase`：ANALYZING→分析中；WAITING_USER→ProgressStepper + QuestionCard；GENERATING_GDD→生成中；CHECKING_GDD→检查中；COMPLETED→定稿按钮。

- [ ] **Step 3: 验 tsc + vite dev**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -E "SuperpowerChat|useGameStore" | wc -l`
Expected: 0（你的文件无错，既有 62 错不管）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/store/useGameStore.ts frontend/src/features/1-brainstorm/SuperpowerChat.tsx
git commit -m "feat(frontend): SuperpowerChat 改逐题驱动（Query 轮询 + QuestionCard）

Co-Authored-By: Kscc <noreply@owtffssent.com>" -- frontend/src/store/useGameStore.ts frontend/src/features/1-brainstorm/SuperpowerChat.tsx
```

---

## Task 12: e2e 手动验收（真 Temporal Server + KSPMAS + GitHub + 前端）

**Goal:** 起后端 API + Temporal Worker + 前端，浏览器跑 §1.2 验收链路。

- [ ] **Step 1: 确认基建**

```bash
docker ps --filter name=temporal-dev  # Temporal 在跑
redis-cli ping  # PONG
git ls-remote https://github.com/CodingZY/Game_Template_Repo.git  # 可达
```

- [ ] **Step 2: 起 Temporal Worker + API + 前端**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m temporal.worker
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m uvicorn app.main:app --port 8000
cd frontend && npx vite dev --port 5173
```

- [ ] **Step 3: 浏览器跑验收**

`http://localhost:5173` → 新建游戏 → 等 02 产 QuestionPlan → 逐题答（选项+影响）→ 等 03 生成 GDD → 定稿 → GitHub。

- [ ] **Step 4: 验收清单**

- [ ] 新建游戏 → 起 GameDesignWorkflow（Temporal）
- [ ] 02 产出 QuestionPlan JSON（逐题展示带 impact）
- [ ] Signal submit_answer 推进逐题
- [ ] skip "帮我决定" 用 default
- [ ] 关网页重开 → getState 继续当前题（Workflow 持久化）
- [ ] Requirements Snapshot 生成（SSOT）
- [ ] 03 读 Snapshot 生成 GDD.md
- [ ] 04 三态（PASS/WARNING/BLOCKING）
- [ ] 定稿 → GitHub 有 GDD + tag

- [ ] **Step 5: 记录 + 提交**

---

## Self-Review 已执行

**1. Spec coverage:** §1.2 验收链路 → Task0-12 全覆盖（Workflow Task2/Activity Task3/SKILL Task4-6/API Task8/前端 Task10-11/e2e Task12）；§2 D1-D12 → Global + 各 task；§3 spike → Global；§4 模块 → File Structure；§5 模块设计 → Task1-8；§6 数据模型 → Task8 状态；§7 测试 → 各 task + Task12；§8 风险 → Global（Docker/JSON 解析/Activity 慢）。

**2. Placeholder scan:** Task 3 `_worktree_cwd` 占位（实现期从 project_key 推或 Workflow 传 cwd）——属执行决策已注明。Activity `project_id=0` 占位（实现期 Workflow 传真实 id）——注明。无 TBD。

**3. Type consistency:** `AnswerSignal{question_id,answer,action}` 跨 Task2/8 一致；`analyze_idea/synthesize_requirements/generate_gdd/check_gdd` 跨 Task2/3/7 一致；`get_design_state` 跨 Task2/8/10 一致；`DesignState` 跨 Task10/11 一致。

## 执行交接

计划已存 `doc/plans/2026-08-18-phase3a-temporal-plan.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每 task 派 subagent + review。

**2. Inline Execution** — 本会话 executing-plans 批量执行 + 检查点。

**你选哪种？**
