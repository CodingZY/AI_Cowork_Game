# Phase 3：GDD → V1 可玩游戏

## 1. 阶段目标

Phase 3 的目标不是一次性生成完整游戏，而是：

> 将 GDD 转化为最多 3 个“完整可运行、可试玩、可验证”的游戏版本，并通过用户试玩反馈逐版本迭代，最终完成 GDD 核心需求。

输入：

```text
GDD.md
ART_STYLE.md
assets.json
assets/
```

输出：

```text
GAME_ARCHITECTURE.md

V1.md
V2.md
V3.md

game source code

可运行游戏

试玩链接

PLAYTEST_REPORT.md
```

版本数量：

```text
1 ≤ N ≤ 3
```

禁止：

```text
V1 → 地图
V2 → 玩家
V3 → 战斗
V4 → UI
V5 → 保存
```

因为这种拆法会导致每一个版本都不是完整产品。

正确方式：

```text
V1 = 最小完整游戏闭环
V2 = 完整游戏 + 第二层核心玩法
V3 = 完整游戏 + 剩余高价值内容
```

---

# 2. Phase 3 总体架构

```text
                 GDD.md
                   │
                   │
         assets.json + assets/
                   │
                   ▼
        ┌─────────────────────┐
        │ game-architecture   │
        └──────────┬──────────┘
                   │
                   ▼
          GAME_ARCHITECTURE.md
                   │
                   ▼
        ┌─────────────────────┐
        │  game-version-      │
        │      planner        │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │ Version Plan        │
        │                     │
        │ V1.md               │
        │ V2.md               │
        │ V3.md               │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  game-code-generator│
        └──────────┬──────────┘
                   │
                   ▼
            Superpowers
            Planning
                   │
                   ▼
                  TDD
                   │
                   ▼
              Code Agent
                   │
                   ▼
              Build Game
                   │
                   ▼
             Deploy Vn
                   │
                   ▼
              Playable URL
                   │
                   ▼
             User Playtest
                   │
                   ▼
              Feedback
                   │
                   ▼
          Next Version / Fix
```

---

# 3. 三个 Skill

Phase 3 保持和当前项目一致，不使用编号。

```text
backend/
└── game-skills/
    └── skills/
        ├── game-brainstorm/
        ├── game-requirements/
        ├── gdd-check/
        ├── gdd-generator/
        │
        ├── game-art-style/
        ├── art-asset-spec/
        ├── art-pipeline/
        ├── art-consistency-check/
        │
        ├── game-architecture/
        ├── game-version-planner/
        └── game-code-generator/
```

三个 Skill 的职责：

| Skill | 输入 | 输出 | 核心问题 |
|---|---|---|---|
| game-architecture | GDD + Assets | GAME_ARCHITECTURE.md | 游戏怎么实现 |
| game-version-planner | GDD + Architecture | V1/V2/V3 | 这次先做什么 |
| game-code-generator | 当前 Version + Architecture + Assets | Game Code | 怎么把当前版本做出来 |

---

# 4. game-architecture

## 4.1 目标

```text
GDD
 ↓
GAME_ARCHITECTURE.md
```

它负责定义：

```text
Engine
Rendering
Game State
Entity
Scene
UI
Input
Save
Audio
Asset Loading
Data
System
```

对于当前项目，固定技术栈：

```yaml
platform: web
engine: Phaser.js
dimension: 2D
language: TypeScript
build: Vite
mode: single_player
```

因此 Architecture Skill 不需要重新讨论引擎选择。

---

# 5. GAME_ARCHITECTURE.md

建议结构：

```markdown
# Game Architecture

## 1. Technical Stack

## 2. Project Structure

## 3. Scene Architecture

## 4. Game State

## 5. Entity Model

## 6. Core Systems

## 7. UI Architecture

## 8. Input

## 9. Asset Loading

## 10. Save System

## 11. Audio

## 12. Data Model

## 13. Version Constraints

## 14. Testing Strategy
```

---

# 6. Phaser Scene Architecture

中小型 Phaser 游戏不建议一开始设计过度复杂的 ECS。

例如：

```text
BootScene
    ↓
PreloadScene
    ↓
MainMenuScene
    ↓
GameScene
    ↓
UIScene
```

如果游戏需要：

```text
ShopScene
BattleScene
MapScene
```

再根据 GDD 增加。

原则：

> 只建立当前游戏实际需要的架构。

---

# 7. Game State

建议明确：

```text
GameState
├── player
├── world
├── inventory
├── currency
├── time
├── quests
├── progression
└── settings
```

例如农场游戏：

```json
{
  "player": {},
  "farm": {},
  "inventory": {},
  "money": 100,
  "day": 1,
  "time": 8,
  "crops": [],
  "settings": {}
}
```

---

# 8. Save System

保存必须从 V1 就存在。

不能：

```text
V1 没保存
V2 再增加保存
```

因为保存是用户完整体验的一部分。

V1 至少支持：

```text
开始游戏
→ 游戏状态变化
→ Save
→ 刷新页面
→ Load
→ 状态恢复
```

对于 Web Phaser 游戏，可以先使用：

```text
localStorage
```

作为 MVP Save。

后续如果需要云存档，再替换实现。

---

# 9. game-version-planner

这是 Phase 3 的核心 Skill。

输入：

```text
GDD.md
GAME_ARCHITECTURE.md
```

输出：

```text
V1.md
V2.md
V3.md
```

但不是强制生成 3 个版本。

应该先判断：

```text
GDD复杂度
核心玩法数量
系统依赖
内容规模
开发风险
```

最终：

```text
1 version
2 versions
或
3 versions
```

---

# 10. Version Planner 的核心原则

## 原则一：每个版本都是完整产品

每个版本必须回答：

```text
玩家能不能启动？
玩家能不能玩？
玩家能不能完成核心目标？
玩家能不能看到结果？
玩家能不能保存？
```

全部 YES 才能成为 Vn。

---

# 11. 什么叫“完整游戏闭环”

例如农场游戏：

```text
进入农场
 ↓
种植
 ↓
等待时间
 ↓
收获
 ↓
出售
 ↓
获得金币
 ↓
保存
```

这就是完整闭环。

V1 可以是：

```text
种植
收获
出售
```

但不能是：

```text
只有种植
```

---

# 12. Version Planner 的拆分方法

首先从 GDD 找出：

```text
Core Gameplay Loop
```

例如：

```text
探索
 ↓
战斗
 ↓
获得资源
 ↓
升级
 ↓
挑战更强敌人
```

然后：

### V1

```text
探索
 ↓
战斗
 ↓
获得资源
 ↓
升级
 ↓
保存
```

### V2

增加：

```text
装备
Boss
地图扩展
```

但 V2 仍然包含：

```text
探索
战斗
资源
升级
保存
```

### V3

增加：

```text
任务
NPC
更多地图
完整内容
```

V3 仍然是完整游戏。

---

# 13. 版本拆分不是按功能数量

错误：

```text
V1
地图 + 玩家

V2
敌人

V3
战斗

```

正确：

```text
V1
最小核心循环

V2
核心循环 + 第二层玩法

V3
核心循环 + 完整内容
```

---

# 14. 三版本上限

必须加入硬约束：

```text
MAX_VERSION_COUNT = 3
```

如果 GDD 很复杂：

```text
不能生成 V4
```

而应该：

```text
V1
最小完整产品

V2
扩展核心玩法

V3
完成剩余重要需求
```

低优先级内容可以：

```text
暂不实现
```

或者进入：

```text
Future / Out of Scope
```

---

# 15. Version Planning 优先级

建议按照：

```text
Core Loop
>
Playability
>
Technical Risk
>
Player Value
>
Content
>
Polish
```

决定版本归属。

---

# 16. V1 的特殊规则

V1 不是“最少代码”。

V1 是：

> **能够证明这个游戏是否成立的最小完整产品。**

V1 必须优先验证：

```text
核心玩法是否好玩
核心循环是否成立
操作是否成立
游戏反馈是否成立
保存是否成立
```

因此 V1 可以没有：

```text
复杂动画
大量 NPC
高级特效
完整剧情
大量地图
```

但必须有：

```text
核心玩法
基本 UI
基本反馈
胜负/完成条件
保存
```

---

# 17. V1.md 结构

建议：

```markdown
# V1

## 1. Version Goal

## 2. Player Experience

## 3. Core Gameplay Loop

## 4. Included Features

## 5. Excluded Features

## 6. Game Flow

## 7. Controls

## 8. Win / Completion Condition

## 9. Save / Load

## 10. Required Assets

## 11. Technical Requirements

## 12. Acceptance Criteria

## 13. Playtest Guide
```

---

# 18. Playtest Guide 是强制字段

每个版本完成后必须告诉用户：

```text
试玩链接

试玩哪些功能

怎么开始

怎么操作

怎么玩

怎么通关

预计试玩时间

本版本重点验证什么
```

例如：

```text
V1 Playtest

试玩链接：
https://xxx

重点试玩：
1. 种植
2. 时间推进
3. 收获
4. 出售
5. 保存

体验步骤：
1. 启动游戏
2. 点击农田
3. 种下种子
4. 推进一天
5. 收获作物
6. 到商店出售
7. 查看金币
8. 保存
9. 刷新页面
10. 确认数据恢复

通关条件：
成功完成一次种植 → 收获 → 出售，
并确认金币增加和存档恢复。

预计时间：
3~5 分钟
```

---

# 19. V2/V3 也必须重新包含完整闭环

例如：

```text
V2
```

虽然新增：

```text
NPC
任务
商店
```

但是试玩仍然应该能够：

```text
开始
 ↓
核心玩法
 ↓
完成目标
 ↓
获得结果
 ↓
保存
```

而不是：

```text
V2 只能试玩 NPC
```

---

# 20. game-code-generator

输入：

```text
V1.md
GAME_ARCHITECTURE.md
assets.json
assets/
```

输出：

```text
可运行 Phaser.js 游戏
```

核心流程：

```text
Version Plan
 ↓
Superpowers Planning
 ↓
Implementation Plan
 ↓
TDD
 ↓
Code
 ↓
Test
 ↓
Build
 ↓
Deploy
 ↓
Playtest
```

---

# 21. Superpowers Planning

Code Generator 不应该直接让 Claude：

```text
“根据 V1 写代码”
```

而应该先生成 Implementation Plan。

例如：

```text
V1
 ↓
Implementation Plan
 ↓
Task List
```

例如：

```text
Task 1
Create Phaser project

Task 2
Create GameScene

Task 3
Create player

Task 4
Create farm tiles

Task 5
Implement planting

Task 6
Implement time

Task 7
Implement harvest

Task 8
Implement selling

Task 9
Implement currency

Task 10
Implement save/load

Task 11
Add UI

Task 12
Integration test
```

---

# 22. TDD

TDD 不要求所有视觉代码都写单元测试。

重点测试：

```text
Game Rules
State
Systems
```

例如：

```text
Plant seed
→ seed removed
→ crop created

Advance day
→ crop growth +1

Harvest
→ crop removed
→ item added

Sell
→ item removed
→ money increased

Save
→ state persisted

Load
→ state restored
```

---

# 23. Code Generator 的实现顺序

推荐：

```text
1. Data Model
2. Game State
3. Core Rules
4. Core Systems
5. Phaser Scene
6. Player Interaction
7. UI
8. Assets
9. Save
10. Audio
11. Polish
```

不要一开始大量写：

```text
UI
Animation
Particle
```

先确保：

```text
Core Loop
```

运行。

---

# 24. 每个版本的完成标准

Version 完成必须同时满足：

```text
Code Complete
+
Build Pass
+
Automated Tests Pass
+
Smoke Test Pass
+
Playable
+
Save/Load Pass
```

其中：

### Code Complete

Vn.md 中所有 Required Features 已实现。

### Build Pass

```text
npm run build
```

成功。

### Automated Tests

核心规则测试通过。

### Smoke Test

至少：

```text
启动
→ 操作
→ 核心循环
→ 完成
→ 保存
→ 加载
```

全部成功。

### Playable

用户可以通过链接进入游戏。

---

# 25. Playtest Workflow

每一个版本完成后：

```text
Code
 ↓
Build
 ↓
Deploy
 ↓
Generate Playtest URL
 ↓
User
 ↓
Playtest
 ↓
Feedback
```

系统必须停止在：

```text
WAITING_FOR_PLAYTEST
```

而不是自动继续开发 V2。

---

# 26. 用户试玩后的三种结果

## PASS

用户认为：

```text
可以
```

进入：

```text
下一版本
```

如果已经是最终版本：

```text
PROJECT_COMPLETE
```

---

## FIX

用户反馈：

```text
Bug
体验问题
操作问题
核心循环问题
```

进入：

```text
Current Version Fix
```

例如：

```text
V1
 ↓
Playtest
 ↓
Bug
 ↓
Fix V1
 ↓
重新部署
 ↓
重新试玩
```

不能把 Bug 自动推迟到 V2。

---

## CHANGE

如果用户提出新的设计需求：

```text
增加钓鱼
增加 NPC
修改战斗
```

重新进入：

```text
Version Planning
```

判断：

```text
当前版本修复
还是
下一个版本
```

---

# 27. Version State Machine

Temporal 中建议维护：

```text
PLANNING
    ↓
IMPLEMENTING
    ↓
TESTING
    ↓
BUILDING
    ↓
DEPLOYING
    ↓
PLAYTEST_READY
    ↓
WAITING_FOR_USER
    ↓
     ├── PASS
     │    ↓
     │  NEXT_VERSION
     │
     ├── FIX
     │    ↓
     │  IMPLEMENTING
     │
     └── CHANGE
          ↓
       REPLAN
```

---

# 28. Temporal Workflow

建议：

```text
GameDevelopmentWorkflow
```

负责整个游戏生命周期。

内部：

```text
GenerateArchitecture
        ↓
PlanVersions
        ↓
DevelopVersion(V1)
        ↓
TestVersion(V1)
        ↓
BuildVersion(V1)
        ↓
DeployVersion(V1)
        ↓
WAIT_FOR_USER
        ↓
User Feedback
        ↓
Fix / Next Version
```

V2：

```text
DevelopVersion(V2)
...
```

最多：

```text
V1 → V2 → V3
```

---

# 29. 不要让 Temporal 自动跳过用户试玩

这是一个重要约束。

禁止：

```text
V1完成
 ↓
自动开发V2
 ↓
自动开发V3
```

正确：

```text
V1完成
 ↓
部署
 ↓
告诉用户试玩
 ↓
等待用户
 ↓
用户确认
 ↓
V2
```

因为 Phase 3 的核心价值就是：

> **让真实用户尽早验证 AI 生成的游戏。**

---

# 30. 试玩链接

每一个完成版本必须生成：

```text
Playtest URL
```

并关联：

```text
game_id
version
commit
build
deployment
```

例如：

```json
{
  "game_id": "farm-game",
  "version": "V1",
  "build_id": "build-001",
  "commit": "abc123",
  "playtest_url": "https://...",
  "status": "PLAYTEST_READY"
}
```

这样以后用户反馈：

> V1 的商店卖东西按钮有问题。

系统可以准确定位：

```text
game
→ V1
→ build
→ commit
```

---

# 31. Playtest Result

每次试玩都记录：

```text
PLAYTEST_REPORT.md
```

例如：

```markdown
# V1 Playtest Report

## Version

V1

## URL

...

## Features Tested

- Planting
- Time
- Harvest
- Selling
- Save

## User Result

PASS

## Feedback

...

## Bugs

...

## Required Changes

...

## Next Action

Proceed to V2
```

---

# 32. V1 → V2 的判断

不是：

```text
V1完成
→ 时间到了
→ V2
```

而是：

```text
V1 Playtest
      ↓
核心闭环成立？
      │
   ┌──┴──┐
   NO    YES
   │      │
 Fix    V2
```

V1 的核心闭环如果没有被验证：

```text
禁止进入 V2。
```

---

# 33. Phase 3 Definition of Done

## Architecture

```text
[ ] GAME_ARCHITECTURE.md
[ ] Scene Architecture
[ ] Game State
[ ] Entity
[ ] Systems
[ ] Input
[ ] Save
[ ] Asset Loading
```

## Version Plan

```text
[ ] V1
[ ] V2（如果需要）
[ ] V3（如果需要）
[ ] ≤ 3 versions
```

## Every Version

```text
[ ] 可以启动
[ ] 可以操作
[ ] 可以完成核心目标
[ ] 可以看到结果
[ ] 可以保存
[ ] 可以加载
[ ] Build Pass
[ ] Tests Pass
[ ] Smoke Test Pass
[ ] Playable URL
```

## User Playtest

```text
[ ] 告诉用户试玩功能
[ ] 告诉用户操作方式
[ ] 告诉用户体验步骤
[ ] 告诉用户通关条件
[ ] 提供试玩链接
[ ] 等待用户反馈
```

---

# 34. Phase 3 最终闭环

```text
                   GDD
                    │
                    ▼
             Architecture
                    │
                    ▼
             Version Planner
                    │
            ┌───────┼───────┐
            ▼       ▼       ▼
           V1       V2      V3
            │       │       │
            ▼       ▼       ▼
          Code     Code    Code
            │       │       │
            ▼       ▼       ▼
          Test     Test    Test
            │       │       │
            ▼       ▼       ▼
         Deploy   Deploy  Deploy
            │       │       │
            ▼       ▼       ▼
         Playtest Playtest Playtest
            │       │       │
            ▼       ▼       ▼
         Feedback Feedback Feedback
            │       │       │
            └───────┴───────┘
                    │
                    ▼
              Final Game
```

最终 MVP 的定义：

> **用户拿到一个真实可访问的游戏链接，可以启动游戏、操作游戏、完成核心游戏循环、保存进度，并能够通过试玩反馈推动后续版本开发。**