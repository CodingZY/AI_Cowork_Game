# Phase 2 Skill 说明

## 1. game-art-style

### 定位

负责：

```text
GDD → ART_STYLE.md
```

它回答：

> “这个游戏应该长什么样？”

### 输入

```text
GDD.md
```

### 输出

```text
ART_STYLE.md
```

### 负责内容

```text
整体风格
色彩
角色比例
建筑风格
植物风格
动物风格
道具风格
镜头
透视
光照
材质
UI
Icon
```

### 不负责

```text
不生成图片
不调用 Hunyuan-DiT
不生成最终 Asset
不修改 GDD
```

### 核心规则

1. GDD 已明确的视觉要求优先。
2. GDD 没有明确的部分允许合理推断。
3. 推断内容必须标记为 inferred。
4. 生成 Style Anchor。
5. Style Anchor 必须能够被后续所有 Asset Prompt 复用。

### 推荐 SKILL.md

```markdown
# game-art-style

## Purpose

Convert the game GDD into a unified visual art style specification.

## Input

- GDD.md

## Output

- ART_STYLE.md

## Responsibilities

- Extract visual requirements from GDD.
- Define overall visual style.
- Define color palette.
- Define character proportions.
- Define camera and perspective.
- Define lighting.
- Define materials.
- Define UI and icon style.
- Generate a reusable STYLE_ANCHOR.

## Rules

- Never invent game entities.
- GDD requirements have highest priority.
- Inferred visual decisions must be explicitly marked.
- All downstream assets must reference STYLE_ANCHOR.

## Acceptance Criteria

- ART_STYLE.md exists.
- Style is internally consistent.
- STYLE_ANCHOR exists.
- All major visual dimensions are defined.
```

---

# 2. art-asset-spec

### 定位

负责：

```text
GDD
+
ART_STYLE
↓
Asset Specification
```

它回答：

> “游戏需要哪些美术资产？”

### 输入

```text
GDD.md
ART_STYLE.md
```

### 输出

```text
art-assets.md
assets.json
```

### 核心任务

第一步：

```text
Extract Visual Entities
```

第二步：

```text
Assign Asset IDs
```

第三步：

```text
Generate Asset Specifications
```

### Asset Category

```text
character
npc
building
animal
plant
prop
map
ui
icon
```

### 核心规则

每个实体必须有：

```text
asset_id
name
category
source
required
visual specification
generation specification
post-process specification
output path
```

### 推荐 SKILL.md

```markdown
# art-asset-spec

## Purpose

Convert visual entities defined in the GDD into executable asset specifications.

## Input

- GDD.md
- ART_STYLE.md

## Output

- art-assets.md
- assets.json

## Workflow

1. Extract all visual entities from GDD.
2. Assign stable Asset IDs.
3. Classify assets.
4. Generate visual specifications.
5. Generate generation specifications.
6. Generate post-processing specifications.
7. Generate output paths.
8. Validate asset coverage.

## Asset Categories

- character
- npc
- building
- animal
- plant
- prop
- map
- ui
- icon

## Required Fields

- asset_id
- name
- category
- source
- required
- visual
- generation
- post_process
- output
- status

## Rules

- Every required GDD visual entity must have an Asset Spec.
- Do not create assets that do not originate from GDD unless explicitly requested.
- Asset IDs must remain stable.
- All assets must reference the project ART_STYLE.
- assets.json is the machine-readable source of truth.

## Acceptance Criteria

GDD visual entities must be traceable to Asset Specs.
```

---

# 3. art-pipeline

### 定位

负责：

```text
Asset Spec
↓
Prompt
↓
Hunyuan-DiT
↓
rembg
↓
Image Processing
↓
Final Asset
```

它回答：

> “如何把 Asset Spec 变成真正的图片？”

### 输入

```text
assets.json
ART_STYLE.md
```

### 输出

```text
assets/raw/
assets/processed/
assets/final/
prompts/
```

### Pipeline

```text
Load Asset
    ↓
Generate Prompt
    ↓
Generate Negative Prompt
    ↓
Call Hunyuan-DiT
    ↓
Save Raw Image
    ↓
rembg
    ↓
Alpha Validation
    ↓
Crop
    ↓
Padding
    ↓
Resize
    ↓
Format Conversion
    ↓
Technical Validation
    ↓
Save Final Asset
```

### rembg 规则

默认：

```text
character → rembg
npc → rembg
animal → rembg
plant → rembg
prop → rembg
building → 根据 Spec
map → 不抠图
UI → 根据 Spec
icon → 通常抠图
```

最终由：

```text
post_process.remove_background
```

决定，而不是由 Category 强制决定。

### 推荐 SKILL.md

```markdown
# art-pipeline

## Purpose

Generate and process game art assets according to assets.json.

## Input

- assets.json
- ART_STYLE.md

## Output

- prompts/
- assets/raw/
- assets/processed/
- assets/final/

## Generation Backend

Hunyuan-DiT deployed on AutoDL.

## Workflow

1. Load Asset Specification.
2. Load STYLE_ANCHOR.
3. Generate asset prompt.
4. Generate negative prompt.
5. Submit generation request.
6. Save raw image.
7. Apply rembg when required.
8. Validate alpha channel.
9. Detect content bounding box.
10. Crop image.
11. Add padding.
12. Resize.
13. Convert image format.
14. Validate final asset.
15. Save final asset.

## Rules

- Never modify Asset IDs.
- Never overwrite raw generated assets.
- Raw images must be preserved.
- Final assets must be reproducible from Asset Spec.
- Generation failures must be retryable.
- Processing failures must not delete raw images.
- Use remove_background from post_process configuration.
- Every final asset must pass technical validation.

## Failure Handling

Generation failure:
- Retry with Temporal.
- Preserve failure status.
- Do not mark asset as completed.

Processing failure:
- Preserve raw asset.
- Mark asset as PROCESSING_FAILED.

Validation failure:
- Mark asset as REVIEW or FAILED.

## Acceptance Criteria

Every required Asset Spec has a corresponding final asset or an explicit failure status.
```

---

# 4. art-consistency-check

### 定位

负责：

```text
GDD
+
ART_STYLE
+
assets.json
+
assets/
↓
ART_REPORT.md
```

它回答：

> “这些图片是不是正确、完整、统一？”

### 第一层：Coverage Check

```text
GDD Entity
      ↓
Asset Spec
      ↓
Final Asset
```

检查：

```text
Missing Asset
Orphan Asset
Duplicate Asset
Invalid Asset ID
```

### 第二层：Technical Check

检查：

```text
文件存在
文件格式
图片尺寸
Alpha
透明背景
命名
目录
```

### 第三层：Visual Check

检查：

```text
Style
Color
Proportion
Camera
Lighting
Material
```

### 推荐 SKILL.md

```markdown
# art-consistency-check

## Purpose

Validate completeness, technical correctness, traceability, and visual consistency of generated game assets.

## Input

- GDD.md
- ART_STYLE.md
- assets.json
- assets/

## Output

- ART_REPORT.md

## Validation Layers

### Coverage

- GDD Entity coverage
- Asset Spec coverage
- Final Asset coverage
- Missing assets
- Orphan assets

### Technical

- File existence
- File name
- Asset ID
- Format
- Resolution
- Alpha channel
- Transparency
- Directory

### Visual

- Style consistency
- Color consistency
- Proportion consistency
- Camera consistency
- Lighting consistency
- Material consistency

## Rules

- Required assets must exist.
- Unknown assets must be reported.
- Technical failures are not visual failures.
- Visual failures should generate regeneration suggestions.
- Do not silently modify assets during validation.

## Output

ART_REPORT.md must contain:

- Summary
- Missing Assets
- Orphan Assets
- Technical Errors
- Visual Consistency Issues
- Regeneration Suggestions
- Final Status

## Acceptance Criteria

Phase 2 passes only when all required assets are either:

- PASS
- or explicitly marked REVIEW/FAILED with a reason.
```

---

# 5. 四个 Skill 的依赖关系

```text
game-art-style
       │
       ▼
ART_STYLE.md
       │
       ▼
art-asset-spec
       │
       ├── art-assets.md
       └── assets.json
                │
                ▼
          art-pipeline
                │
                ├── prompts/
                ├── raw/
                ├── processed/
                └── final/
                         │
                         ▼
                art-consistency-check
                         │
                         ▼
                   ART_REPORT.md
```

---

# 6. Skill 与 Temporal 的边界

Skill 不应该自己承担复杂任务编排。

推荐：

```text
Claude Code
    │
    │ 调用 Skill
    ▼
Skill
    │
    │ 生成任务/参数
    ▼
Temporal
    │
    ├── Generate
    ├── Retry
    ├── rembg
    ├── Process
    ├── Validate
    └── Report
```

特别是：

```text
Hunyuan-DiT
```

和：

```text
rembg
```

都应该作为 Temporal Activity，而不是让 LLM 自己管理长时间任务。

---

# 7. Phase 2 最终 Skill 目录

```text
backend/
└── game-skills/
    ├── skills/
    │   ├── game-brainstorm/
    │   ├── game-requirements/
    │   ├── gdd-check/
    │   ├── gdd-generator/
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
    │   └── art-consistency-check/
    │       └── SKILL.md
    │
    └── templates/
        ├── ART_STYLE.md
        ├── art-assets.md
        ├── assets.json
        └── ART_REPORT.md
```

# 8. 最重要的设计结论

Phase 2 不应该理解成：

```text
GDD
 ↓
AI 生图
```

而应该是：

```text
GDD
 ↓
Visual Entity Registry
 ↓
ART_STYLE
 ↓
Asset Specification
 ↓
Prompt
 ↓
Hunyuan-DiT
 ↓
rembg
 ↓
标准化处理
 ↓
Consistency Check
```

其中真正需要长期保存的核心数据是：

```text
Asset ID
```

它把整个系统串起来：

```text
GDD
 ↓
ANIMAL-001
 ↓
Asset Spec
 ↓
Prompt
 ↓
Hunyuan Request
 ↓
Raw Image
 ↓
rembg
 ↓
Final Image
 ↓
Validation
```

这样 Phase 3 无论是做：

```text
Asset → Unity
```

还是：

```text
Asset → Unreal
```

还是：

```text
Asset → 自动场景生成
```

都可以直接复用 `assets.json`，而不用重新解析 GDD。