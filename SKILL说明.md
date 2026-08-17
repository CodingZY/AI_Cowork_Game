你这个系统本质上不是“让 Claude Code 帮我写游戏”，而是要把 Claude Code + Superpowers 改造成一个**面向游戏研发的 Agentic CI/CD 流水线**：

> **用户创意 → 需求澄清 → GDD → GDD质量门禁 → 全局美术规范 → 美术资产生成 → V1可玩产品 → 自动测试 → 在线试玩 → 用户反馈 → Bug/需求分析 → V2/V3… → GDD完成 → Final**

Superpowers 本身已经提供了 brainstorming、planning、TDD、systematic-debugging、verification-before-completion、subagent-driven-development 等方法论，因此你的游戏 Skill 不应该重复造这些轮子，而应该把它们**编排成游戏研发专用工作流**。Superpowers 官方也明确采用“先澄清需求 → 设计 → 计划 → 实现 → 测试/验证”的流程。([GitHub][1])

下面我给你一套可以直接落地到 Claude Code Plugin 的 **AI_Cowork_Game Skill 体系设计**。

---

# 一、总体架构

我建议不要只做 4~5 个 Skill，而是做成：

```text
AI_Cowork_Game
│
├── 00-orchestrator                  # 总调度
│
├── 01-game-brainstorm               # 游戏创意 → 明确需求
├── 02-gdd-generator                 # 生成 GDD.md
├── 03-gdd-check                     # GDD 质量门禁
│
├── 04-game-art-style                # 全局美术风格规范
├── 05-art-asset-spec                # 生成 art-assets.md
├── 06-art-pipeline                  # 生图/抠图/切图/导入
├── 07-art-consistency-check         # 美术一致性检查
│
├── 08-game-architecture             # 游戏技术架构
├── 09-game-version-planner          # GDD → V1/V2/...执行计划
├── 10-game-code-generator           # 代码生成
├── 11-game-test                     # 自动化测试
├── 12-browser-debug                 # 浏览器自动检测/修复
├── 13-playable-build                # 构建 + 试玩部署
│
├── 14-player-feedback               # 玩家反馈分析
├── 15-feedback-to-code              # Feedback → Code
├── 16-version-regression            # 版本回归
│
└── 17-game-completion-check         # GDD完成度检查
```

再加三个基础设施：

```text
Superpowers
      │
      ▼
AI_Cowork_Game Orchestrator
      │
      ├── GDD Pipeline
      ├── Art Pipeline
      ├── Code Pipeline
      ├── Test Pipeline
      └── Feedback Pipeline
```

其中：

**Superpowers = 通用软件工程能力**

**AI_Cowork_Game = 游戏领域知识 + 流程编排 + 状态机 + 质量标准**

---

# 二、最重要的设计原则

你的 Skill 不应该写成：

> “请 Claude 生成一个游戏。”

而应该写成：

> “Claude 必须遵循一组明确的输入、输出、状态、质量门禁和完成条件。”

也就是说，每个 Skill 都应该有：

```text
Trigger
Input
Preconditions
Workflow
Output
Validation
Failure Handling
State Update
Next Skill
```

这是整个系统能不能稳定工作的关键。

---

# 三、项目目录建议

Claude Code Plugin 可以采用标准 Plugin 结构；当前 Superpowers/Claude Code 生态也是围绕 `skills/<skill-name>/SKILL.md` 组织 Skill。([GitHub][2])

建议：

```text
ai-cowork-game/
│
├── .claude-plugin/
│   └── plugin.json
│
├── skills/
│
│   ├── game-orchestrator/
│   │   └── SKILL.md
│   │
│   ├── game-brainstorm/
│   │   └── SKILL.md
│   │
│   ├── gdd-generator/
│   │   └── SKILL.md
│   │
│   ├── gdd-check/
│   │   └── SKILL.md
│   │
│   ├── game-art-style/
│   │   └── SKILL.md
│   │
│   ├── art-asset-spec/
│   │   └── SKILL.md
│   │
│   ├── art-pipeline/
│   │   └── SKILL.md
│   │
│   ├── art-consistency-check/
│   │   └── SKILL.md
│   │
│   ├── game-architecture/
│   │   └── SKILL.md
│   │
│   ├── game-version-planner/
│   │   └── SKILL.md
│   │
│   ├── game-code-generator/
│   │   └── SKILL.md
│   │
│   ├── game-test/
│   │   └── SKILL.md
│   │
│   ├── browser-debug/
│   │   └── SKILL.md
│   │
│   ├── playable-build/
│   │   └── SKILL.md
│   │
│   ├── player-feedback/
│   │   └── SKILL.md
│   │
│   ├── feedback-to-code/
│   │   └── SKILL.md
│   │
│   ├── version-regression/
│   │   └── SKILL.md
│   │
│   └── game-completion-check/
│       └── SKILL.md
│
├── commands/
│
│   ├── new-game.md
│   ├── generate-gdd.md
│   ├── generate-art.md
│   ├── build-v1.md
│   ├── playtest.md
│   ├── feedback.md
│   └── next-version.md
│
├── hooks/
│
│   └── hooks.json
│
├── scripts/
│
│   ├── browser-test/
│   ├── build/
│   ├── deploy/
│   ├── screenshot/
│   └── asset-pipeline/
│
└── references/
    │
    ├── game-design.md
    ├── genre-patterns.md
    ├── web-game.md
    ├── mobile-game.md
    └── quality-gates.md
```

---

# 四、核心：Game Orchestrator

这是整个系统最重要的 Skill。

## `game-orchestrator`

### 作用

负责判断：

```text
当前项目处于哪个阶段？
下一步应该调用哪个 Skill？
前置条件是否满足？
是否允许进入下一阶段？
```

它实际上是一个：

> **Game Development State Machine**

---

## 状态

建议：

```text
IDEA
 ↓
REQUIREMENT_CLARIFICATION
 ↓
GDD_DRAFT
 ↓
GDD_VALIDATING
 ↓
GDD_APPROVED
 ↓
ART_SPEC
 ↓
ART_GENERATING
 ↓
ART_APPROVED
 ↓
TECH_DESIGN
 ↓
VERSION_PLANNING
 ↓
V1_IMPLEMENTING
 ↓
V1_TESTING
 ↓
V1_PLAYABLE
 ↓
USER_PLAYTEST
 ↓
FEEDBACK_ANALYSIS
 ↓
V2_IMPLEMENTING
 ↓
...
 ↓
GDD_COMPLETE
 ↓
FINAL
```

关键原则：

> **任何 Skill 都不能绕过自己的质量门禁直接修改状态。**

例如：

```text
GDD_GENERATED
```

不能直接：

```text
→ CODE_GENERATING
```

必须：

```text
GDD_GENERATED
→ GDD_CHECK
→ GDD_APPROVED
→ CODE_GENERATING
```

---

# 五、Skill 1：Game Brainstorm

## `game-brainstorm`

这是 Superpowers brainstorming 的游戏领域适配层。

不要自己重新实现 brainstorming。

而是：

```text
User Idea
   ↓
Superpowers Brainstorming
   ↓
Game-specific questioning
   ↓
Game Concept Spec
```

---

## 输入

例如：

```text
我想做一个类似牧场物语的游戏，
玩家经营农场，可以种植、养动物、
和NPC谈恋爱。
```

---

## 必须澄清的问题

Skill 自动检查：

### 核心玩法

```text
Genre
Core Loop
Player Goal
Progression
Failure Condition
Win Condition
```

### 玩家

```text
Target Audience
Platform
Session Length
Camera
Control
```

### 世界

```text
World
Characters
NPC
Economy
Resources
```

### 内容

```text
Crops
Animals
Items
Buildings
Quests
Events
```

### 产品范围

```text
MVP Scope
Expected Playtime
Expected Version Count
```

---

# 六、Skill 2：GDD Generator

## `gdd-generator`

目标不是“写一个漂亮的 GDD”。

目标是：

> **生成能够驱动后续 Asset Pipeline 和 Code Pipeline 的机器可执行 GDD。**

这是非常重要的区别。

---

# GDD.md 应该采用结构化格式

例如：

```markdown
# Game GDD

## 1. Game Overview

## 2. Target Platform

## 3. Core Gameplay Loop

## 4. Player

## 5. Game World

## 6. Characters

## 7. NPC

## 8. Gameplay Systems

### 8.1 Farming

### 8.2 Animal

### 8.3 Relationship

### 8.4 Time

### 8.5 Economy

## 9. Items

## 10. Maps

## 11. UI

## 12. Art Direction

## 13. Audio

## 14. Save System

## 15. Technical Requirements

## 16. Version Roadmap

## 17. Acceptance Criteria

## 18. Non-Goals
```

---

# 七、最关键：GDD必须产生机器可执行 Spec

例如：

```yaml
feature:
  id: farming.crop_growth

  name: Crop Growth

  dependencies:
    - time.system
    - inventory.system

  inputs:
    - seed
    - farmland

  state:
    cropType:
    growthStage:
    plantedDay:
    watered:

  rules:
    growth:
      - day: 1
        stage: seedling
      - day: 2
        stage: growing
      - day: 4
        stage: mature

  ui:
    - crop_status

  assets:
    - crop.tomato.stage1
    - crop.tomato.stage2
    - crop.tomato.stage3

  acceptance:
    - player can plant seed
    - crop consumes seed
    - crop grows with time
    - mature crop can be harvested
```

这意味着：

**GDD不是文档，而是整个 AI Game Factory 的 Source of Truth。**

---

# 八、Skill 3：GDD Check

## `gdd-check`

这个 Skill 是你的第一道质量门。

它不能简单判断：

> “文档写得很好。”

而应该检查：

### 1. Completeness

```text
所有游戏系统是否定义？
```

### 2. Consistency

```text
规则有没有互相矛盾？
```

例如：

```text
一天 = 10分钟

NPC A：
8:00 → Farm

NPC A：
8:00 → Town
```

直接报错。

---

### 3. Asset Generability

检查：

```text
GDD中的实体
↓
是否都能映射到Asset
```

例如：

```text
NPC: Alice

需要：

Alice_idle
Alice_walk
Alice_portrait
Alice_happy
Alice_sad
```

---

### 4. Code Generability

检查：

```text
Feature
↓
State
↓
Input
↓
Logic
↓
UI
↓
Asset
↓
Acceptance Criteria
```

是否完整。

---

### 5. Playability

检查：

```text
玩家能不能：

Start
→ Play
→ Progress
→ Goal
```

---

## GDD Check 输出

不要输出：

```text
PASS
```

而是：

```yaml
gdd_check:

  status: FAILED

  blocking_issues:
    - id: GDD-001
      type: missing_rule
      feature: relationship
      issue: relationship level has no progression rule

    - id: GDD-002
      type: missing_asset
      feature: NPC
      issue: NPC portrait undefined

  warnings:
    - economy balance not specified

  score:
    completeness: 82
    consistency: 91
    asset_readiness: 74
    code_readiness: 68
    playability: 80

  decision:
    can_generate_art: false
    can_generate_code: false
```

---

# 九、Skill 4：Game Art Style

## `game-art-style`

你提出的：

> 素材.md生成需要变成生成的素材全局风格统一

我建议不要直接让 Asset Skill 自己决定风格。

增加：

```text
game-art-style
```

作为全局 Style Authority。

---

## 生成：

```text
ART_STYLE.md
```

例如：

```yaml
art_style:

  visual_identity:
    genre: cozy_farming
    mood: warm
    visual_density: medium

  camera:
    type: orthographic
    angle: 45deg

  character:
    style: stylized_2d
    proportion: chibi
    outline: soft

  environment:
    palette:
    lighting:
    texture:

  ui:
    style:
    border:
    icon:

  constraints:
    - no_photorealism
    - no_anime_realism
    - consistent_outline
```

---

# 十、Skill 5：Art Asset Spec

## `art-asset-spec`

输入：

```text
GDD.md
ART_STYLE.md
```

输出：

```text
art-assets.md
```

---

# Asset Spec必须包含

```yaml
asset:

  id: character.alice.idle

  category: character

  name: Alice Idle

  source:
    gdd_entity: Alice

  style:
    reference: ART_STYLE.md

  generation:
    prompt:
    negative_prompt:

  composition:
    camera:
    pose:
    orientation:

  technical:
    resolution:
    aspect_ratio:
    background: transparent

  postprocess:
    remove_background: true
    crop: true
    resize: true

  variants:
    - idle
    - happy
    - sad

  consistency:
    character_id: alice
    seed:
    style_reference:
```

---

# 十一、Asset Pipeline

## `art-pipeline`

负责：

```text
art-assets.md
       ↓
Prompt Builder
       ↓
Image Generation API
       ↓
Image
       ↓
Background Removal
       ↓
Crop
       ↓
Resize
       ↓
Format Conversion
       ↓
Quality Check
       ↓
Asset Repository
```

---

## 外部服务建议抽象成 Adapter

不要把 Skill 写死：

```text
调用 Midjourney
```

而应该：

```text
ImageGenerationProvider
BackgroundRemovalProvider
UpscaleProvider
```

例如：

```yaml
image_generation:
  provider: xxx

background_removal:
  provider: xxx

upscale:
  provider: xxx
```

以后换服务不用改 Skill。

---

# 十二、美术一致性检查

这是你原始需求里非常值得单独做的 Skill。

## `art-consistency-check`

检查：

```text
Style Consistency
Character Consistency
Scale Consistency
Perspective Consistency
Color Consistency
Naming Consistency
Resolution Consistency
Transparency
```

例如：

```text
Alice.png
Bob.png
Carol.png
```

AI 自动判断：

```text
Alice:
  chibi 2D
  thick outline

Bob:
  realistic
  no outline

Carol:
  pixel art
```

直接：

```text
ART_CONSISTENCY_FAILED
```

而不是进入代码阶段。

---

# 十三、Skill 6：Game Architecture

## `game-architecture`

GDD → 技术架构。

输出：

```text
GAME_ARCHITECTURE.md
```

包括：

```text
Engine
Rendering
Game State
Entity System
UI
Input
Save
Audio
Asset Loading
Scene
Persistence
Testing
Deployment
```

---

# 十四、最关键的 Skill：Version Planner

## `game-version-planner`

这是整个系统的核心。

你的要求：

> GDD 拆成 Vn 执行计划 spec，每个阶段都是可运行的完成产品，而不是半成品。

因此必须定义：

# Vertical Slice Version

每一个版本必须满足：

```text
Installable
+
Runnable
+
Playable
+
Testable
+
Has a complete gameplay loop
```

而不是：

```text
V1 = 地图
V2 = NPC
V3 = 农场
V4 = UI
```

这种是错误的。

---

# 十五、正确的拆分方式

假设最终 GDD：

```text
农场
种植
动物
NPC
恋爱
任务
节日
经济
存档
```

错误：

```text
V1 地图
V2 种植
V3 动物
V4 NPC
V5 恋爱
```

正确：

```text
V1
最小完整农场游戏

启动
→ 进入农场
→ 种植
→ 等待
→ 收获
→ 卖出
→ 获得金币
→ 第二天
→ 保存
```

然后：

```text
V2
V1
+
动物
+
喂养
+
动物产出
```

然后：

```text
V3
V2
+
NPC
+
对话
+
送礼
+
好感度
```

然后：

```text
V4
V3
+
恋爱
+
事件
+
任务
```

---

# 十六、Version Spec

建议生成：

```text
versions/
├── V1.md
├── V2.md
├── V3.md
└── V4.md
```

每个：

```yaml
version:

  id: V1

  goal:
    "完成最小农场核心循环"

  included_features:
    - farming
    - crop_growth
    - harvesting
    - selling
    - day_cycle
    - save

  excluded_features:
    - animals
    - romance
    - festivals

  player_loop:

    - start_game
    - enter_farm
    - plant_seed
    - advance_day
    - harvest
    - sell
    - earn_money
    - save

  assets:
    - farm
    - player
    - crop
    - seed
    - ui

  acceptance_criteria:
    - game launches
    - player can plant
    - crop grows
    - crop can be harvested
    - item can be sold
    - money increases
    - save works

  playable:
    required: true

  completion_definition:
    all_acceptance_criteria_pass: true
```

---

# 十七、Version Planner的核心算法

建议在 Skill 中明确要求：

```text
For each version:

1. Select a complete gameplay loop.
2. Select the minimum set of systems required by that loop.
3. Select required assets.
4. Select required UI.
5. Select required persistence.
6. Select required test cases.
7. Reject any version that cannot be played from start to finish.
```

然后强制：

```text
Vn ⊇ V(n-1)
```

也就是：

> **默认增量版本不能破坏上一版本已经完成的能力。**

---

# 十八、Code Generator

## `game-code-generator`

这个 Skill 不应该直接：

```text
读取 GDD → 写代码
```

而应该：

```text
GDD
 ↓
Version Spec
 ↓
Architecture
 ↓
Implementation Plan
 ↓
Superpowers writing-plans
 ↓
Superpowers TDD
 ↓
Subagent Development
 ↓
Code
```

也就是说：

**Superpowers 是执行引擎。**

你的 Game Skill 是：

**Game-specific planner。**

Superpowers 已经强调 implementation plan、TDD、subagent-driven development 和 verification，因此这里最好直接复用，而不是复制一套类似机制。([GitHub][1])

---

# 十九、Code Generator 的约束

每个 Feature 必须：

```text
Requirement
↓
Test
↓
Implementation
↓
Integration
↓
Playtest
```

例如：

```text
Feature: Crop Growth

Test:
  plant seed
  advance day
  growthStage changes
  mature crop harvestable

Implementation:
  CropSystem
  TimeSystem
  InventorySystem

Integration:
  FarmScene
  UI

Verification:
  Browser Test
```

---

# 二十、自动化验证 Skill

## `game-test`

这个 Skill 负责：

```text
Unit Test
Integration Test
E2E Test
Game State Test
UI Test
Browser Test
```

尤其是你的游戏如果最终是 Web Game：

```text
Claude
 ↓
启动 Dev Server
 ↓
Browser
 ↓
Play Game
 ↓
Console
 ↓
Network
 ↓
DOM
 ↓
Screenshot
```

---

# 二十一、Browser Debug Skill

## `browser-debug`

这是你要求的：

> 可以自动化检测浏览器的报错然后修复 Bug

建议设计成：

```text
BUILD
 ↓
START SERVER
 ↓
OPEN BROWSER
 ↓
COLLECT
 ├── console errors
 ├── uncaught exceptions
 ├── network errors
 ├── failed resources
 ├── runtime errors
 └── screenshot
 ↓
CLASSIFY
 ↓
ROOT CAUSE
 ↓
PATCH
 ↓
RE-RUN
```

最多：

```text
MAX_AUTO_FIX_ATTEMPTS = 3
```

否则进入：

```text
HUMAN_REVIEW_REQUIRED
```

---

# 二十二、不要让 Agent 无限修 Bug

必须设置：

```yaml
debug_policy:

  max_attempts: 3

  after_failure:
    collect_diagnostics: true

  escalation:
    enabled: true

  escalation_reason:
    - architecture_problem
    - unclear_requirement
    - external_service_failure
    - nondeterministic_bug
```

这样可以避免：

> Claude 改 A → B 坏了 → 修 B → C 坏了 → 无限循环。

---

# 二十三、Playable Build Skill

## `playable-build`

当代码通过验证：

```text
Build
 ↓
Deploy
 ↓
Health Check
 ↓
Generate URL
 ↓
Return URL
```

输出：

```yaml
playtest:

  version: V1

  status: READY

  url: ...

  commit: ...

  build_id: ...

  test_status: PASS

  known_issues: []
```

用户就可以：

> 点击试玩。

---

# 二十四、Feedback Skill

## `player-feedback`

用户说：

> “种地的时候感觉等待太久了。”

Agent 不应该直接修改代码。

首先转成：

```yaml
feedback:

  version: V1

  type: UX

  feature: farming

  original:
    "种地的时候感觉等待太久了"

  interpretation:
    crop_growth_duration_too_long

  confidence:
    0.86

  impact:
    medium

  proposed_change:
    reduce_growth_time

  requires_user_confirmation:
    true
```

---

# 二十五、Feedback → Code

## `feedback-to-code`

流程：

```text
User Feedback
 ↓
Feedback Analysis
 ↓
Requirement Change
 ↓
Impact Analysis
 ↓
Update Version Spec
 ↓
Write Plan
 ↓
Implement
 ↓
Test
 ↓
Playtest
```

非常重要：

> **用户反馈不能直接修改代码。**

中间必须产生：

```text
CHANGE_REQUEST.md
```

例如：

```yaml
change:

  id: CR-001

  source: user_feedback

  version: V1

  requested:
    "crop growth feels too slow"

  affected_features:
    - crop_growth
    - day_cycle
    - economy

  change:
    growth_days:
      from: 4
      to: 2

  regression_tests:
    - crop_growth
    - harvesting
    - economy
```

---

# 二十六、Version Regression

## `version-regression`

这是非常重要的 Skill。

V2 修改以后：

```text
V2 New Features
+
V1 Regression Tests
```

都必须通过。

也就是：

```text
V1 PASS
       ↓
V2
       ↓
V1 tests
+
V2 tests
       ↓
PASS
```

---

# 二十七、Game Completion Check

## `game-completion-check`

最终检查：

```text
GDD Features
        │
        ├── implemented?
        ├── tested?
        ├── playable?
        ├── assets?
        ├── UI?
        └── acceptance criteria?
```

最终产生：

```yaml
completion:

  gdd_completion: 100%

  features:
    farming: PASS
    animals: PASS
    romance: PASS
    festivals: PASS

  assets:
    status: PASS

  tests:
    status: PASS

  regression:
    status: PASS

  playable:
    status: PASS

  user_acceptance:
    status: PASS
```

只有：

```text
ALL PASS
```

才能：

```text
PROJECT_COMPLETE
```

---

# 二十八、整个 Pipeline

最终整个系统可以形成：

```text
                         ┌────────────────────┐
                         │     User Idea      │
                         └─────────┬──────────┘
                                   ↓
                       ┌───────────────────────┐
                       │ Superpowers Brainstorm│
                       │ + Game Brainstorm     │
                       └──────────┬────────────┘
                                  ↓
                            GAME_CONCEPT
                                  ↓
                       ┌───────────────────────┐
                       │    GDD Generator      │
                       └──────────┬────────────┘
                                  ↓
                               GDD.md
                                  ↓
                       ┌───────────────────────┐
                       │      GDD Check        │
                       └──────────┬────────────┘
                                  │
                         ┌────────┴────────┐
                         │                 │
                       FAIL              PASS
                         │                 │
                         ↓                 ↓
                    Fix GDD          ART_STYLE.md
                                           ↓
                                  art-assets.md
                                           ↓
                                  Art Generation
                                           ↓
                                  Background Remove
                                           ↓
                                  Asset Validation
                                           ↓
                                  GAME_ARCHITECTURE
                                           ↓
                                  VERSION PLANNER
                                           ↓
                        ┌──────────────────┴──────────────────┐
                        ↓                                     ↓
                       V1                                    V2
                        ↓                                     ↓
                 Code Generation                       Code Generation
                        ↓                                     ↓
                   Auto Test                              Regression
                        ↓                                     ↓
                  Browser Test                           Browser Test
                        ↓                                     ↓
                   Auto Debug                            Auto Debug
                        ↓                                     ↓
                  Build & Deploy                        Build & Deploy
                        ↓                                     ↓
                   PLAYABLE URL                          PLAYABLE URL
                        ↓                                     ↓
                     User Test                            User Test
                        ↓                                     ↓
                    Feedback                              Feedback
                        └──────────────────┬──────────────────┘
                                           ↓
                                    Feedback Analysis
                                           ↓
                                    Change Request
                                           ↓
                                      Code Update
                                           ↓
                                     Next Version
                                           ↓
                                  GDD Completion Check
                                           ↓
                                        FINAL
```

---

# 二十九、我建议再加一个非常重要的概念：Game Manifest

不要让所有 Skill 都通过自然语言互相传递状态。

建立：

```text
GAME_MANIFEST.yaml
```

作为项目状态中心。

例如：

```yaml
project:
  id: farm-love
  name: Farm Love

state:
  current_stage: V2_PLAYTEST
  current_version: V2

documents:
  gdd: GDD.md
  art_style: ART_STYLE.md
  art_assets: art-assets.md
  architecture: GAME_ARCHITECTURE.md

versions:
  current: V2
  completed:
    - V1

assets:
  total: 128
  generated: 128
  validated: 124
  failed: 4

tests:
  unit: pass
  integration: pass
  e2e: pass
  browser: pass

playtest:
  url: ...
  status: waiting_for_user

feedback:
  pending: 3

completion:
  percentage: 64
```

这样每个 Skill 都知道：

```text
我现在在哪里？
我应该做什么？
做完以后应该进入哪里？
```

---

# 三十、再进一步：建立 Artifact Contract

这是我最推荐你增加的设计。

每个 Skill 都不是简单“生成文件”。

而是：

```text
Skill Contract
```

例如：

### GDD Generator

```text
INPUT:
Game Concept

OUTPUT:
GDD.md

MUST:
GDD Check PASS
```

### Art Asset Spec

```text
INPUT:
GDD.md
ART_STYLE.md

OUTPUT:
art-assets.md

MUST:
Every GDD visual entity mapped to asset
```

### Version Planner

```text
INPUT:
GDD.md

OUTPUT:
V1.md ... Vn.md

MUST:
Every version playable
```

### Code Generator

```text
INPUT:
Version Spec

OUTPUT:
Code

MUST:
Tests PASS
Browser PASS
```

### Playable Build

```text
INPUT:
Verified Code

OUTPUT:
Playable URL

MUST:
Health Check PASS
```

这样整个系统会非常稳定。

---

# 三十一、Skill之间的依赖关系

建议定义：

```text
game-brainstorm
        ↓
gdd-generator
        ↓
gdd-check
        ↓
game-art-style
        ↓
art-asset-spec
        ↓
art-pipeline
        ↓
art-consistency-check
        ↓
game-architecture
        ↓
game-version-planner
        ↓
game-code-generator
        ↓
game-test
        ↓
browser-debug
        ↓
playable-build
        ↓
player-feedback
        ↓
feedback-to-code
        ↓
version-regression
        ↓
game-completion-check
```

---

# 三十二、哪些东西交给 Superpowers，哪些东西自己实现

这个边界非常重要。

| 能力                | Superpowers | AI_Cowork_Game     |
| ----------------- | ----------- | ------------------ |
| Brainstorm        | ✅           | 游戏领域问题             |
| 需求澄清              | ✅           | 游戏需求模板             |
| Plan              | ✅           | GDD→Version Plan   |
| TDD               | ✅           | 游戏测试标准             |
| Debug             | ✅           | Browser/Game Debug |
| Code Review       | ✅           | 游戏质量规则             |
| Subagent          | ✅           | 游戏 Agent 分工        |
| Verification      | ✅           | 游戏验收               |
| GDD               | ❌           | ✅                  |
| Art Style         | ❌           | ✅                  |
| Asset Spec        | ❌           | ✅                  |
| Image Generation  | ❌           | ✅                  |
| Game Architecture | 部分          | ✅                  |
| Version Planning  | ❌           | ✅                  |
| Playable Build    | ❌           | ✅                  |
| Playtest          | ❌           | ✅                  |
| Feedback          | ❌           | ✅                  |
| Game Completion   | ❌           | ✅                  |

也就是说：

> **不要复制 Superpowers，要把 Superpowers 当成底层操作系统。**

Superpowers 本身的设计理念就是把通用工程流程拆成可组合 Skill，并通过 Skill 自动触发工作流。([GitHub][1])

---

# 三十三、最终推荐的 Agent 分工

如果后面你要进一步做成真正的 Cowork，我甚至建议把 Agent 也拆开：

```text
                    Game Director Agent
                           │
           ┌───────────────┼────────────────┐
           ↓               ↓                ↓
      Design Agent      Art Agent       Engineering Agent
           │               │                │
         GDD             Assets           Code
           │               │                │
           └───────────────┼────────────────┘
                           ↓
                     QA Agent
                           │
                     Browser Test
                           │
                           ↓
                    Playtest Agent
                           │
                           ↓
                    User Feedback
                           │
                           ↓
                  Product Manager Agent
                           │
                           ↓
                     Next Version
```

其中：

### Game Director Agent

负责：

```text
状态
优先级
版本
质量门禁
Agent调度
```

### Design Agent

负责：

```text
GDD
系统设计
数值
内容
```

### Art Agent

负责：

```text
ART_STYLE
Asset Spec
Prompt
生图
抠图
一致性
```

### Engineering Agent

负责：

```text
Architecture
Plan
Code
Refactor
```

### QA Agent

负责：

```text
Unit
E2E
Browser
Screenshot
Regression
```

### Playtest Agent

负责：

```text
部署
试玩
记录
复现
```

### Product Manager Agent

负责：

```text
用户反馈
需求变化
版本规划
```

---

# 三十四、最终可以形成一个真正的 AI Game Factory

你的最终产品形态不是：

```text
Claude Code + 几个 Skill
```

而应该是：

```text
                 AI_Cowork_Game
                       │
             ┌─────────┴─────────┐
             │   Game Director   │
             └─────────┬─────────┘
                       │
       ┌───────────────┼────────────────┐
       ↓               ↓                ↓
   DESIGN          ART FACTORY     CODE FACTORY
       │               │                │
     GDD.md        Assets.md          V1...Vn
       │               │                │
       └───────────────┼────────────────┘
                       ↓
                    QA FACTORY
                       │
                Auto Test/Debug
                       │
                       ↓
                  PLAYABLE GAME
                       │
                    URL
                       │
                       ↓
                    USER
                       │
                   Feedback
                       │
                       ↓
                 CHANGE REQUEST
                       │
                       ↓
                 NEXT VERSION
                       │
                       └──────────→ ...
```

**最关键的三个“Source of Truth”建议定死：**

```text
GDD.md
   ↓
WHAT the game should be

ART_STYLE.md
   ↓
HOW the game should look

GAME_MANIFEST.yaml
   ↓
WHERE the project currently is
```

然后：

```text
Version Spec
   ↓
WHAT to build now

Code
   ↓
Implementation

Tests
   ↓
Evidence

Playtest
   ↓
Human validation
```

这样你的系统才真正具备**从一句游戏想法，一直自主推进到可试玩游戏，再根据用户反馈持续迭代**的能力。

另外，建议你把这些 Skill 本身也采用 Superpowers 的 `writing-skills` 方法来开发：先构造“没有这个 Skill 时 Agent 会犯什么错误”的压力测试，再写 Skill，再让 Agent 跑测试验证，而不是直接堆大量提示词。Superpowers 官方的 `writing-skills` 就明确采用这种“Skill 的 TDD”方法。([GitHub][3])

**下一步最值得做的不是继续增加 Skill，而是把这 18 个 Skill 的 `SKILL.md` 直接定义出来。**尤其是 `game-orchestrator`、`gdd-generator`、`gdd-check`、`game-version-planner`、`game-code-generator` 这 5 个，它们决定了整个 AI_Cowork_Game 能不能真正跑起来。

[1]: https://github.com/obra/Superpowers?utm_source=chatgpt.com "GitHub - obra/superpowers: An agentic skills framework & software development methodology that works. · GitHub"
[2]: https://github.com/obra/superpowers-developing-for-claude-code/blob/main/skills/developing-claude-code-plugins/references/plugin-structure.md?utm_source=chatgpt.com "superpowers-developing-for-claude-code/skills/developing-claude-code-plugins/references/plugin-structure.md at main · obra/superpowers-developing-for-claude-code · GitHub"
[3]: https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md?plain=1&utm_source=chatgpt.com "superpowers/skills/writing-skills/SKILL.md at main · obra/superpowers · GitHub"
