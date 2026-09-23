# Phase 3 Skills

## 1. game-architecture/SKILL.md

```markdown
# game-architecture

## Purpose

Convert GDD.md into a practical game implementation architecture.

## Input

- GDD.md
- assets.json
- assets/

## Output

- GAME_ARCHITECTURE.md

## Fixed Technology

- Platform: Web
- Engine: Phaser.js
- Dimension: 2D
- Language: TypeScript
- Build: Vite
- Mode: Single Player

## Responsibilities

Define:

- Project structure
- Phaser scenes
- Game state
- Entities
- Core systems
- UI architecture
- Input
- Asset loading
- Save/load
- Audio
- Data model
- Testing strategy

## Rules

1. Architecture must support V1.
2. Do not over-engineer future features.
3. Do not introduce systems not required by GDD or the current version.
4. Save/load must be designed from V1.
5. Core gameplay rules must be separated from rendering where practical.
6. Architecture must support incremental V2/V3 development.
7. Maximum planned versions: 3.

## Acceptance Criteria

- GAME_ARCHITECTURE.md exists.
- V1 can be implemented from the architecture.
- Core game loop is explicitly represented.
- Save/load is defined.
- Asset loading is defined.
- Testing strategy is defined.
```

---

# 2. game-version-planner/SKILL.md

```markdown
# game-version-planner

## Purpose

Convert GDD.md into a maximum of three complete playable game versions.

## Input

- GDD.md
- GAME_ARCHITECTURE.md
- assets.json

## Output

- V1.md
- V2.md (optional)
- V3.md (optional)

## Hard Constraints

MAX_VERSION_COUNT = 3

Every version MUST be a complete playable product.

A version cannot consist only of:

- a map
- a UI
- a character
- a single system
- a technical prototype

## Core Principle

Each version must contain a complete gameplay loop.

The version should be playable from:

Start
→ Core Interaction
→ Progress
→ Goal
→ Result
→ Save

## Planning Priority

1. Core Gameplay Loop
2. Playability
3. Technical Risk
4. Player Value
5. Content
6. Polish

## Version Strategy

V1:

Minimum complete game that proves the core gameplay loop.

V2:

Expand the core game with the next highest-value gameplay systems.

V3:

Complete the remaining high-value GDD requirements.

## Rules

1. Never split versions purely by technical modules.
2. Never create a version that cannot be played independently.
3. Never create more than 3 versions.
4. V1 must contain the minimum complete gameplay loop.
5. Save/load must be included from V1 when the game has persistent progression.
6. Bugs found during V1 playtest must be fixed in V1 before proceeding.
7. User feedback can change version planning.
8. New user requirements must be classified as:
   - current-version fix
   - next-version feature
   - replanning requirement

## Vn Required Sections

Each Vn.md must contain:

- Version Goal
- Player Experience
- Core Gameplay Loop
- Included Features
- Excluded Features
- Game Flow
- Controls
- Completion Condition
- Save/Load
- Required Assets
- Technical Requirements
- Acceptance Criteria
- Playtest Guide

## Playtest Guide

Every Vn must define:

- Playtest URL placeholder
- Features to test
- How to start
- How to operate
- Experience steps
- Completion/clear condition
- Expected playtime
- Main validation goal

## Acceptance Criteria

The planner passes only if:

- 1 to 3 versions are generated.
- Every version is independently playable.
- Every version has a complete gameplay loop.
- V1 proves the game's core loop.
- No version is merely a technical module.
```

---

# 3. game-code-generator/SKILL.md

```markdown
# game-code-generator

## Purpose

Implement the current playable game version from its version specification.

## Input

- Vn.md
- GAME_ARCHITECTURE.md
- assets.json
- assets/

## Output

- Game source code
- Tests
- Build
- Playable deployment

## Development Process

1. Read Vn.md.
2. Read GAME_ARCHITECTURE.md.
3. Read required assets.
4. Create implementation plan.
5. Break implementation into testable tasks.
6. Implement core game rules.
7. Implement game systems.
8. Implement Phaser scenes.
9. Implement UI.
10. Integrate assets.
11. Implement save/load.
12. Write tests.
13. Run tests.
14. Build.
15. Run smoke test.
16. Deploy.
17. Generate playtest information.

## Planning

Before coding, generate an implementation plan covering:

- Data model
- Game state
- Core rules
- Systems
- Scenes
- Input
- UI
- Assets
- Save/load
- Tests

## TDD

Prioritize tests for:

- Game state
- Core rules
- Resource changes
- Progression
- Win/lose conditions
- Save/load
- Important system interactions

Visual presentation does not require exhaustive unit tests.

## Implementation Priority

1. Data
2. Game state
3. Core rules
4. Core systems
5. Phaser scenes
6. Player interaction
7. UI
8. Assets
9. Save/load
10. Audio
11. Polish

## Version Completion Criteria

A version is complete only when:

- Required features implemented
- Tests pass
- Build passes
- Game launches
- Player can interact
- Core gameplay loop works
- Completion condition works
- Save/load works
- Smoke test passes
- Deployment succeeds
- Playtest URL exists

## Playtest Output

After deployment, provide:

### Playtest URL

The real deployed game URL.

### What To Test

List the exact features implemented in this version.

### How To Play

Provide controls and interaction instructions.

### How To Clear

Provide exact steps required to complete the version.

### Expected Playtime

Provide an approximate duration.

### What We Need Feedback On

Identify the main questions the user should validate.

## User Feedback

After the user plays the version:

PASS:
- Proceed to the next version.

FIX:
- Fix the current version.
- Rebuild.
- Redeploy.
- Request another playtest.

CHANGE:
- Re-evaluate version planning.
- Decide whether the request belongs to the current version or a later version.

## Hard Constraints

- Never automatically skip user playtesting.
- Never automatically start V2 immediately after V1 deployment.
- Never mark a version complete before a playable build exists.
- Never claim a playable URL without a successful deployment.
- Never move known V1 core-loop bugs into V2.
- Maximum version count is 3.
```

---

# 4. 三个 Skill 的最终关系

```text
game-architecture
        │
        ▼
GAME_ARCHITECTURE.md
        │
        ▼
game-version-planner
        │
        ├──── V1.md
        ├──── V2.md
        └──── V3.md
                 │
                 ▼
        game-code-generator
                 │
                 ▼
          Playable Game
                 │
                 ▼
            Playtest
                 │
          ┌──────┼──────┐
          ▼      ▼      ▼
         PASS    FIX   CHANGE
          │      │      │
          │      ▼      ▼
          │    Current  Replan
          │    Version
          │
          ▼
      Next Version
```

# 5. 最核心的约束

整个 Phase 3 应该始终遵守：

> **不要把“开发任务”当成“版本”。**

版本是用户看到的产品。

所以：

```text
地图系统
战斗系统
背包系统
NPC系统
```

这些都是：

```text
Feature / Implementation Task
```

而：

```text
V1
V2
V3
```

必须是：

```text
Playable Product
```

最终 Phase 3 的成功标准不是：

```text
AI 写了很多代码
```

而是：

```text
GDD
 ↓
V1
 ↓
真实部署
 ↓
用户打开链接
 ↓
用户知道怎么玩
 ↓
用户完成核心闭环
 ↓
用户成功通关
 ↓
用户保存
 ↓
用户反馈
 ↓
修复 / V2
```

这才是真正的 **AI_COWORK_GAME MVP 闭环**。