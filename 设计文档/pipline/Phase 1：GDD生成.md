可行，而且我认为这个方案比“每问一个问题就调用一次 LLM”更适合你这个 **AI_Cowork_Game**。

核心思想可以概括成：

> **一次 LLM 负责规划“需要确认什么”，Temporal 负责把这些问题变成一个可暂停、可恢复、可人工干预的长流程；前端只是逐题消费 Human Task。**

这样既降低 LLM 调用次数，又能利用 Temporal 的 **Workflow / Signal / Query / Activity** 做可靠的 Human-in-the-Loop。

---

# 一、Phase 1 总体目标

Phase 1 只解决：

```text
用户游戏想法
    ↓
AI 头脑风暴
    ↓
识别需要用户确认的问题
    ↓
一次 LLM 生成 Question Plan
    ↓
Temporal Workflow 暂停等待用户
    ↓
前端逐个展示问题
    ↓
用户选择
    ↓
Temporal Signal 接收答案
    ↓
继续下一个问题
    ↓
所有问题完成
    ↓
LLM 汇总需求
    ↓
生成 GDD.md
    ↓
GDD Check
    ↓
Phase 1 完成
```

注意：

**不是：**

```text
问题1 → LLM
问题2 → LLM
问题3 → LLM
问题4 → LLM
```

而是：

```text
用户想法
   ↓
LLM × 1
   ↓
Question Plan
   ├── Q1
   ├── Q2
   ├── Q3
   ├── Q4
   └── Q5
        ↓
Temporal
        ↓
逐题询问用户
```

---

# 二、为什么 Temporal 非常适合这个场景

你的流程本质上是一个：

> **长时间运行 + 等待人 + 可以暂停 + 可以恢复 + 可以查询状态的 Workflow。**

例如用户回答：

```text
Q1：选择游戏视角
A：俯视角

Q2：核心玩法
A：种田

Q3：是否加入NPC
A：是
```

然后用户突然关闭网页。

Temporal Workflow 不应该消失。

它仍然保持：

```text
Workflow
ID: game-project-001
Status: WAITING_HUMAN
Current Question: Q4
Answered: 3/7
```

用户第二天重新打开：

```text
GET /projects/game-project-001
```

就可以继续：

```text
Q4
```

这正是 Temporal 的优势。

---

# 三、推荐的整体架构

```text
                         ┌──────────────────────┐
                         │      Frontend        │
                         │ React / Next.js      │
                         └──────────┬───────────┘
                                    │
                         HTTP / WebSocket
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Game API Server   │
                         │                      │
                         │ Project API          │
                         │ Question API         │
                         │ Signal API           │
                         │ Query API            │
                         └──────────┬───────────┘
                                    │
                         Temporal Client
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │      Temporal Server        │
                    │                             │
                    │ GameDesignWorkflow          │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
             Temporal Activity              Human Signal
                    │                             │
                    ▼                             │
             Claude Code CLI                      │
                    │                             │
                    ▼                             │
              Claude API                          │
                    │                             │
                    ▼                             │
             Game Design Agent                    │
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                             GDD.md
                                   │
                                   ▼
                              GDD Check
```

---

# 四、Claude Code CLI 在这里应该扮演什么角色？

建议不要让 Temporal Workflow 直接承担 LLM 逻辑。

Temporal：

> **Orchestrator**

Claude Code：

> **Agent Runtime**

LLM：

> **Reasoning Engine**

三者职责明确分开。

```text
Temporal
负责：
- 状态
- 流程
- 等待
- Signal
- Query
- Retry
- Timeout
- Recovery

Claude Code
负责：
- 调用 Skill
- 读取上下文
- 运行 Agent
- 生成 GDD
- GDD Check

LLM
负责：
- 游戏设计推理
- 问题识别
- 需求总结
- GDD生成
```

---

# 五、Phase 1 的核心 Workflow

建议定义：

```text
GameDesignWorkflow
```

输入：

```typescript
interface GameDesignInput {
  projectId: string
  userIdea: string
}
```

Workflow：

```text
GameDesignWorkflow
        │
        ▼
Initialize Project
        │
        ▼
Brainstorm Analysis
        │
        ▼
Generate Question Plan
        │
        ▼
WAIT HUMAN
        │
        ├──── Signal: submitAnswer()
        │
        ├──── Query: getState()
        │
        └──── Signal: skipQuestion()
        │
        ▼
All Questions Answered
        │
        ▼
Requirement Synthesis
        │
        ▼
Generate GDD.md
        │
        ▼
GDD Check
        │
        ├──── PASS
        │      ↓
        │   Complete
        │
        └──── FAIL
               ↓
          Generate Clarification
               ↓
          WAIT HUMAN
```

---

# 六、最关键的设计：Question Plan

这是整个方案的核心。

一次 LLM 调用，不是直接问用户。

而是让 Claude Code 生成：

```json
{
  "questions": [
    {
      "id": "camera",
      "title": "你希望游戏采用什么视角？",
      "type": "single_choice",
      "options": [
        {
          "id": "top_down",
          "label": "俯视角"
        },
        {
          "id": "side_scroll",
          "label": "横版"
        }
      ],
      "required": true,
      "reason": "影响地图、角色移动和 Phaser 实现方式"
    },

    {
      "id": "core_loop",
      "title": "你希望玩家主要做什么？",
      "type": "single_choice",
      "options": [
        {
          "id": "farming",
          "label": "种田经营"
        },
        {
          "id": "combat",
          "label": "战斗冒险"
        },
        {
          "id": "exploration",
          "label": "探索解谜"
        }
      ],
      "required": true
    }
  ]
}
```

然后 Temporal 不再需要 LLM。

Temporal 只做：

```text
Q1
 ↓
等待 Signal
 ↓
Q2
 ↓
等待 Signal
 ↓
Q3
```

---

# 七、为什么“先生成所有问题”比动态问问题更好？

假设用户输入：

> 我想做一个牧场经营小游戏。

LLM 一次分析：

```text
发现 6 个设计不确定性：

1. 视角
2. 核心经营方式
3. 是否有 NPC
4. 是否有战斗
5. 时间系统
6. V1规模
```

生成：

```text
QuestionPlan
```

Temporal 将：

```text
QuestionPlan
```

持久化。

前端：

```text
Q1
```

用户回答：

```text
A1
```

然后：

```text
Q2
```

---

# 八、但这里有一个非常重要的问题

**不能简单地认为“一次 LLM 生成的问题全部有效”。**

因为：

```text
Q1 = 俯视角
Q2 = 战斗
Q3 = 是否有NPC
```

用户回答 Q1 后，可能导致 Q2 已经没有意义。

所以 Question Plan 应该支持：

```text
depends_on
```

例如：

```json
{
  "id": "combat_system",
  "depends_on": [
    {
      "question": "gameplay_type",
      "equals": "adventure"
    }
  ]
}
```

于是：

```text
Q1
 ↓
用户选择 farming
 ↓
combat_system
 ↓
SKIP
```

这样仍然不需要额外 LLM 调用。

---

# 九、推荐 Question Schema

```typescript
interface DesignQuestion {
  id: string

  category:
    | "core_loop"
    | "camera"
    | "player"
    | "world"
    | "progression"
    | "combat"
    | "social"
    | "scope"

  question: string

  type:
    | "single_choice"
    | "multi_choice"
    | "text"

  options?: {
    id: string
    label: string
    description?: string
  }[]

  required: boolean

  priority:
    | "blocking"
    | "important"
    | "optional"

  dependsOn?: {
    questionId: string
    operator: "equals" | "not_equals"
    value: string
  }[]

  defaultOption?: string

  allowCustomInput?: boolean
}
```

---

# 十、为什么一定要有 Priority？

因为你希望：

> **快速进入 GDD。**

所以问题可以分：

```text
BLOCKING
IMPORTANT
OPTIONAL
```

例如：

### Blocking

```text
游戏核心玩法？
游戏视角？
V1目标？
```

必须问。

### Important

```text
是否加入NPC？
是否有商店？
是否有天气？
```

可以问。

### Optional

```text
NPC具体几点睡觉？
商店每天几点刷新？
```

不要问。

---

# 十一、建议设置“最多问题数”

这是防止 Agent 陷入无限需求分析的关键。

例如：

```yaml
brainstorm:
  max_questions: 7
  blocking_questions: 5
  optional_questions: 2
```

甚至：

```text
默认最多 5 个问题
```

如果 5 个问题已经能够生成 V1：

> 立即结束。

---

# 十二、前端如何实现？

前端实际上非常简单。

Temporal Backend 返回：

```json
{
  "projectId": "game-001",
  "status": "WAITING_HUMAN",
  "progress": {
    "current": 2,
    "total": 6
  },
  "question": {
    "id": "camera",
    "question": "你希望采用什么视角？",
    "type": "single_choice",
    "options": [
      {
        "id": "top_down",
        "label": "俯视角"
      },
      {
        "id": "side",
        "label": "横版"
      }
    ]
  }
}
```

页面：

```text
┌──────────────────────────────┐
│       创建你的游戏            │
│                              │
│      第 2 / 6 个问题          │
│                              │
│  你希望采用什么游戏视角？       │
│                              │
│  ┌────────────────────────┐  │
│  │       俯视角            │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │       横版              │  │
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘
```

用户选择：

```text
POST /projects/game-001/answers
```

Backend：

```text
Temporal Signal
      ↓
submitAnswer()
```

---

# 十三、Temporal Signal 设计

建议至少设计 4 个 Signal。

## 1. submitAnswer

```typescript
submitAnswer({
  questionId: string,
  answer: string | string[]
})
```

---

## 2. skipQuestion

```typescript
skipQuestion({
  questionId: string
})
```

用于：

> “我不知道，你帮我决定。”

非常重要。

Agent 可以直接使用：

```text
defaultOption
```

---

## 3. modifyAnswer

用户返回上一题修改：

```typescript
modifyAnswer({
  questionId,
  answer
})
```

Workflow 重新计算后续问题。

例如：

```text
Q1 Farming
 ↓
Q2 NPC
 ↓
Q3 Relationship
```

用户把：

```text
Q2 = No
```

改成：

```text
Q2 = Yes
```

那么：

```text
Q3
```

重新启用。

---

## 4. cancel / restart

```typescript
cancelDesign()

restartBrainstorm()
```

---

# 十四、Temporal Query 设计

你提到：

> Query → 外部实时读取 Agent 当前思考步骤与状态

这里建议稍微调整一个概念：

**不要让 Query 暴露“Agent 内部思维链”。**

应该暴露：

> **可观察的 Workflow 状态 / Agent 执行阶段 / 当前任务。**

例如：

```typescript
getDesignState()
```

返回：

```json
{
  "projectId": "game-001",

  "status": "WAITING_HUMAN",

  "phase": "BRAINSTORM",

  "step": "USER_CONFIRMATION",

  "progress": {
    "answered": 3,
    "total": 6
  },

  "currentQuestionId": "npc",

  "completedQuestions": [
    "camera",
    "core_loop",
    "v1_scope"
  ],

  "message": "等待用户确认是否加入NPC"
}
```

而不是：

```text
Claude 正在思考：
“我认为用户可能……”
```

这是很重要的 Agent 架构边界。

---

# 十五、建议 Query 返回 Agent State Machine

例如：

```text
INIT
 ↓
ANALYZING_IDEA
 ↓
GENERATING_QUESTION_PLAN
 ↓
WAITING_HUMAN
 ↓
COLLECTING_REQUIREMENTS
 ↓
SYNTHESIZING_REQUIREMENTS
 ↓
GENERATING_GDD
 ↓
CHECKING_GDD
 ↓
COMPLETED
```

前端可以直接展示：

```text
游戏需求分析
━━━━━━━━━━━━━━━━━━
✓ 分析游戏想法

✓ 确定核心玩法

● 等待确认游戏视角

○ 确认 V1 范围

○ 生成 GDD

○ GDD 检查
```

---

# 十六、Signal + Query 的完整关系

你这个系统可以形成一个非常漂亮的模式：

```text
                    Frontend
                       │
            ┌──────────┴───────────┐
            │                      │
          Query                  Signal
            │                      │
            ▼                      ▼
     getDesignState()        submitAnswer()
            │                      │
            ▼                      ▼
       Temporal Workflow
```

Query：

> “现在到哪一步了？”

Signal：

> “这是用户刚刚给出的答案。”

这非常符合 Temporal 的使用方式。

---

# 十七、Claude Code CLI 的调用方式

建议把 Claude Code CLI 封装成 Temporal Activity：

```text
Activity: runClaudeCode
```

输入：

```typescript
interface ClaudeTask {
  projectId: string
  skill: string
  prompt: string
  contextFiles: string[]
}
```

例如：

```text
runClaudeCode(
  skill = "game-brainstorm",
  prompt = userIdea
)
```

Claude Code：

```text
读取：

skills/game-brainstorm/SKILL.md

↓

调用 Claude API

↓

生成：

question-plan.json
```

Activity 返回：

```json
{
  "questions": [...]
}
```

Temporal Workflow 保存这个结果。

---

# 十八、不要让 Claude Code 长时间占用 Workflow

这一点很重要。

不要：

```text
Workflow
 └── Claude Code
      └── 一直运行 2小时
```

应该：

```text
Workflow
 │
 ├── Activity: AnalyzeIdea
 │
 ├── WAIT Signal
 │
 ├── WAIT Signal
 │
 ├── Activity: SynthesizeRequirements
 │
 ├── Activity: GenerateGDD
 │
 └── Activity: GDDCheck
```

Temporal Workflow 本身永远只负责 orchestration。

---

# 十九、推荐的 Phase 1 Temporal Workflow

可以直接定义：

```text
GameDesignWorkflow
```

伪代码：

```typescript
async function GameDesignWorkflow(input) {

  // 1
  const questionPlan =
    await activities.analyzeIdea({
      idea: input.userIdea
    })

  // 2
  state.questionPlan = questionPlan

  // 3
  while (!allRequiredQuestionsAnswered()) {

    const question =
      getNextQuestion()

    state.currentQuestion = question

    await condition(
      () =>
        answers.has(question.id) ||
        skipped.has(question.id)
    )

    processAnswer(question)
  }

  // 4
  state.phase = "SYNTHESIZING"

  const requirements =
    await activities.synthesizeRequirements({
      idea,
      answers
    })

  // 5
  const gdd =
    await activities.generateGDD({
      requirements
    })

  // 6
  const check =
    await activities.checkGDD({
      gdd
    })

  // 7
  if (check.status === "PASS") {
    state.phase = "COMPLETED"

    return {
      gdd
    }
  }

  // 8
  if (check.hasBlockingIssues) {

    const clarificationPlan =
      await activities.generateClarification({
        gdd,
        check
      })

    // 再进入 Human Loop
    ...
  }
}
```

---

# 二十、这里建议加入一个“Requirements Snapshot”

不要让最终 GDD 直接基于：

```text
User Idea + 6个答案
```

应该中间产生：

```text
requirements.json
```

结构：

```text
User Idea
    +
Question Plan
    +
User Answers
    ↓
Requirements Snapshot
    ↓
GDD
```

例如：

```json
{
  "game": {
    "genre": "farming_sim",
    "camera": "top_down",
    "platform": "web",
    "engine": "phaser"
  },

  "core_loop": [
    "plant",
    "grow",
    "harvest",
    "sell"
  ],

  "v1": {
    "map": "small_farm",
    "crops": 3,
    "npc": 1,
    "shop": true
  },

  "decisions": [
    {
      "questionId": "camera",
      "answer": "top_down",
      "source": "user"
    }
  ],

  "assumptions": [
    {
      "key": "save",
      "value": "localStorage",
      "source": "default"
    }
  ]
}
```

这个文件非常重要。

因为后续：

```text
GDD
Asset Spec
Code Spec
Version Plan
```

全部可以从：

```text
Requirements Snapshot
```

产生。

---

# 二十一、建议保存完整设计事件

Temporal 本身有 Event History，但业务层最好也保存：

```text
design_events
```

例如：

```json
{
  "eventId": "evt-001",
  "type": "QUESTION_ANSWERED",
  "questionId": "camera",
  "answer": "top_down",
  "timestamp": "..."
}
```

后面用户修改需求时就非常方便。

最终可以形成：

```text
Idea
 ↓
Decision 1
 ↓
Decision 2
 ↓
Decision 3
 ↓
GDD v1
```

甚至：

```text
GDD v1
 ↓
User Feedback
 ↓
Decision Change
 ↓
GDD v2
```

这对后面的 AI_Cowork Game 非常重要。

---

# 二十二、Phase 1 的 Skill 结构

我建议 Claude Code 项目这样组织：

```text
.ai-cowork/
│
├── skills/
│
│   ├── game-brainstorm/
│   │   └── SKILL.md
│   │
│   ├── game-requirements/
│   │   └── SKILL.md
│   │
│   ├── gdd-generator/
│   │   └── SKILL.md
│   │
│   └── gdd-check/
│       └── SKILL.md
│
├── schemas/
│   ├── question-plan.schema.json
│   ├── requirements.schema.json
│   └── gdd-check.schema.json
│
└── templates/
    └── GDD.md
```

这里我建议相比你前面提出的三个 Skill：

```text
game-brainstorm
gdd-generator
gdd-check
```

**增加一个非常轻的 `game-requirements`。**

它不需要调用 LLM。

它主要负责：

```text
Question Plan
+
Answers
+
Defaults
+
User Overrides
↓
Requirements Snapshot
```

这样架构会干净很多。

---

# 二十三、完整 Phase 1 架构

最终：

```text
                     User
                       │
                       ▼
                ┌─────────────┐
                │   Frontend  │
                └──────┬──────┘
                       │
               HTTP / WebSocket
                       │
                       ▼
                ┌─────────────┐
                │   Game API  │
                └──────┬──────┘
                       │
                Temporal Client
                       │
                       ▼
        ┌────────────────────────────┐
        │       Temporal Server      │
        │                            │
        │ GameDesignWorkflow         │
        │                            │
        │  Analyze                   │
        │    ↓                       │
        │  QuestionPlan              │
        │    ↓                       │
        │  WAIT                      │
        │    ↓                       │
        │  Signal                    │
        │    ↓                       │
        │  WAIT                      │
        │    ↓                       │
        │  Requirements              │
        │    ↓                       │
        │  GDD                      │
        │    ↓                       │
        │  GDD Check                 │
        └────────────┬───────────────┘
                     │
                     ▼
              Claude Code CLI
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     brainstorm    gdd-gen    gdd-check
          │          │          │
          └──────────┼──────────┘
                     ▼
                  Claude API
```

---

# 二十四、一个完整例子

用户：

> 我想做一个类似牧场物语的小游戏。

### Step 1

Temporal：

```text
ANALYZING_IDEA
```

Claude Code 调用一次：

```text
game-brainstorm
```

得到：

```text
6 questions
```

---

### Step 2

前端显示：

> 你希望游戏采用什么视角？

```text
[ 俯视角 ]
[ 横版 ]
```

用户：

> 俯视角

Signal：

```text
submitAnswer(camera, top_down)
```

---

### Step 3

前端：

> 你希望 V1 的核心玩法是什么？

```text
[ 种田经营 ]
[ 战斗冒险 ]
[ 探索 ]
```

用户：

> 种田经营

---

### Step 4

前端：

> V1 是否加入 NPC？

```text
[ 不加入 ]
[ 加入 1 个简单 NPC ]
[ 加入多个 NPC ]
```

用户：

> 1 个 NPC

---

### Step 5

系统发现：

```text
NPC = true
```

Question Plan 中：

```text
NPC Relationship
```

被激活。

继续问：

> NPC 是否需要好感度？

```text
[ 不需要 ]
[ 简单好感度 ]
```

---

### Step 6

回答完成。

Temporal：

```text
SYNTHESIZING_REQUIREMENTS
```

然后：

```text
Requirements Snapshot
```

---

### Step 7

Claude Code：

```text
gdd-generator
```

生成：

```text
GDD.md
```

---

### Step 8

Claude Code：

```text
gdd-check
```

得到：

```yaml
status: PASS

blocking: []

warnings:
  - economy values are provisional
  - NPC schedule uses default values
```

Temporal：

```text
COMPLETED
```

---

# 二十五、最终前端看到的不是“AI思考”

而是：

```text
┌──────────────────────────────────────┐
│ 创建你的 Phaser 2D 游戏               │
│                                      │
│ 需求确认                             │
│                                      │
│ ✓ 游戏核心玩法                       │
│ ✓ 游戏视角                           │
│ ✓ V1范围                             │
│ ● NPC设计                             │
│ ○ 时间系统                            │
│                                      │
│              4 / 6                   │
│                                      │
│ NPC 是否需要好感度？                  │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │ 简单好感度                        │ │
│ └──────────────────────────────────┘ │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │ 不需要                            │ │
│ └──────────────────────────────────┘ │
│                                      │
│              [帮我决定]              │
└──────────────────────────────────────┘
```

而后端：

```text
Temporal Workflow
        │
        ├── Query → 当前状态
        │
        └── Signal → 用户决策
```

这就是非常标准的 **Human-in-the-Loop Workflow**。

---

# 二十六、我建议 Phase 1 最终定义成 6 个状态

不要搞复杂状态机。

```text
CREATED
   ↓
BRAINSTORMING
   ↓
WAITING_USER
   ↓
GENERATING_GDD
   ↓
CHECKING_GDD
   ↓
COMPLETED
```

其中：

```text
WAITING_USER
```

是最核心的状态。

Temporal Workflow 可以在这里：

```text
await condition(...)
```

等待几个小时甚至几天都没关系。

---

# 二十七、一个关键优化：不要真的“只调用一次 LLM”

你的说法：

> “只调用一次 LLM 检查出多个需要确认的问题”

**对于第一轮 Brainstorm 非常合适，但不要把它设计成绝对规则。**

更合理的是：

```text
第一轮：
1次 LLM
↓
Question Plan
↓
用户回答
↓
无需LLM

如果用户答案触发重大设计分支：
↓
第二次 LLM
↓
生成新的 Question Plan
```

例如：

```text
用户：
我要加入战斗。

```

这可能使原来的：

```text
种田游戏
```

变成：

```text
种田 + RPG
```

这时可以重新调用：

```text
game-brainstorm
```

但这是**异常/分支情况**，不是每个问题都调用。

所以更准确的策略是：

> **Batch LLM + Conditional Replanning**

而不是：

> **One LLM Call Only**

这样才能兼顾成本和准确性。

---

# 二十八、Phase 1 的验收标准

我建议你把 Phase 1 的 DoD 定成：

### 输入

```text
一段自然语言游戏想法
```

例如：

> “我想做一个像牧场物语一样的小游戏，但主要玩法是种田和探索。”

### 系统必须做到

```text
✓ 创建 Temporal Workflow
✓ 调用一次 Claude Code Brainstorm
✓ 生成 Question Plan
✓ 前端逐题展示
✓ Signal 接收答案
✓ Query 查询实时状态
✓ 用户关闭页面后 Workflow 不丢失
✓ 用户重新进入可以继续
✓ 自动生成 Requirements Snapshot
✓ 自动生成 GDD.md
✓ 自动执行 GDD Check
✓ 输出 PASS / FAIL
```

### 不要求

```text
× 代码生成
× 美术生成
× 游戏运行
× 自动测试
```

这些放到 Phase 2+。

---

## 最后给你一个我认为非常适合整个 AI_Cowork_Game 的核心架构原则

后面 Phase 2、Phase 3、Phase 4 都沿用：

```text
                  AI_Cowork_Game
                         │
                 Temporal Workflow
                         │
       ┌─────────────────┼──────────────────┐
       │                 │                  │
     Agent             Human              Tools
       │                 │                  │
 Claude Code           Signal            External API
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                       Query
                         │
                      Frontend
```

其中：

**Signal = 用户改变世界**

```text
“我选择A”
“把这个功能删掉”
“重新生成”
“这个版本通过”
“这个Bug修好了”
```

**Query = 用户观察世界**

```text
“现在进行到哪了？”
“Agent在做什么？”
“还有几个问题？”
“当前GDD是什么？”
“V2开发到哪里？”
```

**Temporal = 负责让整个过程不会丢**

```text
等待
暂停
恢复
重试
超时
人工介入
状态持久化
Workflow版本演进
```

**Claude Code = 真正干活**

```text
Brainstorm
GDD
Asset
Code
QA
```

这个分层一旦建立起来，后面的 **Phase 2：GDD → Version Plan → Phaser V1 → 自动运行 → 浏览器测试 → 试玩链接** 就可以自然地接在同一个 Temporal Workflow / Child Workflow 体系上，而不需要重新设计整个后端。

另外一点：**Query 建议只暴露 Agent 的“阶段、任务、进度、工具调用摘要、当前等待事项”，不要暴露或试图读取模型的隐藏思维链。** 这既更适合产品化，也让前后端状态契约稳定。
对。你这里真正需要设计的不是“多问几个问题”，而是**Phase 1 的需求澄清机制**：如何让 Claude Code + Temporal 在**尽量少的 LLM 调用下，把模糊游戏想法收敛成一个可以直接进入开发的 GDD**。

我建议 Phase 1 不要设计成传统的“AI 问卷”，而设计成：

> **LLM 一次分析 → 生成需求决策树 → Temporal 持久化 → 前端逐题确认 → Signal 回传 → 必要时局部重规划 → 生成 Requirements Snapshot → GDD → GDD Check。**

下面只讲最关键的设计。

---

# Phase 1：需求 → GDD

## 1. Phase 1 的目标

输入：

```text
用户：
“我想做一个类似牧场物语的小游戏，
玩家可以种田、养动物、和NPC互动。”
```

输出：

```text
Requirements Snapshot
        ↓
GDD.md
        ↓
GDD Check
        ↓
GDD_READY
```

最终 GDD 必须达到的标准不是：

> “游戏设计得非常完整。”

而是：

> **“另一个 Agent 不需要再问用户，就可以开始规划 V1 并编写 Phaser.js 2D 游戏。”**

因此 Phase 1 的核心指标应该是：

```text
需求澄清成本 ↓
LLM 调用次数 ↓
用户等待时间 ↓

V1 可开发率 ↑
需求一致性 ↑
GDD 可执行性 ↑
```

---

# 2. 总体架构

建议：

```text
                    用户
                     │
                     ▼
              ┌─────────────┐
              │   Frontend  │
              └──────┬──────┘
                     │
             HTTP / WebSocket
                     │
                     ▼
              ┌─────────────┐
              │  Game API   │
              └──────┬──────┘
                     │
              Temporal Client
                     │
                     ▼
        ┌───────────────────────────┐
        │       Temporal            │
        │                           │
        │ GameDesignWorkflow        │
        └────────────┬──────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
   Claude Code Activity      Human Signal
          │                     ▲
          ▼                     │
    Claude API                  │
          │                     │
          ▼                     │
   Game Brainstorm              │
   GDD Generator                │
   GDD Check                    │
                                │
                         用户逐题回答
```

这里的核心分工：

| 模块              | 职责              |
| --------------- | --------------- |
| Claude Code CLI | Agent 执行环境      |
| Claude API      | 游戏设计推理          |
| Skill           | 约束 Agent 行为     |
| Temporal        | 长流程编排、等待、恢复     |
| Signal          | 用户输入/人工干预       |
| Query           | 获取当前流程状态        |
| Frontend        | 一题一题展示          |
| DB/Artifact     | 保存项目状态、GDD、决策记录 |

---

# 3. 最关键：一次 LLM 不直接生成“问题”，而是生成 Question Plan

这是整个 Phase 1 最重要的设计。

不要：

```text
用户输入
 ↓
LLM
 ↓
“你要不要NPC？”
 ↓
用户回答
 ↓
LLM
 ↓
“要不要好感度？”
 ↓
用户回答
 ↓
LLM
```

这样会导致：

```text
LLM调用次数 = 用户回答次数
```

成本高，而且流程不稳定。

---

应该：

```text
用户输入
      ↓
Claude Code
      ↓
Game Brainstorm Skill
      ↓
Question Plan
```

例如：

```json
{
  "questions": [
    {
      "id": "camera",
      "priority": "blocking",
      "question": "你希望采用什么视角？",
      "options": [
        {
          "id": "top_down",
          "label": "俯视角",
          "impact": "适合牧场/经营类2D游戏"
        },
        {
          "id": "side",
          "label": "横版",
          "impact": "更适合平台跳跃/横向探索"
        }
      ]
    },

    {
      "id": "core_loop",
      "priority": "blocking",
      "question": "V1最核心的玩法是什么？",
      "options": [
        {
          "id": "farming",
          "label": "种田经营"
        },
        {
          "id": "exploration",
          "label": "探索"
        },
        {
          "id": "combat",
          "label": "战斗"
        }
      ]
    },

    {
      "id": "npc",
      "priority": "important",
      "question": "NPC在V1中承担什么作用？",
      "options": [
        {
          "id": "none",
          "label": "不加入NPC"
        },
        {
          "id": "simple",
          "label": "1个功能型NPC",
          "description": "提供任务、商店或教程，不设计复杂关系系统"
        },
        {
          "id": "multiple",
          "label": "多个NPC",
          "description": "需要增加对话、日程、关系等系统"
        }
      ]
    }
  ]
}
```

**注意这里的区别。**

不是简单：

> “要不要 NPC？”

而是：

> **把选择的后果告诉用户。**

这就是你刚才指出“指导意义不足”的核心问题。

---

# 4. 每一个问题都应该包含“设计影响”

这是我建议你重点加入 Skill 的规则。

用户不是游戏策划专家的时候，不能只给选项。

应该：

```text
问题
+
选项
+
选择影响
+
推荐
```

例如：

### NPC

```text
V1 是否加入 NPC？

① 不加入
   → V1 聚焦核心玩法
   → 开发最快
   → 推荐用于第一次试玩

② 加入 1 个功能型 NPC
   → 可以提供商店/任务/教程
   → 增加少量对话和交互
   → 推荐：如果希望游戏更有“游戏感”

③ 多个 NPC
   → 需要 NPC 数据、对话、位置、日程
   → 后续还可能引入关系系统
   → 会明显扩大 V1 范围
```

然后 Agent：

```text
基于你的“种田 + 经营”核心玩法，
我推荐 ②：1 个功能型 NPC。

这样 V1 可以形成：

种植
 ↓
收获
 ↓
出售
 ↓
NPC商店
 ↓
购买种子
 ↓
继续种植

同时不会引入复杂的 NPC 社交系统。

请选择：
```

这就具有真正的**设计辅助意义**。

---

# 5. Question Plan 本质上应该是一棵“需求决策树”

不要把问题当成平铺列表。

应该：

```text
                    Core Gameplay
                         │
              ┌──────────┼──────────┐
              ↓          ↓          ↓
             Farming    Combat    Exploration
              │
              ↓
           NPC?
          /     \
        No       Yes
                 │
                 ↓
             NPC Type
             /      \
        Functional  Social
                       │
                       ↓
                   Relationship
```

例如用户选择：

```text
Farming
```

那么：

```text
Combat System
```

直接跳过。

用户选择：

```text
NPC = No
```

那么：

```text
NPC Relationship
NPC Schedule
NPC Dialogue
```

全部跳过。

所以 Question Plan 应该支持：

```yaml
depends_on:
  question: npc
  value: social
```

---

# 6. 不要让 LLM 规划“所有问题”，而是规划“决策点”

这是 Skill 设计中非常重要的区别。

LLM 不应该输出：

```text
Q1 游戏视角
Q2 玩家速度
Q3 NPC数量
Q4 NPC名字
Q5 NPC年龄
Q6 NPC性格
Q7 NPC作息
Q8 NPC喜欢什么
...
```

而应该识别：

```text
Decision Point 1:
Core Loop

Decision Point 2:
Camera

Decision Point 3:
V1 Scope

Decision Point 4:
NPC是否影响Core Loop

Decision Point 5:
Progression
```

然后每个 Decision Point 再生成一个用户容易理解的问题。

---

# 7. 需求澄清分成三类

建议 Skill 固定采用：

```text
BLOCKING
IMPORTANT
OPTIONAL
```

## BLOCKING

不确定就不能开始 V1。

例如：

```text
核心玩法
视角
玩家主要操作
V1目标
胜负/完成条件
```

---

## IMPORTANT

会影响游戏体验，但可以采用默认方案。

例如：

```text
NPC
商店
简单升级
时间系统
存档
```

---

## OPTIONAL

不要问。

例如：

```text
NPC具体作息
天气概率
音效细节
具体数值
完整剧情
```

这些交给 Agent 默认设计或者后续迭代。

---

# 8. 用户每次只回答一个问题，但 LLM 不需要每次参与

这是 Temporal 的核心价值。

流程：

```text
Claude Code
    │
    │ 一次调用
    ▼
Question Plan
    │
    ▼
Temporal Workflow
    │
    ├── Q1
    │    ↓ Signal
    │
    ├── Q2
    │    ↓ Signal
    │
    ├── Q3
    │    ↓ Signal
    │
    └── Q4
```

Temporal 每次：

```text
await condition(
    () => answerReceived(questionId)
)
```

等待。

---

# 9. Signal 设计

至少需要：

```text
submitAnswer
skipQuestion
changeAnswer
requestAIRecommendation
```

### submitAnswer

```json
{
  "questionId": "npc",
  "answer": "simple"
}
```

---

### skipQuestion

用户：

> “这个我不知道，你帮我决定。”

```json
{
  "questionId": "npc",
  "action": "AI_DEFAULT"
}
```

然后系统使用：

```text
recommended_option
```

而不是再次问用户。

---

### changeAnswer

用户后来发现：

> “我还是想加多个 NPC。”

Signal：

```json
{
  "questionId": "npc",
  "answer": "multiple"
}
```

Temporal 重新计算依赖：

```text
NPC
 ↓
NPC Schedule
 ↓
NPC Dialogue
 ↓
Relationship
```

需要增加的问题。

---

# 10. Query 不应该返回“AI正在思考什么”

你原来的：

> Query → 外部实时读取 Agent 当前思考步骤与状态

建议改成：

> **Query → 查询 Agent 可观察状态，而不是隐藏思维过程。**

返回：

```json
{
  "phase": "BRAINSTORM",
  "status": "WAITING_USER",

  "progress": {
    "completed": 3,
    "total": 6
  },

  "currentQuestion": {
    "id": "npc",
    "category": "social",
    "question": "V1是否加入NPC？"
  },

  "decisions": [
    {
      "id": "camera",
      "answer": "top_down"
    },
    {
      "id": "core_loop",
      "answer": "farming"
    }
  ]
}
```

前端因此可以实时显示：

```text
需求分析

✓ 核心玩法
✓ 游戏视角
✓ V1规模
● NPC设计
○ 经济系统
○ 完成条件

当前：等待你确认 NPC 设计
```

---

# 11. Temporal Workflow 应该是“需求状态机”

推荐：

```text
CREATED
   ↓
ANALYZING
   ↓
QUESTION_PLAN_READY
   ↓
WAITING_USER
   ↓
COLLECTING_REQUIREMENTS
   ↓
REQUIREMENTS_READY
   ↓
GENERATING_GDD
   ↓
GDD_CHECKING
   ↓
GDD_READY
```

其中：

```text
WAITING_USER
```

可能持续：

```text
5分钟
5小时
5天
```

Temporal 都可以保持 Workflow 状态。

---

# 12. 设计一个 Requirements Snapshot

这是我认为 Phase 1 中**仅次于 Question Plan 的第二个核心设计**。

不要：

```text
用户回答
 ↓
直接生成 GDD
```

而应该：

```text
User Idea
   +
Question Plan
   +
User Answers
   +
AI Defaults
   +
Design Decisions
        ↓
Requirements Snapshot
        ↓
GDD
```

例如：

```yaml
game:
  genre: farming_sim
  camera: top_down
  platform: web
  engine: Phaser.js

core_loop:
  - plant
  - grow
  - harvest
  - sell
  - buy_seeds

npc:
  enabled: true
  type: functional
  count: 1

v1:
  map: small_farm
  crops: 3
  npc: 1
  shop: true

decisions:
  - id: camera
    value: top_down
    source: user

  - id: npc
    value: functional
    source: user

assumptions:
  - id: save
    value: localStorage
    source: system_default
```

这个 Snapshot 是后面所有 Agent 的**单一事实来源 SSOT**。

---

# 13. GDD Generator 不应该重新“理解游戏”

非常重要。

流程应该是：

```text
用户原始想法
      ↓
Brainstorm Agent
      ↓
Question Plan
      ↓
User Decisions
      ↓
Requirements Snapshot   ← SSOT
      ↓
GDD Generator
      ↓
GDD.md
```

而不是：

```text
用户想法
   ↓
GDD Agent 再理解一次
   ↓
重新猜测用户需求
```

否则非常容易出现：

> 用户明明选择了“不加入 NPC”，GDD Agent 又自己写出了 NPC 系统。

---

# 14. GDD 生成的重点

GDD Generator 不需要写百科全书。

只要让 Code Agent 能够开发。

重点输出：

```text
1. Game Goal
2. Core Loop
3. Player
4. Core Systems
5. Game Entities
6. Scenes / Maps
7. Input
8. UI
9. Assets
10. Progression
11. V1 Scope
12. Acceptance Criteria
```

其中最重要的是：

```text
Core Loop
+
Core Systems
+
V1 Scope
+
Acceptance Criteria
```

---

# 15. GDD Check 的定位

GDD Check 不应该问：

> “这个 NPC 的性格是不是定义得足够完整？”

而应该问：

> **“Code Agent 能不能按照这个 GDD 开始做 V1？”**

检查：

```text
                    GDD
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
    Core Loop     V1 Scope     Systems
        │            │            │
        └────────────┼────────────┘
                     ↓
               Can Build V1?
                     │
              ┌──────┴──────┐
             YES            NO
              │              │
            PASS          BLOCKING
```

---

# 16. GDD Check 只允许三种结果

```text
PASS
WARNING
BLOCKING
```

例如：

### PASS

```text
Core loop明确
V1范围明确
核心系统明确
输入明确
Acceptance Criteria明确
```

### WARNING

```text
NPC数值未平衡
商店价格未确定
音效未确定
未来剧情未确定
```

这些不阻塞开发。

### BLOCKING

```text
核心玩法不明确
V1没有完成目标
核心系统规则缺失
无法判断玩家如何操作
无法形成可玩闭环
```

才重新进入 Human-in-the-Loop。

---

# 17. Phase 1 最终完整流程

因此我建议你最终把 Phase 1 定义成：

```text
┌────────────────────────────────────────────┐
│              Phase 1: Idea → GDD           │
└────────────────────────────────────────────┘

User Idea
    │
    ▼
┌───────────────────────┐
│ Claude Code           │
│ game-brainstorm       │
│                       │
│ 一次识别：            │
│ Decision Points       │
│ Question Plan         │
│ Defaults              │
│ Dependencies          │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Temporal Workflow      │
│                       │
│ 持久化 Question Plan  │
└───────────┬───────────┘
            │
            ▼
       ┌─────────┐
       │ Q1      │
       └────┬────┘
            │ Signal
            ▼
       ┌─────────┐
       │ Q2      │
       └────┬────┘
            │ Signal
            ▼
       ┌─────────┐
       │ Q3      │
       └────┬────┘
            │
           ...
            │
            ▼
┌─────────────────────────┐
│ Requirements Snapshot   │
│                         │
│ User Decisions          │
│ AI Defaults             │
│ Constraints             │
│ Scope                   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Claude Code             │
│ gdd-generator           │
└────────────┬────────────┘
             │
             ▼
          GDD.md
             │
             ▼
┌─────────────────────────┐
│ Claude Code             │
│ gdd-check               │
└────────────┬────────────┘
             │
        ┌────┴────┐
        ▼         ▼
      PASS      BLOCKING
        │         │
        ▼         ▼
     GDD_READY   Human Loop
```

---

# 18. Phase 1 最值得落地的 5 个设计点

如果你现在真的准备开始用 **Claude Code CLI + Temporal** 开发，我建议第一阶段不要做得太大，先把下面 **5 个东西做扎实**：

### ① `game-brainstorm` Skill

负责：

```text
用户想法
→ Decision Points
→ Question Plan
→ 推荐方案
→ 依赖关系
```

---

### ② `QuestionPlan JSON Schema`

这是前后端契约：

```text
LLM
 ↓
QuestionPlan JSON
 ↓
Temporal
 ↓
Frontend
```

**不要让前端解析自然语言问题。**

---

### ③ `GameDesignWorkflow`

只负责：

```text
执行 Activity
等待 Signal
维护状态
推进问题
生成 Requirements Snapshot
```

---

### ④ `Requirements Snapshot`

作为：

> **Phase 1 的 SSOT**

后续 GDD、Asset、Code 全部从这里派生。

---

### ⑤ `gdd-generator + gdd-check`

最终形成：

```text
Requirements Snapshot
          ↓
       GDD.md
          ↓
     GDD Check
          ↓
     GDD_READY
```

---

## 最终我建议你把 Phase 1 的产品体验定成一句话

> **“AI 先替你想清楚哪些事情值得问，然后一次性规划问题；Temporal 负责记住整个需求澄清过程，用户只需要逐题做设计决策；AI 再把这些决策固化成可执行的 GDD。”**

这样设计以后，**“V1 是否加入 NPC？”** 就不会只是一个傻问题，而会变成：

> **“加入 NPC 会扩大 V1 的开发范围，所以我给你三个方案，并告诉你每个方案对玩法和开发量的影响；基于你目前的核心玩法，我推荐其中一个，你只需要做最后的设计决策。”**

这才是 `game-brainstorm` 在 AI_Cowork_Game 里的真正价值。

而 Temporal 则负责把这个过程变成一个**可以暂停、恢复、修改、追踪、人工干预的长期 Agent Workflow**。
