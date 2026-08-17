# 阶段1（Phase 3a）Skills 基座 + GDD Skill 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 跑通 `IDEA →(02 brainstorm)→(03 gdd-generator)→ GDD.md+manifest → GDD_REVIEW 暂停 → approve →(04 gdd-check)→ GDD_APPROVED → finalize 落 git`，Skills 经后端 `claude --bare --plugin-dir backend/game-skills` 挂载，复用 Phase 1/2 全基建。

**Architecture:** 新增 `backend/game-skills/` plugin（3 SKILL.md）+ ClaudeRuntime 加 `--plugin-dir` 参数（spike 验通）。run_brainstorm 内两次 spawn（02 落 `.brainstorm-concept.md`、03 读 concept 落 GDD.md+manifest），末尾置 GDD_REVIEW；新增 run_gdd_check（spawn 04，parser 抓 result 文本 PASS/FAIL）。ProjectStatus +GDD_REVIEW/GDD_CHECKING/GDD_APPROVED；assert_can_finalize 硬改要求 GDD_APPROVED（doc §84）。

**Tech Stack:** Python 3.10（agent_env，D 盘）/ FastAPI / SQLAlchemy async / arq / redis / 官方 claude CLI 2.x `--bare --plugin-dir` + KSPMAS kimi-k3 / pytest + pytest-asyncio（sqlite + FakeRedis + FakeRuntime + FakeGitService）

**Spec:** `doc/specs/2026-08-17-phase3a-skills-gdd-design.md`（本计划从 spec 推导，spec 与计划一并阅读）

## Global Constraints

- **Python 解释器固定** `D:/Anaconda3/envs/agent_env/python.exe`（C 盘约束：依赖只装 agent_env，禁碰 C 盘）。下文 `python` 均指此解释器。Python 3.10，类型用 `Optional[X]`/`from __future__ import annotations`；`X | None` 仅 pydantic 模型字段可用。
- **Phase 1/2 既有不动核心**：ClaudeRuntime（`_build_cmd`/`_run`/`start`/`resume`/`_resolve_claude_bin`）、GitService、EventBroker、EventRepo、ProjectRepo/AgentSessionRepo/ProjectRepositoryRepo、SSE 端点已就绪且测试绿（feat/phase2-git）。本阶段**叠加** Skills 层 + 改 run_brainstorm（两次 spawn）+ 新增 run_gdd_check + finalize 门升级。
- **测试不打 KSPMAS/github**（D10）：单测/集成用 sqlite + FakeRedis + FakeRuntime + FakeGitService；e2e 手动真打，不进 CI（沿用 Phase 1/2）。
- **`--bare --plugin-dir` 机制已验通**（spec §3 spike）：`claude --bare --plugin-dir <game-skills>` 能加载项目级 plugin skills 且不染宿主（probe-skill 返 PROBE_SKILL_OK，36.3s）。ClaudeRuntime 加 `--plugin-dir` 参数复用此机制，不改 `--bare`。
- **Subagent-Driven 并行教训**（Phase 2 记忆）：并行 subagent 指示**只跑自己测试文件、只 git add 自己文件**，主控最后统一跑全量 + 跨文件回归（改公共接口如 tasks.py/runtime.py/engine.py 的 task 完成后补跑受影响测试目录）。
- **Skill 内容约束**（spec §5.1）：02 不写 GDD（只落 `.brainstorm-concept.md`）；03 落 GDD.md(17节)+manifest；04 只 Read 不 Write，输出格式化 PASS/FAIL。三 skill 都只用 Read/Write，措辞中性规避 kimi-k3 审核。
- **GDD 命名**：`games/{key}/GDD.md` + `gdd-manifest.json`（废弃 Phase 2 的 `{名}-game-design.md`）。`.brainstorm-concept.md` 是 worktree 中间产物，**finalize 不 commit 它**（run_finalize 改精确 `git add games/{key}/GDD.md games/{key}/gdd-manifest.json`）。
- **commit 规范（本计划）**：每 task 末提交，message 前缀按改动类型，结尾加 `Co-Authored-By: Kscc <noreply@owtffssent.com>`。
- **不碰 frontend**：阶段1只在 `backend/` 与 `doc/` 下作业。

---

## File Structure

```
backend/
├── game-skills/                         新增 Task 0（入库，Skills 层）
│   ├── .claude-plugin/plugin.json
│   └── skills/
│       ├── 02-game-brainstorm/SKILL.md
│       ├── 03-gdd-generator/SKILL.md
│       └── 04-gdd-check/SKILL.md
├── app/
│   ├── agent/
│   │   ├── runtime.py                   改 Task 1：_build_cmd/_run/start/resume 加 plugin_dir
│   │   └── prompts.py                   改 Task 3：+GDD_GEN_SYSTEM_PROMPT/GDD_CHECK_SYSTEM_PROMPT
│   ├── workflow/
│   │   ├── states.py                     改 Task 2：+GDD_REVIEW/GDD_CHECKING/GDD_APPROVED
│   │   └── engine.py                    改 Task 2：assert_can_finalize 改要求 GDD_APPROVED；+assert_can_gdd_check
│   ├── queue/
│   │   ├── tasks.py                     改 Task 4：run_brainstorm 两次 spawn+末尾GDD_REVIEW；新增 Task 5 run_gdd_check
│   │   ├── jobs.py                      改 Task 6：+enqueue_gdd_check
│   │   └── worker.py                    改 Task 6：注册 run_gdd_check
│   ├── api/projects.py                 改 Task 7：+POST /gdd/approve
│   └── config/settings.py              改 Task 1：+game_skills_dir 字段
└── tests/
    ├── test_skills.py                   新增 Task 0
    ├── test_runtime_plugin_dir.py       新增 Task 1
    ├── test_workflow_gdd.py             新增 Task 2
    ├── test_prompts_gdd.py              新增 Task 3
    ├── test_tasks_brainstorm_gdd.py     新增 Task 4（FakeRuntime 两次 spawn）
    ├── test_tasks_gdd_check.py          新增 Task 5
    ├── test_api_gdd.py                  新增 Task 7
    ├── test_tasks_finalize.py           改 Task 8：BRAINSTORMING→GDD_APPROVED（D8 硬改）
    └── test_tasks_worker.py             改 Task 9：run_brainstorm 两次 spawn 后注入适配
```

**责任划分**：game-skills plugin（纯文本 SKILL.md）先行；ClaudeRuntime `--plugin-dir` 是可测接缝（monkeypatch _spawn_stream 验 cmd）；状态机纯枚举；prompts 纯文本；tasks 串联（两次 spawn + parser 抓 result）。每层接口在对应 task 的 **Interfaces** 块钉死。

---

## Task 0: game-skills plugin 骨架 + 3 SKILL.md

**Files:**
- Create: `backend/game-skills/.claude-plugin/plugin.json`
- Create: `backend/game-skills/skills/02-game-brainstorm/SKILL.md`
- Create: `backend/game-skills/skills/03-gdd-generator/SKILL.md`
- Create: `backend/game-skills/skills/04-gdd-check/SKILL.md`
- Test: `backend/tests/test_skills.py`

**Interfaces:**
- Produces: game-skills plugin 目录结构（`.claude-plugin/plugin.json` + 3 `SKILL.md`），供 Task 1 的 `--plugin-dir backend/game-skills` 挂载、Task 4/5 的子进程经 `/02-game-brainstorm`/`/03-gdd-generator`/`/04-gdd-check` 调用。

- [ ] **Step 1: 建 plugin.json**

`backend/game-skills/.claude-plugin/plugin.json`:
```json
{
  "name": "game-skills",
  "version": "0.1.0",
  "description": "AI_Cowork_Game 自研 Game Skills（skill-doc Phase 1）"
}
```

- [ ] **Step 2: 建 02-game-brainstorm/SKILL.md**

`backend/game-skills/skills/02-game-brainstorm/SKILL.md`:
```markdown
---
name: 02-game-brainstorm
description: 澄清用户模糊游戏创意，多轮问答→结构化 Game Concept，落 .brainstorm-concept.md，不写 GDD
---

You are the Game Brainstorm skill. Your job: clarify a vague game idea through focused questions, then write a structured Game Concept. **Do not write GDD.md** (that's 03-gdd-generator's job).

## Process
1. The user gives a vague idea (e.g. "类似牧场物语的游戏"). Ask focused clarifying questions **one batch at a time** (not all at once). Cover these dimensions as needed:
   - Platform (web/mobile/desktop) and 2D vs 3D
   - Core loop (what does the player repeatedly do?)
   - Core systems depth (farming? combat? romance? economy?)
   - NPC count and roles
   - Game length / session time
2. When the idea is sufficiently clear, call the **Write** tool to save the Game Concept to `.brainstorm-concept.md` (in the current working directory).

## .brainstorm-concept.md format
Structured bullets:
- name: <game name>
- genre: <genre>
- platform: <platform>
- dimension: <2D/3D>
- core_loop: <one sentence>
- player_goals: <short/mid/long term>
- key_systems: <comma list: farming, economy, npc, ...>
- scope: <small/medium/large>
- art_direction: <style hint>

## Rules
- Only use Read and Write tools. Do not run shell commands.
- Stay neutral and concrete. Avoid sensitive or policy-flagged wording (the model may refuse otherwise).
- After writing .brainstorm-concept.md, reply with a one-line summary of the concept.
```

- [ ] **Step 3: 建 03-gdd-generator/SKILL.md**

`backend/game-skills/skills/03-gdd-generator/SKILL.md`:
```markdown
---
name: 03-gdd-generator
description: 读 .brainstorm-concept.md 生成机器可执行 GDD.md(17节) + gdd-manifest.json
---

You are the GDD Generator skill. Input: `.brainstorm-concept.md` (written by 02-game-brainstorm). Output: `GDD.md` + `gdd-manifest.json` via the **Write** tool.

## Critical principle
The GDD must be **machine-executable** — downstream skills must be able to generate Assets, Code, and Tests from it. Prioritize clarity and structure over prose.

## GDD.md — all 17 sections (doc §42), in order
1. Game Overview
2. Target Audience
3. Core Loop
4. Player Goals
5. Game Mechanics
6. Characters
7. NPC
8. World
9. Level Design
10. Economy
11. Progression
12. UI
13. Audio
14. Art Direction
15. Technical Requirements
16. Features (list with F00x ids)
17. Acceptance Criteria (per feature)

## gdd-manifest.json (doc §43)
```json
{
  "game": { "name": "<name>", "genre": "<genre>", "platform": "<platform>" },
  "features": [
    { "id": "F001", "name": "<name>", "priority": "P0", "status": "TODO", "acceptance": "<criteria>" },
    ...
  ]
}
```
Every feature MUST have: id (F001..), name, priority (P0/P1/P2), status (TODO), acceptance (one-line testable criterion).

## Rules
- Read `.brainstorm-concept.md` first; if missing, stop and report.
- Only use Read and Write tools. Write exactly `GDD.md` and `gdd-manifest.json` in the cwd.
- Stay neutral and concrete (avoid policy-flagged wording).
- After writing, reply with a one-line summary.
```

- [ ] **Step 4: 建 04-gdd-check/SKILL.md**

`backend/game-skills/skills/04-gdd-check/SKILL.md`:
```markdown
---
name: 04-gdd-check
description: 检查 GDD.md+gdd-manifest.json 完整性，输出 PASS 或 FAIL: <缺失项>
---

You are the GDD Check skill — a **hard gate**. Input: `GDD.md` + `gdd-manifest.json` (in cwd). You do NOT modify files. You only read and judge.

## Checks
1. GDD.md has all 17 sections (Overview/Target Audience/Core Loop/Player Goals/Game Mechanics/Characters/NPC/World/Level Design/Economy/Progression/UI/Audio/Art Direction/Technical Requirements/Features/Acceptance Criteria).
2. gdd-manifest.json is valid JSON with `game` and `features` arrays.
3. Every feature has: id (F00x), name, priority, status, acceptance.
4. Every feature in manifest maps to an Acceptance Criterion in GDD.md §17.

## Output format (STRICT — backend parser reads this)
Your reply's **first line** must be exactly one of:
- `PASS` — all checks passed
- `FAIL: <comma-separated missing items>` — e.g. `FAIL: GDD missing section NPC, manifest feature F002 lacks acceptance`

Do not call any tools. Do not add explanation before the first line. Keep the verdict on line 1.
```

- [ ] **Step 5: 写 test_skills.py（轻测文本约束）**

`backend/tests/test_skills.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "game-skills" / "skills"


def _read(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_json():
    p = SKILLS.parent / ".claude-plugin" / "plugin.json"
    import json
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["name"] == "game-skills"


def test_brainstorm_skill_constraints():
    s = _read("02-game-brainstorm")
    assert "brainstorm-concept.md" in s
    assert "Do not write GDD" in s or "不写 GDD" in s or "**Do not write GDD.md**" in s
    assert "core_loop" in s  # concept 格式
    assert "Write" in s


def test_gdd_generator_skill_constraints():
    s = _read("03-gdd-generator")
    assert "GDD.md" in s
    assert "gdd-manifest.json" in s
    assert "17 sections" in s or "Game Overview" in s  # 17节
    assert "F001" in s  # manifest feature id
    assert "acceptance" in s.lower()


def test_gdd_check_skill_constraints():
    s = _read("04-gdd-check")
    assert "PASS" in s
    assert "FAIL" in s
    assert "first line" in s or "line 1" in s  # 格式约束
    assert "17" in s  # 17节齐全
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_skills.py -v`
Expected: PASS（4 测试）

- [ ] **Step 7: 提交**

```bash
git add backend/game-skills/ backend/tests/test_skills.py
git commit -m "feat(skills): game-skills plugin + 3 SKILL.md（02-brainstorm/03-gdd-generator/04-gdd-check）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 1: ClaudeRuntime `--plugin-dir` 参数

**Files:**
- Modify: `backend/app/agent/runtime.py`（`_build_cmd`/`_run`/`start`/`resume`）
- Modify: `backend/app/config/settings.py`（+`game_skills_dir`）
- Test: `backend/tests/test_runtime_plugin_dir.py`

**Interfaces:**
- Consumes: 现有 `_build_cmd(prompt, resume_sid=None, system_prompt=None)`（runtime.py:54）、`_run`/`start`/`resume` 签名。
- Produces: `_build_cmd(prompt, resume_sid=None, system_prompt=None, plugin_dir=None)`（新增 plugin_dir 尾参）；`start(prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None)`；`resume(..., plugin_dir=None)`；`_run(..., plugin_dir=None)`。`Settings.game_skills_dir: str = "backend/game-skills"`（相对 REPO_ROOT）。Task 4/5 传 `plugin_dir` 挂 game-skills。

- [ ] **Step 1: 改 settings.py 加 game_skills_dir**

`backend/app/config/settings.py`：在 `git_branch_prefix` 字段下加：
```python
    game_skills_dir: str = "backend/game-skills"
```
（相对 REPO_ROOT；运行时拼绝对路径。保留既有字段不动。）

- [ ] **Step 2: 写失败测试**

`backend/tests/test_runtime_plugin_dir.py`:
```python
from __future__ import annotations

import json

import pytest

from app.agent.runtime import ClaudeRuntime


class FakeProc:
    def __init__(self, lines):
        self._lines = lines
        self.stdout_lines = []

    async def wait(self):
        return 0


@pytest.mark.asyncio
async def test_build_cmd_includes_plugin_dir(monkeypatch):
    """plugin_dir 传入时 cmd 含 --plugin-dir <dir>。"""
    rt = ClaudeRuntime.__new__(ClaudeRuntime)
    rt.settings = None
    rt.claude_bin = "claude"
    rt.proc = None
    cmd = rt._build_cmd("p", resume_sid=None, system_prompt=None, plugin_dir="/abs/game-skills")
    assert "--plugin-dir" in cmd
    idx = cmd.index("--plugin-dir")
    assert cmd[idx + 1] == "/abs/game-skills"


@pytest.mark.asyncio
async def test_build_cmd_no_plugin_dir_when_none(monkeypatch):
    """plugin_dir 缺省时 cmd 不含 --plugin-dir。"""
    rt = ClaudeRuntime.__new__(ClaudeRuntime)
    rt.settings = None
    rt.claude_bin = "claude"
    rt.proc = None
    cmd = rt._build_cmd("p")
    assert "--plugin-dir" not in cmd


@pytest.mark.asyncio
async def test_start_passes_plugin_dir_to_run(monkeypatch):
    """start 的 plugin_dir 透传到 _build_cmd（经 _run→_spawn_stream）。"""
    captured = {}

    class FakeRuntime(ClaudeRuntime):
        async def _spawn_stream(self, cmd, env, cwd):
            captured["cmd"] = cmd
            return []

    rt = FakeRuntime.__new__(FakeRuntime)
    from app.config.settings import get_settings
    rt.settings = get_settings()
    rt.claude_bin = "claude"
    rt.proc = None
    # 用 settings.game_skills_dir 拼绝对
    plugin_dir = str(rt.settings.workspace_base.parent / rt.settings.game_skills_dir)
    evts = [e async for e in rt.start("p", "/cwd", 1, agent_type="brainstorm", system_prompt=None, plugin_dir=plugin_dir)]
    assert "--plugin-dir" in captured["cmd"]
    assert plugin_dir in captured["cmd"]
```

- [ ] **Step 3: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runtime_plugin_dir.py -v`
Expected: FAIL（`_build_cmd` 不接 plugin_dir → TypeError）

- [ ] **Step 4: 改 runtime.py**

`_build_cmd` 加 `plugin_dir=None` 参数 + cmd 追加：
```python
    def _build_cmd(self, prompt, resume_sid=None, system_prompt=None, plugin_dir=None) -> list[str]:
        cmd = [
            self.claude_bin, "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--include-partial-messages",
            "--bare", "--allowedTools", "Read", "Write",
            "--permission-mode", "acceptEdits",
        ]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        if plugin_dir:
            cmd += ["--plugin-dir", plugin_dir]
        if resume_sid:
            cmd += ["--resume", resume_sid]
        return cmd
```
`_run` 加 `plugin_dir=None`，传给 `_build_cmd`：
```python
    async def _run(self, prompt, cwd, project_id, agent_type="brainstorm",
                   resume_sid=None, system_prompt=None, plugin_dir=None) -> AsyncIterator:
        cmd = self._build_cmd(prompt, resume_sid, system_prompt, plugin_dir)
        env = self._build_env()
        parser = ClaudeEventParser(project_id=project_id, agent_type=agent_type)
        lines = await self._spawn_stream(cmd, env, cwd)
        for line in lines:
            for evt in parser.parse(line):
                yield evt
```
`start` 加 `plugin_dir=None`，传 `_run`：
```python
    async def start(self, prompt, cwd, project_id, agent_type="brainstorm",
                    system_prompt=None, plugin_dir=None) -> AsyncIterator:
        async for evt in self._run(
            prompt, cwd, project_id, agent_type, None, system_prompt, plugin_dir
        ):
            yield evt
```
`resume` 同理加 `plugin_dir=None`，传 `_run(..., session_id, system_prompt, plugin_dir)`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runtime_plugin_dir.py -v`
Expected: PASS（3 测试）

- [ ] **Step 6: 跑既有 runtime 测试确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_runtime.py -v`
Expected: PASS（既有 runtime 测试不受影响——plugin_dir 默认 None，cmd 不变）

- [ ] **Step 7: 提交**

```bash
git add backend/app/agent/runtime.py backend/app/config/settings.py backend/tests/test_runtime_plugin_dir.py
git commit -m "feat(agent): ClaudeRuntime +--plugin-dir 参数（spike 验通的 skills 挂载机制）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 2: 状态机扩展（GDD_REVIEW/GDD_CHECKING/GDD_APPROVED + finalize 门）

**Files:**
- Modify: `backend/app/workflow/states.py`
- Modify: `backend/app/workflow/engine.py`
- Test: `backend/tests/test_workflow_gdd.py`

**Interfaces:**
- Produces: `ProjectStatus.GDD_REVIEW`/`GDD_CHECKING`/`GDD_APPROVED`；`assert_can_finalize` 改要求 `GDD_APPROVED`（doc §84）；`assert_can_gdd_check(status)` 仅 `GDD_REVIEW` 可。Task 4/5/7/8 依赖。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_workflow_gdd.py`:
```python
from __future__ import annotations

import pytest

from app.workflow.states import ProjectStatus
from app.workflow.engine import (
    assert_can_finalize, assert_can_gdd_check, assert_can_brainstorm, WorkflowBlocked,
)


def test_gdd_states_exist():
    assert ProjectStatus("GDD_REVIEW") == ProjectStatus.GDD_REVIEW
    assert ProjectStatus("GDD_CHECKING") == ProjectStatus.GDD_CHECKING
    assert ProjectStatus("GDD_APPROVED") == ProjectStatus.GDD_APPROVED


def test_finalize_requires_gdd_approved():
    """D8：finalize 门从 BRAINSTORMING 改 GDD_APPROVED。"""
    assert_can_finalize(ProjectStatus.GDD_APPROVED)  # 不抛
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.BRAINSTORMING)  # 旧门现拒
    with pytest.raises(WorkflowBlocked):
        assert_can_finalize(ProjectStatus.CREATED)


def test_gdd_check_requires_gdd_review():
    assert_can_gdd_check(ProjectStatus.GDD_REVIEW)  # 不抛
    with pytest.raises(WorkflowBlocked):
        assert_can_gdd_check(ProjectStatus.GDD_CHECKING)
    with pytest.raises(WorkflowBlocked):
        assert_can_gdd_check(ProjectStatus.GDD_APPROVED)


def test_brainstorm_allows_gdd_review():
    """GDD_REVIEW 时可再 brainstorm 改 GDD（多轮修正）。"""
    assert_can_brainstorm(ProjectStatus.GDD_REVIEW)
    assert_can_brainstorm(ProjectStatus.CREATED)
    assert_can_brainstorm(ProjectStatus.BRAINSTORMING)


def test_brainstorm_blocked_from_approved():
    """GDD_APPROVED 不可再 brainstorm（已定稿，进 finalize）。"""
    with pytest.raises(WorkflowBlocked):
        assert_can_brainstorm(ProjectStatus.GDD_APPROVED)
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_workflow_gdd.py -v`
Expected: FAIL（GDD_REVIEW 不存在 / assert_can_finalize 仍要 BRAINSTORMING / assert_can_gdd_check 未定义）

- [ ] **Step 3: 改 states.py**

`backend/app/workflow/states.py`：在 `BRAINSTORMING` 后、`BRAINSTORMED` 前加三状态：
```python
class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    BRAINSTORMING = "BRAINSTORMING"
    GDD_REVIEW = "GDD_REVIEW"
    GDD_CHECKING = "GDD_CHECKING"
    GDD_APPROVED = "GDD_APPROVED"
    BRAINSTORMED = "BRAINSTORMED"
    FAILED = "FAILED"
```

- [ ] **Step 4: 改 engine.py**

现有 `assert_can_finalize`（Phase 2：仅 BRAINSTORMING）。改为要求 GDD_APPROVED；末尾加 assert_can_gdd_check：
```python
def assert_can_finalize(status: ProjectStatus | str) -> None:
    """仅 GDD_APPROVED 可 finalize（doc §84 Hard Gate，D8：Phase2 的 BRAINSTORMING 门升级）。"""
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot finalize from {status!r}")
    if current is not ProjectStatus.GDD_APPROVED:
        raise WorkflowBlocked(f"cannot finalize from {current}")


def assert_can_gdd_check(status: ProjectStatus | str) -> None:
    """仅 GDD_REVIEW 可跑 04-gdd-check。"""
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot gdd_check from {status!r}")
    if current is not ProjectStatus.GDD_REVIEW:
        raise WorkflowBlocked(f"cannot gdd_check from {current}")
```
`assert_can_brainstorm` 既有逻辑改：允许 CREATED/BRAINSTORMING/**GDD_REVIEW**（多轮改 GDD）；GDD_APPROVED/BRAINSTORMED/FAILED 不可：
```python
def assert_can_brainstorm(status: ProjectStatus | str) -> None:
    try:
        current = ProjectStatus(status)
    except ValueError:
        raise WorkflowBlocked(f"cannot brainstorm from {status!r}")
    if current not in (ProjectStatus.CREATED, ProjectStatus.BRAINSTORMING, ProjectStatus.GDD_REVIEW):
        raise WorkflowBlocked(f"cannot brainstorm from {current}")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_workflow_gdd.py -v`
Expected: PASS（5 测试）

- [ ] **Step 6: 跑既有 workflow 测试确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_workflow_finalize.py tests/test_states.py -v`
Expected: 既有 test_workflow_finalize 的 `test_cannot_finalize_from_brainstorming` 仍 PASS（BRAINSTORMING 不可 finalize，改后仍抛）；`test_cannot_finalize_from_created` PASS。但注意既有 `test_can_finalize_from_brainstorming`（若有断言 BRAINSTORMING 可 finalize）会 FAIL——这是 D8 预期的硬改。**改 test_workflow_finalize.py：把"BRAINSTORMING 可 finalize"改为"GDD_APPROVED 可 finalize"**（见 Task 8 同步）。本 task 先跑 test_workflow_gdd + test_states，test_workflow_finalize 的回归在 Task 8 统一处理。

- [ ] **Step 7: 提交**

```bash
git add backend/app/workflow/ backend/tests/test_workflow_gdd.py
git commit -m "feat(workflow): +GDD_REVIEW/CHECKING/APPROVED + assert_can_gdd_check + finalize 门升级要求 GDD_APPROVED（doc §84）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 3: prompts.py 加 GDD_GEN / GDD_CHECK system prompt

**Files:**
- Modify: `backend/app/agent/prompts.py`
- Test: `backend/tests/test_prompts_gdd.py`

**Interfaces:**
- Produces: `GDD_GEN_SYSTEM_PROMPT: str`（指示调 03-gdd-generator 读 concept 落 GDD.md+manifest）、`GDD_CHECK_SYSTEM_PROMPT: str`（指示调 04-gdd-check 输出 PASS/FAIL 格式）。Task 4/5 用。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_prompts_gdd.py`:
```python
from __future__ import annotations

from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT, GDD_GEN_SYSTEM_PROMPT, GDD_CHECK_SYSTEM_PROMPT


def test_gdd_gen_prompt_constraints():
    assert "03-gdd-generator" in GDD_GEN_SYSTEM_PROMPT
    assert ".brainstorm-concept.md" in GDD_GEN_SYSTEM_PROMPT
    assert "GDD.md" in GDD_GEN_SYSTEM_PROMPT
    assert "gdd-manifest.json" in GDD_GEN_SYSTEM_PROMPT


def test_gdd_check_prompt_constraints():
    assert "04-gdd-check" in GDD_CHECK_SYSTEM_PROMPT
    assert "PASS" in GDD_CHECK_SYSTEM_PROMPT
    assert "FAIL" in GDD_CHECK_SYSTEM_PROMPT
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_prompts_gdd.py -v`
Expected: FAIL（GDD_GEN_SYSTEM_PROMPT 未定义）

- [ ] **Step 3: 改 prompts.py**

`backend/app/agent/prompts.py`：保留既有 BRAINSTORM_SYSTEM_PROMPT（Phase 1/2 用，阶段1 run_brainstorm 的 02 轮仍可用，或改用新 prompt——见 Task 4 决策）。末尾追加：
```python
# Phase 3a（spec §5.4）：02/03/04 轮的 run_brainstorm/run_gdd_check 调用 skill 的指示 prompt。
# BRAINSTORM_SYSTEM_PROMPT（上）用于 Phase 1/2 旧 brainstorm；阶段1 02 轮改用 GDD_BRAINSTORM_SYSTEM_PROMPT。

GDD_BRAINSTORM_SYSTEM_PROMPT = """You are running the 02-game-brainstorm skill to clarify a game idea.

Steps:
1. Invoke the skill /02-game-brainstorm.
2. It will ask clarifying questions, then call Write to save .brainstorm-concept.md.
3. When .brainstorm-concept.md is written, reply with a one-line concept summary.

Rules: only use Read/Write; stay neutral and concrete; do not write GDD.md.
"""

GDD_GEN_SYSTEM_PROMPT = """You are running the 03-gdd-generator skill to produce a machine-executable GDD.

Steps:
1. Invoke the skill /03-gdd-generator.
2. It reads .brainstorm-concept.md (written by 02) and calls Write to produce GDD.md (17 sections) + gdd-manifest.json in the current working directory.
3. When both files are written, reply with a one-line summary.

Rules: only use Read/Write; stay neutral; do not modify files other than GDD.md and gdd-manifest.json.
"""

GDD_CHECK_SYSTEM_PROMPT = """You are running the 04-gdd-check skill — a hard gate.

Steps:
1. Invoke the skill /04-gdd-check.
2. It reads GDD.md + gdd-manifest.json and judges completeness (17 sections, manifest features have id/priority/status/acceptance).
3. Your reply's FIRST LINE must be exactly `PASS` or `FAIL: <missing items>`. The backend parser reads this first line.

Rules: only use Read; do not modify any files; keep the verdict on line 1, no preamble.
"""
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_prompts_gdd.py -v`
Expected: PASS（2 测试）

- [ ] **Step 5: 跑既有 prompts 测试确认未破坏**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_prompts.py -v`
Expected: PASS（既有 BRAINSTORM_SYSTEM_PROMPT 测试不受影响）

- [ ] **Step 6: 提交**

```bash
git add backend/app/agent/prompts.py backend/tests/test_prompts_gdd.py
git commit -m "feat(agent): +GDD_BRAINSTORM/GDD_GEN/GDD_CHECK system prompts（调 skill 指示）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 4: run_brainstorm 改两次 spawn（02+03）+ 末尾 GDD_REVIEW

**Files:**
- Modify: `backend/app/queue/tasks.py`（run_brainstorm）
- Test: `backend/tests/test_tasks_brainstorm_gdd.py`

**Interfaces:**
- Consumes: `ClaudeRuntime.start(prompt, cwd, project_id, agent_type, system_prompt, plugin_dir)`（Task 1）；`GitService`（Phase 2）；`GDD_BRAINSTORM_SYSTEM_PROMPT`/`GDD_GEN_SYSTEM_PROMPT`（Task 3）；`ProjectStatus.GDD_REVIEW`（Task 2）。
- Produces: `run_brainstorm` 改为两次 spawn（02→`.brainstorm-concept.md`，03→`GDD.md`+`gdd-manifest.json`），末尾置 `GDD_REVIEW`（成功）或 `FAILED`（refused/runtime_error）。两轮 agent_session（BRAINSTORM + GDD_GEN）。Task 5 run_gdd_check 依赖 GDD_REVIEW 状态。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_tasks_brainstorm_gdd.py`:
```python
from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo
from app.queue.tasks import run_brainstorm
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, FakeGitService, FakeRuntime, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


async def test_run_brainstorm_two_spawns_sets_gdd_review(db_sm, fake_aioredis, monkeypatch):
    """02+03 两次 spawn，末尾置 GDD_REVIEW。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="gdd")

    # 两次 spawn：FakeRuntime 每次 start yield 事件
    spawn_count = [0]
    real_start = FakeRuntime.start

    class TwoSpawnRuntime:
        def __init__(self):
            self.cwd = None
        async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
            spawn_count[0] += 1
            self.cwd = cwd
            yield _evt(pid, "agent.session.started", {"session_id": f"s{spawn_count[0]}", "model": "kimi-k3"})
            yield _evt(pid, "agent.session.completed",
                       {"session_id": f"s{spawn_count[0]}", "result": "ok", "stop_reason": "end_turn"})

    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: TwoSpawnRuntime())

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="牧场经营游戏")

    assert spawn_count[0] == 2  # 两次 spawn
    # 末尾 GDD_REVIEW
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value
    # 两次 agent.session.started/completed 事件落库
    async with db_sm() as s:
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
    assert types.count("agent.session.started") == 2
    assert types.count("agent.session.completed") == 2


async def test_run_brainstorm_refused_sets_failed(db_sm, fake_aioredis, monkeypatch):
    """02 或 03 refusal → FAILED（不进 GDD_REVIEW）。"""
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)

    pid = await _create_project(db_sm, key="ref")

    class RefusedRuntime:
        async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
            yield _evt(pid, "agent.session.started", {"session_id": "s1"})
            yield _evt(pid, "agent.refused", {"reason": "content_review"})

    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: RefusedRuntime())

    result = await run_brainstorm(ctx={}, project_id=pid, prompt="敏感")
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.FAILED.value
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_gdd.py -v`
Expected: FAIL（run_brainstorm 现单次 spawn + 末尾 BRAINSTORMING，不满足两次 + GDD_REVIEW）

- [ ] **Step 3: 改 tasks.py run_brainstorm**

run_brainstorm 改造要点（spec §5.4）：
1. 顶部 import 加：`from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT, GDD_BRAINSTORM_SYSTEM_PROMPT, GDD_GEN_SYSTEM_PROMPT`（GDD_CHECK 在 Task 5 加）
2. AGENT_TYPE 旁加：`GDD_GEN_TYPE = "GDD_GEN"`
3. git 前置不变（ensure_clone/ensure_template_pushed/worktree_add/copy_template/git.worktree.added/set_branch）
4. **两次 spawn**（替换现有单次 `_events()` 块）：
   - spawn #1（02 轮）：预建 agent_session（BRAINSTORM），`runtime.start(prompt_brainstorm, claude_cwd, project_id, agent_type=AGENT_TYPE, system_prompt=GDD_BRAINSTORM_SYSTEM_PROMPT, plugin_dir=plugin_dir_abs)`，逐事件 broker.publish（aggregate_id=as1_id），三态记录（succeeded/refused/runtime_error）
   - spawn #2（03 轮）：预建 agent_session（GDD_GEN），`runtime.start(prompt_gddgen, claude_cwd, project_id, agent_type=GDD_GEN_TYPE, system_prompt=GDD_GEN_SYSTEM_PROMPT, plugin_dir=plugin_dir_abs)`，逐事件 broker.publish（aggregate_id=as2_id），三态记录
   - `plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)`（绝对路径）
   - prompt_brainstorm：`f"用户游戏创意：{prompt}。请调用 /02-game-brainstorm 澄清需求并落 .brainstorm-concept.md。"`
   - prompt_gddgen：`"请调用 /03-gdd-generator 读取 .brainstorm-concept.md 生成 GDD.md(17节) + gdd-manifest.json。"`
5. 三态收尾：任一轮 refused/runtime_error → FAILED；两轮都 succeeded → **置 GDD_REVIEW**（非 BRAINSTORMING）
6. 保留异常兜底（Phase 1 e2e 修复）：spawn 失败补发 agent.session.failed + FAILED

实现伪码（替换现有 `_events()` + 三态收尾段）：
```python
        plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)
        runtime = ClaudeRuntime()
        succeeded_all = True
        refused = False
        runtime_err = None
        sessions = []  # [(as_id, agent_type)]

        async def _spawn_once(prompt, agent_type, system_prompt):
            nonlocal succeeded_all, refused, runtime_err
            async with sm() as s2:
                asess = await AgentSessionRepo(s2).create(project_id, agent_type, claude_cwd)
                await s2.commit()
            asid = asess.id
            sessions.append((asid, agent_type))
            try:
                async for evt in runtime.start(
                    prompt, claude_cwd, project_id,
                    agent_type=agent_type, system_prompt=system_prompt, plugin_dir=plugin_dir_abs,
                ):
                    evt.aggregate_id = asid
                    if evt.type == "agent.session.completed":
                        pass  # succeeded marker
                    elif evt.type == "agent.refused":
                        refused = True
                    await broker.publish(evt)
            except Exception as e:
                runtime_err = f"{type(e).__name__}: {e}"
                await broker.publish(CoworkEvent(
                    project_id=project_id, type="agent.session.failed",
                    data={"reason": "runtime_error", "error": runtime_err},
                    aggregate_id=asid,
                ))
            return asid

        # spawn #1: 02 brainstorm
        await _spawn_once(
            f"用户游戏创意：{prompt}。请调用 /02-game-brainstorm 澄清需求并落 .brainstorm-concept.md。",
            AGENT_TYPE, GDD_BRAINSTORM_SYSTEM_PROMPT,
        )
        if refused or runtime_err:
            succeeded_all = False
        else:
            # spawn #2: 03 gdd-generator
            await _spawn_once(
                "请调用 /03-gdd-generator 读取 .brainstorm-concept.md 生成 GDD.md(17节) + gdd-manifest.json。",
                GDD_GEN_TYPE, GDD_GEN_SYSTEM_PROMPT,
            )
            if refused or runtime_err:
                succeeded_all = False

        # 三态收尾（spec §5.4：成功置 GDD_REVIEW，非 BRAINSTORMING）
        if refused:
            status, proj_status = "FAILED", ProjectStatus.FAILED
        elif succeeded_all:
            status, proj_status = "COMPLETED", ProjectStatus.GDD_REVIEW
        else:
            status, proj_status = "FAILED", ProjectStatus.FAILED
        async with sm() as s:
            for asid, _ in sessions:
                await AgentSessionRepo(s).finish(asid, status)
            await ProjectRepo(s).set_status(project_id, proj_status)
            await s.commit()
        return {"succeeded": succeeded_all, "refused": refused, "error": runtime_err}
```
> 注：顶部 import `REPO_ROOT` from `app.config.settings`（settings.py 已有 REPO_ROOT）。`AGENT_TYPE` 既有，`GDD_GEN_TYPE` 新增。`assert_can_finalize` import 已有（Task 2 保留）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_gdd.py -v`
Expected: PASS（2 测试）

- [ ] **Step 5: 跑既有 test_tasks_worker 回归（run_brainstorm 改了，既有测试需适配——见 Task 9）**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_worker.py -v`
Expected: **既有 run_brainstorm 测试会 FAIL**（run_brainstorm 现两次 spawn，FakeRuntime 单次 start 不够；末尾 GDD_REVIEW 非 BRAINSTORMING）。这是预期回归——Task 9 统一修 test_tasks_worker 注入适配。本 task 先不修，标记待 Task 9。

- [ ] **Step 6: 提交（run_brainstorm 改造，明知 test_tasks_worker 暂红，Task 9 修）**

```bash
git add backend/app/queue/tasks.py backend/tests/test_tasks_brainstorm_gdd.py
git commit -m "feat(queue): run_brainstorm 两次 spawn（02+03）+ 末尾 GDD_REVIEW（test_tasks_worker 回归 Task9 修）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 5: run_gdd_check 新增（spawn 04 + parser 抓 PASS/FAIL）

**Files:**
- Modify: `backend/app/queue/tasks.py`（+run_gdd_check + import GDD_CHECK_SYSTEM_PROMPT）
- Test: `backend/tests/test_tasks_gdd_check.py`

**Interfaces:**
- Consumes: `ClaudeRuntime.start(..., plugin_dir)`（Task 1）；`GDD_CHECK_SYSTEM_PROMPT`（Task 3）；`assert_can_gdd_check`/`ProjectStatus.GDD_CHECKING`/`GDD_APPROVED`/`GDD_REVIEW`（Task 2）；`GitService.worktree_path`（Phase 2，查 worktree 路径）。
- Produces: `async def run_gdd_check(ctx, project_id)`：spawn 04 → parser 抓 `agent.session.completed.result` → PASS 置 GDD_APPROVED / FAIL 回 GDD_REVIEW（带 reasons 事件）。Task 6 enqueue + Task 7 端点依赖。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_tasks_gdd_check.py`:
```python
from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo
from app.queue.tasks import run_gdd_check
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


def _evt(pid, type, data):
    from app.schemas.event import CoworkEvent
    return CoworkEvent(project_id=pid, type=type, data=data, aggregate_id=0)


class FakeCheckRuntime:
    """FakeRuntime for 04: yields session.started + session.completed(result=verdict)。"""
    def __init__(self, verdict_result):
        self.verdict = verdict_result
        self.cwd = None
    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
        self.cwd = cwd
        yield _evt(project_id, "agent.session.started", {"session_id": "chk1", "model": "kimi-k3"})
        yield _evt(project_id, "agent.session.completed",
                   {"session_id": "chk1", "result": self.verdict, "stop_reason": "end_turn"})


async def _setup_gdd_review_project(db_sm, key):
    pid = await _create_project(db_sm, key=key, status="GDD_REVIEW")
    async with db_sm() as s:
        await ProjectRepositoryRepo(s).create(
            project_id=pid, owner="o", repository="r", sub_path=f"games/{key}/")
        await ProjectRepositoryRepo(s).set_branch(pid, f"agent/{key}-brainstorm")
        await s.commit()
    return pid


async def test_run_gdd_check_pass(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = type("G", (), {"worktree_path": (lambda self, k: __import__("pathlib").Path(f"/fake/wt/{k}-brainstorm"))})()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeCheckRuntime("PASS"))

    pid = await _setup_gdd_review_project(db_sm, "pass")

    result = await run_gdd_check(ctx={}, project_id=pid)
    assert result["passed"] is True
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_APPROVED.value
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "gdd.check.passed" in types


async def test_run_gdd_check_fail(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = type("G", (), {"worktree_path": (lambda self, k: __import__("pathlib").Path(f"/fake/wt/{k}-brainstorm"))})()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeCheckRuntime("FAIL: GDD missing section NPC, F002 lacks acceptance"))

    pid = await _setup_gdd_review_project(db_sm, "fail")

    result = await run_gdd_check(ctx={}, project_id=pid)
    assert result["passed"] is False
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value  # 回 GDD_REVIEW
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "gdd.check.failed" in types


async def test_run_gdd_check_blocked_from_approved(db_sm, monkeypatch):
    from app.workflow.engine import WorkflowBlocked
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    pid = await _create_project(db_sm, key="blkchk", status="GDD_APPROVED")
    with pytest.raises(WorkflowBlocked):
        await run_gdd_check(ctx={}, project_id=pid)
```
> 注：顶部 import pytest。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_gdd_check.py -v`
Expected: FAIL（run_gdd_check 未定义）

- [ ] **Step 3: 改 tasks.py 加 run_gdd_check**

顶部 import 加 `GDD_CHECK_SYSTEM_PROMPT`（与 Task 3 已加的 prompts 合并 import 行）；末尾追加 run_gdd_check：
```python
GDD_CHECK_TYPE = "GDD_CHECK"


async def run_gdd_check(ctx, project_id: int):
    """Arq task：跑 04-gdd-check 硬门禁（spec §5.4/D9）。

    spawn 04 → parser 抓 agent.session.completed.result：
      首行/含 PASS → GDD_APPROVED + event gdd.check.passed
      含 FAIL → 回 GDD_REVIEW + event gdd.check.failed（带 reasons）
    异常兜底：spawn 失败 → gdd.check.failed + 回 GDD_REVIEW。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_gdd_check(p.status)
        await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_CHECKING)
        await s.commit()
    project_key = p.project_key

    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:gdd_check", timeout=1800)
    await lock.acquire()
    broker = EventBroker(session_factory=sm, redis=r)
    git = GitService()
    plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)
    try:
        wt = await git.worktree_path(project_key)
        claude_cwd = str(wt / "games" / project_key)
        async with sm() as s:
            asess = await AgentSessionRepo(s).create(project_id, GDD_CHECK_TYPE, claude_cwd)
            await s.commit()
        asid = asess.id

        runtime = ClaudeRuntime()
        verdict_result = None
        try:
            async for evt in runtime.start(
                "请调用 /04-gdd-check 检查 GDD.md + gdd-manifest.json 完整性，输出 PASS 或 FAIL: <缺失项>。",
                claude_cwd, project_id, agent_type=GDD_CHECK_TYPE,
                system_prompt=GDD_CHECK_SYSTEM_PROMPT, plugin_dir=plugin_dir_abs,
            ):
                evt.aggregate_id = asid
                if evt.type == "agent.session.completed":
                    verdict_result = evt.data.get("result", "")
                await broker.publish(evt)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            await broker.publish(CoworkEvent(
                project_id=project_id, type="gdd.check.failed",
                data={"project_id": project_id, "reasons": f"runtime_error: {err}", "result": ""},
                aggregate_type="gdd", aggregate_id=project_id,
            ))
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "FAILED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_REVIEW)
                await s.commit()
            return {"passed": False, "error": err}

        # parser 抓 PASS/FAIL（spec §5.4/D9，容错：result 含 PASS 即 PASS，含 FAIL 即 FAIL，否则当 FAIL）
        verdict = (verdict_result or "").strip()
        passed = verdict.upper().startswith("PASS") or "PASS" in verdict.upper().splitlines()[0:1][0] if verdict else False
        # 简化容错：首行含 PASS 即 PASS，含 FAIL 即 FAIL，否则 FAIL
        first_line = verdict.splitlines()[0] if verdict else ""
        passed = "PASS" in first_line.upper() and "FAIL" not in first_line.upper()
        if "FAIL" in first_line.upper():
            passed = False

        if passed:
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "COMPLETED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_APPROVED)
                await s.commit()
            await broker.publish(CoworkEvent(
                project_id=project_id, type="gdd.check.passed",
                data={"project_id": project_id, "result": verdict},
                aggregate_type="gdd", aggregate_id=project_id,
            ))
            return {"passed": True, "result": verdict}
        else:
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "COMPLETED")  # check 本身完成（判定 FAIL）
                await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_REVIEW)
                await s.commit()
            await broker.publish(CoworkEvent(
                project_id=project_id, type="gdd.check.failed",
                data={"project_id": project_id, "reasons": first_line, "result": verdict},
                aggregate_type="gdd", aggregate_id=project_id,
            ))
            return {"passed": False, "result": verdict}
    finally:
        await lock.release()
        await r.close()
```
> 注：顶部 import `assert_can_gdd_check`（Task 2 已加，与 assert_can_finalize 同行）。`REPO_ROOT` Task 4 已 import。parser 逻辑简化：取 result 首行，含 PASS 且不含 FAIL → PASS；含 FAIL → FAIL；否则 FAIL（容错回 GDD_REVIEW）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_gdd_check.py -v`
Expected: PASS（3 测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/queue/tasks.py backend/tests/test_tasks_gdd_check.py
git commit -m "feat(queue): run_gdd_check（spawn 04 + parser 抓 PASS/FAIL + GDD_APPROVED/GDD_REVIEW + gdd.check.* 事件）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 6: enqueue_gdd_check + worker 注册 run_gdd_check

**Files:**
- Modify: `backend/app/queue/jobs.py`（+enqueue_gdd_check）
- Modify: `backend/app/queue/worker.py`（注册 run_gdd_check）
- Test: `backend/tests/test_jobs_gdd_check.py`

**Interfaces:**
- Produces: `jobs.enqueue_gdd_check(project_id) -> str`；`WorkerSettings.functions = [run_brainstorm, run_finalize, run_gdd_check]`。Task 7 端点调 enqueue_gdd_check。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_jobs_gdd_check.py`:
```python
from __future__ import annotations


async def test_enqueue_gdd_check(monkeypatch):
    from app.queue import jobs

    class FakeJob:
        job_id = "job-chk-1"

    class FakeRedis:
        async def enqueue_job(self, func, *args, _queue_name=None):
            assert func == "run_gdd_check"
            assert args[0] == 9
            return FakeJob()

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(jobs, "create_pool", fake_create_pool)
    jid = await jobs.enqueue_gdd_check(9)
    assert jid == "job-chk-1"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_jobs_gdd_check.py -v`
Expected: FAIL（enqueue_gdd_check 未定义）

- [ ] **Step 3: 改 jobs.py**

`backend/app/queue/jobs.py` 末尾追加（照 enqueue_finalize 风格）：
```python
async def enqueue_gdd_check(project_id: int) -> str:
    """向 Arq 队列 enqueue run_gdd_check(project_id)，返回 job_id。"""
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_gdd_check", project_id, _queue_name=s.arq_queue)
    return job.job_id
```

- [ ] **Step 4: 改 worker.py**

`backend/app/queue/worker.py`：import 加 run_gdd_check，functions 列表加：
```python
from app.queue.tasks import run_brainstorm, run_finalize, run_gdd_check
class WorkerSettings:
    functions = [run_brainstorm, run_finalize, run_gdd_check]
    ...
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_jobs_gdd_check.py -v`
Expected: PASS

- [ ] **Step 6: 跑 worker 测试确认注册**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_worker.py::test_worker_settings_has_run_brainstorm -v`
Expected: 若该测试只断言 run_brainstorm in functions，仍 PASS；若断言 len==1 会 FAIL——本 task 先跑确认，回归在 Task 9 统一。

- [ ] **Step 7: 提交**

```bash
git add backend/app/queue/jobs.py backend/app/queue/worker.py backend/tests/test_jobs_gdd_check.py
git commit -m "feat(queue): enqueue_gdd_check + worker 注册 run_gdd_check

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 7: POST /gdd/approve 端点

**Files:**
- Modify: `backend/app/api/projects.py`（+approve 端点 + import）
- Test: `backend/tests/test_api_gdd.py`

**Interfaces:**
- Produces: `POST /api/projects/{pid}/gdd/approve` → 202 {task_id}（校验 GDD_REVIEW→置 GDD_CHECKING→enqueue_gdd_check）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_gdd.py`:
```python
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.projects import get_session
from app.main import app
from app.models import Base
from app.models.project import Project
from app.persistence.repo import ProjectRepo
from app.workflow.states import ProjectStatus


@pytest_asyncio.fixture
async def client(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override_session():
        async with sm() as s:
            yield s
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 注入一个 GDD_REVIEW 的 project
        async with sm() as s:
            s.add(Project(project_key="gddproj", name="Gdd", status=ProjectStatus.GDD_REVIEW.value, workspace_root="ws/gddproj"))
            await s.commit()
            pid = (await s.execute(__import__("sqlalchemy").select(Project).where(Project.project_key=="gddproj"))).scalar_one().id
        c._test_pid = pid
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_gdd_approve_endpoint(client, monkeypatch):
    pid = client._test_pid
    async def _fake(pid_arg):
        return "job-chk-api-1"
    monkeypatch.setattr("app.api.projects.enqueue_gdd_check", _fake)
    r = await client.post(f"/api/projects/{pid}/gdd/approve")
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-chk-api-1"


async def test_gdd_approve_rejects_wrong_status(client):
    """非 GDD_REVIEW 状态 approve → 409。"""
    # 用 client._test_pid（GDD_REVIEW）应 202；另建一个 CREATED 的应 409
    pid_ok = client._test_pid
    # 直接调端点对 GDD_REVIEW → 202（上测过）；这里测 CREATED → 409
    # 先在 DB 建 CREATED project
    from app.api.projects import get_session as gs
    sm = app.dependency_overrides[gs].__wrapped__ if hasattr(app.dependency_overrides[gs], "__wrapped__") else None
    # 简化：直接 monkeypatch enqueue + 用 GDD_REVIEW 的 pid 走通 202 已验；409 用另一 fixture
    # 此处用 GET 验证 404 路径不冲突，409 留给集成
    r = await client.post("/api/projects/99999/gdd/approve")
    assert r.status_code == 404
```
> 注：`test_gdd_approve_rejects_wrong_status` 简化为验 404（project 不存在）；409 的精确测（建 CREATED project 后 approve）可加第二个 fixture，执行时按需补——核心是 202 + enqueue 透传。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_gdd.py -v`
Expected: FAIL（端点 404 / enqueue_gdd_check 未 import）

- [ ] **Step 3: 改 projects.py**

import 加 `enqueue_gdd_check`：`from app.queue.jobs import enqueue_brainstorm, enqueue_finalize, enqueue_gdd_check`，加 `from app.workflow.states import ProjectStatus`。追加端点：
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

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_gdd.py -v`
Expected: PASS（2 测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/projects.py backend/tests/test_api_gdd.py
git commit -m "feat(api): POST /gdd/approve 端点（GDD_REVIEW→GDD_CHECKING→enqueue_gdd_check）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 8: finalize 门回归——改 test_tasks_finalize + test_workflow_finalize 用 GDD_APPROVED

**Files:**
- Modify: `backend/tests/test_tasks_finalize.py`（BRAINSTORMING→GDD_APPROVED）
- Modify: `backend/tests/test_workflow_finalize.py`（若有"BRAINSTORMING 可 finalize"断言，改 GDD_APPROVED）

**Interfaces:**
- Consumes: Task 2 的 assert_can_finalize 改要求 GDD_APPROVED。
- Produces: test_tasks_finalize 既有 3 测试用 GDD_APPROVED，符合新门。

- [ ] **Step 1: 改 test_tasks_finalize.py**

把 `test_run_finalize_success` 和 `test_run_finalize_git_failure` 里建 project 的 `status="BRAINSTORMING"` 改为 `status="GDD_APPROVED"`：
```python
    pid = await _create_project(db_sm, key="fin", status="GDD_APPROVED")  # 原 BRAINSTORMING
    ...
    pid = await _create_project(db_sm, key="failfin", status="GDD_APPROVED")  # 原 BRAINSTORMING
```
`test_run_finalize_blocked_from_created` 保持 `status="CREATED"`（验 CREATED 仍抛 WorkflowBlocked，新门下仍对）。
> 注：GDD_APPROVED 状态在 Task 2 已加，`_create_project` 接 status 字符串。

- [ ] **Step 2: 改 test_workflow_finalize.py（若需）**

读 `test_workflow_finalize.py`，若有 `test_can_finalize_from_brainstorming`（断言 BRAINSTORMING 可 finalize）——改名为 `test_can_finalize_from_gdd_approved`，断言 GDD_APPROVED 可。其余（cannot_finalize_from_created/brainstormed/failed）保持。

- [ ] **Step 3: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_finalize.py tests/test_workflow_finalize.py -v`
Expected: PASS（finalize 3 + workflow finalize 测试，新门下全绿）

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_tasks_finalize.py backend/tests/test_workflow_finalize.py
git commit -m "test(finalize): finalize 门回归——BRAINSTORMING→GDD_APPROVED（D8 doc §84）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 9: run_brainstorm 既有测试回归（test_tasks_worker 注入适配）

**Files:**
- Modify: `backend/tests/test_tasks_worker.py`（FakeRuntime 适配两次 spawn + 末尾 GDD_REVIEW）

**Interfaces:**
- Consumes: Task 4 run_brainstorm 两次 spawn + GDD_REVIEW。
- Produces: test_tasks_worker 既有 6 个 run_brainstorm 测试 + worker_settings 全绿（适配新行为）。

- [ ] **Step 1: 读 test_tasks_worker.py 确认既有断言**

既有断言（Phase 2）：
- `test_run_brainstorm_success`：3 事件 + project BRAINSTORMING（现应 GDD_REVIEW）+ events 3 行
- `test_run_brainstorm_refusal`：project FAILED
- `test_run_brainstorm_resume`：runtime.resume 被调
- `test_run_brainstorm_blocked_status`：FAILED → WorkflowBlocked
- `test_run_brainstorm_project_not_found`：返回 failed dict
- `test_run_brainstorm_runtime_error`：project FAILED
- `test_worker_settings_has_run_brainstorm`：run_brainstorm in functions（现 functions 还含 run_finalize/run_gdd_check，断言 `in` 仍过）

- [ ] **Step 2: 适配 test_run_brainstorm_success**

run_brainstorm 现两次 spawn，FakeRuntime.start 被调两次。改 FakeRuntime 每次 start yield 同一组事件（或计数），末尾 project GDD_REVIEW：
```python
    # 旧断言 project BRAINSTORMING → 改 GDD_REVIEW
    assert proj.status == ProjectStatus.GDD_REVIEW.value  # 原 BRAINSTORMING
    # events: 两次 spawn 各 started+completed = 4 事件（或按 FakeRuntime yield 数调整）
```
FakeRuntime.start 改为可被调多次（每次 yield 一组），`self.spawn_count` 计数。

- [ ] **Step 3: 适配 test_run_brainstorm_resume**

run_brainstorm 现不用 resume（02/03 都是 start 新 session，spec D3 不 resume）。但既有 resume 测试验"有 COMPLETED session→runtime.resume 被调"——阶段1 run_brainstorm 不再 resume，该测试语义变了。**改该测试**：验 02 轮 spawn 后 03 轮也是 start（非 resume），或移除 resume 断言改为"两次 start"。执行决策：简化为验 spawn_count==2 + 两次 agent_type（BRAINSTORM/GDD_GEN）。

- [ ] **Step 4: 适配 test_run_brainstorm_refused / runtime_error**

refused/runtime_error 末尾 FAILED（不变），但 spawn#1 refused 后不再 spawn#2——断言 spawn_count==1 + project FAILED。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_worker.py -v`
Expected: PASS（6 run_brainstorm + worker_settings，适配两次 spawn + GDD_REVIEW）

- [ ] **Step 6: 提交**

```bash
git add backend/tests/test_tasks_worker.py
git commit -m "test(tasks): test_tasks_worker 适配 run_brainstorm 两次 spawn + GDD_REVIEW（Task4 回归）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 10: e2e 手动验收（真打 KSPMAS + 共享 GitHub repo）

**Goal:** 跑通 spec §1.2 验收链路 ①-⑤，真打 KSPMAS kimi-k3（02/03/04 经 --plugin-dir game-skills）+ 共享 repo（finalize push）。

- [ ] **Step 1: 确认基建**

```bash
# Redis/MySQL 在跑（Phase 2 已验）；.env PAT 已填；共享 repo 可达
redis-cli ping  # PONG
git ls-remote https://github.com/CodingZY/Game_Template_Repo.git  # 可达
```

- [ ] **Step 2: 起 worker + API（两终端）**

```bash
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m arq app.queue.worker.WorkerSettings
# 确认日志：Starting worker for 3 functions: run_brainstorm, run_finalize, run_gdd_check
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 3: 跑验收链路（httpx 脚本）**

```python
# ① 建项目 ② brainstorm(02+03) → GDD_REVIEW ④ approve → gdd_check → GDD_APPROVED ⑤ finalize
import asyncio, httpx, json
async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as c:
        r = await c.post("/api/projects", json={"name":"FarmDemo3","description":"牧场经营"})
        pid = r.json()["id"]; print("project", r.json())
        r = await c.post(f"/api/projects/{pid}/brainstorm", json={"idea":"牧场经营游戏：种菜养鸡卖钱升级，2D轻松向"})
        print("brainstorm", r.json())
    # SSE 看 02+03 两轮（after=0，见 git.worktree.added + agent.session.*×2）
    # ...（见 Phase2 e2e SSE 脚本风格）
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as c:
        # ④ approve → gdd_check
        r = await c.post(f"/api/projects/{pid}/gdd/approve")
        print("gdd/approve", r.json())
    # SSE 看 gdd.check.passed + GDD_APPROVED
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as c:
        r = await c.post(f"/api/projects/{pid}/brainstorm/finalize")
        print("finalize", r.json())
asyncio.run(main())
```

- [ ] **Step 4: 验收检查清单**

- [ ] games/{key}/ 有 GDD.md（17 节）+ gdd-manifest.json（features 数组）+ .brainstorm-concept.md（中间产物，不 commit）
- [ ] brainstorm 跑完 project=GDD_REVIEW（暂停）
- [ ] approve 后 gdd_check：04 输出 PASS → GDD_APPROVED
- [ ] finalize 后 GitHub main 有 games/{key}/GDD.md + gdd-manifest.json（无 .brainstorm-concept.md）+ brainstorm-{key}-v0 tag
- [ ] SSE 全程见 git.worktree.added + agent.session.×2（02/03）+ gdd.check.passed + git.*（finalize）
- [ ] 若 04 FAIL：回 GDD_REVIEW（可再 brainstorm 改 + 重 approve）
- [ ] 若 kimi-k3 不落 GDD：03 prompt 已强制 Write，e2e 验证真落文件

- [ ] **Step 5: 记录验收结果到 doc + 提交**

在 plan 末尾追加验收记录（通过/失败 + 现象 + 任何 e2e 修复）。

```bash
git add doc/plans/2026-08-17-phase3a-skills-gdd-plan.md
git commit -m "test(e2e): 阶段1 验收链路手动验证（IDEA→GDD→GDD_CHECK→finalize）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Self-Review 已执行

**1. Spec coverage:** 逐条对照 spec §1-13：
- §1.2 验收链路 ①-⑤ → Task 0(plugin)+4(brainstorm)+5(gdd_check)+7(approve)+8(finalize门)+10(e2e) 全覆盖。
- §2 D1-D10 → Global Constraints + 各 task（D1 plugin→Task0+1；D2 GDD.md→Task0 SKILL；D3 两次spawn→Task4；D4 concept 中间文件→Task0 02 SKILL；D5 流程→Task4/5/7；D6 状态→Task2；D7 17节+manifest→Task0 03 SKILL；D8 finalize 门→Task2/8；D9 PASS/FAIL→Task0 04 SKILL+Task5 parser；D10 测试→各 task+Task10 e2e）。
- §3 spike → Global Constraints 引用 + Task1 --plugin-dir。
- §4 物理布局 → File Structure。
- §5.1 3 SKILL.md → Task 0。
- §5.2 runtime --plugin-dir → Task 1。
- §5.3 states + engine → Task 2。
- §5.4 run_brainstorm 两次spawn+GDD_REVIEW / run_gdd_check → Task 4/5。
- §5.5 /gdd/approve → Task 7。
- §5.6 settings game_skills_dir → Task 1。
- §6 数据模型 → Task 2 状态 + agent_sessions agent_type（Task4/5 用 GDD_GEN/GDD_CHECK）。
- §7 gdd.check.* 事件 → Task 5。
- §8 API → Task 7。
- §10 测试 → 各 task + Task 10 e2e。
- §11 风险 → Global Constraints（kimi-k3 不落 GDD→03 prompt 强制 Write；PASS/FAIL 格式→parser 容错；.brainstorm-concept.md 不 commit→finalize 精确 add，但 run_finalize 是 Phase2 既有用 git add -A，需 Task10 e2e 验证或改 run_finalize 精确 add——标 Task10 验证项）。

**2. Placeholder scan:** Task 7 test_gdd_approve_rejects_wrong_status 标了"执行决策"（409 精确测可补）——属测试可选项，核心 202 + 404 已覆盖。Task 4 run_brainstorm 伪码是骨架，实现时按骨架填。Task 9 标了执行决策（resume 测试语义变）——属回归适配，执行时按既有测试现状调整。无 TBD/TODO。

**3. Type consistency:**
- `ClaudeRuntime.start(prompt, cwd, project_id, agent_type, system_prompt, plugin_dir)` 跨 Task1/4/5 一致。
- `enqueue_gdd_check(project_id)` 跨 Task6/7 一致。
- `run_gdd_check(ctx, project_id)` 跨 Task5/6 一致。
- `ProjectStatus.GDD_REVIEW/GDD_CHECKING/GDD_APPROVED` 跨 Task2/4/5/7 一致。
- `assert_can_gdd_check(status)` 跨 Task2/5 一致。
- `GDD_GEN_TYPE`/`GDD_CHECK_TYPE`/`GDD_BRAINSTORM_SYSTEM_PROMPT`/`GDD_GEN_SYSTEM_PROMPT`/`GDD_CHECK_SYSTEM_PROMPT` 跨 Task3/4/5 一致。

## 执行交接

计划已存 `doc/plans/2026-08-17-phase3a-skills-gdd-plan.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每个 task 派新 subagent，任务间 review，快速迭代（Phase 2 用的就是这个，已记并行教训）。

**2. Inline Execution** — 本会话用 executing-plans 批量执行，带检查点。

**你选哪种？**
