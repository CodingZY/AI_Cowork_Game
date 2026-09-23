你这个问题说明 **Phase 3 的 `codegen-contracts` 方案解决了“0 Write”问题，但新的瓶颈已经从 Context 问题转移成了“并行代码一致性”问题**。

这两个问题要分开解决：

```text
第一阶段问题：
Coder 不写代码
        ↓
Contract Context Compression
        ↓
解决

第二阶段问题：
Coder 都写了代码
        ↓
接口/依赖不一致
        ↓
TS/Build 失败
```

所以我建议现在对 Phase 3 做一次重要修正：

> **Contract 可以并行生成，但代码不能无条件并行写。必须先冻结共享接口，再按照依赖 Wave 并行实现。**

同时，Phase 4 不承担“看起来好不好”的判断，只负责：

> **代码是否能通过自动化测试、浏览器运行是否报错、能否 Build、能否部署。**

视觉体验、玩法是否有趣、素材是否正确等，全部放到下一阶段人工试玩。

---

# 一、先解决 Phase 3 当前的两个问题

## 1. 56 个文件并行写，接口不一致

你现在类似：

```text
Contract A → Coder A ─┐
Contract B → Coder B ─┤
Contract C → Coder C ─┤
Contract D → Coder D ─┤
                      ↓
                  Integration
                      ↓
                    tsc ❌
```

例如：

```text
NightResolutionSystem
        ↓
ShadowThreat
        ↓
active
x
y
destroy()
```

但是另一个 Contract 实际实现的 `ShadowThreat` 没这些 API。

这不是 Coder 能不能写好的问题，而是：

> **并行 Coder 在共同接口尚未冻结的情况下各自“猜接口”。**

---

# 二、Phase 3 应改成“接口先行，代码并行”

新的架构：

```text
V1
 ↓
Planner
 ↓
Interface Planning
 ↓
冻结 Shared Types / APIs
 ↓
Contract Validation
 ↓
Dependency Graph
 ↓
Execution Waves
 ↓
Coder
```

而不是：

```text
V1
 ↓
生成 56 Contracts
 ↓
56 Coders 全部并行
```

---

# 三、增加一个非常重要的东西：Shared API Contract

在：

```text
codegen-contracts/
```

之外增加：

```text
codegen-contracts/
├── 00-v1-overview.md
├── 00-shared-api.md
├── 01-GameState.md
├── 02-PlayerSystem.md
├── 03-ShadowThreat.md
├── ...
```

或者更工程化：

```text
codegen-contracts/
├── shared-api.md
├── shared-types.ts
└── ...
```

其中：

```text
shared-api.md
```

是 Planner 生成的**接口真相源**。

例如：

````markdown
# Shared API Contract

## ShadowThreat

```ts
interface ShadowThreat {
  id: string
  x: number
  y: number
  active: boolean

  destroy(): void
}
````

## ShadowThreatSystem

```ts
interface ShadowThreatSystem {
  spawn(x: number, y: number): ShadowThreat
  resolve(threatId: string): void
}
```

````

然后：

```text
NightResolutionSystem
````

不能自己定义：

```ts
ShadowThreat.active
```

而是必须以：

```text
shared-api.md
```

为准。

---

# 四、最好进一步把 TypeScript 类型变成真正的 Single Source of Truth

如果可以，我更推荐：

```text
src/types/
├── GameTypes.ts
├── EntityTypes.ts
├── EventTypes.ts
└── SystemTypes.ts
```

这些文件由 Planner / Foundation Coder **优先生成并冻结**。

例如：

```ts
export interface ShadowThreat {
  id: string
  x: number
  y: number
  active: boolean
  destroy(): void
}
```

那么其他 Coder：

```ts
import type { ShadowThreat } from "../types/EntityTypes"
```

而不是：

```ts
interface ShadowThreat {
  ...
}
```

自己重新定义。

这样：

> **TypeScript 编译器本身就成为 Contract Validator。**

---

# 五、代码生成应该变成 4 个 Wave

我建议以后不要再：

```text
56 coder 全部 spawn
```

而是：

```text
Wave 0：Foundation
        ↓
Wave 1：Core Systems
        ↓
Wave 2：Scenes / UI
        ↓
Wave 3：Integration
```

例如：

### Wave 0

```text
GameTypes
GameState
Events
Constants
AssetRegistry
```

这些必须先完成。

---

### Wave 1

可以并行：

```text
PlayerSystem
InventorySystem
TimeSystem
LanternSystem
ShadowThreatSystem
SaveSystem
```

前提：

> 它们只依赖 Wave 0 已经冻结的 API。

---

### Wave 2

例如：

```text
NightScene
FarmScene
GameUI
InventoryUI
```

它们依赖 Wave 1。

---

### Wave 3

```text
GameIntegration
SaveIntegration
SceneTransitions
```

最后统一整合。

---

# 六、并行的核心原则

以后 Codegen Planner 必须遵守：

```text
允许：

A ─────┐
B ─────┼──→ 并行
C ─────┘

禁止：

A ──→ B
     ↓
     A/B 同时修改接口
```

更严格一点：

> **Coder 可以并行写不同模块，但不能并行修改同一个文件，也不能并行定义同一个公共接口。**

---

# 七、增加 File Ownership

每个 Contract 增加：

```markdown
## File Ownership

WRITE:
src/systems/ShadowThreatSystem.ts

READ:
src/types/EntityTypes.ts
src/core/GameState.ts

DO NOT MODIFY:
src/types/EntityTypes.ts
src/core/GameState.ts
```

这样：

```text
Coder A
WRITE ShadowThreatSystem.ts

Coder B
WRITE NightResolutionSystem.ts
```

但：

```text
EntityTypes.ts
```

已经冻结。

---

# 八、Coder 不能修改 Contract

这一条建议直接写死：

```text
Coder MUST NOT:

- 修改 shared-api.md
- 修改 shared-types.ts
- 修改其他 Contract
- 修改其他 Coder 的 owned files
- 为解决 tsc 错误自行改变公共 API
```

如果发现：

```text
Contract A 与 Contract B 冲突
```

应该：

```text
STOP
 ↓
REPORT_CONTRACT_CONFLICT
 ↓
Planner 修正
 ↓
重新生成 Contract
```

而不是让 Coder 自己“聪明地修”。

---

# 九、解决 `.ts + .js` 双份代码问题

这个问题也很典型。

你现在：

```text
src/
├── xxx.ts
├── xxx.js
├── yyy.ts
├── yyy.js
```

这是不应该发生的。

## 明确规定

开发源码：

```text
src/**/*.ts
```

只能有：

```text
.ts
```

编译输出：

```text
dist/**/*.js
```

统一放到：

```text
dist/
```

所以：

```text
src/
    TypeScript

      ↓ tsc / Vite

dist/
    JavaScript
```

而不是：

```text
src/
├── xxx.ts
└── xxx.js
```

---

# 十、Phase 3 增加 Source Hygiene

在代码生成阶段增加硬规则：

```text
SOURCE_LANGUAGE = TypeScript

src/
  *.ts

FORBIDDEN:
src/**/*.js
src/**/*.mjs
src/**/*.cjs
```

Coder Prompt：

```text
You are working in a TypeScript project.

Rules:

1. Write TypeScript only.
2. NEVER create .js files inside src/.
3. NEVER create duplicate .ts/.js implementations.
4. Do not manually transpile TypeScript.
5. Build output belongs to dist/.
```

---

# 十一、tsconfig 也要兜底

建议：

```json
{
  "compilerOptions": {
    "allowJs": false,
    "checkJs": false,
    "noEmit": false,
    "outDir": "dist"
  },
  "include": ["src/**/*.ts", "tests/**/*.ts"],
  "exclude": ["dist", "node_modules"]
}
```

具体配置还要根据你的 Phaser/Vite 项目实际结构调整，但原则是：

```text
src = TS
dist = compiled JS
```

---

# 十二、Phaser / Vitest 的 `Cannot find module` 问题

这个问题不能让 Coder 自己解决。

应该由项目初始化阶段统一处理：

```text
package.json
      ↓
npm install
      ↓
Phaser
Vitest
Vite
TypeScript
```

然后所有 Coder 共用同一个：

```text
node_modules
```

Coder 不应该：

```text
Coder A → 自己猜 package
Coder B → 自己安装 package
Coder C → 自己修改 package.json
```

否则又会产生并行环境不一致。

---

# 十三、增加 Dependency Ownership

建议：

```text
package.json
package-lock.json
vite.config.ts
tsconfig.json
vitest.config.ts
```

全部归：

```text
Infrastructure / Foundation
```

Coder 默认：

```text
DO NOT MODIFY
```

如果 Contract 真的需要新依赖：

```text
REPORT_DEPENDENCY_REQUEST
```

交给 Planner / Infrastructure Agent 处理。

---

# 十四、所以 Phase 3 最终调整为

```text
Planner
 ↓
Shared API / Types
 ↓
Contract Generation
 ↓
Contract Validation
 ↓
Dependency Graph
 ↓
Wave 0
 ↓
tsc
 ↓
Wave 1 parallel
 ↓
tsc
 ↓
Wave 2 parallel
 ↓
tsc
 ↓
Integration
 ↓
Full Test
```

而不是：

```text
56 parallel coder
 ↓
tsc
 ↓
希望它能过
```

---

# Phase 4：自动测试 → Debug → Playable Build

现在进入你要求的 Phase 4。

我建议这一阶段的目标非常明确：

> **Phase 4 不负责判断“游戏好不好玩”，只负责判断“代码是不是健康、游戏能不能正常运行”。**

---

# 十五、Phase 4 的职责边界

## Phase 4 自动检查

负责：

```text
代码
 ↓
TypeScript
 ↓
Unit Test
 ↓
Integration Test
 ↓
E2E Smoke Test
 ↓
Browser Runtime
 ↓
Build
 ↓
Deploy
 ↓
Health Check
```

发现：

```text
TS Error
Test Error
Runtime Error
Console Error
Network Error
Build Error
```

自动 Debug。

---

## Phase 4 不负责

不判断：

```text
❌ 角色好不好看
❌ UI 是否美观
❌ 地图是否漂亮
❌ 游戏是否有趣
❌ 美术风格是否统一
❌ 操作手感好不好
❌ 难度是否合理
❌ 玩家是否喜欢
```

这些全部留给：

# Phase 5：人工试玩 → Feedback → Fix

---

# 十六、Phase 4 Skill

继续使用你规划的四个：

```text
12-game-test
13-browser-debug
14-playable-build
15-version-regression
```

我建议职责如下：

| Skill                | 核心职责                          |
| -------------------- | ----------------------------- |
| `game-test`          | 测试策略 + 自动测试                   |
| `browser-debug`      | 浏览器运行错误检测 + 自动修复              |
| `playable-build`     | Build + Deploy + Health Check |
| `version-regression` | V2/V3 回归 V1/V2                |

---

# 十七、12-game-test

## 目标

建立自动化测试体系：

```text
Unit
Integration
E2E
Game State
```

但对于 Phaser 游戏，不要过度追求测试数量。

重点是：

> **验证游戏逻辑和核心游戏循环。**

---

# 十八、Unit Test

测试：

```text
纯游戏逻辑
```

例如：

```text
TimeSystem
InventorySystem
CombatSystem
LanternSystem
ScoreSystem
SaveSystem
```

例如：

```text
TimeSystem

day 0
 ↓
advance()
 ↓
day 1
```

---

# 十九、Game State Test

这个测试非常重要。

例如：

```text
初始：

coins = 0
seeds = 3

plant
 ↓

seeds = 2

harvest
 ↓

coins = 10
```

直接验证：

```text
GameState
```

而不是验证 UI。

---

# 二十、Integration Test

验证：

```text
System A
+
System B
```

例如：

```text
Player
 ↓
InteractionSystem
 ↓
LanternSystem
 ↓
GameState
```

或者：

```text
FarmSystem
 ↓
TimeSystem
 ↓
CropSystem
 ↓
EconomySystem
```

---

# 二十一、E2E Test

Phase 4 不做视觉判断。

E2E 只验证：

```text
Browser
 ↓
Game starts
 ↓
Canvas exists
 ↓
No fatal runtime error
 ↓
Can perform basic input
 ↓
No fatal error
```

例如：

```text
open game
 ↓
wait 3 seconds
 ↓
press ArrowRight
 ↓
press ArrowUp
 ↓
click interaction
 ↓
wait
 ↓
check console
```

不检查：

```text
“角色是不是在正确位置”
```

因为目前没有多模态能力。

---

# 二十二、Browser Debug 简化

你原来的：

```text
Console
Network
Runtime
Screenshot
```

Phase 4 改成：

```text
Console
Network
Runtime
```

删除：

```text
Screenshot Analysis
```

因为当前阶段没有视觉判断能力。

---

# 二十三、Browser Debug 检查项

自动浏览器运行：

```text
Browser
 ↓
Load URL
 ↓
Wait
 ↓
Console Errors
 ↓
Page Errors
 ↓
Failed Network Requests
 ↓
Basic Interaction
 ↓
Runtime Errors
```

最终：

```text
PASS
```

或者：

```text
FAIL
```

---

# 二十四、什么叫 Browser PASS？

不是：

> 游戏看起来正常。

而是：

```text
Browser PASS

✓ Page loaded
✓ Phaser initialized
✓ Canvas created
✓ No uncaught exception
✓ No console error
✓ No critical network failure
✓ Basic input executed
```

这就够了。

---

# 二十五、自动 Debug

完整流程：

```text
Test
 ↓
FAIL
 ↓
Collect Error
 ↓
Root Cause Analysis
 ↓
Patch
 ↓
Targeted Test
 ↓
Full Test
```

最多：

```text
MAX_AUTO_FIX = 3
```

---

# 二十六、不要让 Debug Agent 无限修改

必须：

```text
attempt = 1

FAIL
 ↓
Fix
 ↓
Test

attempt = 2

FAIL
 ↓
Fix
 ↓
Test

attempt = 3

FAIL
 ↓
STOP
```

输出：

```text
HUMAN_REVIEW_REQUIRED
```

---

# 二十七、Debug Agent 的重要限制

Debug Agent 只能：

```text
修复测试发现的问题
```

不能：

```text
顺便重构架构
顺便优化代码
顺便改 UI
顺便重新设计系统
```

否则一个小错误：

```text
TypeError
```

最后变成：

```text
修改 15 个文件
引入 8 个新问题
```

---

# 二十八、13-browser-debug Skill

建议：

```markdown
# browser-debug

## Goal

检测 Web Game 的运行时错误。

## Input

- Playable Build
- URL
- Test Scenario

## Check

1. Page Load
2. Console Errors
3. Uncaught Exceptions
4. Network Failures
5. Basic Input
6. Phaser Initialization

## No Visual Validation

This skill MUST NOT judge:

- visual quality
- layout
- animation quality
- asset correctness
- gameplay fun

## Auto Fix

MAX_ATTEMPTS = 3

For each failure:

Detect
→ Diagnose
→ Patch
→ Targeted Test
→ Full Test

After 3 failures:

HUMAN_REVIEW_REQUIRED
```

---

# 二十九、14-playable-build

这个 Skill 非常简单：

```text
Source
 ↓
Install
 ↓
TypeCheck
 ↓
Test
 ↓
Build
 ↓
Deploy
 ↓
Health Check
 ↓
URL
```

---

# 三十、Build 必须成为发布门禁

不能：

```text
Test PASS
 ↓
Deploy
```

而应该：

```text
Unit PASS
 ↓
Integration PASS
 ↓
E2E PASS
 ↓
Browser PASS
 ↓
TypeScript PASS
 ↓
Build PASS
 ↓
Deploy
```

任何一步：

```text
FAIL
```

都不能生成：

```text
PLAYABLE_URL
```

---

# 三十一、Playtest URL 生成条件

只有：

```text
ALL_CHECKS_PASS
```

才：

```text
DEPLOY
 ↓
HEALTH CHECK
 ↓
PLAYABLE_URL
```

---

# 三十二、15-version-regression

V1：

```text
V1 Tests
```

V2：

```text
V1 Tests
+
V2 Tests
```

V3：

```text
V1 Tests
+
V2 Tests
+
V3 Tests
```

---

# 三十三、为什么必须保留旧测试？

因为：

```text
V2
```

可能增加：

```text
Inventory
```

结果把：

```text
V1 的 Save
```

搞坏了。

所以：

```text
V2
```

不是只测试：

```text
Inventory
```

而必须：

```text
V1 全部通过
+
Inventory 通过
```

---

# 三十四、Phase 4 Temporal Workflow

最终 Temporal 可以设计成：

```text
GameVersionWorkflow
        │
        ▼
GenerateTests
        │
        ▼
TypeCheck
        │
        ▼
UnitTest
        │
        ▼
IntegrationTest
        │
        ▼
Build
        │
        ▼
Deploy Preview
        │
        ▼
BrowserSmokeTest
        │
        ├── PASS ──────────────┐
        │                      │
        └── FAIL               │
             ↓                 │
        BrowserDebug           │
             ↓                 │
        TargetedTest           │
             ↓                 │
        FullTest ──────────────┘
             │
        3 failures
             ↓
    HUMAN_REVIEW_REQUIRED
```

如果全部通过：

```text
PlayableBuild
 ↓
HealthCheck
 ↓
PLAYABLE_URL
```

---

# 三十五、Phase 4 最终文件结构

建议：

```text
workspace/games/<game-id>/
│
├── GDD.md
├── ART_STYLE.md
├── GAME_ARCHITECTURE.md
│
├── assets/
├── assets.json
├── codegen-assets.json
│
├── versions/
│   ├── V1.md
│   ├── V2.md
│   └── V3.md
│
├── codegen-contracts/
│
├── src/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── state/
│
├── test-results/
│   ├── V1-test-report.md
│   └── V1-debug-report.md
│
├── build/
│
└── playtest/
    ├── V1-playtest.md
    └── V1-url.md
```

---

# 三十六、Phase 4 SKILL 总设计

## `12-game-test`

```text
GDD
+
Vn
+
Architecture
+
Code
 ↓
Test Plan
 ↓
Unit
Integration
State
E2E
 ↓
Test Report
```

核心原则：

> 测试核心游戏逻辑，不测试视觉质量。

---

## `13-browser-debug`

```text
Playable Build
 ↓
Browser
 ↓
Console
Runtime
Network
 ↓
Error
 ↓
Root Cause
 ↓
Patch
 ↓
Retest
```

最多：

```text
3 attempts
```

失败：

```text
HUMAN_REVIEW_REQUIRED
```

---

## `14-playable-build`

```text
Code
 ↓
TypeCheck
 ↓
Tests
 ↓
Build
 ↓
Deploy
 ↓
Health Check
 ↓
Playable URL
```

---

## `15-version-regression`

```text
V1
 ↓
V1 Tests

V2
 ↓
V1 Tests
+
V2 Tests

V3
 ↓
V1 Tests
+
V2 Tests
+
V3 Tests
```

---

# 三十七、Phase 4 验收标准

最终 Temporal 返回：

```text
━━━━━━━━━━━━━━━━━━━━━━━━
V1 AUTOMATED VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━

TypeScript       PASS
Unit Test        PASS
Integration Test PASS
Game State Test  PASS
E2E Smoke Test   PASS

Browser:
  Page Load      PASS
  Phaser Init    PASS
  Console        PASS
  Runtime        PASS
  Network        PASS

Build            PASS
Deploy           PASS
Health Check     PASS

━━━━━━━━━━━━━━━━━━━━━━━━
PLAYABLE
━━━━━━━━━━━━━━━━━━━━━━━━

URL:
https://xxx
```

这里的 **PASS 不代表“游戏好玩”**。

只代表：

> **代码、运行时和构建链路健康，可以交给用户试玩。**

---

# 三十八、Phase 3 + Phase 4 的最终边界

这样整个系统的职责就非常清楚了：

```text
Phase 1
需求 → GDD
        │
        ▼
Phase 2
GDD → 美术资产
        │
        ▼
Phase 3
GDD + Assets → 完整 V1 代码
        │
        │
        ├─ Planner 看全局
        ├─ Contract 压缩 Context
        ├─ Shared API 冻结
        ├─ Wave 并行开发
        └─ Integration
        │
        ▼
Phase 4
自动测试 → Debug → Build → Deploy
        │
        ▼
Playable URL
        │
        ▼
Phase 5
人工试玩
        │
        ├─ 视觉反馈
        ├─ 玩法反馈
        ├─ Bug
        └─ 修改意见
        │
        ▼
修复 / 下一版本
```

这里最值得你现在马上修改 Phase 3 的有 **三个硬规则**：

### ① Contract 可以并行生成，但不能让 56 个 Coder 无条件并行

改成：

```text
Shared API/Types
      ↓
冻结
      ↓
Dependency Waves
      ↓
Wave 内有限并行
```

### ② `src/` 禁止 `.js`

统一：

```text
src/**/*.ts
        ↓
      build
        ↓
dist/**/*.js
```

并把：

```text
package.json
tsconfig
vite
vitest
```

设为基础设施文件，Coder 默认不得修改。

### ③ Phase 4 不做视觉检查

自动浏览器阶段只判断：

```text
能打开
+
Phaser 初始化
+
没有 Console/Runtime/Network 致命错误
+
基础输入可以执行
```

**“角色位置对不对、素材好不好看、UI 是否合理、游戏好不好玩”全部留到 Phase 5 人工试玩。**

这样 Phase 3 解决的是**“正确地生成代码”**，Phase 4 解决的是**“机器自动证明代码至少能运行”**，Phase 5 才解决**“人来证明这个游戏值得玩”**。这三个阶段的边界会非常清晰。
