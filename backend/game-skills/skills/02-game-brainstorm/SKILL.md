---
name: game-brainstorm
description: Use when a user provides a new game idea and the idea is not yet clear enough to begin a small or medium Phaser.js 2D web game. Optimize for fast convergence and early playable implementation rather than exhaustive game-design interviews.

---

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

- 不同答案会导致完全不同的游戏玩法
- 不同答案会导致不同的技术架构
- 不同答案会改变 V1 范围
- 不同答案会导致用户体验明显不同
- Agent 无法合理推断

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

- 打败最终 Boss
- 建设农场
- 解锁地图
- 完成一天一天的经营
- 找到所有宝藏

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

- 实时战斗还是回合制？
- 横版还是俯视角？
- 单角色还是多角色？
- 是否需要 NPC？
- 是否需要关卡？
- 是否需要随机生成？

---

# 6. Do Not Over-Design

不要主动设计：

- 复杂经济系统
- 完整世界观
- 大量 NPC
- 完整任务树
- 完整数值体系
- 100 个道具
- 完整剧情
- 完整音频设计

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

- 小型农场
- Roguelike Demo
- 简单平台跳跃
- 解谜游戏

### Medium

多个系统组合。

例如：

- 农场 + NPC + 商店
- RPG + 战斗 + 装备
- Tower Defense + 技能 + 升级

### Large

明显超出当前快速开发范围：

- 大型开放世界
- 大量内容
- 多人联机
- 复杂服务器
- 大型剧情 RPG

如果是 Large：

不要继续无限澄清。

应该：

`Scope Down → Define V1`

---

# 10. Phaser Feasibility

只有发现明显问题时才介入技术讨论。

重点检查：

- 2D 是否足够
- Phaser Scene 是否能表达
- Sprite / Tilemap 是否足够
- 浏览器输入是否足够
- LocalStorage 是否足够
- 是否需要服务器

不要因为技术细节打断正常游戏设计。

---

# 11. Fast Path

如果用户已经提供了：

- 游戏类型
- 核心玩法
- 基本视角
- V1 大致范围

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

- Core Loop 明确
- Player Goal 明确
- V1 范围明确
- 关键玩法没有重大歧义
- Phaser.js 2D 可实现
- 用户没有明显反对当前方案

然后：

`→ gdd-generator`

---

# Anti-Patterns

禁止：

- 连续提出十几个问题
- 为了完整而完整
- 用户没有要求却设计大量系统
- 把 GDD 当成百科全书
- 在 Brainstorm 阶段写代码
- 因为细节未知而阻止进入 V1