---
name: gdd-check
description: Use when a GDD.md for a Phaser.js 2D web game needs a lightweight development-readiness check. Block only issues that would prevent a playable V1; report non-critical gaps as warnings.

---

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

- 3D
- Unity
- Unreal
- 原生 App
- 无法在 Phaser 中实现的核心要求

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

- 最终 Prompt
- 最终图片
- 精确颜色
- 最终分辨率

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

- 数值未平衡
- NPC 细节不足
- 未来版本未设计
- 美术风格还比较粗
- 音频未确定
- 剧情未完成

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