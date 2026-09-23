# Phase 2：GDD → 美术资产

## 1. 阶段目标

Phase 2 的目标是：

> 从 Phase 1 生成的 GDD 自动分析游戏中的可视化实体，建立统一的游戏美术风格和资产规格，并通过 AutoDL 部署的 Hunyuan-DiT 自动生成游戏美术资源，再通过 rembg 和图像处理流水线完成资产标准化，最终输出可直接进入游戏项目的 Assets。

输入：

```text
GDD.md
```

输出：

```text
ART_STYLE.md
art-assets.md
assets.json
assets/
ART_REPORT.md
```

核心链路：

```text
GDD.md
   ↓
Visual Entity Extraction
   ↓
ART_STYLE.md
   ↓
Asset Specification
   ↓
art-assets.md
assets.json
   ↓
Prompt Generation
   ↓
Hunyuan-DiT
   ↓
Raw Images
   ↓
rembg
   ↓
Crop / Resize / Format
   ↓
Asset Validation
   ↓
Consistency Check
   ↓
assets/
```

---

# 2. 与现有项目结构的关系

当前项目：

```text
AI_COWORK_GAME/
│
├── backend/
│   ├── game-skills/
│   │   ├── skills/
│   │   │   ├── game-brainstorm/
│   │   │   ├── game-requirements/
│   │   │   ├── gdd-check/
│   │   │   └── gdd-generator/
│   │   │
│   │   └── templates/
│   │
│   ├── temporal/
│   └── tests/
│
├── doc/
├── frontend/
│
└── workspace/
    ├── games-repo/
    │   └── template/
    └── worktrees/
```

Phase 2 不改变现有 Skill 体系，而是在：

```text
backend/game-skills/skills/
```

增加：

```text
game-art-style/
art-asset-spec/
art-pipeline/
art-consistency-check/
```

最终：

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
    │   ├── art-asset-spec/
    │   ├── art-pipeline/
    │   └── art-consistency-check/
    │
    └── templates/
```

不需要人为添加 Skill 序号。

---

# 3. Phase 2 Skill 职责

四个 Skill 分工：

| Skill | 输入 | 输出 | 职责 |
|---|---|---|---|
| game-art-style | GDD | ART_STYLE.md | 定义统一视觉风格 |
| art-asset-spec | GDD + ART_STYLE | art-assets.md + assets.json | 提取并定义所有美术资产 |
| art-pipeline | assets.json + ART_STYLE | assets/ | Prompt、生图、抠图、处理 |
| art-consistency-check | GDD + ART_STYLE + assets.json + assets | ART_REPORT.md | 完整性和视觉一致性检查 |

职责必须保持单向：

```text
game-art-style
      ↓
art-asset-spec
      ↓
art-pipeline
      ↓
art-consistency-check
```

---

# 4. 核心设计原则

## 4.1 GDD 是唯一业务来源

美术系统不能自己创造游戏实体。

例如 GDD 中存在：

```text
农场主屋
鸡舍
奶牛
鸡
苹果树
锄头
水壶
```

系统应该生成对应 Asset。

不能因为模型认为“农场游戏通常还有马车”，就自动生成：

```text
horse_cart.png
```

如果需要新增资产，应进入：

```text
Asset Change Request
```

而不是直接生成。

---

# 5. Visual Entity Registry

Phase 2 首先从 GDD 中提取：

```text
Visual Entity
```

例如：

```text
GDD
│
├── Character
│   └── Player
│
├── NPC
│   ├── Alice
│   └── Bob
│
├── Building
│   ├── Farmhouse
│   └── Chicken Coop
│
├── Animal
│   ├── Cow
│   └── Chicken
│
├── Plant
│   └── Apple Tree
│
└── Prop
    ├── Hoe
    └── Watering Can
```

每个实体分配唯一：

```text
asset_id
```

例如：

```text
CHAR-001
NPC-001
NPC-002
BUILD-001
BUILD-002
ANIMAL-001
ANIMAL-002
PLANT-001
PROP-001
PROP-002
```

Asset ID 是整个 Phase 2 的核心主键。

---

# 6. Asset Traceability

必须建立：

```text
GDD Entity
     ↓
Asset ID
     ↓
Asset Spec
     ↓
Prompt
     ↓
Generation Request
     ↓
Raw Asset
     ↓
Processed Asset
```

例如：

```text
GDD:
animal.cow

↓

Asset:
ANIMAL-001

↓

Spec:
assets.json → ANIMAL-001

↓

Prompt:
prompts/animals/ANIMAL-001.txt

↓

Raw:
assets/raw/animals/ANIMAL-001.png

↓

Processed:
assets/animals/ANIMAL-001.png
```

最终可以反向追踪：

```text
ANIMAL-001.png
```

来自哪个 GDD 实体。

---

# 7. ART_STYLE

`game-art-style` 负责生成：

```text
ART_STYLE.md
```

内容包括：

```text
整体视觉风格
色彩体系
角色比例
建筑风格
植物风格
动物风格
道具风格
地图风格
镜头
透视
光照
材质
UI
Icon
背景
```

例如：

```yaml
style_id: STYLE-001

visual_style:
  type: stylized
  mood: warm
  detail_level: medium

camera:
  type: orthographic
  angle: 3/4

lighting:
  type: soft_daylight

material:
  type: stylized_matte

color:
  saturation: medium_high

character:
  proportion: chibi
```

---

# 8. Style Anchor

ART_STYLE 生成之后，必须抽取：

```text
STYLE_ANCHOR
```

它是所有 Prompt 的公共前缀。

例如：

```text
[STYLE_ANCHOR]

Cute stylized farming game.
Soft 3D appearance.
Warm pastel color palette.
3/4 orthographic view.
Soft daylight.
Stylized matte material.
Simple clean shapes.
Friendly proportions.
Consistent game asset presentation.
```

之后：

```text
Cow Prompt
=
STYLE_ANCHOR
+
Cow Asset Description
```

而不是每个 Asset 自己重新描述风格。

这样可以减少：

```text
角色一个风格
建筑一个风格
动物一个风格
```

的问题。

---

# 9. Asset Specification

`art-asset-spec` 将 GDD 中所有可视化实体转换成：

```text
art-assets.md
assets.json
```

其中：

```text
art-assets.md
```

用于人阅读。

```text
assets.json
```

用于程序和 Temporal。

推荐结构：

```json
{
  "asset_id": "ANIMAL-001",
  "name": "cow",
  "category": "animal",
  "required": true,

  "source": {
    "gdd_entity": "animal.cow"
  },

  "visual": {
    "description": "friendly farm cow",
    "view": "3/4",
    "pose": "standing",
    "proportion": "stylized"
  },

  "generation": {
    "model": "Hunyuan-DiT",
    "width": 1024,
    "height": 1024,
    "steps": 30,
    "cfg": 7.5,
    "seed": null
  },

  "post_process": {
    "remove_background": true,
    "crop": true,
    "resize": true,
    "format": "png"
  },

  "output": {
    "raw": "assets/raw/animals/ANIMAL-001.png",
    "final": "assets/animals/ANIMAL-001.png"
  },

  "status": "pending"
}
```

---

# 10. Art Pipeline

`art-pipeline` 是真正执行资产生成的 Skill。

流程：

```text
Asset Spec
     ↓
Prompt Generator
     ↓
Hunyuan-DiT
     ↓
Raw Image
     ↓
rembg
     ↓
Alpha Validation
     ↓
Auto Crop
     ↓
Padding
     ↓
Resize
     ↓
PNG
     ↓
Technical Validation
```

---

# 11. Hunyuan-DiT

Hunyuan-DiT 部署在：

```text
AutoDL
```

项目后端不要直接依赖 Hunyuan-DiT 内部实现。

建议封装统一的 Image Generation API：

```text
POST /v1/images/generate
```

请求：

```json
{
  "asset_id": "ANIMAL-001",
  "prompt": "...",
  "negative_prompt": "...",
  "width": 1024,
  "height": 1024,
  "steps": 30,
  "cfg": 7.5,
  "seed": 123456
}
```

返回：

```json
{
  "asset_id": "ANIMAL-001",
  "status": "success",
  "image_path": "...",
  "seed": 123456,
  "model": "Hunyuan-DiT"
}
```

以后即使更换：

```text
Hunyuan-DiT
↓
SDXL
↓
Flux
↓
其他模型
```

也不需要修改 Art Pipeline 的上层逻辑。

---

# 12. rembg 后处理

生成图片之后，不直接进入最终 Assets。

目录：

```text
assets/
├── raw/
└── processed/
```

流程：

```text
Hunyuan-DiT
      ↓
raw/ANIMAL-001.png
      ↓
rembg
      ↓
透明背景
      ↓
自动检测 Alpha
      ↓
计算 Bounding Box
      ↓
自动 Crop
      ↓
Padding
      ↓
Resize
      ↓
processed/ANIMAL-001.png
```

`rembg` 是标准后处理步骤。

如果 Asset Spec：

```json
{
  "remove_background": true
}
```

则执行：

```text
rembg
```

如果是：

```text
地图
UI 背景
完整场景
```

则可以：

```json
{
  "remove_background": false
}
```

---

# 13. Assets 目录

建议最终：

```text
assets/
├── raw/
│   ├── characters/
│   ├── npcs/
│   ├── buildings/
│   ├── animals/
│   ├── plants/
│   └── props/
│
├── processed/
│   ├── characters/
│   ├── npcs/
│   ├── buildings/
│   ├── animals/
│   ├── plants/
│   └── props/
│
└── final/
    ├── characters/
    ├── npcs/
    ├── buildings/
    ├── animals/
    ├── plants/
    ├── props/
    ├── maps/
    ├── ui/
    └── icons/
```

这样：

```text
raw
```

保存原始生成结果。

```text
processed
```

保存 rembg + crop + resize 后结果。

```text
final
```

作为游戏实际使用的资源。

---

# 14. Prompt 设计

Prompt 不直接写死在 Skill 中。

应该：

```text
ART_STYLE
+
Asset Spec
+
Style Anchor
+
Category Template
+
Negative Prompt
```

生成：

```text
Asset Prompt
```

例如：

```text
STYLE_ANCHOR

+

CATEGORY_TEMPLATE_ANIMAL

+

ANIMAL_SPEC_COW
```

最终：

```text
prompts/
├── characters/
├── npcs/
├── animals/
├── buildings/
├── plants/
└── props/
```

每一个 Prompt 都和 Asset ID 对应。

---

# 15. Temporal Workflow

Temporal 负责整个 Phase 2 的执行。

Workflow：

```text
ArtPipelineWorkflow
```

流程：

```text
Load GDD
   ↓
Generate Art Style
   ↓
Extract Visual Entities
   ↓
Generate Asset Specs
   ↓
Validate Asset Specs
   ↓
Generate Prompts
   ↓
Generate Assets
   ↓
rembg
   ↓
Crop / Resize
   ↓
Technical Validation
   ↓
Consistency Check
   ↓
Generate ART_REPORT
```

其中生图阶段可以并行：

```text
                  Generate Assets
                        │
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
 Characters         Buildings         Animals
       ↓                ↓                ↓
     rembg            rembg             rembg
       ↓                ↓                ↓
    Validate         Validate          Validate
```

---

# 16. 重试机制

Hunyuan-DiT 是外部服务，因此必须支持：

```text
timeout
retry
backoff
failure
```

例如：

```text
第一次失败
    ↓
等待
    ↓
第二次
    ↓
等待
    ↓
第三次
    ↓
失败
    ↓
标记 GENERATION_FAILED
```

不能因为一个 Asset 失败导致整个 Phase 2 Workflow 失败。

---

# 17. 生成状态

每个 Asset 都维护：

```text
PENDING
GENERATING
GENERATED
PROCESSING
PROCESSED
VALIDATING
PASSED
REVIEW
FAILED
```

例如：

```json
{
  "asset_id": "ANIMAL-001",
  "status": "PROCESSED"
}
```

这样 Temporal 可以做到断点恢复。

---

# 18. 一致性检查

`art-consistency-check` 分为两层。

## Technical Check

检查：

```text
文件存在
文件名
Asset ID
格式
尺寸
Alpha
透明背景
目录
```

例如：

```text
ANIMAL-001.png
```

必须：

```text
存在
PNG
RGBA
尺寸符合规格
透明背景符合要求
```

---

## Visual Check

检查：

```text
Style
Color
Proportion
Camera
Lighting
Material
```

例如：

```text
Style        92
Color        89
Proportion   91
Camera       95
Lighting     88
Material     90
```

最终：

```text
Consistency Score
```

---

# 19. GDD / Spec / Asset 三方一致性

这是 Phase 2 最重要的验收。

系统建立三个集合：

```text
GDD_ENTITIES
SPEC_ASSETS
ACTUAL_ASSETS
```

然后计算：

```text
GDD_ENTITIES ∩ SPEC_ASSETS ∩ ACTUAL_ASSETS
```

必须保证 Required Asset 全部存在。

例如：

```text
GDD:
cow
chicken
apple_tree

Spec:
cow
chicken
apple_tree

Assets:
cow.png
chicken.png
apple_tree.png
```

PASS。

如果：

```text
GDD:
cow
chicken
apple_tree

Spec:
cow
chicken

Assets:
cow.png
chicken.png
```

FAIL：

```text
Missing Asset:
apple_tree
```

如果：

```text
Assets:
horse.png
```

但 GDD 没有：

```text
horse
```

则：

```text
Orphan Asset:
horse
```

---

# 20. ART_REPORT.md

最终生成：

```text
ART_REPORT.md
```

内容：

```text
# Art Generation Report

## Summary

Total Assets: 20
Generated: 20
Processed: 20
Passed: 18
Review: 1
Failed: 1

## Missing Assets

...

## Orphan Assets

...

## Technical Errors

...

## Consistency Issues

...

## Regeneration Suggestions

...
```

---

# 21. Phase 2 最终验收

必须满足：

### 文件

```text
[PASS] ART_STYLE.md
[PASS] art-assets.md
[PASS] assets.json
[PASS] assets/
[PASS] ART_REPORT.md
```

### Asset Coverage

```text
GDD Visual Entity
=
Asset Spec Entity
=
Generated Asset
```

### Pipeline

```text
[PASS] Prompt generation
[PASS] Hunyuan-DiT generation
[PASS] rembg
[PASS] crop
[PASS] resize
[PASS] format conversion
```

### Consistency

```text
[PASS] Style
[PASS] Color
[PASS] Proportion
[PASS] Camera
[PASS] Lighting
[PASS] Material
```

### Traceability

任何：

```text
assets/animals/ANIMAL-001.png
```

都可以追溯：

```text
Asset
 ↓
Asset Spec
 ↓
Prompt
 ↓
GDD Entity
```

---

# 22. Phase 2 与 Phase 1 的接口

Phase 1 最终输出：

```text
GDD.md
```

Phase 2：

```text
GDD.md
 ↓
ART_STYLE.md
 ↓
art-assets.md
 ↓
assets.json
 ↓
assets/
```

因此 Phase 1 不需要知道：

```text
Hunyuan-DiT
rembg
Temporal
```

Phase 2 负责把：

```text
游戏设计
```

转换成：

```text
可执行的美术资产生产任务。
```

---

# 23. 为 Phase 3 预留接口

Phase 2 的 `assets.json` 不仅服务 Phase 2。

未来 Phase 3 可以直接：

```text
assets.json
+
GDD
+
Map Specification
        ↓
Scene Generation
        ↓
Unity / Unreal
```

因此现在一定要保留：

```text
asset_id
category
source
transform
size
output
```

这些字段。

---

# 24. 最终架构

```text
                 Phase 1
              Requirements
                    ↓
                  GDD.md
                    │
                    ▼
        ┌─────────────────────┐
        │   game-art-style    │
        └──────────┬──────────┘
                   ↓
             ART_STYLE.md
                   │
                   ▼
        ┌─────────────────────┐
        │   art-asset-spec    │
        └──────────┬──────────┘
                   ↓
          art-assets.md
          assets.json
                   │
                   ▼
        ┌─────────────────────┐
        │    art-pipeline     │
        └──────────┬──────────┘
                   │
              Temporal
                   │
                   ▼
             Hunyuan-DiT
              AutoDL API
                   │
                   ▼
                raw/
                   │
                 rembg
                   │
                   ▼
              processed/
                   │
            Crop / Resize
                   │
                   ▼
                final/
                   │
                   ▼
        ┌─────────────────────┐
        │ art-consistency-    │
        │       check         │
        └──────────┬──────────┘
                   ↓
            ART_REPORT.md
                   │
                   ▼
                Phase 3
