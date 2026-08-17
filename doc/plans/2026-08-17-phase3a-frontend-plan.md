# 阶段1前端连接 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 把前端阶段1从 mock 自演改成真后端交互——用户输入创意→02 产出带选项问题→用户选/答→03 生成 GDD→前端可编辑 GDD→04 检查→finalize 落 git。其余阶段（2-5）保留 mock。

**Architecture:** 后端 run_brainstorm 拆两个 Arq job（job1 出题→BRAINSTORMING 等答；POST /brainstorm/answer 触发 job2 生成→GDD_REVIEW）。02 SKILL 改产出"带选项问题"文本，后端 questions_parser 解析成结构化存 brainstorm_questions 表。新增 GET /projects、GET /gdd、POST /brainstorm/answer、POST /gdd/submit。前端新增 api/backend.ts + useSSE hook，store 阶段1 actions 切真后端，QuestionForm/GddReviewPanel 组件。只 2 次 KSPMAS（出题+生成），vite proxy 同源无需 CORS。

**Tech Stack:** Python 3.10（agent_env D 盘）/ FastAPI / SQLAlchemy async / arq / 官方 claude `--bare --plugin-dir` + KSPMAS kimi-k3 / React 18 + Vite + TS + zustand / pytest（sqlite+Fake）/ 前端手动 e2e

**Spec:** `doc/specs/2026-08-17-phase3a-frontend-design.md`（本计划从 spec 推导，spec 与计划一并阅读）

## Global Constraints

- **Python 解释器固定** `D:/Anaconda3/envs/agent_env/python.exe`（C 盘约束：禁碰 C 盘）。Python 3.10，类型用 `Optional[X]`/`from __future__ import annotations`。
- **后端测试不打 KSPMAS/github**（D10）：sqlite + FakeRedis + FakeRuntime + FakeGitService；e2e 手动真打，不进 CI。
- **前端无单测**：前端改动靠手动 e2e（沿用现状，frontend/ 无 test 脚本）。
- **vite proxy 同源**（D6）：`frontend/vite.config.ts` 已配 `/api → 127.0.0.1:8000`，前端 dev 同源，**不加 CORS**。SSE 经 vite proxy 需实现期验通（首步）。
- **阶段1后端已就绪**：ClaudeRuntime（`--bare --plugin-dir`）、GitService、EventBroker、Arq（run_brainstorm/run_finalize/run_gdd_check）、SSE、ProjectStatus（GDD_REVIEW/CHECKING/APPROVED）、API（POST /projects、GET /projects/{id}、POST /brainstorm、POST /brainstorm/finalize、POST /gdd/approve、GET /stream）。02/03 SKILL 现状：02 产 concept 内部多轮落 `.brainstorm-concept.md`，03 读 concept 落 GDD.md+manifest——**本计划改 02/03**。
- **前端现状**：完整 mock 原型（useGameStore 用 simulateAgentStream+nextAgentReply 自演，api/client.ts 是脱节早期骨架 /api/runs）。只改阶段1，阶段 2-5 mock 保留（D1）。
- **Subagent 并行教训**（Phase 2/3a 记忆）：并行 subagent 指示**只跑自己测试文件、只 git add 自己文件**，主控统一跑全量 + 跨文件回归（改公共接口如 tasks.py/projects.py 的 task 完成后补跑受影响测试）。
- **只 2 次 KSPMAS**（D2）：02 出题一次 + 03 生成一次，不逐轮 resume（避免 refusal 叠加，e2e 已见 kimi-k3 高度不稳）。
- **commit 规范**：每 task 末提交，前缀按改动类型，结尾 `Co-Authored-By: Kscc <noreply@owtffssent.com>`。
- **不碰阶段 2-5 前端**：只改 `features/1-brainstorm` + store 阶段1 actions + 新增 api/hook。

---

## File Structure

```
backend/
├── app/
│   ├── agent/
│   │   ├── questions_parser.py            新增 Task 0：kimi-k3 文本→结构化问题
│   │   └── prompts.py                      改 Task 2：GDD_BRAINSTORM_QUESTIONS_PROMPT / GDD_GEN_FROM_ANSWERS_PROMPT
├── game-skills/skills/
│   ├── 02-game-brainstorm/SKILL.md         改 Task 2：产出带选项问题（不落 concept）
│   └── 03-gdd-generator/SKILL.md           改 Task 2：读 answers 生成 GDD（非 concept）
├── models/brainstorm_questions.py          新增 Task 1：ORM
├── models/__init__.py                       改 Task 1：注册
├── persistence/repo.py                      改 Task 1：+QuestionRepo；改 Task 6：+ProjectRepo.list_all + GddRepo
├── queue/
│   ├── tasks.py                             改 Task 3/4：run_brainstorm 拆 run_brainstorm_questions/run_brainstorm_generate
│   └── jobs.py                              改 Task 5：+enqueue_brainstorm_generate
├── api/projects.py                         改 Task 5/6/7：+POST /brainstorm/answer、GET /projects、GET /gdd、POST /gdd/submit
└── tests/
    ├── test_questions_parser.py            新增 Task 0
    ├── test_brainstorm_questions.py        新增 Task 1
    ├── test_tasks_brainstorm_questions.py  新增 Task 3
    ├── test_tasks_brainstorm_generate.py   新增 Task 4
    ├── test_api_projects_list.py           新增 Task 6
    ├── test_api_gdd.py                      改 Task 7（加 submit 测试）
    └── test_tasks_brainstorm_gdd.py        改 Task 8：既有 run_brainstorm 拆 job 后适配
frontend/src/
├── api/backend.ts                          新增 Task 9
├── hooks/useSSE.ts                         新增 Task 9
├── store/useGameStore.ts                   改 Task 10：阶段1 actions 切真后端
├── features/1-brainstorm/
│   ├── QuestionForm.tsx                    新增 Task 10
│   ├── GddReviewPanel.tsx                  新增 Task 10
│   ├── SuperpowerChat.tsx                   改 Task 10：状态机驱动
│   └── NewGameDialog.tsx                    改 Task 10：createProject
└── 其余 features/2-5                        不动（mock）
```

**责任划分**：questions_parser 纯函数最易测先行；表+Repo 纯模型；SKILL/prompt 纯文本；tasks 拆 job 串联；API 端点；前端 api/hook 独立；store/组件最后。每层接口在对应 task 的 **Interfaces** 块钉死。

---

## Task 0: questions_parser（kimi-k3 文本→结构化问题）

**Files:**
- Create: `backend/app/agent/questions_parser.py`
- Test: `backend/tests/test_questions_parser.py`

**Interfaces:**
- Produces: `parse_questions(text: str) -> list[dict]`，解析 `N. 问题 (A)选项 (B)选项` 文本成 `[{id:str, question:str, options:list[str]}]`。容错：解析失败/空→`[]`（前端当无选项自由文本答）。Task 3 run_brainstorm_questions 用。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_questions_parser.py`:
```python
from __future__ import annotations

from app.agent.questions_parser import parse_questions


def test_parse_single_question_with_options():
    text = "1. 目标平台是什么？(A)手机移动端 (B)PC端 (C)PC/网页多平台"
    qs = parse_questions(text)
    assert len(qs) == 1
    assert qs[0]["id"] == "1"
    assert qs[0]["question"] == "目标平台是什么？"
    assert qs[0]["options"] == ["手机移动端", "PC端", "PC/网页多平台"]


def test_parse_multiple_questions():
    text = """1. 目标平台？(A)手机 (B)PC (C)网页
2. 核心玩法？(A)纯农场经营 (B)农场+RPG (C)农场+社交
4. 单人还是多人？(A)纯单人 (B)单人+访客 (C)多人社交为主"""
    qs = parse_questions(text)
    assert len(qs) == 3
    assert qs[0]["id"] == "1"
    assert qs[1]["id"] == "2"
    assert qs[2]["id"] == "4"  # 编号可不连续
    assert qs[1]["options"] == ["纯农场经营", "农场+RPG", "农场+社交"]


def test_parse_question_without_options():
    """问题无选项 → options=[]（前端自由文本答）。"""
    text = "1. 你希望游戏的核心体验是什么？"
    qs = parse_questions(text)
    assert len(qs) == 1
    assert qs[0]["question"] == "你希望游戏的核心体验是什么？"
    assert qs[0]["options"] == []


def test_parse_empty_or_garbage():
    assert parse_questions("") == []
    assert parse_questions("这是一段没有问题的文本") == []
    assert parse_questions("随机废话\n更多废话") == []


def test_parse_strips_whitespace_and_noise():
    """kimi-k3 可能加前言/后语，只取问题行。"""
    text = """好的，以下是需要澄清的问题：

1. 平台？(A)手机 (B)PC
2. 风格？(A)像素 (B)卡通

希望这些帮助你了解。"""
    qs = parse_questions(text)
    assert len(qs) == 2
    assert qs[0]["question"] == "平台？"
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_questions_parser.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 questions_parser.py**

`backend/app/agent/questions_parser.py`:
```python
from __future__ import annotations

import re

# 行首 数字. 问题文本，后跟可选的若干 (X)选项
# 例：1. 目标平台？(A)手机 (B)PC (C)网页
_QLINE = re.compile(r"^\s*(\d+)\s*[.、]\s*(.+?)\s*$")
_OPT = re.compile(r"[（(]([A-Za-z\d])[)）]\s*([^（()（）]+?)(?=\s*[（(][A-Za-z\d][)）]|$)")


def parse_questions(text: str) -> list[dict]:
    """解析 kimi-k3 的 'N. 问题 (A)选项 (B)选项' 文本成结构化。

    返回 [{id, question, options}]。容错：无问题/乱格式→[]。
    只取形如 '数字. ...' 的行，忽略前言后语。
    """
    if not text:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        m = _QLINE.match(line)
        if not m:
            continue
        qid = m.group(1)
        rest = m.group(2)
        # 在 rest 里找 (A)选项 (B)选项 ...，分离 question 与 options
        opts = _OPT.findall(rest)
        if opts:
            # question 是第一个 (X) 之前的文本
            first_opt_pos = rest.find(opts[0][0])  # 用 label 字符定位
            # 更稳：用第一个 (X) 的位置
            mfirst = re.search(r"[（(][A-Za-z\d][)）]", rest)
            question = rest[: mfirst.start()].strip() if mfirst else rest.strip()
            options = [text_opt.strip() for _label, text_opt in opts]
        else:
            question = rest.strip()
            options = []
        # 去掉 question 末尾可能残留的冒号/问号空格
        out.append({"id": qid, "question": question, "options": options})
    return out
```
> 注：正则需对照 spike 实际文本调。实现期用 spike 产出的真实 6 问题文本加测试样例，确保解析对。若 kimi-k3 实际输出与样例略有出入，调正则。

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_questions_parser.py -v`
Expected: PASS（5 测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/questions_parser.py backend/tests/test_questions_parser.py
git commit -m "feat(agent): questions_parser（kimi-k3 带选项问题文本→结构化，容错）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 1: brainstorm_questions 表 + ORM + QuestionRepo

**Files:**
- Create: `backend/app/models/brainstorm_questions.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/persistence/repo.py`（+QuestionRepo）
- Test: `backend/tests/test_brainstorm_questions.py`

**Interfaces:**
- Produces: `BrainstormQuestion` ORM（`brainstorm_questions` 表：id/project_id/round/questions(JSON)/answers(JSON nullable)/created_at/updated_at）；`QuestionRepo(session)`：`create(project_id, round, questions)` / `get_latest(project_id) -> Optional[BrainstormQuestion]` / `set_answers(project_id, round, answers)`。Task 3/4/5 用。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_brainstorm_questions.py`:
```python
from __future__ import annotations

from app.models.brainstorm_questions import BrainstormQuestion
from app.persistence.repo import QuestionRepo, ProjectRepo


async def test_create_and_get_latest(async_db_session):
    proj = await ProjectRepo(async_db_session).create(
        project_key="farm", name="Farm", status="CREATED", workspace_root="ws/farm")
    repo = QuestionRepo(async_db_session)
    qs = [{"id": "1", "question": "平台？", "options": ["手机", "PC"]}]
    row = await repo.create(project_id=proj.id, round=1, questions=qs)
    assert row.id is not None
    assert row.questions == qs
    assert row.answers is None

    got = await repo.get_latest(proj.id)
    assert got is not None
    assert got.round == 1


async def test_set_answers(async_db_session):
    proj = await ProjectRepo(async_db_session).create(
        project_key="k1", name="K1", status="CREATED", workspace_root="ws/k1")
    repo = QuestionRepo(async_db_session)
    await repo.create(project_id=proj.id, round=1, questions=[{"id": "1", "question": "q", "options": []}])
    answers = [{"question_id": "1", "answer": "PC"}]
    await repo.set_answers(proj.id, 1, answers)
    got = await repo.get_latest(proj.id)
    assert got.answers == answers
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_brainstorm_questions.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 ORM**

`backend/app/models/brainstorm_questions.py`:
```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class BrainstormQuestion(Base):
    """brainstorm_questions 表：每轮澄清问题 + 用户答案（spec §5.5）。"""

    __tablename__ = "brainstorm_questions"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    questions: Mapped[list] = mapped_column(JSON, nullable=False)  # [{id,question,options}]
    answers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{question_id,answer}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: 注册到 models/__init__.py**

在 `from .project_repository import ProjectRepository` 下加 `from .brainstorm_questions import BrainstormQuestion  # noqa: E402,F401`，`__all__` 加 `"BrainstormQuestion"`。

- [ ] **Step 5: 实现 QuestionRepo（追加到 repo.py）**

```python
from app.models.brainstorm_questions import BrainstormQuestion


class QuestionRepo:
    """brainstorm_questions 表 CRUD（spec §5.5）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: int, round: int, questions: list) -> BrainstormQuestion:
        row = BrainstormQuestion(project_id=project_id, round=round, questions=questions)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_latest(self, project_id: int) -> Optional[BrainstormQuestion]:
        q = (
            select(BrainstormQuestion)
            .where(BrainstormQuestion.project_id == project_id)
            .order_by(BrainstormQuestion.round.desc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalar_one_or_none()

    async def set_answers(self, project_id: int, round: int, answers: list) -> None:
        row = await self.get_latest(project_id)
        if row is not None:
            await self.session.execute(
                update(BrainstormQuestion)
                .where(BrainstormQuestion.id == row.id)
                .values(answers=answers)
            )
```

- [ ] **Step 6: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_brainstorm_questions.py -v`
Expected: PASS

- [ ] **Step 7: 跑全量确认未破坏（只非git，git慢）**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q --ignore=tests/test_git_service.py --ignore=tests/test_template.py`
Expected: 全绿（新表 import 链不破坏既有）

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/ backend/app/persistence/repo.py backend/tests/test_brainstorm_questions.py
git commit -m "feat(models): brainstorm_questions 表 + QuestionRepo（澄清问题与答案）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 2: 02/03 SKILL + prompts 改（出题/读 answers）

**Files:**
- Modify: `backend/game-skills/skills/02-game-brainstorm/SKILL.md`
- Modify: `backend/game-skills/skills/03-gdd-generator/SKILL.md`
- Modify: `backend/app/agent/prompts.py`
- Test: `backend/tests/test_skills.py`（改断言）+ `backend/tests/test_prompts_gdd.py`（改）

**Interfaces:**
- Produces: 02 SKILL 改为"产出带选项问题"（格式 `N. 问题 (A)选项`，4-6 个，不落 concept、不内部多轮）；03 SKILL 改为"读用户答案生成 GDD.md+manifest"（非读 concept）。`prompts.py` 新增 `GDD_BRAINSTORM_QUESTIONS_PROMPT` + `GDD_GEN_FROM_ANSWERS_PROMPT`（替换既有 GDD_BRAINSTORM/GDD_GEN 用于新 job1/job2）。

- [ ] **Step 1: 改 02-game-brainstorm/SKILL.md**

改为（产出带选项问题，不落 concept）：
```markdown
---
name: 02-game-brainstorm
description: 根据用户游戏创意，产出一批带选项的澄清问题，供用户选择或自由输入
---

You are the Game Brainstorm skill. Given the user's game idea, output a batch of **clarifying questions**, each with selectable options. Do NOT write any file, do NOT generate GDD.

## Process
1. Read the user's game idea.
2. Produce 4-6 clarifying questions covering: platform, 2D/3D, core loop, core systems depth, game length, art style.
3. Each question gives 2-4 options the user can pick from (they may also type their own).

## Output format (STRICT — backend parser reads this)
Each question on its own line:
`N. 问题文本 (A)选项1 (B)选项2 (C)选项3`

Example:
```
1. 目标平台？(A)手机移动端 (B)PC端 (C)PC/网页多平台
2. 核心玩法特点？(A)纯农场经营 (B)农场+RPG冒险 (C)农场+社交/经营
3. 美术风格？(A)2D像素 (B)手绘卡通 (C)暗黑线稿
```
Only output the question lines. No preamble, no explanation. 4-6 questions.

## Rules
- Do not call any tools (no Read/Write needed).
- Stay neutral and concrete (avoid policy-flagged wording).
- Questions must be answerable by picking an option or a short free-text answer.
```

- [ ] **Step 2: 改 03-gdd-generator/SKILL.md**

改为（读 answers，非 concept）：
```markdown
---
name: 03-gdd-generator
description: 读用户创意 + 澄清答案，生成机器可执行 GDD.md(17节) + gdd-manifest.json
---

You are the GDD Generator skill. Input: the user's game idea + their answers to clarifying questions (provided in the prompt). Output: `GDD.md` + `gdd-manifest.json` via the **Write** tool.

## Critical principle
The GDD must be **machine-executable** — downstream skills generate Assets/Code/Tests from it. Prioritize clarity and structure over prose.

## GDD.md — all 17 sections (doc §42), in order
1. Game Overview  2. Target Audience  3. Core Loop  4. Player Goals  5. Game Mechanics
6. Characters  7. NPC  8. World  9. Level Design  10. Economy  11. Progression
12. UI  13. Audio  14. Art Direction  15. Technical Requirements  16. Features (F00x ids)  17. Acceptance Criteria

## gdd-manifest.json (doc §43)
{ "game": { "name","genre","platform" }, "features": [ { "id":"F001","name","priority":"P0","status":"TODO","acceptance":"<criteria>" } ] }
Every feature MUST have: id (F001..), name, priority (P0/P1/P2), status (TODO), acceptance (testable).

## Rules
- Only use Read and Write tools. Write exactly `GDD.md` and `gdd-manifest.json` in the cwd.
- Stay neutral and concrete (avoid policy-flagged wording).
- After writing, reply with a one-line summary.
```

- [ ] **Step 3: 改 prompts.py**

保留既有 `BRAINSTORM_SYSTEM_PROMPT`（Phase 1/2 旧路径，不动）。把 `GDD_BRAINSTORM_SYSTEM_PROMPT`/`GDD_GEN_SYSTEM_PROMPT` 改为新版（或新增两个并让 Task 3/4 用新的）：
```python
# Phase3a 前端连接版（spec D4）：02 出题 / 03 读 answers 生成
GDD_BRAINSTORM_QUESTIONS_PROMPT = """You are running the 02-game-brainstorm skill to produce clarifying questions.

Steps:
1. Invoke the skill /02-game-brainstorm.
2. It outputs 4-6 clarifying questions, each with (A)..(B).. options (user picks or types own).
3. Your reply's content IS the questions (format: `N. 问题 (A)选项 (B)选项`, one per line, no preamble).

Rules: do not call Write; do not generate GDD; keep the question-line format strict (backend parses it).
"""

GDD_GEN_FROM_ANSWERS_PROMPT = """You are running the 03-gdd-generator skill to produce a machine-executable GDD from the user's idea + their answers.

Steps:
1. Invoke the skill /03-gdd-generator.
2. It reads the user's idea and their clarifying answers (provided in the prompt), then calls Write to produce GDD.md (17 sections) + gdd-manifest.json in the cwd.
3. Reply with a one-line summary when done.

Rules: only use Read/Write; do not modify files other than GDD.md and gdd-manifest.json.
"""
```
保留旧 `GDD_BRAINSTORM_SYSTEM_PROMPT`/`GDD_GEN_SYSTEM_PROMPT` 不删（避免破坏既有 import，Task 8 处理）。

- [ ] **Step 4: 改 test_skills.py 断言**

02 断言改为含"带选项问题"格式而非"concept"：
```python
def test_brainstorm_skill_constraints():
    s = _read("02-game-brainstorm")
    assert "(A)" in s  # 带选项格式
    assert "问题" in s
    assert "Do NOT write" in s or "不落" in s  # 不写文件
```
03 断言去掉"读 .brainstorm-concept.md"，改为"答案"/"answers"：
```python
def test_gdd_generator_skill_constraints():
    s = _read("03-gdd-generator")
    assert "GDD.md" in s
    assert "gdd-manifest.json" in s
    assert "answers" in s.lower() or "答案" in s
    assert "F001" in s
```

- [ ] **Step 5: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_skills.py tests/test_prompts_gdd.py -v`
Expected: PASS（test_skills 改断言后绿；test_prompts_gdd 若断言旧 prompt 名需同步——见 Step 6）

- [ ] **Step 6: 改 test_prompts_gdd.py（若断言旧 prompt 名）**

若 `test_prompts_gdd.py` 断言 `GDD_GEN_SYSTEM_PROMPT` 含"03-gdd-generator"+"concept"，改为断言新 `GDD_GEN_FROM_ANSWERS_PROMPT` 含"03-gdd-generator"+"answers"。加断言 `GDD_BRAINSTORM_QUESTIONS_PROMPT` 含"(A)"+"问题"。

- [ ] **Step 7: 提交**

```bash
git add backend/game-skills/skills/02-game-brainstorm/SKILL.md backend/game-skills/skills/03-gdd-generator/SKILL.md backend/app/agent/prompts.py backend/tests/test_skills.py backend/tests/test_prompts_gdd.py
git commit -m "feat(skills): 02改产出带选项问题、03改读answers生成 + 新 prompts

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 3: run_brainstorm_questions（job1：spawn 02 出题）

**Files:**
- Modify: `backend/app/queue/tasks.py`（拆 run_brainstorm：保留旧名兼容或重命名）
- Test: `backend/tests/test_tasks_brainstorm_questions.py`

**Interfaces:**
- Consumes: `ClaudeRuntime.start(..., plugin_dir)`、`GitService`、`QuestionRepo`（Task 1）、`questions_parser.parse_questions`（Task 0）、`GDD_BRAINSTORM_QUESTIONS_PROMPT`（Task 2）、`ProjectStatus.BRAINSTORMING`。
- Produces: `async def run_brainstorm_questions(ctx, project_id, idea)`：git 前置（worktree_add）→ spawn 02 → 解析 result 文本成 questions → 存 brainstorm_questions 表 → event `brainstorm.questions_ready {questions}` → project=BRAINSTORMING（等答）。refused/runtime_error→FAILED。Task 5 端点 enqueue 此。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_tasks_brainstorm_questions.py`:
```python
from __future__ import annotations

from sqlalchemy import select

from app.models.brainstorm_questions import BrainstormQuestion
from app.models.event import Event
from app.persistence.repo import ProjectRepo, QuestionRepo
from app.queue.tasks import run_brainstorm_questions
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, FakeGitService, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


class FakeQuestionsRuntime:
    """FakeRuntime：02 出题，result 文本含带选项问题。"""
    def __init__(self, result_text):
        self.result_text = result_text
        self.cwd = None
    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
        self.cwd = cwd
        yield _evt(project_id, "agent.session.started", {"session_id": "q1", "model": "kimi-k3"})
        yield _evt(project_id, "agent.session.completed",
                   {"session_id": "q1", "result": self.result_text, "stop_reason": "end_turn"})


QUESTIONS_TEXT = """1. 目标平台？(A)手机 (B)PC (C)网页
2. 核心玩法？(A)纯经营 (B)经营+RPG
3. 美术风格？(A)像素 (B)卡通"""


async def test_run_brainstorm_questions(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ensure_template_pushed", fake_git.ensure_template_pushed)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeQuestionsRuntime(QUESTIONS_TEXT))

    pid = await _create_project(db_sm, key="q")

    result = await run_brainstorm_questions(ctx={}, project_id=pid, idea="种田游戏")

    assert result["succeeded"] is True
    # project BRAINSTORMING（等答）
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.BRAINSTORMING.value
    # 问题存表
    async with db_sm() as s:
        bq = (await s.execute(select(BrainstormQuestion).where(BrainstormQuestion.project_id == pid))).scalar_one()
        assert len(bq.questions) == 3
        assert bq.questions[0]["id"] == "1"
        assert bq.questions[0]["options"] == ["手机", "PC", "网页"]
    # event brainstorm.questions_ready
    async with db_sm() as s:
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "brainstorm.questions_ready" in types
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_questions.py -v`
Expected: FAIL（run_brainstorm_questions 未定义）

- [ ] **Step 3: 实现 run_brainstorm_questions（tasks.py 追加）**

顶部 import 加：`from app.agent.questions_parser import parse_questions` + `from app.agent.prompts import ..., GDD_BRAINSTORM_QUESTIONS_PROMPT` + `from app.persistence.repo import ..., QuestionRepo` + `from app.models.brainstorm_questions import BrainstormQuestion`（或在 repo 用）。

```python
async def run_brainstorm_questions(ctx, project_id: int, idea: str):
    """job1：spawn 02 出题 → 解析存表 → brainstorm.questions_ready → BRAINSTORMING（等答）。

    git 前置（worktree）复用 Phase2；02 result 文本经 parse_questions 成结构化问题存
    brainstorm_questions 表；refused/runtime_error→FAILED。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_brainstorm(p.status)
        await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMING)
        await s.commit()
    project_key = p.project_key

    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:brainstorm", timeout=1800)
    await lock.acquire()
    try:
        broker = EventBroker(session_factory=sm, redis=r)
        git = GitService()
        await git.ensure_clone()
        await ensure_template_pushed(git)
        branch = f"{settings.git_branch_prefix}/{project_key}-brainstorm"
        wt = await git.worktree_add(project_key, branch)
        await broker.publish(CoworkEvent(
            project_id=project_id, type="git.worktree.added",
            data={"project_id": project_id, "branch": branch, "path": str(wt)},
            aggregate_type="git", aggregate_id=project_id,
        ))
        claude_cwd = str(wt / "games" / project_key)
        async with sm() as s:
            prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
            if prow is None:
                await ProjectRepositoryRepo(s).create(
                    project_id=project_id, owner="", repository="", sub_path=f"games/{project_key}/")
            await ProjectRepositoryRepo(s).set_branch(project_id, branch)
            await s.commit()

        plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)
        runtime = ClaudeRuntime()
        result_text = None
        refused = False
        runtime_err = None
        asid = None
        async with sm() as s:
            asess = await AgentSessionRepo(s).create(project_id, AGENT_TYPE, claude_cwd)
            await s.commit()
        asid = asess.id
        try:
            async for evt in runtime.start(
                f"用户游戏创意：{idea}。请调用 /02-game-brainstorm 产出一批带选项的澄清问题。",
                claude_cwd, project_id, agent_type=AGENT_TYPE,
                system_prompt=GDD_BRAINSTORM_QUESTIONS_PROMPT, plugin_dir=plugin_dir_abs,
            ):
                evt.aggregate_id = asid
                if evt.type == "agent.session.completed":
                    result_text = evt.data.get("result", "")
                elif evt.type == "agent.refused":
                    refused = True
                await broker.publish(evt)
        except Exception as e:
            runtime_err = f"{type(e).__name__}: {e}"
            await broker.publish(CoworkEvent(
                project_id=project_id, type="agent.session.failed",
                data={"reason": "runtime_error", "error": runtime_err}, aggregate_id=asid,
            ))

        # 三态收尾
        if refused or runtime_err or not result_text:
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "FAILED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.FAILED)
                await s.commit()
            return {"succeeded": False, "refused": refused, "error": runtime_err}

        questions = parse_questions(result_text)
        async with sm() as s:
            await QuestionRepo(s).create(project_id, 1, questions)
            await AgentSessionRepo(s).finish(asid, "COMPLETED")
            await s.commit()
        await broker.publish(CoworkEvent(
            project_id=project_id, type="brainstorm.questions_ready",
            data={"project_id": project_id, "questions": questions},
            aggregate_type="brainstorm", aggregate_id=project_id,
        ))
        return {"succeeded": True, "questions": questions}
    finally:
        await lock.release()
        await r.close()
```

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_questions.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/queue/tasks.py backend/tests/test_tasks_brainstorm_questions.py
git commit -m "feat(queue): run_brainstorm_questions（job1 spawn 02 出题→解析→存表→brainstorm.questions_ready）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 4: run_brainstorm_generate（job2：读 answers→spawn 03→GDD）

**Files:**
- Modify: `backend/app/queue/tasks.py`（+run_brainstorm_generate）
- Test: `backend/tests/test_tasks_brainstorm_generate.py`

**Interfaces:**
- Consumes: `QuestionRepo.get_latest`（Task 1，读 answers）、`GDD_GEN_FROM_ANSWERS_PROMPT`（Task 2）、`ProjectStatus.GDD_REVIEW`。
- Produces: `async def run_brainstorm_generate(ctx, project_id)`：状态校验 BRAINSTORMING → 读 brainstorm_questions answers → spawn 03（prompt 拼 idea+answers）→ 落 GDD.md+manifest → event `gdd.review_ready` → GDD_REVIEW。Task 5 端点 enqueue。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_tasks_brainstorm_generate.py`:
```python
from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.persistence.repo import ProjectRepo, QuestionRepo
from app.queue.tasks import run_brainstorm_generate
from app.workflow.states import ProjectStatus

from tests.test_tasks_worker import (
    FakeAioredis, FakeGitService, _evt, _create_project, db_sm, fake_aioredis, fake_redis_lock,
)


class FakeGenerateRuntime:
    async def start(self, prompt, cwd, project_id, agent_type="brainstorm", system_prompt=None, plugin_dir=None):
        yield _evt(project_id, "agent.session.started", {"session_id": "g1", "model": "kimi-k3"})
        yield _evt(project_id, "agent.session.completed",
                   {"session_id": "g1", "result": "GDD generated", "stop_reason": "end_turn"})


async def test_run_brainstorm_generate(db_sm, fake_aioredis, monkeypatch):
    monkeypatch.setattr("app.queue.tasks.get_sessionmaker", lambda: db_sm)
    monkeypatch.setattr("app.queue.tasks.aioredis", fake_aioredis)
    fake_git = FakeGitService()
    monkeypatch.setattr("app.queue.tasks.GitService", lambda: fake_git)
    monkeypatch.setattr("app.queue.tasks.ClaudeRuntime", lambda: FakeGenerateRuntime())

    pid = await _create_project(db_sm, key="gen", status="BRAINSTORMING")
    # 预置 questions + answers
    async with db_sm() as s:
        await QuestionRepo(s).create(pid, 1, [{"id": "1", "question": "平台？", "options": ["手机", "PC"]}])
        await QuestionRepo(s).set_answers(pid, 1, [{"question_id": "1", "answer": "PC"}])
        await s.commit()

    result = await run_brainstorm_generate(ctx={}, project_id=pid)
    assert result["succeeded"] is True
    async with db_sm() as s:
        proj = await ProjectRepo(s).get(pid)
        assert proj.status == ProjectStatus.GDD_REVIEW.value
        types = [r.event_type for r in (await s.execute(
            select(Event).where(Event.project_id == pid))).scalars().all()]
        assert "gdd.review_ready" in types
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_generate.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 run_brainstorm_generate**

```python
GDD_GEN_AGENT_TYPE = "GDD_GEN"


async def run_brainstorm_generate(ctx, project_id: int):
    """job2：读 answers → spawn 03 生成 GDD → gdd.review_ready → GDD_REVIEW。"""
    settings = get_settings()
    sm = get_sessionmaker()

    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        if p.status != ProjectStatus.BRAINSTORMING.value:
            raise WorkflowBlocked(f"cannot generate from {p.status}")
        bq = await QuestionRepo(s).get_latest(project_id)
        await s.commit()
    project_key = p.project_key
    answers = bq.answers if bq else []

    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:brainstorm", timeout=1800)
    await lock.acquire()
    try:
        broker = EventBroker(session_factory=sm, redis=r)
        git = GitService()
        wt = await git.worktree_path(project_key)
        claude_cwd = str(wt / "games" / project_key)
        plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)

        async with sm() as s:
            asess = await AgentSessionRepo(s).create(project_id, GDD_GEN_AGENT_TYPE, claude_cwd)
            await s.commit()
        asid = asess.id

        runtime = ClaudeRuntime()
        refused = False
        runtime_err = None
        succeeded = False
        prompt = f"用户创意与澄清答案（JSON）：{json.dumps({'idea': '<见 idea 传入或从表>', 'answers': answers}, ensure_ascii=False)}。请调用 /03-gdd-generator 生成 GDD.md(17节) + gdd-manifest.json。"
        # 注：idea 从哪来？brainstorm_questions 表无 idea，需另存或从 project.description 取。
        # 执行决策：idea 存 project.description（createProject 时），此处读 project.description。
        try:
            async for evt in runtime.start(
                prompt, claude_cwd, project_id, agent_type=GDD_GEN_AGENT_TYPE,
                system_prompt=GDD_GEN_FROM_ANSWERS_PROMPT, plugin_dir=plugin_dir_abs,
            ):
                evt.aggregate_id = asid
                if evt.type == "agent.session.completed":
                    succeeded = True
                elif evt.type == "agent.refused":
                    refused = True
                await broker.publish(evt)
        except Exception as e:
            runtime_err = f"{type(e).__name__}: {e}"
            await broker.publish(CoworkEvent(
                project_id=project_id, type="agent.session.failed",
                data={"reason": "runtime_error", "error": runtime_err}, aggregate_id=asid,
            ))

        if refused or runtime_err or not succeeded:
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "FAILED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.FAILED)
                await s.commit()
            return {"succeeded": False, "refused": refused, "error": runtime_err}

        async with sm() as s:
            await AgentSessionRepo(s).finish(asid, "COMPLETED")
            await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_REVIEW)
            await s.commit()
        await broker.publish(CoworkEvent(
            project_id=project_id, type="gdd.review_ready",
            data={"project_id": project_id}, aggregate_type="gdd", aggregate_id=project_id,
        ))
        return {"succeeded": True}
    finally:
        await lock.release()
        await r.close()
```
> **执行决策（idea 来源）**：job2 需要 idea 拼 prompt。idea 在 job1 传入但 job2 是独立 task 拿不到。方案：idea 存 `project.description`（createProject 时前端传，或 job1 存入 brainstorm_questions 表的 questions 旁加 idea 字段）。**简化：job1 把 idea 存进 brainstorm_questions 表（加 idea 列）或在 answers 表存**——但 Task 1 已定义表无 idea 列。**更简：job1 存 idea 到 project.description**（project_service.create 已支持 description）。前端 createProject 传 idea 作 description；job1 的 idea 参数也写进 project.description（若空）。job2 读 project.description。实现时按此：job1 开头 `if not p.description: set description=idea`；job2 读 `p.description`。prompt 用 `p.description`。

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_tasks_brainstorm_generate.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/queue/tasks.py backend/tests/test_tasks_brainstorm_generate.py
git commit -m "feat(queue): run_brainstorm_generate（job2 读answers→spawn03→gdd.review_ready→GDD_REVIEW）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 5: POST /brainstorm/answer 端点 + enqueue_brainstorm_generate

**Files:**
- Modify: `backend/app/queue/jobs.py`（+enqueue_brainstorm_generate）
- Modify: `backend/app/queue/worker.py`（注册 run_brainstorm_questions/generate）
- Modify: `backend/app/api/projects.py`（改 POST /brainstorm 调 run_brainstorm_questions + 新增 POST /brainstorm/answer）
- Test: `backend/tests/test_api_brainstorm_answer.py`

**Interfaces:**
- Produces: `POST /brainstorm` 改为 enqueue `run_brainstorm_questions`（非旧 run_brainstorm）；`POST /brainstorm/answer {answers}` → 存 answers + enqueue `run_brainstorm_generate` → 202；worker 注册新两 job。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_brainstorm_answer.py`:
```python
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.api.projects import get_session
from app.main import app
from app.models import Base
from app.models.project import Project
from app.persistence.repo import QuestionRepo
from app.workflow.states import ProjectStatus


@pytest_asyncio.fixture
async def client(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override():
        async with sm() as s:
            yield s
    app.dependency_overrides[get_session] = override
    async with sm() as s:
        s.add(Project(project_key="p1", name="P", status=ProjectStatus.BRAINSTORMING.value, workspace_root="ws/p1", description="种田"))
        await s.commit()
        pid = (await s.execute(select(Project).where(Project.project_key=="p1"))).scalar_one().id
        await QuestionRepo(s).create(pid, 1, [{"id": "1", "question": "平台？", "options": ["手机", "PC"]}])
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        async with sm() as s:
            c._pid = (await s.execute(select(Project).where(Project.project_key=="p1"))).scalar_one().id
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_submit_answer(client, monkeypatch):
    pid = client._pid
    calls = []
    async def fake_enqueue(p):
        calls.append(p); return "job-gen-1"
    monkeypatch.setattr("app.api.projects.enqueue_brainstorm_generate", fake_enqueue)
    r = await client.post(f"/api/projects/{pid}/brainstorm/answer", json={"answers": [{"question_id": "1", "answer": "PC"}]})
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-gen-1"
    assert calls == [pid]
    # answers 存表
    from app.api.projects import get_session as gs
    # 直接验：端点已存 answers 到 brainstorm_questions
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_brainstorm_answer.py -v`
Expected: FAIL

- [ ] **Step 3: 改 jobs.py**

```python
async def enqueue_brainstorm_questions(project_id: int, idea: str) -> str:
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_brainstorm_questions", project_id, idea, _queue_name=s.arq_queue)
    return job.job_id


async def enqueue_brainstorm_generate(project_id: int) -> str:
    s = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(s.redis_url))
    job = await redis.enqueue_job("run_brainstorm_generate", project_id, _queue_name=s.arq_queue)
    return job.job_id
```

- [ ] **Step 4: 改 worker.py**

`functions = [run_brainstorm_questions, run_brainstorm_generate, run_finalize, run_gdd_check]`（替换旧 run_brainstorm；import 改）。保留 `job_timeout=900`。

- [ ] **Step 5: 改 api/projects.py**

`POST /brainstorm` 改调 `enqueue_brainstorm_questions`（import 改）：
```python
@router.post("/projects/{pid}/brainstorm", status_code=202)
async def start_brainstorm(pid: int, body: BrainstormRequest, session: AsyncSession = Depends(get_session)):
    # 存 idea 到 project.description（供 job2 读）
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if not p.description:
        await ProjectRepo(session).set_description(pid, body.idea)  # 新增 set_description
    await session.commit()
    job_id = await enqueue_brainstorm_questions(pid, body.idea)
    return {"task_id": job_id}
```
新增 answer 端点：
```python
class AnswerBody(BaseModel):
    answers: list  # [{question_id, answer}]

@router.post("/projects/{pid}/brainstorm/answer", status_code=202)
async def submit_answer(pid: int, body: AnswerBody, session: AsyncSession = Depends(get_session)):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if p.status != ProjectStatus.BRAINSTORMING.value:
        raise HTTPException(409, f"cannot answer from {p.status}")
    await QuestionRepo(session).set_answers(pid, 1, body.answers)
    await session.commit()
    job_id = await enqueue_brainstorm_generate(pid)
    return {"task_id": job_id}
```
import 加 `enqueue_brainstorm_questions, enqueue_brainstorm_generate` + `QuestionRepo` + `ProjectStatus` + `AnswerBody`（pydantic）。ProjectRepo 加 `set_description`（repo.py 加：`update(Project).values(description=...)`）。

- [ ] **Step 6: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_brainstorm_answer.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/queue/jobs.py backend/app/queue/worker.py backend/app/api/projects.py backend/app/persistence/repo.py backend/tests/test_api_brainstorm_answer.py
git commit -m "feat(api): POST /brainstorm/answer + enqueue_brainstorm_questions/generate + worker注册

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 6: GET /projects 列表 + GET /projects/{id}/gdd

**Files:**
- Modify: `backend/app/persistence/repo.py`（+ProjectRepo.list_all）
- Modify: `backend/app/api/projects.py`（+GET /projects + GET /gdd）
- Test: `backend/tests/test_api_projects_list.py`

**Interfaces:**
- Produces: `GET /api/projects` → list[ProjectRead]；`GET /api/projects/{id}/gdd` → `{gdd_md, manifest}`（读 worktree 文件）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_projects_list.py`:
```python
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.api.projects import get_session
from app.main import app
from app.models import Base
from app.models.project import Project


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override():
        async with sm() as s:
            yield s
    app.dependency_overrides[get_session] = override
    async with sm() as s:
        s.add(Project(project_key="a", name="A", status="CREATED", workspace_root="ws/a"))
        s.add(Project(project_key="b", name="B", status="GDD_REVIEW", workspace_root="ws/b"))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_list_projects(client):
    r = await client.get("/api/projects")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    keys = [p["project_key"] for p in data]
    assert "a" in keys and "b" in keys


async def test_get_gdd(client, monkeypatch):
    """GET /gdd 读 worktree 文件。"""
    pid = 1
    # monkeypatch GitService.worktree_path + 文件读
    from pathlib import Path
    async def fake_wp(self, key):
        return Path(f"/fake/wt/{key}-brainstorm")
    monkeypatch.setattr("app.api.projects.GitService", lambda: type("G",(),{"worktree_path":fake_wp})())
    # 注：文件不存在→404 或空。测端点 200 + 结构（gdd_md/manifest 字段）
    import unittest.mock as mock
    # mock open 读 GDD.md/manifest
    monkeypatch.setattr("builtins.open", mock.mock_open(read_data="# GDD\n"))
    r = await client.get(f"/api/projects/{pid}/gdd")
    assert r.status_code == 200
    assert "gdd_md" in r.json()
```
> 注：GET /gdd 读真实文件，单测用 monkeypatch mock 文件读。执行时按实际 worktree 文件 API 调。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_projects_list.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

ProjectRepo.list_all:
```python
async def list_all(self) -> list[Project]:
    return (await self.session.execute(select(Project).order_by(Project.id.desc()))).scalars().all()
```
GET /projects:
```python
@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)):
    return await ProjectRepo(session).list_all()
```
GET /gdd:
```python
@router.get("/projects/{pid}/gdd")
async def get_gdd(pid: int):
    p = await ProjectRepo(get_sessionmaker()()).get(pid)  # 用独立 session
    if p is None:
        raise HTTPException(404, "project not found")
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    gdd_path = wt / "games" / p.project_key / "GDD.md"
    man_path = wt / "games" / p.project_key / "gdd-manifest.json"
    gdd_md = gdd_path.read_text(encoding="utf-8") if gdd_path.exists() else ""
    manifest = man_path.read_text(encoding="utf-8") if man_path.exists() else ""
    return {"gdd_md": gdd_md, "manifest": manifest}
```
import 加 GitService。注：get_gdd 用独立 sessionmaker（非 Depends，避免 async 依赖问题）或加 Depends。实现时对齐既有 get_project 风格。

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_projects_list.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/persistence/repo.py backend/app/api/projects.py backend/tests/test_api_projects_list.py
git commit -m "feat(api): GET /projects 列表 + GET /projects/{id}/gdd（读 worktree GDD）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 7: POST /gdd/submit（写回 GDD + 04）

**Files:**
- Modify: `backend/app/api/projects.py`（+POST /gdd/submit）
- Test: `backend/tests/test_api_gdd.py`（加 submit 测试）

**Interfaces:**
- Produces: `POST /api/projects/{id}/gdd/submit {gdd_md}` → 校验 GDD_REVIEW → 写回 worktree GDD.md → 置 GDD_CHECKING → enqueue run_gdd_check → 202。

- [ ] **Step 1: 写失败测试（追加到 test_api_gdd.py）**

```python
async def test_submit_gdd(client, monkeypatch):
    """POST /gdd/submit 写回 GDD + 触发 04。"""
    # client fixture（Task 7 既有 test_api_gdd client 建 GDD_REVIEW project）
    async def fake_enqueue(p):
        return "job-chk-submit-1"
    monkeypatch.setattr("app.api.projects.enqueue_gdd_check", fake_enqueue)
    monkeypatch.setattr("app.api.projects.GitService", lambda: type("G",(),{"worktree_path": lambda self,k: __import__("pathlib").Path(f"/fake/wt/{k}-brainstorm")})())
    r = await client.post("/api/projects/1/gdd/submit", json={"gdd_md": "# edited GDD\n"})
    assert r.status_code == 202
    assert r.json()["task_id"] == "job-chk-submit-1"
```
> 注：worktree_path mock 成 async 或 sync（对齐 GitService 实际——是 async，mock 用 async 函数，见 Task 5 5 教训）。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_gdd.py -v -k submit`
Expected: FAIL

- [ ] **Step 3: 实现 submit 端点**

```python
class GddBody(BaseModel):
    gdd_md: str

@router.post("/projects/{pid}/gdd/submit", status_code=202)
async def submit_gdd(pid: int, body: GddBody, session: AsyncSession = Depends(get_session)):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    if p.status != ProjectStatus.GDD_REVIEW.value:
        raise HTTPException(409, f"cannot submit from {p.status}")
    # 写回 worktree GDD.md
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    gdd_path = wt / "games" / p.project_key / "GDD.md"
    gdd_path.parent.mkdir(parents=True, exist_ok=True)
    gdd_path.write_text(body.gdd_md, encoding="utf-8")
    await ProjectRepo(session).set_status(pid, ProjectStatus.GDD_CHECKING)
    await session.commit()
    job_id = await enqueue_gdd_check(pid)
    return {"task_id": job_id}
```
import 加 `GddBody`/`GitService`/`enqueue_gdd_check`（已有）。

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest tests/test_api_gdd.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/projects.py backend/tests/test_api_gdd.py
git commit -m "feat(api): POST /gdd/submit（写回GDD+触发04）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 8: 既有 run_brainstorm 测试回归适配

**Files:**
- Modify: `backend/tests/test_tasks_brainstorm_gdd.py`（旧 run_brainstorm 两次 spawn 测试）
- Modify: `backend/tests/test_tasks_worker.py`（FakeRuntime/断言适配）

**Interfaces:**
- Consumes: run_brainstorm 拆成 job1/job2 后，旧 `test_tasks_brainstorm_gdd`（测 run_brainstorm 两次 spawn）失效。
- Produces: 旧测试删除或改为测 job1/job2（Task 3/4 已覆盖），test_tasks_worker 的 run_brainstorm 引用清理。

- [ ] **Step 1: 评估旧 test_tasks_brainstorm_gdd**

run_brainstorm（旧两次 spawn 版）被拆成 run_brainstorm_questions + run_brainstorm_generate。旧测试 `test_run_brainstorm_two_spawns_sets_gdd_review` / `test_run_brainstorm_refused_sets_failed` 测的 run_brainstorm 已不存在。**删除 test_tasks_brainstorm_gdd.py**（job1/job2 的测试在 Task 3/4 已建覆盖）。

- [ ] **Step 2: 清理 test_tasks_worker 对 run_brainstorm 的引用**

`test_tasks_worker.py` 的 `test_run_brainstorm_*`（success/refusal/resume/runtime_error）测旧 run_brainstorm——旧 run_brainstorm 删除后这些 import 失败。**改这些测试为测 run_brainstorm_questions**（job1 单次 spawn 出题）或删除。执行决策：保留 `test_worker_settings_has_run_brainstorm` 改为 `run_brainstorm_questions in functions`；其余 run_brainstorm 测试删除（job1/job2 覆盖）。

- [ ] **Step 3: 跑全量确认**

Run: `cd backend && D:/Anaconda3/envs/agent_env/python.exe -m pytest -q --ignore=tests/test_git_service.py --ignore=tests/test_template.py`
Expected: 全绿（旧 run_brainstorm 测试删除后无残留引用）

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_tasks_brainstorm_gdd.py backend/tests/test_tasks_worker.py
git commit -m "test(tasks): 旧 run_brainstorm 测试回归（拆 job1/job2 后清理）

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```
（若 test_tasks_brainstorm_gdd.py 删除，git add -u 或 git rm）

---

## Task 9: 前端 api/backend.ts + hooks/useSSE.ts

**Files:**
- Create: `frontend/src/api/backend.ts`
- Create: `frontend/src/hooks/useSSE.ts`

**Interfaces:**
- Produces: `backend.ts` 导出 `createProject/listProjects/getProject/enqueueBrainstorm/submitAnswer/getGdd/submitGdd/approveGdd/finalizeGdd`（fetch /api/*，vite proxy）；`useSSE(projectId, onEvent)` hook（EventSource 连 /api/projects/{id}/stream，派发事件，返回 close）。

- [ ] **Step 1: 写 api/backend.ts**

`frontend/src/api/backend.ts`:
```typescript
const BASE = '/api'

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export interface ProjectRead {
  id: number; project_key: string; name: string; status: string; workspace_root: string
}
export interface Question { id: string; question: string; options: string[] }
export interface Answer { question_id: string; answer: string }
export interface GddContent { gdd_md: string; manifest: string }

export async function createProject(name: string, description?: string): Promise<ProjectRead> {
  return j(await fetch(`${BASE}/projects`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description }) }))
}
export async function listProjects(): Promise<ProjectRead[]> {
  return j(await fetch(`${BASE}/projects`))
}
export async function getProject(id: number): Promise<ProjectRead> {
  return j(await fetch(`${BASE}/projects/${id}`))
}
export async function enqueueBrainstorm(id: number, idea: string): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/brainstorm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idea }) }))
}
export async function submitAnswer(id: number, answers: Answer[]): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/brainstorm/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) }))
}
export async function getGdd(id: number): Promise<GddContent> {
  return j(await fetch(`${BASE}/projects/${id}/gdd`))
}
export async function submitGdd(id: number, gddMd: string): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/gdd/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gdd_md: gddMd }) }))
}
export async function approveGdd(id: number): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/gdd/approve`, { method: 'POST' }))
}
export async function finalizeGdd(id: number): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/brainstorm/finalize`, { method: 'POST' }))
}

export interface CoworkEvent { type: string; data: any; event_id?: string }

export function connectSSE(projectId: number, onEvent: (e: CoworkEvent) => void): () => void {
  const es = new EventSource(`${BASE}/projects/${projectId}/stream?after=0`)
  es.onmessage = (msg) => {
    try { onEvent(JSON.parse(msg.data)) } catch {}
  }
  return () => es.close()
}
```

- [ ] **Step 2: 写 hooks/useSSE.ts**

`frontend/src/hooks/useSSE.ts`:
```typescript
import { useEffect, useRef } from 'react'
import { connectSSE, type CoworkEvent } from '@/api/backend'

export function useSSE(projectId: number | null, onEvent: (e: CoworkEvent) => void) {
  const cbRef = useRef(onEvent)
  cbRef.current = onEvent
  useEffect(() => {
    if (projectId == null) return
    const close = connectSSE(projectId, (e) => cbRef.current(e))
    return close
  }, [projectId])
}
```

- [ ] **Step 3: 验 TS 编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误（前端无单测，tsc 是唯一静态检查）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/backend.ts frontend/src/hooks/useSSE.ts
git commit -m "feat(frontend): api/backend.ts 真后端客户端 + useSSE hook

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 10: 前端 store 阶段1 actions 切真后端 + 组件

**Files:**
- Modify: `frontend/src/store/useGameStore.ts`（阶段1 actions 切真后端，2-5 mock 保留）
- Create: `frontend/src/features/1-brainstorm/QuestionForm.tsx`
- Create: `frontend/src/features/1-brainstorm/GddReviewPanel.tsx`
- Modify: `frontend/src/features/1-brainstorm/SuperpowerChat.tsx`（状态机驱动）
- Modify: `frontend/src/features/1-brainstorm/NewGameDialog.tsx`（createProject）

**Interfaces:**
- Produces: store 新增真后端 actions（`createProject`/`sendIdea`/`submitAnswers`/`loadGdd`/`submitGdd`/`approveGdd`/`finalizeGdd`）+ SSE 事件驱动状态；`QuestionForm`（渲染问题+选项+自由输入）；`GddReviewPanel`（GDD.md 编辑/预览 + 提交/批准）；`SuperpowerChat` 按 project.status 切换显示 QuestionForm/GddReviewPanel/定稿按钮。

- [ ] **Step 1: 改 useGameStore 阶段1 actions**

在 `useGameStore` 加真后端阶段1状态 + actions（不删 mock 的阶段 2-5 actions）：
```typescript
import * as api from '@/api/backend'
import type { Question, Answer, GddContent, CoworkEvent } from '@/api/backend'

// 新增阶段1真后端状态字段
interface GameState {
  // ...既有 mock 字段...
  // 阶段1真后端
  realProject: api.ProjectRead | null
  realQuestions: Question[]
  realAnswers: Answer[]
  gddContent: GddContent | null
  gddMd: string  // 可编辑的 GDD.md
  sseClose?: () => void
  // actions
  createRealProject: (name: string, idea: string) => Promise<void>
  sendIdea: (idea: string) => Promise<void>
  submitRealAnswers: () => Promise<void>
  loadGdd: () => Promise<void>
  setGddMd: (text: string) => void
  submitRealGdd: () => Promise<void>
  approveRealGdd: () => Promise<void>
  finalizeRealGdd: () => Promise<void>
  handleSSEEvent: (e: CoworkEvent) => void
  setRealAnswer: (qid: string, answer: string) => void
}
```
实现（关键 actions）：
```typescript
createRealProject: async (name, idea) => {
  const p = await api.createProject(name, idea)
  set({ realProject: p })
},
sendIdea: async (idea) => {
  const p = get().realProject
  if (!p) return
  await api.enqueueBrainstorm(p.id, idea)
  // SSE 在 SuperpowerChat 用 useSSE 接，事件调 handleSSEEvent
},
handleSSEEvent: (e) => {
  if (e.type === 'brainstorm.questions_ready') {
    set({ realQuestions: e.data.questions, realAnswers: [] })
  } else if (e.type === 'agent.message.delta') {
    // 追加到 chat（03 生成流）——复用现有 chat 结构或单独流
  } else if (e.type === 'gdd.review_ready') {
    get().loadGdd()
  } else if (e.type === 'gdd.check.passed') {
    set((s) => ({ realProject: s.realProject ? { ...s.realProject, status: 'GDD_APPROVED' } : null }))
  } else if (e.type === 'gdd.check.failed') {
    set((s) => ({ realProject: s.realProject ? { ...s.realProject, status: 'GDD_REVIEW' } : null }))
  } else if (e.type === 'git.tagged') {
    set((s) => ({ realProject: s.realProject ? { ...s.realProject, status: 'BRAINSTORMED' } : null }))
  }
},
loadGdd: async () => {
  const p = get().realProject
  if (!p) return
  const g = await api.getGdd(p.id)
  set({ gddContent: g, gddMd: g.gdd_md })
},
submitRealAnswers: async () => {
  const p = get().realProject
  if (!p) return
  await api.submitAnswer(p.id, get().realAnswers)
},
submitRealGdd: async () => {
  const p = get().realProject
  if (!p) return
  await api.submitGdd(p.id, get().gddMd)
},
approveRealGdd: async () => {
  const p = get().realProject
  if (!p) return
  await api.approveGdd(p.id)
},
finalizeRealGdd: async () => {
  const p = get().realProject
  if (!p) return
  await api.finalizeGdd(p.id)
},
```
保留既有 mock 的 `startNewGame`/`sendBrainstormText`/`chooseBrainstormOption`/`appendUserThenStream`（阶段 2-5 的 mock 链路用，不动）——但 SuperpowerChat 改用真后端 actions。新增 `setRealAnswer(qid, answer)` 收集答案。

- [ ] **Step 2: 写 QuestionForm.tsx**

`frontend/src/features/1-brainstorm/QuestionForm.tsx`:
```tsx
import { useGameStore } from '@/store/useGameStore'
import { OptionChips } from './OptionChips'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useState } from 'react'
import type { Question } from '@/api/backend'

export function QuestionForm() {
  const questions = useGameStore((s) => s.realQuestions)
  const submit = useGameStore((s) => s.submitRealAnswers)
  const setRealAnswer = useGameStore((s) => s.setRealAnswer)
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  const set = (qid: string, val: string) => {
    setDrafts((d) => ({ ...d, [qid]: val }))
    setRealAnswer(qid, val)
  }

  return (
    <div className="space-y-4 p-4">
      {questions.map((q) => (
        <div key={q.id} className="rounded-lg border border-line/70 p-3">
          <div className="mb-2 text-sm font-medium text-ink">{q.question}</div>
          {q.options.length > 0 && (
            <OptionChips
              options={q.options.map((o, i) => ({ id: String(i), label: o }))}
              disabled={false}
              onPick={(opt) => set(q.id, opt.label)}
            />
          )}
          <Input
            className="mt-2"
            placeholder="或自行输入"
            value={drafts[q.id] ?? ''}
            onChange={(e) => set(q.id, e.target.value)}
          />
        </div>
      ))}
      <Button onClick={() => submit()} disabled={questions.length === 0}>提交答案</Button>
    </div>
  )
}
```
> 注：OptionChips 现有签名 `{id,label}[]`，对齐。

- [ ] **Step 3: 写 GddReviewPanel.tsx**

`frontend/src/features/1-brainstorm/GddReviewPanel.tsx`:
```tsx
import { useState } from 'react'
import { useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'
import { MarkdownView } from '@/components/shared/MarkdownView'

export function GddReviewPanel() {
  const gddMd = useGameStore((s) => s.gddMd)
  const setGddMd = useGameStore((s) => s.setGddMd)
  const submit = useGameStore((s) => s.submitRealGdd)
  const approve = useGameStore((s) => s.approveRealGdd)
  const [editing, setEditing] = useState(false)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line/70 p-3">
        <Button size="sm" variant={editing ? 'default' : 'ghost'} onClick={() => setEditing(!editing)}>
          {editing ? '预览' : '编辑'}
        </Button>
        <Button size="sm" onClick={() => submit()}>提交并检查</Button>
        <Button size="sm" variant="ghost" onClick={() => approve()}>直接批准</Button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto p-4">
        {editing ? (
          <textarea
            className="h-full w-full resize-none rounded-lg border border-line/70 p-3 font-mono text-sm"
            value={gddMd}
            onChange={(e) => setGddMd(e.target.value)}
          />
        ) : (
          <MarkdownView content={gddMd} />
        )}
      </div>
    </div>
  )
}
```
> 注：MarkdownView 组件需确认 props（content）。先 Read 确认其对齐。

- [ ] **Step 4: 改 SuperpowerChat.tsx（状态机驱动）**

改 SuperpowerChat：用 `realProject.status` 切换显示。CREATED 显示"输入创意"框；BRAINSTORMING 显示 QuestionForm；GDD_REVIEW 显示 GddReviewPanel；GDD_APPROVED 显示"定稿落 git"按钮；BRAINSTORMED 显示完成。用 `useSSE(realProject?.id, handleSSEEvent)` 接事件。保留既有 mock 的 chat 渲染作为 agent.message.delta 流显示（或单独流区）。
```tsx
import { useSSE } from '@/hooks/useSSE'
import { useGameStore } from '@/store/useGameStore'
import { QuestionForm } from './QuestionForm'
import { GddReviewPanel } from './GddReviewPanel'
// ... 既有 imports

export function SuperpowerChat() {
  const project = useGameStore((s) => s.realProject)
  const createRealProject = useGameStore((s) => s.createRealProject)
  const sendIdea = useGameStore((s) => s.sendIdea)
  const finalize = useGameStore((s) => s.finalizeRealGdd)
  const handleSSEEvent = useGameStore((s) => s.handleSSEEvent)
  useSSE(project?.id ?? null, handleSSEEvent)
  const [name, setName] = useState('')
  const [idea, setIdea] = useState('')

  if (!project) {
    return <NewGameInline onCreate={async (n, i) => { await createRealProject(n, i); }} />
  }
  const st = project.status
  return (
    <div className="flex h-full flex-col">
      {st === 'CREATED' && <IdeaInput idea={idea} setIdea={setIdea} onSend={() => sendIdea(idea)} />}
      {st === 'BRAINSTORMING' && <QuestionForm />}
      {st === 'GDD_REVIEW' && <GddReviewPanel />}
      {st === 'GDD_CHECKING' && <div className="p-4 text-sm text-ink-3">GDD 检查中…</div>}
      {st === 'GDD_APPROVED' && (
        <div className="p-4"><Button onClick={() => finalize()}>定稿落 git</Button></div>
      )}
      {st === 'BRAINSTORMED' && <div className="p-4 text-sm">已完成，GDD 已落 git。</div>}
      {st === 'FAILED' && <div className="p-4 text-sm text-red-500">失败（kimi-k3 refusal 或错误），可重试。</div>}
    </div>
  )
}
```
> 注：IdeaInput/NewGameInline 是简化内联组件，实现时对齐既有 UI 风格。NewGameDialog 改调 createRealProject。

- [ ] **Step 5: 改 NewGameDialog.tsx**

`submit` 改：
```tsx
const submit = () => {
  createRealProject(name.trim() || '新游戏创意', idea.trim())  // 需加 idea 输入框
  setName(''); setIdea('')
  onOpenChange(false)
  navigate('/brainstorm')
}
```
加 idea 输入框（创意文本）。

- [ ] **Step 6: 验 TS 编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 7: 提交**

```bash
git add frontend/src/store/useGameStore.ts frontend/src/features/1-brainstorm/ frontend/src/features/1-brainstorm/NewGameDialog.tsx
git commit -m "feat(frontend): store阶段1切真后端 + QuestionForm/GddReviewPanel + SuperpowerChat状态机

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Task 11: e2e 手动验收（真打 KSPMAS + GitHub + 前端）

**Goal:** 起 后端 API+worker + 前端 vite dev，浏览器跑 spec §1.2 验收链路。

- [ ] **Step 1: 确认基建**

```bash
redis-cli ping  # PONG
# MySQL 在跑；.env PAT 填了；共享 repo 可达
```

- [ ] **Step 2: 首步验 SSE 经 vite proxy**

```bash
# 起后端
cd backend && D:/Anaconda3/envs/agent_env/python.exe -m uvicorn app.main:app --port 8000
# 起前端
cd frontend && npm run dev  # :5173
# 浏览器/curl 验 SSE 经 proxy
curl -N http://127.0.0.1:5173/api/projects/1/stream?after=0  # 应见 SSE 流（或 keepalive）
```
若 SSE 经 proxy 不通：检查 vite.config proxy 是否需 `ws:true`/`changeOrigin`；或后端加 CORS（临时）。记现象。

- [ ] **Step 3: 浏览器跑验收链路**

浏览器开 `http://localhost:5173`：
1. 新建游戏（输入名+创意）→ 后端建 project（CREATED）→ 验：`curl localhost:8000/api/projects` 见新 project
2. brainstorm 页 → 创意发送 → SSE 收 02 问题 → 前端 QuestionForm 渲染选项 chips
3. 选选项/自填 → 提交答案 → SSE 收 03 生成流 → GDD_REVIEW → GddReviewPanel 显示 GDD.md
4. 编辑 GDD → 提交 → 04 检查 → PASS（GDD_APPROVED）或 FAIL（回 GDD_REVIEW）
5. GDD_APPROVED → 点定稿 → SSE 收 git.* → GitHub 有 GDD.md + tag

- [ ] **Step 4: 验收检查清单**

- [ ] 新建游戏 → 后端真建 project（CREATED，GET /projects 见）
- [ ] 创意发送 → 前端渲染 02 带选项问题（OptionChips）
- [ ] 选/答 → 提交 → 03 生成 GDD → 前端显示 GDD.md（可编辑）
- [ ] 编辑 GDD → 提交 → 04 → PASS=GDD_APPROVED / FAIL=回 GDD_REVIEW
- [ ] 定稿 → GitHub 有 games/{key}/GDD.md + brainstorm-{key}-v0 tag
- [ ] kimi-k3 refusal 时前端显示 FAILED 提示（三态）
- [ ] SSE 经 vite proxy 全程可见事件

- [ ] **Step 5: 记录验收结果 + 提交**

plan 末尾追加验收记录。

```bash
git add doc/plans/2026-08-17-phase3a-frontend-plan.md
git commit -m "test(e2e): 阶段1前端连接验收

Co-Authored-By: Kscc <noreply@owtffssent.com>"
```

---

## Self-Review 已执行

**1. Spec coverage:** 逐条对照 spec §1-12：
- §1.2 验收链路 ①-⑦ → Task 0(parser)+3(job1)+5(answer端点)+4(job2)+6(gdd端点)+7(submit)+10(前端)+11(e2e) 全覆盖。
- §2 D1-D10 → Global Constraints + 各 task（D1 只接阶段1→Task10 保留 mock；D2 2次KSPMAS→Task3/4 各一次spawn；D3 带选项→Task0 parser+Task2 02 SKILL；D4 02改出题→Task2；D5 GDD可编辑→Task7 submit+Task10 GddReviewPanel；D6 vite proxy→Global+Task11 验；D7 两Arq job→Task3/4/5；D8 解析容错→Task0；D9 SSE→Task9 useSSE；D10 测试→各 task+Task11）。
- §3 spike → Global 引用 + Task0 parser 基于 spike 文本。
- §4.2 模块清单 → File Structure 全覆盖。
- §5.1-5.8 模块设计 → Task 0-10 全对应。
- §6 brainstorm_questions 表 → Task 1。
- §7 事件 brainstorm.questions_ready/gdd.review_ready → Task 3/4。
- §8 API → Task 5/6/7。
- §10 风险 → Global（kimi-k3 refusal/SSE proxy）+ Task 11 验。
- §11 边界 → Global（不碰 2-5）。

**2. Placeholder scan:** Task 4 idea 来源标"执行决策"（存 project.description）——属设计决策已明，实现按此。Task 6/7 mock 文件读、Task 10 MarkdownView props 需 Read 确认——属实现细节，已注明。无 TBD/TODO。

**3. Type consistency:**
- `parse_questions(text) -> list[dict]` 跨 Task 0/3 一致。
- `QuestionRepo.create/get_latest/set_answers` 跨 Task 1/3/4/5 一致。
- `run_brainstorm_questions(ctx, project_id, idea)` / `run_brainstorm_generate(ctx, project_id)` 跨 Task 3/4/5 一致。
- `enqueue_brainstorm_questions(id, idea)` / `enqueue_brainstorm_generate(id)` 跨 Task 5 一致。
- `ProjectRead {id, project_key, name, status, workspace_root}` 跨后端 Task 6 / 前端 Task 9 一致。
- `Question {id, question, options}` / `Answer {question_id, answer}` 跨 Task 9/10 一致。
- `CoworkEvent {type, data}` 跨 Task 9/10 SSE 一致。

## 执行交接

计划已存 `doc/plans/2026-08-17-phase3a-frontend-plan.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每 task 派 subagent，任务间 review（Phase 2/3a 用的这个）。

**2. Inline Execution** — 本会话 executing-plans 批量执行 + 检查点。

**你选哪种？**
