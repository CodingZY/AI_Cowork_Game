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
