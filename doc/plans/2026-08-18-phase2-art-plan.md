# 阶段2 GDD→美术资产 实施计划

**Goal:** Phase 2 后端全链路骨架——4 Skill + ArtPipelineWorkflow + Activities + ImageGenClient(占位图) + rembg pipeline + API + 测试 + doc，顺带修前端存档列表。AutoDL API 未给用占位图策略。

**Spec:** `doc/specs/2026-08-18-phase2-art-design.md`

**状态：✅ 全部完成**（132 后端测试通过，前端 typecheck src 零错误）。下文为任务拆解记录。

## Global Constraints
- Python `D:/Anaconda3/envs/agent_env/python.exe`（C 盘约束）。
- 复用 Phase 1 模式：`_ensure_worktree`/`_spawn_skill`/磁盘产物/phase 状态机/Query 轮询。
- AutoDL 未配置→占位图；rembg 用本地 `.rembg_models/u2net.onnx`（不碰 C 盘）。
- 不新建 DB 表（assets.json 当 SSOT）。

## 任务拆解

- [x] **T1 4 个 SKILL.md**：game-art-style/art-asset-spec/art-pipeline(划界)/art-consistency-check。
- [x] **T2 .env + Settings**：AUTODL_BASE_URL/API_KEY(空)/ART_ASSETS_PARALLEL + Settings 字段。
- [x] **T3 app/ai**：image_client.ImageGenClient(占位图+真API)+image_pipeline.run_image_pipeline(rembg/crop/resize)。
- [x] **T4 prompts.py +4**：ART_STYLE/ASSET_SPEC/ART_PIPELINE(边界词)/CONSISTENCY_CHECK prompt。
- [x] **T5 activities.py +8**：4 spawn-skill + validate_asset_specs/generate_image/post_process_asset/validate_asset。
- [x] **T6 workflows.py +ArtPipelineWorkflow**：并行+断点恢复+approve/retry signal+get_art_state query。
- [x] **T7 client.py +3 + worker.py**：start_art_workflow/send_art_signal/query_art_state + 注册。
- [x] **T8 api/art.py + main.py**：6 端点 + include。
- [x] **T9 测试**：test_art_workflow/art_activities/image_client/api_art + test_skills +4。
- [x] **T10 前端 loadGames**：store mapProjectToGame/mapStatusToStage + App.tsx useEffect。
- [x] **T11 doc**：spec + 本 plan。

## 端到端验证（手动，需重启 worker+API）
1. 用 Phase 1 已 COMPLETED 的守灯人 → `POST /api/projects/8/art/pipeline` → 轮询 `GET /art/state` 走完 phase → assets/ 有占位图（rembg 抠 alpha）→ ART_REPORT.md → ART_REVIEW → `POST /art/approve` → COMPLETED。
2. 断点恢复：处理中途停 worker 再启 → 跳过 PASSED 继续。
3. 单资产失败不阻塞：某 validate FAILED → 该资产 FAILED，其余 PASSED，workflow 不崩。
4. 存档列表：前端打开 → 已存档显示守灯人。

## 后续（下轮）
- 前端 3-assets UI 接真后端（Query 轮询 /art/state + 资产卡片显真状态 + approve 按钮）。
- AutoDL API 给后填 .env，测真生图。
- 隔离 art task_queue（CV 重活动独立 worker）。
