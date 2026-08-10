# Asset Pipeline（S3）设计规格书

> 本 spec 覆盖 `美术素材.md` 的消费者：Asset Pipeline（S3 阶段）。
>
> 用户在前端确认 `美术素材.md`（S2 闸通过）后，Pipeline 解析清单、批量文生图存 `raw/`，逐张在前端卡片展示，提供【直接保存】/【抠图并保存】/【修改 Prompt 重试】；另有全局【风格转绘】面板（风格参考图 + 结构参考图）。用户显式点【素材完成】过 S3 闸进 S4。
>
> `美术素材.md` 的格式契约由 Art Agent spec（`doc/specs/2026-08-10-art-agent-s2-design.md` §1）拥有；本 spec 引用并定义其解析器。
>
> 本文是 `doc/agent-system-design.md`（总架构）的子项目细化，仅描述 S3。

---

## 0. 设计总览

### 0.1 定位：确定性异步流水线（无 LLM）

**S3 不跑 `claude_agent_sdk.query()`**——它全程无 LLM 推理环节：批量文生图、抠图、存盘、按用户键重试/转绘都是确定性工作。Orchestrator 把它当后台异步任务驱动；逐张覆盖操作是直接 REST 端点。

对照 S2（Art Agent，真 LLM agent，生产清单）：S2 生产清单，S3 消费清单。这是两模块形状不同的关键。

### 0.2 抠图时机：只自动生图，抠图逐张按需

**已确认决策**：用户确认清单后，Pipeline 只批量文生图存 `raw/`，**不自动抠图**。抠图是逐张按需触发——用户在卡片点【抠图并保存】才生成透明 PNG 落 `processed/`；点【直接保存】把原图拷进 `processed/`（供背景类不需要透明的资产）。`raw/` 存所有生成原图，`processed/` 存最终资产。

> 读法：README 流程图标"自动抠图"，但卡片按钮【直接保存】/【抠图并保存】/【重试】暗示按需。按"只自动生图、抠图逐张按需"落地——更省额度、更可控。

### 0.3 与 README/总架构的对齐

- README §Asset Pipeline：`[素材 Prompt] → 文生图 API (Flux/SD) → 生成图预览 → AI 抠图 API (RMBG) → 导出透明 PNG`；另支持 `[待转绘图 + 风格图] → 图生图/风格转绘`。调用**阿里 Token Plan** 兼容端点 + `wan2.7-image-pro`；抠图用 **imgly/rembg**。
- 前端交互：风格转绘面板（上传风格参考图 + 结构参考图）；每张卡片【直接保存】/【抠图并保存】/【修改 Prompt 重试】。
- 总架构 §1 工具表：Asset Pipeline 工具 = `generate_image(wan2.7)`、`style_transfer`、`cutout(腾讯)`、`save_png`，作用域 `Games/<name>/assets/`。本 spec 把抠图从"腾讯云 API"改为**本地 rembg**（README 最新要求 + agent_env 已装 rembg 2.0.69），并把"工具"实现为**Python 模块 + REST 端点**而非 SDK 工具（因 S3 不跑 query，无需 SDK 工具形态）。

### 0.4 已确认的设计决策

1. **形状**：S3 是确定性异步 Python 流水线，**不跑 `query()`**，无 LLM。
2. **抠图**：只批量生图存 `raw/`，抠图逐张按需（卡片【抠图并保存】）。`matting:false`（背景类）用【直接保存】。
3. **风格转绘**：顶部全局面板，批量——一张风格参考图 + 选一组目标资产（各资产自己的 raw 作结构参考，不另传结构参考图）。
4. **S3 完成**：用户显式点【素材完成】即过闸进 S4（允许部分资产未处理；Coder 侧 assets_map 对缺图做占位）。
5. **approve/reject**：按 run 当前 stage 自动判定；不新增持久化表；资产状态靠磁盘（`processed/` 存在性）。
6. **并发**：批量文生图有界并发（默认 3），`asyncio.Semaphore`。
7. **重试**：外部 API 失败指数退避 3 次 → 仍败记 `error` 状态，前端卡片显示 + 可重试。
8. **C 盘约束**：rembg 模型目录指 D 盘（`U2NET_HOME`）；httpx/PIL/onnxruntime 已在 agent_env。
9. **不验证 API 真实能力**（用户指定"按证据设计"）：imagegen 按 OpenAI 兼容同步 `/images/generations` 设计；styletransfer 做适配器（原生 img2img / prompt 降级），实现期第一个任务验证端点真实能力并定型。
10. **输入文件名中立（兼容性）**：S3 读 Art Agent 产出的 `docs/美术素材.md`——这是 Art Agent 自身产物的固定约定（Art Agent 写权限仅限该名），非外部文件名假设，故无兼容问题。S3 不读设计文档（那是 S2 的输入，由 S2 发现），故 S3 不受设计文档命名影响。
11. **类别可扩展（兼容性）**：`AssetSpec.category` 为任意非空字符串（Art Agent spec §1.2 已定为非封闭枚举）。S3 与前端按 category 字符串动态分组/展示，不假设固定四类——含 5+ 类别的清单照常处理。

---

## 1. 输入契约：解析 `美术素材.md`

引用 Art Agent spec §1。本 spec 定义解析器：

### 1.1 parser

`backend/pipeline/parser.py`：
```python
@dataclass
class AssetSpec:
    id: str          # A01..（正则 ^A\d{2,}$，无上限）
    category: str    # 任意非空字符串，非封闭枚举（见决策 11）
    file: str        # slug，无后缀
    prompt: str      # 含背景约束
    width: int
    height: int
    matting: bool

def parse_art_list(md: str) -> list[AssetSpec]:
    """解析 美术素材.md 的所有 ```yaml 块为 AssetSpec 列表。
    先过 validate_art_assets（Art Agent spec §1.4）；不过抛 ValueError(原因+行号)。"""
```

- 按 ` ```yaml ` 块切分；每块 `yaml.safe_load`。
- 字段映射：`size` "WxH" → `width`/`height` int；`matting` → bool；`category` 原样保留（字符串，不校验是否在四类内）。
- 解析前先调 `validate_art_assets(md)`（contract），失败抛带原因的 ValueError（含受影响块序号）。
- 单测：fixture md → 期望 AssetSpec 列表；**含 5+ 类别的 md 须正常解析**；非法 md → ValueError。

### 1.2 命名与产物路径

- 原图：`Games/<slug>/assets/raw/<id>_<file>.png`（带 id 前缀防重名，如 `A01_hero_idle.png`）。
- 最终资产：`Games/<slug>/assets/processed/<file>.png`（无 id 前缀，Coder 的 assets_map 按 `<file>` 引用，如 `hero_idle.png`）。

---

## 2. 流水线子组件

新建 `backend/pipeline/` 包，五个子组件 + 编排器。均为纯/可单测，无 SDK 依赖。

### 2.1 imagegen — 文生图客户端

`backend/pipeline/imagegen.py`：
```python
class ImageGenError(Exception): ...

class ImageGenClient:
    def __init__(self, base_url, api_key, model, concurrency=3): ...
    async def gen(self, prompt: str, size: str) -> bytes:
        """OpenAI 兼容：POST {base}/images/generations，body {model, prompt, n:1, size}，
        响应取 data[0].url（下载）或 data[0].b64_json（解码）→ PNG bytes。
        指数退避重试 3 次（429/5xx/网络）→ 仍败抛 ImageGenError。"""
    async def aclose(self): ...
```

- `httpx.AsyncClient`；`Authorization: Bearer <key>`。
- **size 分隔符**：YAML 中 `size` 存 `WxH`（小写 `x`，如 `1024x1024`，人友好）；`gen` 内部按端点要求转换分隔符——阿里 wan 兼容端点多用 `*`（如 `1024*1024`）。实现期 Task 1 验证端点真实接受的分隔符与格式后定型，默认按 `*` 发送。
- **PNG 规范化**：`gen` 返回 **PNG bytes**。若端点返回 url，下载后用 PIL 读入再 `save` 为 PNG；若返回 b64_json，解码后同样 PIL 规范化。保证 `raw/` 一律 PNG，供 rembg（§2.3）与前端缩略图统一处理。
- 响应两种取法：`data[0].url`（httpx 下载）或 `data[0].b64_json`（base64 解码）——两种都支持，按响应字段自动选择。
- 模型 `wan2.7-image-pro`；端点 `token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。
- **实现期验证（Task 1）**：一次最小付费调用确认端点/模型/size 分隔符/返回是 url 还是 b64。spec 先按上述设计，验证后若端点用异步任务（`task_id` 轮询）则改 `gen` 为轮询模式并更新本节。

### 2.2 styletransfer — 风格转绘适配器

`backend/pipeline/styletransfer.py`：
```python
class StyleTransferClient:
    def __init__(self, base_url, api_key, model): ...
    async def transfer(self, style_ref: bytes, struct_ref: bytes, prompt: str) -> bytes:
        """以 style_ref 为风格、struct_ref 为结构，生成图 → PNG bytes。
        适配器：若端点支持原生 img2img（带参考图），走原生；
        否则降级为 prompt 增补风格描述 + 文生图（结构参考仅作 prompt 提示，不传图）。
        退避重试同 imagegen。"""
```

- **适配器设计**：实现期第一个任务验证端点是否吃参考图：
  - **路径 A（原生 img2img）**：端点支持传图 → body 含 `image`/`image_url`（结构参考）+ `style_image`/`style_url`（风格参考）+ `prompt` → 返回图。
  - **路径 B（prompt 降级）**：端点不吃图 → `prompt = f"以如下风格重绘：{风格描述}。原图主体：{结构描述}。{原prompt}"` + 纯文生图（结构/风格参考图不传，仅靠描述）。
- spec 写清两条路径与切换点；实现期验证后选其一，更新本节标注"已验证路径"。
- `style_ref`（用户上传的风格参考图 bytes）、`struct_ref`（目标资产自己的 raw bytes）。
- 单测：mock 两条路径各一次。

### 2.3 cutout — 本地抠图（rembg）

`backend/pipeline/cutout.py`：
```python
async def cutout(png_bytes: bytes) -> bytes:
    """rembg.remove → 透明 PNG bytes。"""
```

- 用 `rembg.remove(png_bytes)`（同步，包进 `asyncio.to_thread` 避免阻塞事件循环）。输入由 §2.1 的 PNG 规范化保证为 PNG bytes（retry/style-transfer 路径同样经 imagegen/transfer 返回 PNG）。
- **模型落 D 盘**：模块加载时设 `os.environ.setdefault("U2NET_HOME", REMBG_MODELS_DIR)`（从 deps 读，默认 `D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models`）。rembg 首次运行下载 u2net ~176MB 到此目录，**不落 C 盘**。
- 默认模型 `u2net`（通用）；`matting:true` 的角色/物品均适用。
- 纯函数，可单测（fixture 图 → 输出有 alpha 通道）；rembg 装在 agent_env，真跑，快。

### 2.4 storage — 存盘

`backend/pipeline/storage.py`：
```python
def save_raw(game_root: Path, spec: AssetSpec, data: bytes) -> Path:
    """存 assets/raw/<id>_<file>.png，返回路径。"""
def save_processed(game_root: Path, spec: AssetSpec, data: bytes) -> Path:
    """存 assets/processed/<file>.png，返回路径。mkdir parents。"""
def raw_path(game_root: Path, spec: AssetSpec) -> Path: ...
def processed_path(game_root: Path, spec: AssetSpec) -> Path: ...
def has_processed(game_root: Path, spec: AssetSpec) -> bool:
    """processed/<file>.png 是否存在——卡片状态与 S3 完成判定的磁盘事实。"""
```

### 2.5 orchestrator — 批量编排

`backend/pipeline/orchestrator.py`：
```python
async def run_art_pipeline(game_root: Path, specs: list[AssetSpec], *,
    gen_client: ImageGenClient, on_progress) -> dict[str, str]:
    """有界并发批量文生图（Semaphore(concurrency)），每张落 raw/。
    返回 {aid: 'generated'|'error'}。失败记 error，不抛（前端可重试）。
    每张完成经 on_progress 推 {'type':'asset','aid','status','raw_path'}。
    不自动抠图。"""
```

- 信号量并发；每张独立 try/except，失败不中断其他。
- 完成 → `save_raw` + `on_progress`。
- 已生成的资产（raw 存在）可跳过重生成（幂等：`start` 端点重跑时）。

---

## 3. Orchestrator / FSM

`backend/orchestrator/states.py` 已有 `S3_art_gen`。`machine.py` 扩展 S3 转移（与 S2 spec 的 S2 转移一并加）：

| 方法 | 触发 | 返回 Transition |
|---|---|---|
| `start_art_gen(run)` | runtime 启动批量生图 | `(S3_art_gen, running)` |
| `complete_art_gen(run)` | 批量生图完成 | `(S3_art_gen, awaiting_approval)` |
| `approve(run, stage=S3_art_gen)` | 用户点【素材完成】 | `(S4_coding, not_implemented)` |
| `reject(run, stage=S3_art_gen, feedback)` | 兜底重跑批量 | `(S3_art_gen, running)` |

`approve`/`reject` 按 `stage` 分支：S1→S2、S2→S3、S3→S4。守卫同 S2：仅 `awaiting_approval` 时允许。

> S3 的 awaiting_approval 语义：批量生图完成即进闸（`complete_art_gen`）；之后逐张 save/cutout/retry/style-transfer **不**改阶段状态，只在磁盘与卡片状态反映；用户点完成才 `approve(S3)`→S4。无 reject 必要（不满意继续改），保留作兜底。

---

## 4. 持久化与 runtime

### 4.1 不新增表

资产逐张状态不入库——`processed/<file>.png` 存在性即状态，重启可由磁盘重建。`PendingApproval` S3 payload：`{"artifacts_dir": "assets/processed"}`。

### 4.2 Runtime

新增 `start_art_gen(run_id, game_name)`（`backend/api/runtime.py` 扩展），后台任务：
- `game_root = games_root() / _slug(game_name)`
- 读 `docs/美术素材.md` → `parse_art_list`（失败推 error + 不启动）。
- 构造 `ImageGenClient`（deps 读配置）。
- `run_art_pipeline(game_root, specs, gen_client=..., on_progress=broker 推)`。
- 跑完 **原子提交** `update_stage(S3 awaiting_approval) + create_approval(payload={"artifacts_dir":"assets/processed"})`（复用显式事务模式）。
- broker 推 `{"type":"gate","stage":"S3_art_gen","status":"awaiting_approval"}`。
- 异常 → error + raise。强引用持有后台任务（复用 `_background_tasks`）。

### 4.3 S2→S3 衔接

S2 `approve`（S2 spec）返回 `(S3_art_gen, running)`，并在 approve 路由里启动 `start_art_gen` 后台任务。即：用户通过 S2 清单闸 → 自动进 S3 跑批量生图。

---

## 5. REST 路由

`backend/api/routes.py` 扩展。资产状态由磁盘决定，端点直接读写文件。

| 方法 路径 | 行为 |
|---|---|
| `POST /runs/{id}/artifacts/start` | 解析清单 + 批量生图（FSM 自动触发；可手动重跑幂等——已生成的 raw 跳过）。需 run 在 S3 |
| `GET /runs/{id}/artifacts` | 返回每张卡片：`{aid, file, category, matting, raw_url, processed_url?, status}`；`status` 由磁盘推（`generated`=仅 raw 存在、`saved`=processed 存在且未抠图、`cutout`=processed 存在且带 alpha、`error`=生成失败、`pending`=未生成） |
| `GET /runs/{id}/artifacts/{aid}/raw` | 流式返回 `assets/raw/<id>_<file>.png`（带 run_id 鉴权边界，不裸用 StaticFiles）；不存在 404 |
| `GET /runs/{id}/artifacts/{aid}/processed` | 流式返回 `assets/processed/<file>.png`；不存在 404 |
| `POST /runs/{id}/artifacts/{aid}/save` | 【直接保存】：raw 拷到 `processed/<file>.png`；返回 processed_url |
| `POST /runs/{id}/artifacts/{aid}/cutout` | 【抠图并保存】：`cutout(raw)→processed/<file>.png`；返回 processed_url |
| `POST /runs/{id}/artifacts/{aid}/retry` | body `{prompt}`：重生 raw（覆盖）。**并删除该资产旧 processed**（旧 processed 派生自旧 raw，现已过时）→ 卡片回到"已生成未保存"，强制重新 save/cutout。返回 raw_url |
| `POST /runs/{id}/artifacts/style-transfer` | body `{style_ref, target_aids: [...], prompt?}`：对每个目标资产以 `style_ref + 该资产 raw` 调 transfer → 覆盖其 raw，**并删除这些资产旧 processed**（同上，避免过时）。返回各 aid 的 raw_url |
| `POST /runs/{id}/approve` | 按 run 当前 stage：S3→S4（S3 spec 侧） |
| `POST /runs/{id}/reject` | S3→重跑批量（兜底） |

`raw_url`/`processed_url` 即上表的两个 `GET .../raw`、`.../processed` 路径——专用端点带 run_id 鉴权边界，不用 StaticFiles（StaticFiles 难限单 run）。

`aid` 校验：须在当前清单内（`parse_art_list` 比对），否则 404。

`style_ref` 传输：前端上传文件 → multipart 表单；后端读为 bytes 传给 `StyleTransferClient`。`target_aids` 为 JSON 数组。

---

## 6. 前端

### 6.1 ArtifactsBoard（S3）

新增 `frontend/src/stages/ArtifactsBoard.tsx`：
- **卡片网格**：每张卡片 = 缩略图（`raw_url`）+ 状态徽标（待处理/已保存/已抠图/出错）+ 三按钮【直接保存】/【抠图并保存】/【修改 Prompt 重试】。已保存/已抠图卡片显示 processed 缩略图。**按 `category` 字符串动态分组/分区展示**（不硬编码四类——含 5+ 类别时各组各自分区，类别未知也能渲染）。
- **顶部【风格转绘】全局面板**：上传风格参考图 + 多选目标资产（checkbox 列表，按类别分组）+ 可选统一结构参考图（留空则各资产用自己的 raw）+ 可选 prompt 附加 → 调 style-transfer 端点。
- **顶部【素材完成】按钮**：`status==='awaiting_approval'` 时启用 → approve 过闸进 S4。
- **进度流**：WebSocket 推 `{"type":"asset",...}` 更新卡片状态。

### 6.2 client / App

`client.ts` 加：`getArtifacts`、`startArtifacts`、`saveArtifact`、`cutoutArtifact`、`retryArtifact`、`styleTransfer`。`App.tsx` 按 `S3_art_gen` 切 ArtifactsBoard。

---

## 7. 配置与 C 盘约束（硬性）

`backend/.env.example` 扩展：
```env
# 阿里 Token Plan 兼容端点（图像生成）
ART_API_BASE=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
ART_API_KEY=replace-with-aliyun-token-plan-key
ART_IMAGE_MODEL=wan2.7-image-pro
ART_GEN_CONCURRENCY=3
# rembg 模型目录（必须 D 盘，避免 ~176MB 模型落 C 盘）
REMBG_MODELS_DIR=D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models
```
真实 key 落 gitignored `backend/.env`。`deps.py` 读以上 + `ART_API_BASE`/`ART_API_KEY`/`ART_IMAGE_MODEL`/`ART_GEN_CONCURRENCY`/`REMBG_MODELS_DIR`。`Games/` 与 `.rembg_models/` 入 .gitignore。

依赖：httpx 0.28.1、Pillow 12.3.0、rembg 2.0.69、onnxruntime 1.23.2、PyYAML 6.0.3 均已在 agent_env（已确认），无需补装。`Games/` 与 `.rembg_models/` 入 .gitignore。

---

## 8. 测试

pytest + pytest-asyncio；mock 为主；cutout 真跑（rembg 在 agent_env，快）。用户不手动测 S3（除可选的真 API 端点验证）。

- **parser**：fixture md → AssetSpec 列表；非法 md → ValueError。**含 6 个类别（含 `特效与粒子` 等扩展类）的 md 须正常解析为 6 组**，证明类别不限四类。
- **imagegen**：mock httpx → 返回 `data[0].url`（下载）与 `data[0].b64_json`（解码）两条；重试 3 次后抛 ImageGenError。
- **styletransfer**：mock 路径 A（原生 img2img）与路径 B（prompt 降级）各一次。
- **cutout**：fixture 图 → rembg → 输出有 alpha 通道（真跑）。
- **storage**：save_raw/save_processed/has_processed 路径与存在性。
- **pipeline orchestrator**：mock gen_client，3 并发批量，1 张失败记 error 不影响其他，全落 raw/。
- **FSM**：`S2→S3 running→awaiting_approval→(approve)S4 not_implemented`、`(reject)S3 running`；守卫。
- **routes**：`GET artifacts`（磁盘推 status）、`save`（raw→processed）、`cutout`（raw→rembg→processed）、`retry`（重生 raw）、`style-transfer`（多目标覆盖 raw）、`approve` S3→S4。
- **e2e**：`test_e2e_s3`——mock imagegen 批量生图 → 卡片 generated → cutout 一张 → processed 存在 → approve → S4 not_implemented。复用 ASGITransport + set_games_root。
- **实现期真验证（用户授权时，Task 1）**：一次最小付费调用确认 imagegen 端点/模型/size 格式/返回形态；styletransfer 原生 vs 降级路径。spec 已标为 Task 1。

---

## 9. 文件清单

**新建**：
- `backend/pipeline/__init__.py`
- `backend/pipeline/parser.py`
- `backend/pipeline/imagegen.py`
- `backend/pipeline/styletransfer.py`
- `backend/pipeline/cutout.py`
- `backend/pipeline/storage.py`
- `backend/pipeline/orchestrator.py`
- `frontend/src/stages/ArtifactsBoard.tsx`
- `backend/tests/test_pipeline_*.py`、`test_e2e_s3.py`
- `frontend/src/__tests__/artifacts_board.test.tsx`

**修改**：
- `backend/orchestrator/machine.py` — 加 S3 转移 + approve/reject 分 stage（与 S2 一并）
- `backend/api/runtime.py` — 加 `start_art_gen`
- `backend/api/routes.py` — 加 artifacts 路由 + approve/reject 分 stage
- `backend/api/deps.py` — 读图像 API 配置 + REMBG_MODELS_DIR
- `backend/.env.example` — 加图像 API/rembg 配置
- `frontend/src/api/client.ts` — 加 artifacts 客户端
- `frontend/src/App.tsx` — 按 stage 切 ArtifactsBoard
- `.gitignore` — 加 `.rembg_models/`

---

## 10. 范围与边界

- **本 spec 只覆盖 S3**（Asset Pipeline：imagegen/styletransfer/cutout/storage/编排 + S3 前端卡片 + 风格转绘全局面板 + S2→S3→S4 衔接的 S3 侧）。
- **接口面**：与 S2 spec 共享 `美术素材.md` 格式（S2 拥有，本 spec 定义解析器）与 FSM `approve(S2)→S3 running`/`approve(S3)→S4`（双方各写己侧）。
- **兼容性**（决策 10/11）：S3 读 `美术素材.md`（Art Agent 自身产物的固定约定，非外部文件名假设，故不受设计文档命名影响）；`category` 为任意非空字符串，S3 与前端按其动态分组，不假设固定四类。
- **S4**（Coder）由后续 spec 覆盖；本 spec 不定义 Coder 如何读 `processed/`（那是 S4 的 assets_map）。
- **未验证项**（实现期 Task 1 定型）：imagegen 端点 size 分隔符与返回形态、styletransfer 原生 vs 降级路径。
- 实施计划由后续 `writing-plans` 环节产出。
