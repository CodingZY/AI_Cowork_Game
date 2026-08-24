对，我也认为上一版**过度工程化了**。

如果目标是中小型 Phaser.js 2D 游戏，最大的风险不是“GDD 不够详细”，而是：

> **Agent 为了把 GDD 写完整，不断向用户提问，最后用户还没看到游戏，已经被需求分析耗尽耐心。**

所以这三个 Skill 应该从“完整性优先”改成：

> **最小充分设计（Minimum Sufficient Design） + 风险驱动澄清（Risk-driven Clarification） + 默认决策（Sensible Defaults） + 尽早进入可玩版本。**

尤其你的最终目标是：

```text
想法
 ↓
快速形成可玩的 V1
 ↓
用户试玩
 ↓
通过实际试玩发现问题
 ↓
V2/V3迭代
```

而不是：

```text
想法
 ↓
问 50 个问题
 ↓
写 100 页 GDD
 ↓
用户发现“其实我想要的不是这个”
```

因此我建议把三个 Skill 改成下面这个版本。

---

# 一、重新定义三个 Skill 的职责

不要让三个 Skill 都追求“把设计想清楚”。

应该变成：

```text
game-brainstorm
    ↓
把模糊想法变成“足够开始做”的游戏方案

gdd-generator
    ↓
把方案变成“足够让 AI 开始开发”的 GDD

gdd-check
    ↓
只阻止真正会导致开发失败的问题
```

核心原则：

> **不是要求 GDD 完美，而是要求 GDD 足够明确，可以开始 V1。**

---

# 二、优化后的总体流程

我建议最终采用这个：

```text
用户想法
   ↓
快速理解
   ↓
发现真正影响游戏的未知项
   ↓
只询问关键问题
   ↓
合理默认其他细节
   ↓
Game Concept
   ↓
GDD Draft
   ↓
轻量 GDD Check
   ↓
┌───────────────┐
│ 是否足够开发V1 │
└───────┬───────┘
        │
     Yes│
        ↓
      V1开发
        ↓
      试玩
        ↓
    用户反馈
        ↓
     再修改
```

而不是追求：

```text
GDD 100% 完整
```

---

# 三、优化版 `game-brainstorm`

核心变化：

### 从：

> “系统性询问所有游戏设计问题”

改成：

> **“只有不明确的地方会阻碍 V1 开发时才询问。”**

而且增加：

## Fast Mode

默认进入快速模式。

对于中小型游戏：

> **最多主动询问 3～7 个关键问题。**

很多东西直接采用合理默认值。

例如用户说：

> “我想做一个像星露谷一样的俯视角种田小游戏。”

Agent 不应该问：

```text
目标用户？
游戏生命周期？
NPC数量？
经济系统？
时间系统？
成长系统？
地图规模？
存档机制？
音频？
……
```

而应该快速确认：

```text
1. 核心玩法是否就是“种植→成长→收获→出售”？
2. 是否需要 NPC / 社交？
3. V1 是做一个小型农场还是完整村庄？
4. 操作是否采用 WASD + E + 鼠标？
```

剩下的：

```text
Web
Phaser
2D
Top-down
单机
LocalStorage
基础 UI
```

直接默认。

---

name: game-brainstorm
description: Use when a user provides a new game idea and the idea is not yet clear enough to begin a small or medium Phaser.js 2D web game. Optimize for fast convergence and early playable implementation rather than exhaustive game-design interviews.
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Game Brainstorm

## Mission

将用户的模糊游戏想法快速转化为：

`Game Concept → 可直接进入 GDD Generator`

本 Skill 服务于**中小型 Phaser.js 2D Web Game**。

目标不是得到完美设计。

目标是：

> **用最少的交互，把真正影响 V1 开发的设计决策确定下来。**

---

# Core Principles

## 1. Start Building Early

不要为了完整设计而延迟开发。

如果已经有足够信息形成一个合理的 V1：

`STOP ASKING → GENERATE CONCEPT`

---

## 2. Ask Only Blocking Questions

只有以下情况才询问用户：

* 不同答案会导致完全不同的游戏玩法
* 不同答案会导致不同的技术架构
* 不同答案会改变 V1 范围
* 不同答案会导致用户体验明显不同
* Agent 无法合理推断

其他内容使用合理默认值。

---

# 3. Use Sensible Defaults

当前项目固定：

```yaml
platform: web
engine: Phaser.js
dimension: 2D
mode: single_player
```

默认：

```yaml
input:
  keyboard: true
  mouse: true

save:
  local_storage: true

rendering:
  2d: true

network:
  required: false

mobile_native:
  false
```

除非用户明确要求，否则不要询问这些问题。

---

# 4. Progressive Clarification

不要一次询问完整问卷。

采用：

```text
Idea
 ↓
Identify uncertainty
 ↓
Ask 1~3 questions
 ↓
Update understanding
 ↓
Identify remaining blocking uncertainty
 ↓
Ask again only if necessary
```

如果已经足够：

`STOP`

---

# 5. Question Priority

按照以下顺序处理。

## Level 1 — Core Loop

必须明确：

> 玩家最主要反复做什么？

例如：

```text
探索 → 战斗 → 获得装备 → 变强
```

或者：

```text
种植 → 等待 → 收获 → 出售 → 购买种子
```

如果 Core Loop 不明确：

`ASK`

---

## Level 2 — Player Goal

只需要知道：

> 玩家为什么继续玩？

例如：

* 打败最终 Boss
* 建设农场
* 解锁地图
* 完成一天一天的经营
* 找到所有宝藏

不要求一次定义完整成长体系。

---

## Level 3 — V1 Scope

必须明确：

> 第一版到底做多大？

例如：

```text
一个小农场
3种作物
1个NPC
1个商店
1个核心循环
```

优先缩小范围，而不是扩大范围。

---

## Level 4 — Critical Mechanics

只询问真正影响实现的问题。

例如：

* 实时战斗还是回合制？
* 横版还是俯视角？
* 单角色还是多角色？
* 是否需要 NPC？
* 是否需要关卡？
* 是否需要随机生成？

---

# 6. Do Not Over-Design

不要主动设计：

* 复杂经济系统
* 完整世界观
* 大量 NPC
* 完整任务树
* 完整数值体系
* 100 个道具
* 完整剧情
* 完整音频设计

除非这些东西是核心玩法。

这些内容可以在后续版本迭代。

---

# 7. Suggest Before Asking

如果存在多个合理方案：

不要连续提问。

直接给出：

```text
我建议 V1 使用 A。

原因：
- 实现简单
- 更快进入试玩
- 不影响后续扩展

如果你没有特别偏好，我会采用 A。
```

用户没有反对：

`采用 A`

---

# 8. Assumption Disclosure

当 Agent 使用默认设计时，明确告诉用户：

```text
以下内容我先采用默认方案，后续可以通过试玩调整：

- WASD 移动
- E 交互
- LocalStorage 存档
- 单地图
- 简单 NPC
```

不要要求用户逐项确认。

---

# 9. Game Size Classification

将项目快速分类：

### Small

核心循环 + 少量内容。

例如：

* 小型农场
* Roguelike Demo
* 简单平台跳跃
* 解谜游戏

### Medium

多个系统组合。

例如：

* 农场 + NPC + 商店
* RPG + 战斗 + 装备
* Tower Defense + 技能 + 升级

### Large

明显超出当前快速开发范围：

* 大型开放世界
* 大量内容
* 多人联机
* 复杂服务器
* 大型剧情 RPG

如果是 Large：

不要继续无限澄清。

应该：

`Scope Down → Define V1`

---

# 10. Phaser Feasibility

只有发现明显问题时才介入技术讨论。

重点检查：

* 2D 是否足够
* Phaser Scene 是否能表达
* Sprite / Tilemap 是否足够
* 浏览器输入是否足够
* LocalStorage 是否足够
* 是否需要服务器

不要因为技术细节打断正常游戏设计。

---

# 11. Fast Path

如果用户已经提供了：

* 游戏类型
* 核心玩法
* 基本视角
* V1 大致范围

则直接：

`Generate Game Concept`

不要继续提问。

---

# 12. Output

输出一个简洁的 Game Concept：

```yaml
game_concept:
  title:
  genre:
  core_loop:
  player_goal:

  camera:
  controls:

  core_features:
    - id:
      name:
      description:

  entities:
    - id:
      name:
      type:

  progression:

  v1:
    goal:
    features:

  future:
    - feature:

  assumptions:
    - assumption:

  non_goals:
    - item:

  platform:
    web: true
    engine: Phaser.js
    dimension: 2D
```

---

# 13. Completion Rule

满足以下条件立即结束 Brainstorm：

* Core Loop 明确
* Player Goal 明确
* V1 范围明确
* 关键玩法没有重大歧义
* Phaser.js 2D 可实现
* 用户没有明显反对当前方案

然后：

`→ gdd-generator`

---

# Anti-Patterns

禁止：

* 连续提出十几个问题
* 为了完整而完整
* 用户没有要求却设计大量系统
* 把 GDD 当成百科全书
* 在 Brainstorm 阶段写代码
* 因为细节未知而阻止进入 V1

---

# 四、优化版 `gdd-generator`

这里也要“大幅瘦身”。

上一版 GDD 26 个章节，对于中小型游戏明显太重。

我建议把 GDD 分成：

```text
必须有
+
有就写
+
后续补充
```

而不是要求所有游戏都填写所有章节。

---

## GDD 最核心的原则

一个系统只需要回答：

```text
玩家怎么触发？
↓
系统状态是什么？
↓
发生什么？
↓
结果是什么？
```

例如“种田”：

```text
E 交互
 ↓
检查土地
 ↓
消耗种子
 ↓
生成作物
 ↓
每天成长
 ↓
成熟
 ↓
玩家收获
```

这已经足够 Code Agent 开始工作。

不需要在 V1 GDD 中写一篇“农业系统设计论文”。

---

name: gdd-generator
description: Use when a confirmed Game Concept needs to be converted into a concise, implementation-ready GDD.md for a small or medium Phaser.js 2D web game. Prefer minimum sufficient specification over exhaustive documentation.
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# GDD Generator

## Mission

将 Game Concept 转换为：

`GDD.md`

GDD 的目标不是完整记录所有游戏内容。

目标是：

> **让后续的 Asset Agent、Version Planner、Code Agent 和 QA Agent 能够开始工作。**

---

# Core Principle

## Minimum Sufficient GDD

只定义：

> **实现当前游戏所必需的信息。**

不要求提前设计未来所有内容。

---

# Fixed Platform

所有项目固定：

```yaml
platform: Web
engine: Phaser.js
dimension: 2D
```

不得生成 3D / Unity / Unreal / Godot 方案。

---

# GDD Structure

只要求以下核心章节。

# 1. Game Overview

包含：

```text
Title
Genre
High Concept
Player Goal
Game Pillars
```

Game Pillars 控制在 3~5 个。

---

# 2. Core Gameplay Loop

必须描述：

```text
Player Action
→ Result
→ Reward / Progression
→ Next Decision
```

同时定义：

* Primary Loop
* Long-term Goal

这是 GDD 最重要的部分。

---

# 3. Game Flow

只定义玩家实际经历的流程：

```text
Start
→ Main Menu
→ Gameplay
→ Progression
→ Save
```

如果有：

* Level
* Game Over
* Victory
* Restart

再加入。

---

# 4. Core Features

每个核心功能采用最小规格：

```markdown
## Feature: Farming

Purpose:
玩家种植并收获作物。

Player Input:
E / Mouse

State:
- farmland
- cropType
- growthStage

Rules:
- empty farmland can be planted
- planting consumes seed
- crop grows when day advances
- mature crop can be harvested

Result:
- crop enters inventory
- farmland becomes empty

Dependencies:
- inventory
- time

Acceptance:
- player can plant
- crop grows
- player can harvest
```

不要要求每个 Feature 都写十几个章节。

---

# 5. Entities

只记录实际需要的实体。

格式：

```yaml
entities:
  - id: player
    type: player

  - id: npc.alice
    type: npc

  - id: item.tomato_seed
    type: item

  - id: crop.tomato
    type: crop
```

实体需要稳定 ID。

---

# 6. World

只有涉及地图 / 场景时才填写。

包括：

```text
Maps
Scenes
Spawn
Collision
Interactive Areas
Camera
```

Phaser 对应关系：

```text
Map → Tilemap
Scene → Phaser.Scene
Entity → Sprite / Container / GameObject
```

---

# 7. Controls

只定义实际使用的输入：

```yaml
controls:
  movement: WASD
  interaction: E
  primary_action: mouse_left
  pause: ESC
```

---

# 8. Progression

只有存在成长系统时填写：

```text
Player
Currency
Level
Unlock
Relationship
Equipment
```

不需要提前设计完整数值。

---

# 9. UI

只定义核心 UI：

```text
Main Menu
HUD
Inventory
Dialogue
Shop
Pause
```

每个 UI 只需要：

```text
Purpose
Open
Close
Main Actions
Displayed Data
```

---

# 10. Art Direction

只定义能影响资产生成的关键内容：

```yaml
art_direction:
  style:
  camera:
  perspective:
  palette:
  character_style:
  environment_style:
  ui_style:
```

详细美术规范交给：

`game-art-style`

---

# 11. Asset Requirements

只建立资产索引，不生成完整 Prompt。

```yaml
assets:
  - id: player.idle
    type: character
    entity: player

  - id: crop.tomato
    type: sprite
    entity: crop.tomato
    states:
      - seed
      - growing
      - mature
```

后续：

`art-asset-spec`

负责详细生成规格。

---

# 12. Persistence

如果需要存档，只定义：

```text
Save Method
Saved State
Save Trigger
Load Behavior
```

默认：

```text
localStorage
```

---

# 13. Technical Constraints

固定：

```yaml
platform: web
engine: Phaser.js
dimension: 2D
```

可补充：

```text
TypeScript
Vite
localStorage
```

但不要在 GDD 中设计复杂工程架构。

技术架构交给：

`game-architecture`

---

# 14. V1 Definition

这是必须章节。

定义：

```yaml
v1:
  goal:
  included:
    - feature
    - feature

  player_loop:
    - step
    - step
    - step

  acceptance:
    - condition
    - condition

  playable: true
```

V1 必须是：

> **可以从开始玩到完成一个明确目标的完整小游戏。**

---

# 15. Future Features

只记录高层次内容：

```text
V2:
- NPC
- Shop upgrade

V3:
- Relationship
- Events
```

不要在 V1 GDD 中提前详细设计。

---

# 16. Non-Goals

明确当前不做的内容：

```text
- Multiplayer
- 3D
- Native Mobile
- Online Account
```

以及当前项目明确不包含的游戏系统。

---

# 17. Definition of Done

只需要：

```text
All V1 acceptance criteria pass
AND
Game launches
AND
Core loop playable
AND
No blocking browser errors
AND
Playable build available
```

---

# Defaults

除非用户明确要求：

```yaml
platform: web
engine: Phaser.js
dimension: 2D
language: TypeScript
build: Vite
save: localStorage
multiplayer: false
backend: false
```

不要反复询问这些默认值。

---

# GDD Detail Level

根据项目规模自动调整。

### Small Game

GDD 可以非常短：

```text
10~20 pages or less
```

重点是：

* Core Loop
* Features
* Entities
* V1
* Acceptance Criteria

### Medium Game

增加：

* Systems
* Progression
* NPC
* Economy
* Multiple scenes
* Version roadmap

但仍然不要求完整百科式 GDD。

---

# Do Not Invent

如果用户没有确定：

* 剧情
* NPC 性格
* 经济数值
* 道具数量
* 关卡数量

不要大量虚构内容。

可以使用：

`TBD`

或者合理默认，但必须放入：

`assumptions`

---

# Completion

GDD 完成条件：

```text
Core Loop clear
AND
V1 scope clear
AND
Core features implementable
AND
Core entities identified
AND
Required assets identifiable
AND
Acceptance criteria testable
```

满足即可：

`→ gdd-check`

不要为了追求完整继续询问用户。

---

# 五、优化版 `gdd-check`

这个 Skill 是三者中我认为**最需要改变的**。

上一版的 18 项检查太像“论文审稿”。

对于你的 AI Game Cowork：

> **GDD Check 的目的不是找所有问题，而是找会导致 V1 无法开发/无法试玩的问题。**

所以应该引入三个等级：

```text
BLOCKING
WARNING
INFO
```

而且：

## 只有 BLOCKING 阻止开发。

---

---

name: gdd-check
description: Use when a GDD.md for a Phaser.js 2D web game needs a lightweight development-readiness check. Block only issues that would prevent a playable V1; report non-critical gaps as warnings.
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# GDD Check

## Mission

判断：

> **这个 GDD 是否已经足够让 AI 开始开发一个可玩的 Phaser.js 2D Web Game V1？**

不是判断：

> 这个 GDD 是否完美？

---

# Core Principle

## Block Development Only When Necessary

问题分为：

```text
BLOCKING
WARNING
INFO
```

### BLOCKING

必须修复。

### WARNING

可以先开发，后续补充。

### INFO

仅记录。

---

# 1. Platform Check

必须：

```yaml
platform: web
engine: Phaser.js
dimension: 2D
```

如果出现：

* 3D
* Unity
* Unreal
* 原生 App
* 无法在 Phaser 中实现的核心要求

则：

`BLOCKING`

---

# 2. Core Loop Check

必须能够回答：

```text
玩家做什么？
↓
发生什么？
↓
获得什么？
↓
为什么继续？
```

例如：

```text
移动
→ 攻击敌人
→ 获得金币
→ 升级武器
→ 挑战更强敌人
```

如果 Core Loop 完全不明确：

`BLOCKING`

如果细节不完整：

`WARNING`

---

# 3. V1 Scope Check

必须明确：

```text
V1 Goal
V1 Features
V1 Player Loop
V1 Acceptance
```

如果没有 V1：

`BLOCKING`

---

# 4. Playability Check

模拟：

```text
Start
→ First Action
→ Core Loop
→ Progression
→ V1 Goal
```

如果无法形成完整闭环：

`BLOCKING`

---

# 5. Feature Readiness

每个 V1 核心 Feature 至少需要：

```text
Purpose
Input / Trigger
State
Rules
Result
```

如果核心 Feature 缺失这些信息：

`BLOCKING`

如果非核心 Feature 缺失：

`WARNING`

---

# 6. Entity Check

检查核心 Entity：

```text
Player
NPC
Enemy
Item
Map
Interactive Object
```

如果代码需要但 GDD 完全没有定义：

`BLOCKING`

如果只有名称而没有详细数据：

`WARNING`

---

# 7. Asset Check

只检查：

> Code Agent 是否知道这个对象需要什么类型的资产。

例如：

```text
player
→ character sprite

enemy.slime
→ enemy sprite

crop.tomato
→ crop sprite
```

不要求：

* 最终 Prompt
* 最终图片
* 精确颜色
* 最终分辨率

这些由 Asset Pipeline 负责。

如果核心游戏对象没有任何资产定义：

`BLOCKING`

---

# 8. Input Check

检查核心操作是否存在：

```text
Move
Interact
Attack
Jump
Plant
Harvest
etc.
```

如果核心操作没有输入：

`BLOCKING`

---

# 9. State Check

检查核心玩法是否存在最基本状态。

例如：

```text
Crop
→ growthStage

Player
→ position
→ inventory

Enemy
→ health
```

如果规则依赖不存在的状态：

`BLOCKING`

---

# 10. Dependency Check

检查：

```text
Feature A
requires B
```

但 B 完全不存在：

`BLOCKING`

例如：

```text
Harvest
requires
Inventory
```

但是没有 Inventory。

---

# 11. UI Check

只检查核心操作是否有可用 UI / Feedback。

例如：

玩家获得金币后：

```text
HUD displays money
```

如果玩家无法知道核心状态：

`WARNING`

如果因此无法继续游戏：

`BLOCKING`

---

# 12. Phaser Feasibility

只做快速检查。

确认：

```text
Rendering
Input
Scene
Camera
Sprite
Tilemap
Storage
```

是否能实现核心玩法。

不进行详细技术架构审查。

如果核心玩法明显不能通过 Phaser.js 2D 实现：

`BLOCKING`

否则：

`PASS`

---

# 13. Testability

每个 V1 核心 Feature 至少有一个 Acceptance Criterion。

例如：

```text
Given player has tomato seed
When player interacts with empty farmland
Then crop is planted
And seed count decreases
```

如果无法测试：

`BLOCKING`

如果测试描述较粗：

`WARNING`

---

# 14. Numerical Check

只检查明显逻辑死锁。

例如：

```text
Starting money = 0
Seed price = 100
唯一收入来源 = Crop
Crop 必须 Seed 才能种
```

则：

`BLOCKING`

但不要求在 GDD Check 阶段完成完整经济平衡。

---

# 15. Save Check

如果 GDD 要求存档：

检查：

```text
Can Save
Can Load
Important State Identified
```

如果没有存档需求：

直接跳过。

---

# 16. Scope Check

检查 V1 是否明显过大。

如果 V1 包含：

```text
20 systems
50 NPC
100 quests
10 maps
```

应该：

`WARNING`

而不是自动 FAIL。

建议：

> 优先拆出一个更小的可玩 V1。

只有当规模已经明显无法在当前项目目标下实现：

`BLOCKING`

---

# 17. Missing Future Design

未来功能没有详细设计：

`INFO`

或者：

`WARNING`

绝对不能阻止 V1。

例如：

```text
V2:
Add romance system
```

完全可以接受。

---

# 18. Output

输出：

```yaml
gdd_check:
  status: PASS | FAIL

  blocking_issues:
    - id:
      category:
      problem:
      why_blocking:
      suggested_fix:

  warnings:
    - id:
      category:
      problem:
      suggestion:

  info:
    - message:

  v1:
    playable: true | false
    core_loop: pass | fail
    scope: pass | warning | fail
    acceptance: pass | fail

  phaser:
    feasible: true | false

  readiness:
    art: ready | needs_warning | blocked
    version_planning: ready | blocked
    code: ready | blocked

  recommendation:
    - action
```

---

# PASS Rule

只要：

```text
No BLOCKING issues
AND
Core Loop exists
AND
V1 exists
AND
V1 is theoretically playable
AND
Core Features implementable
AND
Phaser.js feasible
AND
Core Acceptance Criteria testable
```

就：

`PASS`

即使存在：

* 数值未平衡
* NPC 细节不足
* 未来版本未设计
* 美术风格还比较粗
* 音频未确定
* 剧情未完成

也允许进入开发。

---

# FAIL Rule

只有真正阻止开发的问题才：

`FAIL`

例如：

```text
BLOCKING:
V1 has no gameplay loop

BLOCKING:
Core feature has undefined rules

BLOCKING:
Player action has no input

BLOCKING:
Required entity does not exist

BLOCKING:
Core mechanic cannot be implemented in Phaser.js

BLOCKING:
V1 has no playable goal
```

---

# Important Behavior

## Do Not Rewrite GDD Automatically

发现问题后：

不要擅自修改用户的核心设计。

输出：

```text
Problem
+
Why
+
Suggested Minimal Fix
```

如果只是小问题：

允许 GDD Generator 自动修正。

如果涉及核心玩法：

返回：

`game-brainstorm`

---

# Minimal Fix Principle

修复 GDD 时：

> **优先最小修改，不要借机扩充游戏设计。**

例如：

```text
Problem:
NPC schedule undefined.
```

正确：

```text
Default:
NPC stays at shop from 09:00-18:00.
```

错误：

```text
顺便设计完整 NPC 日程系统、天气系统、季节系统……
```

---

# Final Question

GDD Check 最终只需要回答：

> **现在能不能开始做一个可以玩的 V1？**

如果：

`YES → PASS`

如果：

`NO → FAIL`

---

# 六、这版和上一版最大的区别

我建议把整个设计理念从：

> **Specification First**

改成：

> **Playable First**

对比一下：

|            | 上一版      | 优化版                    |
| ---------- | -------- | ---------------------- |
| Brainstorm | 完整需求访谈   | 快速收敛                   |
| 提问         | 尽可能完整    | 只问 Blocking Question   |
| 默认值        | 少        | 多                      |
| GDD        | 完整规格书    | Minimum Sufficient GDD |
| GDD章节      | 26章      | 15章左右                  |
| GDD Check  | 全面审查     | V1开发门禁                 |
| 缺失细节       | 容易 FAIL  | 大多数 WARNING            |
| 未来功能       | 需要描述     | 可以 TBD                 |
| 数值         | 尽量完整     | 只检查死锁                  |
| 美术         | 详细       | 只定义 Asset Requirement  |
| 技术架构       | GDD里大量描述 | 后续 Skill负责             |
| 目标         | 完整设计     | 尽快试玩                   |
| 设计闭环       | GDD完成    | V1可玩                   |

---

# 七、最重要的一条：允许 GDD“不完整”

我建议你把这条直接写进 AI_Cowork_Game 的总规范：

```text
GDD does not need to be complete.
GDD needs to be sufficient for the current version.
```

也就是说：

```text
GDD
│
├── Core Design ───── 必须明确
│
├── V1 ────────────── 必须明确
│
├── V2 ────────────── 粗略即可
│
├── V3 ────────────── 可以 TBD
│
└── Future ────────── 可以没有
```

甚至可以进一步把 GDD 状态设计成：

```text
GDD_DRAFT
     ↓
GDD_V1_READY
     ↓
V1 DEVELOPMENT
     ↓
PLAYTEST
     ↓
GDD_EVOLVING
     ↓
V2_READY
     ↓
...
```

而不是：

```text
GDD_DRAFT
 ↓
GDD_100%_COMPLETE
 ↓
开始开发
```

**这个改变会非常关键。**

因为你真正想构建的不是“AI 游戏设计师”，而是：

> **一个通过快速 V1 → 试玩 → 反馈，不断发现需求的 AI Game Cowork。**

对于中小型游戏，这种模式其实比“一开始把 GDD 定死”更适合。

---

## 八、进一步建议：把“用户确认”也降到最低

我甚至建议 `game-brainstorm` 最终采用这个交互模式：

```text
用户：
我想做一个像牧场物语一样的小游戏。

AI：
我理解你想做的是一个 Phaser.js 2D 网页游戏。
为了尽快做出 V1，我先采用：

- 俯视角
- WASD 移动
- E 交互
- 一个小农场
- 3种作物
- 种植→成长→收获→出售
- 暂无 NPC
- LocalStorage 存档

现在只需要确认一个问题：

V1 你更希望：
A. 重点做种田经营
B. 加入一个 NPC + 简单对话
C. 加入简单战斗

如果没有特别偏好，我推荐 A。
```

用户：

> A

然后就应该：

```text
Game Concept
 ↓
GDD
 ↓
GDD Check
 ↓
Version Planner
 ↓
V1
```

**而不是继续问 20 个问题。**

这会更符合你要做的 AI_Cowork_Game：**让 AI 尽早产出一个真正可以点击、可以玩的东西，然后让用户通过试玩参与设计。**
