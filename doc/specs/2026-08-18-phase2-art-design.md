# 阶段2 GDD→美术资产 设计规格书

- **版本**：v0.1
- **日期**：2026-08-18
- **阶段**：Phase 2（GDD → 美术资产）
- **定位**：接续 Phase 1 的 GDD.md，自动提取可视化实体、定义美术风格、生成资产规格、调 AutoDL Hunyuan-DiT 生图、rembg 标准化、一致性检查，输出 `assets/` + `ART_REPORT.md`，供 Phase 3 复用 `assets.json`。
- **依据**：《Phase 2：GDD→美术资产》《Phase 2 Skill 说明与 SKILL.md 设计》两份文档。

---

## 1. 目标与验收

```
GDD.md（Phase 1 COMPLETED）
  → game-art-style      → ART_STYLE.md（含 [STYLE_ANCHOR]）
  → art-asset-spec      → art-assets.md + assets.json（SSOT，9 类别 + asset_id）
  → art-pipeline        → prompts/{cat}/{id}.txt + .neg.txt
  → generate_image      → assets/raw/{cat}/{id}.png（AutoDL / 占位图）
  → post_process_asset  → assets/processed + assets/final（rembg + crop + resize）
  → validate_asset      → 技术校验（Alpha/尺寸/格式）
  → run_consistency_check → ART_REPORT.md（Coverage/Technical/Visual 三层）
  → ART_REVIEW（人工 approve）→ COMPLETED
```

### 验收（Definition of Done）
- ART_STYLE.md / art-assets.md / assets.json / assets/ / ART_REPORT.md 产出。
- GDD 可视实体 ∩ Asset Spec ∩ 生成资产 可追溯（asset_id 串全链）。
- 生图并行 + 单资产失败不阻塞整体 + 断点恢复（worker 重启跳过 PASSED）。
- AutoDL API 未配置时返占位图，全链路端到端跑通；配 API 后只改 `ImageGenClient` 一处。

---

## 2. 奠基决策

| # | 决策点 | 选定 | 影响 |
|---|---|---|---|
| D1 | Skill/Activity 边界 | LLM 只做产出 markdown/json/prompt 文本；**生图 + rembg 是 Temporal Activity** | art-pipeline SKILL 严格划界（只生 prompt 文本，不生图不 rembg）；Hunyuan-DiT/rembg 由 Activity 执行 |
| D2 | 复用 Phase 1 worktree | 同一 `worktrees/{key}-brainstorm`，cwd=`games/{key}` | ART_STYLE/assets.json/assets 与 GDD.md 并存；`_ensure_worktree` 原样复用；Phase 2 在 Phase 1 COMPLETED 后起 |
| D3 | AutoDL 未给 | 占位图策略 | ImageGenClient 未配置返按 category 上色+水印白底 PNG，rembg 有东西可抠；给 API 改一处 |
| D4 | DB | 不新建表 | SSOT=assets.json（磁盘）+ Query（workflow 内存 asset_status）；对齐 Phase 1 |
| D5 | 并行/重试/断点 | asyncio.gather + _in_flight 信号量 + RetryPolicy + activity 幂等 | 生图并行限流；瞬时失败自动重试 3 次；业务失败记 FAILED 不阻塞；worker 重启 replay 跳过 PASSED |
| D6 | task_queue | 与 Phase 1 共用 `game-design` | 两 workflow 共 worker；后续可加 `temporal_art_task_queue` 隔离 CV 重活动（预留） |
| D7 | rembg 模型 | 本地 `.rembg_models/u2net.onnx` | 避免默认下 C 盘 `~/.u2net`（C 盘约束） |
| D8 | 人工 gate | ART_REVIEW + approve_report signal | 对齐 Phase 1 GDD_REVIEW/save_gdd |

---

## 3. 四个 Skill（`backend/game-skills/skills/{name}/SKILL.md`，无前缀精简格式）

| Skill | 输入 | 输出 | Activity |
|---|---|---|---|
| game-art-style | GDD.md | ART_STYLE.md + [STYLE_ANCHOR] | generate_art_style（spawn claude） |
| art-asset-spec | GDD+ART_STYLE | art-assets.md + assets.json | generate_asset_spec（spawn） |
| art-pipeline | assets.json+ART_STYLE | prompts/{cat}/{id}.txt + .neg.txt | generate_prompts（spawn + 纯 Python 模板兜底） |
| art-consistency-check | 全部 | ART_REPORT.md | run_consistency_check（spawn） |

assets.json schema（每资产）：`{asset_id, name, category(9类), required, source{gdd_entity}, visual{description,view,pose,proportion}, generation{model,width,height,steps,cfg,seed}, post_process{remove_background,crop,resize,format}, output{raw,final}, status}`。asset_id 规则 `{CATEGORY前缀}-001`。

---

## 4. ArtPipelineWorkflow（`backend/temporal/workflows.py`）

phase 状态机：`CREATED → GENERATING_ART_STYLE → GENERATING_ASSET_SPEC → VALIDATING_SPECS → GENERATING_PROMPTS → GENERATING_ASSETS(并行) → [RETRYING_ASSETS] → CONSISTENCY_CHECK → ART_REVIEW → COMPLETED/FAILED`。

- `run(max_parallel)`：顺序 execute_activity 跑前 4 步 → `_process_all_assets` → retry → consistency → ART_REVIEW 暂停 → COMPLETED。
- `_process_one_asset`：`wait_condition(_in_flight<max_parallel)` 限流 → 跳过 PASSED → generate_image(RetryPolicy 3 次)→post_process→validate，try/except 记 FAILED 不 re-raise，finally `_in_flight-=1`。
- signal：`approve_report`、`retry_asset(RetryAssetSignal)`。
- query `get_art_state`：phase/progress(total,passed,failed,processing,pending)/assets[{asset_id,name,category,status}]/spec_check/art_report。

---

## 5. Activities（`backend/temporal/activities.py` +8）

spawn-skill（4）：`generate_art_style`/`generate_asset_spec`/`generate_prompts`(含 `_fallback_template_prompts`)/`run_consistency_check`，复用 `_ensure_worktree`/`_spawn_skill`/`_parse_json`/`_load_assets_json`/`_find_asset`。

纯 Python/外部（4）：`validate_asset_specs`(asset_id 唯一/9 类别/必填字段)、`generate_image`(幂等，raw 存在则跳过)、`post_process_asset`(调 `image_pipeline.run_image_pipeline`)、`validate_asset`(final 存在/PNG/尺寸/Alpha/remove_background→透明)。

---

## 6. ImageGenClient + image_pipeline（`backend/app/ai/`）

- `image_client.ImageGenClient`：`enabled=bool(base_url and api_key)`。未配→`_placeholder`(PIL 按 category 上色+asset_id 水印白底 PNG)；已配→httpx POST `{base_url}/v1/images/generate`，支持 image_b64/url/local_path 返回。换 API 改一处。
- `image_pipeline.run_image_pipeline`：rembg(本地 u2net.onnx，按 `remove_background`)→alpha bbox autocrop→pad to square→resize→PNG，写 processed+final。`_category_dir` 复数化目录。

---

## 7. API（`backend/app/api/art.py`，main.py include）

`POST /projects/{pid}/art/pipeline`(校验 project+GDD.md 存在→start_art_workflow)、`GET /art/state`(Query)、`POST /art/approve`、`POST /art/retry/{asset_id}`、`GET /art/assets`(读磁盘 assets.json)、`GET /art/report`(读磁盘 ART_REPORT.md)。

---

## 8. 配置（`backend/.env` + `app/config/settings.py`）

`AUTODL_BASE_URL=`、`AUTODL_API_KEY=`（空→占位图）、`ART_ASSETS_PARALLEL=4`。Settings 同名字段带默认值。

---

## 9. 测试

`test_art_workflow.py`(mock activity+WorkflowEnvironment+approve，单资产 FAILED 不阻塞)、`test_art_activities.py`(monkeypatch `_spawn_stream`+`_project_id_from_workflow`+image_pipeline)、`test_image_client.py`(占位图+mock httpx base64)、`test_api_art.py`(mock start/query)、`test_skills.py`(+4 断言)。全 132 测试通过。

---

## 10. 前端存档列表小修

`store/useGameStore.ts`：初始 `games:[]`/`currentGameId:null`，`loadGames` 调 `api.listProjects()`→`mapProjectToGame`（`mapStatusToStage` 把 ProjectRead.status 映射 EngineStage）。App.tsx 挂载 `useEffect` 触发一次。已存档/切换器显示真实项目（含守灯人）。

---

## 11. 风险与权衡

1. art-pipeline skill 边界靠 LLM 生 prompt（保质量），多一次 spawn，模板兜底缓解。
2. 无新 DB 表：assets.json+Query 即 SSOT，Phase 3 需 SQL 聚合再加表。
3. 同 task_queue：CV 重活动与 LLM spawn 共 worker，后续可隔离。
4. 占位图 rembg 质量：链路跑通是目的，视觉质量待真 API。
5. worktree 复用：API 校验 GDD.md 存在+status=COMPLETED 防 Phase 1 未完成就起 Phase 2。
