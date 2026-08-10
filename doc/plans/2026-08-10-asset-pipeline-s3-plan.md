# Asset Pipeline（S3）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 S3 阶段端到端可运行：用户确认美术素材.md 后，Pipeline 批量文生图存 `raw/`，前端卡片逐张展示并提供【直接保存】/【抠图并保存】/【修改 Prompt 重试】+ 全局【风格转绘】面板，用户点【素材完成】过闸进 S4。

**Architecture:** S3 是确定性异步 Python 流水线（**不跑 `claude_agent_sdk.query()`，无 LLM**）。新建 `backend/pipeline/` 包：`parser`（解析清单）、`imagegen`（阿里 wan 兼容端点文生图）、`styletransfer`（风格转绘适配器）、`cutout`（本地 rembg 抠图）、`storage`（存盘）、`orchestrator`（有界并发批量编排）。FSM 扩展 S3 转移；S2 approve 后自动启动 S3。前端 ArtifactsBoard 卡片 + 风格转绘全局面板。本计划只实现 S3，依赖已实现的 S2 产物（美术素材.md）。

**Tech Stack:** Python 3.10（conda env `agent_env`）· httpx 0.28.1 · Pillow 12.3.0 · rembg 2.0.69 · onnxruntime 1.23.2 · PyYAML 6.0.3 · FastAPI · SQLAlchemy 2.0(async) · SQLite（测试）· React 18 · Vite · TypeScript · Vitest。

## Global Constraints

- **Python 环境**：`agent_env`（`D:/Anaconda3/envs/agent_env`，Python 3.10.19）。运行用 `D:/Anaconda3/envs/agent_env/python.exe`。
- **已装依赖**：httpx 0.28.1、Pillow 12.3.0、rembg 2.0.69、onnxruntime 1.23.2、PyYAML 6.0.3、fastapi、SQLAlchemy、pytest、pytest-asyncio、aiosqlite。无需补装。
- **Node**：v20.20.1 / npm 10.8.2（前端）。
- **平台**：Windows + Git Bash；路径用正斜杠。装包用 `--no-cache-dir`。
- **C 盘约束（硬性）**：rembg 模型目录指 D 盘（`U2NET_HOME=D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models`），首次下载 u2net ~176MB 不落 C 盘。`.rembg_models/` 入 .gitignore。
- **语言/规范**：所有代码中文注释；每个后端文件顶部有简短中文功能说明注释。
- **输入契约**：`美术素材.md` 格式由 S2 spec 拥有，本计划解析器 `parse_art_list` 复用 S2 的 `validate_art_assets`（`backend/agents/contract.py`）。
- **类别可扩展**：`AssetSpec.category` 原样保留，前端按字符串动态分组，不假设固定四类。
- **抠图逐张按需**：只自动批量生图存 `raw/`；抠图是卡片【抠图并保存】触发，存 `processed/`。
- **测试约定**：pytest + pytest-asyncio；DB 用 SQLite in-memory。cutout 真跑 rembg（fixture 图，快）。imagegen/styletransfer mock httpx。**用户不手动测 S3**；接真阿里 API 的端点验证为可选手动步骤（见 Task 1）。
- **参考 spec**：`doc/specs/2026-08-10-asset-pipeline-s3-design.md`。

---

## File Structure

**后端 `backend/pipeline/`（新建包）**
- `backend/pipeline/__init__.py` — 包标记
- `backend/pipeline/parser.py` — `AssetSpec` + `parse_art_list`
- `backend/pipeline/imagegen.py` — `ImageGenClient`/`ImageGenError`
- `backend/pipeline/styletransfer.py` — `StyleTransferClient`
- `backend/pipeline/cutout.py` — `cutout(png_bytes) -> bytes`
- `backend/pipeline/storage.py` — `save_raw`/`save_processed`/`raw_path`/`processed_path`/`has_processed`
- `backend/pipeline/orchestrator.py` — `run_art_pipeline`

**后端其他（修改）**
- `backend/orchestrator/machine.py` — 加 S3 转移（start_art_gen/complete_art_gen）；approve/reject 分 stage 已由 S2 计划搭好
- `backend/api/runtime.py` — 加 `start_art_gen`
- `backend/api/routes.py` — 加 artifacts 路由 + PNG 流式端点
- `backend/api/deps.py` — 读图像 API 配置 + REMBG_MODELS_DIR
- `backend/.env.example` — 加图像 API/rembg 配置
- `.gitignore` — 加 `.rembg_models/`

**前端 `frontend/`**
- `frontend/src/stages/ArtifactsBoard.tsx` — 新建
- `frontend/src/api/client.ts` — 加 artifacts 客户端
- `frontend/src/App.tsx` — 按 S3 切 ArtifactsBoard

**测试**
- `backend/tests/test_pipeline_parser.py` — 新建
- `backend/tests/test_pipeline_imagegen.py` — 新建
- `backend/tests/test_pipeline_styletransfer.py` — 新建
- `backend/tests/test_pipeline_cutout.py` — 新建
- `backend/tests/test_pipeline_storage.py` — 新建
- `backend/tests/test_pipeline_orchestrator.py` — 新建
- `backend/tests/test_machine.py` — 加 S3 用例（若 S2 计划未覆盖）
- `backend/tests/test_artifacts_routes.py` — 新建
- `backend/tests/test_e2e_s3.py` — 新建
- `frontend/src/__tests__/artifacts_board.test.tsx` — 新建

---

## Task 1: parser（AssetSpec + parse_art_list）

**Files:**
- Create: `backend/pipeline/__init__.py`、`backend/pipeline/parser.py`
- Test: `backend/tests/test_pipeline_parser.py`

**Interfaces:**
- Consumes: `validate_art_assets`（`backend/agents/contract.py`，S2 计划已实现）、PyYAML。
- Produces: `AssetSpec` dataclass（id/category/file/prompt/width/height/maturing）、`parse_art_list(md: str) -> list[AssetSpec]`（先过 `validate_art_assets`，失败抛 ValueError）。后续 imagegen/cutout/storage/orchestrator 依赖 `AssetSpec`。

- [ ] **Step 1: 写失败测试**

```python
"""pipeline parser：从 美术素材.md 解析 AssetSpec 列表；非法抛 ValueError。含 6 类别正常解析。"""
import pytest
from pipeline.parser import parse_art_list, AssetSpec

SIX_CAT_MD = """## 美术素材清单
| ID | 类别 | 文件名 | 尺寸 | 抠图 |
|----|------|--------|------|------|
| A01 | 角色与NPC | hero_idle | 1024x1024 | 是 |
| A02 | 开场/背景 | title | 1024x1024 | 否 |
| A03 | 地图与建筑物 | floor | 512x512 | 是 |
| A04 | 物品与UI | coin | 512x512 | 是 |
| A05 | 特效与粒子 | fx | 512x512 | 是 |
| A06 | 载具 | cart | 1024x1024 | 是 |

### A01 · 角色与NPC · hero_idle
```yaml
id: A01
category: 角色与NPC
file: hero_idle
prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"
size: "1024x1024"
matting: true
```
### A02 · 开场/背景 · title
```yaml
id: A02
category: 开场/背景
file: title
prompt: "像素风农场开场，可含场景"
size: "1024x1024"
matting: false
```
### A03 · 地图与建筑物 · floor
```yaml
id: A03
category: 地图与建筑物
file: floor
prompt: "像素风地块，纯白背景，无场景，仅保留本体"
size: "512x512"
matting: true
```
### A04 · 物品与UI · coin
```yaml
id: A04
category: 物品与UI
file: coin
prompt: "像素风金币，纯白背景，无场景，仅保留本体"
size: "512x512"
matting: true
```
### A05 · 特效与粒子 · fx
```yaml
id: A05
category: 特效与粒子
file: fx
prompt: "像素风特效，纯白背景，无场景，仅保留本体"
size: "512x512"
matting: true
```
### A06 · 载具 · cart
```yaml
id: A06
category: 载具
file: cart
prompt: "像素风推车，纯白背景，无场景，仅保留本体"
size: "1024x1024"
matting: true
```
"""

def test_parse_art_list_six_categories():
    specs = parse_art_list(SIX_CAT_MD)
    assert len(specs) == 6
    assert {s.category for s in specs} == {"角色与NPC","开场/背景","地图与建筑物","物品与UI","特效与粒子","载具"}
    assert isinstance(specs[0], AssetSpec)
    assert specs[0].width == 1024 and specs[0].height == 1024
    assert specs[0].matting is True
    assert specs[1].matting is False

def test_parse_art_list_invalid_raises():
    bad = "## 美术素材清单\n| ID | 类别 |\n|----|------|\n| A01 | 角色与NPC |\n"  # 无 yaml 块
    with pytest.raises(ValueError):
        parse_art_list(bad)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_parser.py -v`
Expected: FAIL（`pipeline` 包未导入）。

- [ ] **Step 3: 实现 __init__.py 与 parser.py**

`backend/pipeline/__init__.py`：
```python
"""Asset Pipeline：图像生成 / 风格转绘 / 抠图 / 存盘 / 批量编排（确定性，无 LLM）。"""
```

`backend/pipeline/parser.py`：
```python
"""解析 美术素材.md 为 AssetSpec 列表；复用 Art Agent 的 validate_art_assets 校验。"""
import re
import yaml
from dataclasses import dataclass
from agents.contract import validate_art_assets


@dataclass
class AssetSpec:
    id: str
    category: str
    file: str
    prompt: str
    width: int
    height: int
    matting: bool


_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")


def parse_art_list(md: str) -> list[AssetSpec]:
    """解析所有 ```yaml 块为 AssetSpec。先过 validate_art_assets，失败抛 ValueError。"""
    ok, reasons = validate_art_assets(md)
    if not ok:
        raise ValueError("美术素材.md 校验失败: " + "; ".join(reasons))
    blocks = re.findall(r"```yaml\s*\n(.*?)```", md, flags=re.DOTALL)
    specs: list[AssetSpec] = []
    for blk in blocks:
        d = yaml.safe_load(blk)
        m = _SIZE_RE.match(str(d["size"]))
        specs.append(AssetSpec(
            id=str(d["id"]), category=str(d["category"]), file=str(d["file"]),
            prompt=str(d["prompt"]), width=int(m.group(1)), height=int(m.group(2)),
            matting=bool(d["matting"]),
        ))
    return specs
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_parser.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game"
git add backend/pipeline/__init__.py backend/pipeline/parser.py backend/tests/test_pipeline_parser.py
git commit -m "feat(pipeline): parser 解析 美术素材.md 为 AssetSpec"
```

---

## Task 2: imagegen（文生图客户端）

**Files:**
- Create: `backend/pipeline/imagegen.py`
- Test: `backend/tests/test_pipeline_imagegen.py`

**Interfaces:**
- Consumes: httpx、PIL。
- Produces: `ImageGenError`、`ImageGenClient(base_url, api_key, model, concurrency=3)`，`async gen(prompt, size) -> bytes`（PNG bytes，PNG 规范化）、`async aclose()`。orchestrator/routes 依赖之。
- size 分隔符：默认按端点 `*` 发送（阿里 wan 兼容端点）；实现期 Task 9 真验证后定型。spec 注：YAML 存 `WxH`（小写 x），`gen` 内部转 `*`。

- [ ] **Step 1: 写失败测试（mock httpx）**

```python
"""imagegen：mock httpx 验证 url/b64 两条返回 + 重试 3 次抛 ImageGenError。"""
import pytest
import base64
from io import BytesIO
from PIL import Image
import pipeline.imagegen as imagegen_mod


def _png_bytes(color=(255,0,0)):
    b = BytesIO(); Image.new("RGB", (8,8), color).save(b, "PNG"); return b.getvalue()

@pytest.mark.asyncio
async def test_gen_from_b64(monkeypatch):
    client = imagegen_mod.ImageGenClient("http://x", "k", "m")
    b64 = base64.b64encode(_png_bytes()).decode()
    async def fake_post(self, url, **kw): 
        class R:
            status_code = 200
            def json(s): return {"data":[{"b64_json": b64}]}
            def raise_for_status(s): pass
        return R()
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    data = await client.gen("红苹果", "1024x1024")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数

@pytest.mark.asyncio
async def test_gen_from_url(monkeypatch):
    client = imagegen_mod.ImageGenClient("http://x", "k", "m")
    png = _png_bytes()
    async def fake_post(self, url, **kw):
        class R:
            status_code = 200
            def json(s): return {"data":[{"url":"http://img/x.png"}]}
            def raise_for_status(s): pass
        return R()
    async def fake_get(self, url, **kw):
        class R:
            status_code = 200
            content = png
            def raise_for_status(s): pass
        return R()
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    data = await client.gen("红苹果", "1024x1024")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

@pytest.mark.asyncio
async def test_gen_retries_then_raises(monkeypatch):
    client = imagegen_mod.ImageGenClient("http://x", "k", "m")
    calls = {"n":0}
    async def fake_post(self, url, **kw):
        calls["n"]+=1
        class R:
            status_code = 500
            text = "err"
            def raise_for_status(s): raise httpx.HTTPStatusError("500", request=None, response=None)
        return R()
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(imagegen_mod.asyncio, "sleep", lambda *a,**k: None)  # 跳过退避等待
    with pytest.raises(imagegen_mod.ImageGenError):
        await client.gen("x", "1024x1024")
    assert calls["n"] == 3
```
> 注：测试顶部需 `import httpx`。

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_imagegen.py -v`
Expected: FAIL（`ImageGenClient` 未定义）。

- [ ] **Step 3: 实现 imagegen.py**

```python
"""文生图客户端：OpenAI 兼容 /images/generations，返回 PNG bytes（PIL 规范化），指数退避重试 3 次。"""
import asyncio
import base64
from io import BytesIO
import httpx
from PIL import Image


class ImageGenError(Exception):
    pass


class ImageGenClient:
    def __init__(self, base_url: str, api_key: str, model: str, concurrency: int = 3):
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._sem = asyncio.Semaphore(concurrency)
        self._client = httpx.AsyncClient(timeout=120)

    def _norm_png(self, raw: bytes) -> bytes:
        """PIL 读入再存 PNG，保证一律 PNG 供 rembg 与前端统一处理。"""
        img = Image.open(BytesIO(raw))
        out = BytesIO()
        img.save(out, "PNG")
        return out.getvalue()

    async def gen(self, prompt: str, size: str) -> bytes:
        """size 形如 '1024x1024'；内部转端点要求的 '*' 分隔（阿里 wan 兼容端点）。"""
        size_api = size.replace("x", "*")
        body = {"model": self._model, "prompt": prompt, "n": 1, "size": size_api}
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        async with self._sem:
            last_err = None
            for _ in range(3):
                try:
                    r = await self._client.post(f"{self._base}/images/generations", json=body, headers=headers)
                    r.raise_for_status()
                    data = r.json()["data"][0]
                    if "b64_json" in data:
                        raw = base64.b64decode(data["b64_json"])
                    elif "url" in data:
                        gr = await self._client.get(data["url"])
                        gr.raise_for_status()
                        raw = gr.content
                    else:
                        raise ImageGenError(f"响应无 b64_json/url: {data}")
                    return self._norm_png(raw)
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(0.5 * (_ + 1))  # 退避 0.5/1/1.5s
            raise ImageGenError(f"文生图重试 3 次仍败: {last_err}")

    async def aclose(self):
        await self._client.aclose()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_imagegen.py -v`
Expected: PASS（3 用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/pipeline/imagegen.py backend/tests/test_pipeline_imagegen.py
git commit -m "feat(pipeline): imagegen 文生图客户端（url/b64 + 重试 + PNG 规范化）"
```

---

## Task 3: styletransfer（风格转绘适配器）

**Files:**
- Create: `backend/pipeline/styletransfer.py`
- Test: `backend/tests/test_pipeline_styletransfer.py`

**Interfaces:**
- Consumes: httpx、PIL、`ImageGenError`（imagegen）。
- Produces: `StyleTransferClient(base_url, api_key, model)`，`async transfer(style_ref: bytes, struct_ref: bytes, prompt: str) -> bytes`（PNG bytes）。两条路径（原生 img2img / prompt 降级），实现期 Task 9 验证后选其一；本任务实现适配器框架，默认走"prompt 降级"路径（最稳，不依赖端点吃图）。

- [ ] **Step 1: 写失败测试（mock 两条路径）**

```python
"""styletransfer：mock 路径 A（原生 img2img）与路径 B（prompt 降级）。"""
import pytest
import base64
from io import BytesIO
from PIL import Image
import pipeline.styletransfer as st_mod


def _png(c=(0,0,255)):
    b=BytesIO(); Image.new("RGB",(8,8),c).save(b,"PNG"); return b.getvalue()

@pytest.mark.asyncio
async def test_transfer_path_b_prompt_fallback(monkeypatch):
    # 默认路径 B：prompt 降级（不传图，纯文生图）
    client = st_mod.StyleTransferClient("http://x","k","m")
    b64 = base64.b64encode(_png()).decode()
    async def fake_post(self, url, **kw):
        body = kw.get("json", {})
        # 路径 B 不应在 body 含 image 字段
        assert "image" not in body and "image_url" not in body
        assert "风格" in body["prompt"]
        class R:
            status_code=200
            def json(s): return {"data":[{"b64_json":b64}]}
            def raise_for_status(s): pass
        return R()
    monkeypatch.setattr(__import__("httpx").AsyncClient, "post", fake_post)
    data = await client.transfer(style_ref=_png(), struct_ref=_png(), prompt="像素风农夫")
    assert data[:8]==b"\x89PNG\r\n\x1a\n"

@pytest.mark.asyncio
async def test_transfer_path_a_native(monkeypatch):
    # 路径 A：原生 img2img（传图），通过 mode="native" 开关
    client = st_mod.StyleTransferClient("http://x","k","m", mode="native")
    b64 = base64.b64encode(_png()).decode()
    async def fake_post(self, url, **kw):
        body = kw.get("json", {})
        assert "image" in body or "image_url" in body  # 传了结构参考
        class R:
            status_code=200
            def json(s): return {"data":[{"b64_json":b64}]}
            def raise_for_status(s): pass
        return R()
    monkeypatch.setattr(__import__("httpx").AsyncClient, "post", fake_post)
    data = await client.transfer(style_ref=_png(), struct_ref=_png(), prompt="像素风农夫")
    assert data[:8]==b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_styletransfer.py -v`
Expected: FAIL（`StyleTransferClient` 未定义）。

- [ ] **Step 3: 实现 styletransfer.py**

```python
"""风格转绘适配器：路径 A 原生 img2img（传图）/ 路径 B prompt 降级（不传图）。
默认 mode='prompt'（最稳）；实现期真验证端点是否吃图后，切 mode='native' 或保留默认。"""
import asyncio
import base64
from io import BytesIO
import httpx
from PIL import Image
from .imagegen import ImageGenError


class StyleTransferClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, mode: str = "prompt"):
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._mode = mode  # 'prompt' | 'native'
        self._client = httpx.AsyncClient(timeout=120)

    def _norm_png(self, raw: bytes) -> bytes:
        img = Image.open(BytesIO(raw)); out = BytesIO(); img.save(out, "PNG"); return out.getvalue()

    async def transfer(self, style_ref: bytes, struct_ref: bytes, prompt: str) -> bytes:
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        if self._mode == "native":
            # 路径 A：传结构参考图（base64）
            body = {
                "model": self._model,
                "prompt": f"以风格重绘：{prompt}",
                "image": base64.b64encode(struct_ref).decode(),
                "n": 1,
            }
        else:
            # 路径 B：prompt 降级，不传图
            body = {
                "model": self._model,
                "prompt": f"以如下风格重绘：风格参考图所示画风。原图主体：{prompt}。{prompt}",
                "n": 1,
            }
        last = None
        for _ in range(3):
            try:
                r = await self._client.post(f"{self._base}/images/generations", json=body, headers=headers)
                r.raise_for_status()
                data = r.json()["data"][0]
                raw = base64.b64decode(data["b64_json"]) if "b64_json" in data else (await self._client.get(data["url"])).content
                return self._norm_png(raw)
            except Exception as e:
                last = e; await asyncio.sleep(0.5 * (_ + 1))
        raise ImageGenError(f"风格转绘重试 3 次仍败: {last}")

    async def aclose(self):
        await self._client.aclose()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_styletransfer.py -v`
Expected: PASS（2 用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/pipeline/styletransfer.py backend/tests/test_pipeline_styletransfer.py
git commit -m "feat(pipeline): styletransfer 风格转绘适配器（原生/prompt 降级）"
```

---

## Task 4: cutout（本地 rembg 抠图）

**Files:**
- Create: `backend/pipeline/cutout.py`
- Test: `backend/tests/test_pipeline_cutout.py`

**Interfaces:**
- Consumes: rembg（`rembg.remove`）、`asyncio.to_thread`、`os`、deps `REMBG_MODELS_DIR`（本 Task 先在模块内设默认值，Task 6 从 deps 读）。
- Produces: `async cutout(png_bytes: bytes) -> bytes`（透明 PNG bytes）。routes 依赖之。
- **模型落 D 盘**：模块加载设 `U2NET_HOME`（默认 `D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models`），首次下载 u2net 到此。

- [ ] **Step 1: 写失败测试（真跑 rembg，fixture 图）**

```python
"""cutout：真跑 rembg，验证输出为带 alpha 通道的 PNG。"""
import pytest
from io import BytesIO
from PIL import Image
from pipeline.cutout import cutout


@pytest.mark.asyncio
async def test_cutout_produces_alpha():
    # 生成一张实心 RGB PNG（红方块白底）
    b = BytesIO(); Image.new("RGB", (64, 64), (255, 255, 255)).save(b, "PNG")
    out = await cutout(b.getvalue())
    img = Image.open(BytesIO(out))
    assert img.format == "PNG"
    assert img.mode in ("RGBA", "LA") or "transparency" in img.info  # 透明
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_cutout.py -v`
Expected: FAIL（`cutout` 未定义）。
> 首次运行会触发 rembg 下载 u2net 模型到 `U2NET_HOME`（D 盘），可能耗时数十秒。

- [ ] **Step 3: 实现 cutout.py**

```python
"""本地抠图：rembg.remove 包进 asyncio.to_thread，避免阻塞事件循环。模型落 D 盘（U2NET_HOME）。"""
import asyncio
import os
import threading

# 确保只设一次 U2NET_HOME（rembg 首次加载模型据此下载）
_DEFAULT_REMBG_DIR = "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models"
os.environ.setdefault("U2NET_HOME", _DEFAULT_REMBG_DIR)

from rembg import remove as _rembg_remove  # noqa: E402


async def cutout(png_bytes: bytes) -> bytes:
    """rembg.remove → 透明 PNG bytes。输入须为 PNG bytes（imagegen/styletransfer 已规范化）。"""
    return await asyncio.to_thread(_rembg_remove, png_bytes)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_cutout.py -v`
Expected: PASS（真跑 rembg，输出带透明）。

- [ ] **Step 5: 提交**

```bash
git add backend/pipeline/cutout.py backend/tests/test_pipeline_cutout.py
git commit -m "feat(pipeline): cutout 本地 rembg 抠图（模型落 D 盘）"
```

---

## Task 5: storage（存盘 + 路径 + has_processed）

**Files:**
- Create: `backend/pipeline/storage.py`
- Test: `backend/tests/test_pipeline_storage.py`

**Interfaces:**
- Consumes: `AssetSpec`（parser）。
- Produces: `save_raw(game_root, spec, data) -> Path`、`save_processed(game_root, spec, data) -> Path`、`raw_path(game_root, spec) -> Path`、`processed_path(game_root, spec) -> Path`、`has_processed(game_root, spec) -> bool`。orchestrator/routes 依赖之。
- 命名：`raw/<id>_<file>.png`；`processed/<file>.png`（无 id 前缀，Coder assets_map 按 file 引用）。

- [ ] **Step 1: 写失败测试**

```python
"""storage：raw/processed 路径、存盘、存在性。"""
import pytest
from pathlib import Path
from pipeline.parser import AssetSpec
from pipeline.storage import save_raw, save_processed, raw_path, processed_path, has_processed

_SPEC = AssetSpec("A01","角色与NPC","hero_idle","p",1024,1024,True)

def test_raw_path():
    p = raw_path(Path("/g"), _SPEC)
    assert p == Path("/g/assets/raw/A01_hero_idle.png")

def test_processed_path():
    p = processed_path(Path("/g"), _SPEC)
    assert p == Path("/g/assets/processed/hero_idle.png")

def test_save_raw_and_processed(tmp_path):
    save_raw(tmp_path, _SPEC, b"\x89PNG")
    save_processed(tmp_path, _SPEC, b"\x89PNG")
    assert raw_path(tmp_path, _SPEC).exists()
    assert processed_path(tmp_path, _SPEC).exists()
    assert has_processed(tmp_path, _SPEC) is True

def test_has_processed_false(tmp_path):
    assert has_processed(tmp_path, _SPEC) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_storage.py -v`
Expected: FAIL（`storage` 未定义）。

- [ ] **Step 3: 实现 storage.py**

```python
"""资产存盘：raw 带 id 前缀防重名，processed 无前缀供 Coder assets_map 引用。"""
from pathlib import Path
from .parser import AssetSpec


def raw_path(game_root: Path, spec: AssetSpec) -> Path:
    return game_root / "assets" / "raw" / f"{spec.id}_{spec.file}.png"


def processed_path(game_root: Path, spec: AssetSpec) -> Path:
    return game_root / "assets" / "processed" / f"{spec.file}.png"


def save_raw(game_root: Path, spec: AssetSpec, data: bytes) -> Path:
    p = raw_path(game_root, spec)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def save_processed(game_root: Path, spec: AssetSpec, data: bytes) -> Path:
    p = processed_path(game_root, spec)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def has_processed(game_root: Path, spec: AssetSpec) -> bool:
    return processed_path(game_root, spec).exists()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_storage.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/pipeline/storage.py backend/tests/test_pipeline_storage.py
git commit -m "feat(pipeline): storage 存盘 + 路径 + has_processed"
```

---

## Task 6: deps + .env.example + .gitignore 配置

**Files:**
- Modify: `backend/api/deps.py`、`backend/.env.example`、`.gitignore`

**Interfaces:**
- Produces: `ART_API_BASE`/`ART_API_KEY`/`ART_IMAGE_MODEL`/`ART_GEN_CONCURRENCY`/`REMBG_MODELS_DIR` env 读取。runtime/routes 依赖之。cutout 模块的 `U2NET_HOME` 在 Task 4 用默认值，本 Task 让 deps 暴露 `REMBG_MODELS_DIR`（cutout 可在启动时从 deps 读并覆盖默认——见 Task 8 runtime 启动时设 env）。

- [ ] **Step 1: 改 deps.py（在 ART_MODEL 行后追加）**

```python
ART_MODEL = os.getenv("ART_MODEL", "claude-sonnet-4-6")
ART_API_BASE = os.getenv("ART_API_BASE")
ART_API_KEY = os.getenv("ART_API_KEY")
ART_IMAGE_MODEL = os.getenv("ART_IMAGE_MODEL", "wan2.7-image-pro")
ART_GEN_CONCURRENCY = int(os.getenv("ART_GEN_CONCURRENCY", "3"))
REMBG_MODELS_DIR = os.getenv("REMBG_MODELS_DIR", "D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models")
```

- [ ] **Step 2: 改 .env.example（追加图像 API 段）**

```env
# 阿里 Token Plan 兼容端点（图像生成）
ART_API_BASE=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
ART_API_KEY=replace-with-aliyun-token-plan-key
ART_IMAGE_MODEL=wan2.7-image-pro
ART_GEN_CONCURRENCY=3
# rembg 模型目录（必须 D 盘，避免 ~176MB 模型落 C 盘）
REMBG_MODELS_DIR=D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models
```

- [ ] **Step 3: 改 .gitignore（加 rembg 模型目录）**

在 `.gitignore` 末尾加一行：
```
.rembg_models/
```

- [ ] **Step 4: 验证导入**

Run: `D:/Anaconda3/envs/agent_env/python.exe -c "from api.deps import ART_API_BASE, ART_GEN_CONCURRENCY, REMBG_MODELS_DIR; print(ART_GEN_CONCURRENCY, REMBG_MODELS_DIR)"`
Expected: 打印 `3 D:/yanjiusheng/shixi/youxicehua/AI_Cowork_Game/.rembg_models`，无异常。

- [ ] **Step 5: 提交**

```bash
git add backend/api/deps.py backend/.env.example .gitignore
git commit -m "feat(api): deps 加图像 API/rembg 配置 + .gitignore"
```

---

## Task 7: orchestrator（批量编排）

**Files:**
- Create: `backend/pipeline/orchestrator.py`
- Test: `backend/tests/test_pipeline_orchestrator.py`

**Interfaces:**
- Consumes: `AssetSpec`（parser）、`ImageGenClient`（imagegen）、`save_raw`（storage）、`asyncio.Semaphore`。
- Produces: `async run_art_pipeline(game_root, specs, *, gen_client, on_progress) -> dict[str,str]`。runtime `start_art_gen` 调用之。每张完成推 `{'type':'asset','aid','status','raw_path'}`；失败记 `error` 不抛。不自动抠图。

- [ ] **Step 1: 写失败测试（mock gen_client）**

```python
"""pipeline orchestrator：mock gen_client，3 并发批量，1 张失败记 error 不影响其他。"""
import pytest
from pathlib import Path
from pipeline.parser import AssetSpec
from pipeline.orchestrator import run_art_pipeline

def _spec(aid, file="a"):
    return AssetSpec(aid, "角色与NPC", file, "p", 512, 512, True)


class _FakeGen:
    def __init__(self, fail_aid=None):
        self.fail_aid = fail_aid
    async def gen(self, prompt, size):
        return b"\x89PNG"
    async def aclose(self): pass


@pytest.mark.asyncio
async def test_run_pipeline_all_generated(tmp_path):
    specs = [_spec("A01","a"), _spec("A02","b"), _spec("A03","c")]
    progress = []
    async def on_progress(m): progress.append(m)
    res = await run_art_pipeline(tmp_path, specs, gen_client=_FakeGen(), on_progress=on_progress)
    assert res == {"A01":"generated","A02":"generated","A03":"generated"}
    assert len([m for m in progress if m.get("status")=="generated"]) == 3
    from pipeline.storage import raw_path
    assert all(raw_path(tmp_path, s).exists() for s in specs)


class _FakeGenFail:
    async def gen(self, prompt, size):
        if "A02" in prompt:
            from pipeline.imagegen import ImageGenError
            raise ImageGenError("fail")
        return b"\x89PNG"
    async def aclose(self): pass


@pytest.mark.asyncio
async def test_run_pipeline_one_fails_others_ok(tmp_path):
    specs = [_spec("A01","a"), _spec("A02","b"), _spec("A03","c")]
    res = await run_art_pipeline(tmp_path, specs, gen_client=_FakeGenFail(), on_progress=lambda m: None)
    assert res["A01"]=="generated" and res["A03"]=="generated"
    assert res["A02"]=="error"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_orchestrator.py -v`
Expected: FAIL（`run_art_pipeline` 未定义）。

- [ ] **Step 3: 实现 orchestrator.py**

```python
"""批量文生图编排：有界并发，每张落 raw/，失败记 error 不中断其他。不自动抠图。"""
import asyncio
from pathlib import Path
from .parser import AssetSpec
from .imagegen import ImageGenClient, ImageGenError
from .storage import save_raw


async def run_art_pipeline(game_root: Path, specs: list[AssetSpec], *,
                           gen_client, on_progress) -> dict[str, str]:
    """有界并发批量文生图。返回 {aid: 'generated'|'error'}。每张完成经 on_progress 推进度。"""
    results: dict[str, str] = {}

    async def gen_one(spec: AssetSpec):
        try:
            data = await gen_client.gen(spec.prompt, f"{spec.width}x{spec.height}")
            p = save_raw(game_root, spec, data)
            results[spec.id] = "generated"
            await on_progress({"type": "asset", "aid": spec.id, "status": "generated", "raw_path": str(p)})
        except ImageGenError as e:
            results[spec.id] = "error"
            await on_progress({"type": "asset", "aid": spec.id, "status": "error", "message": str(e)})

    await asyncio.gather(*(gen_one(s) for s in specs))
    return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_pipeline_orchestrator.py -v`
Expected: PASS（2 用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/pipeline/orchestrator.py backend/tests/test_pipeline_orchestrator.py
git commit -m "feat(pipeline): orchestrator 有界并发批量文生图"
```

---

## Task 8: FSM S3 转移 + runtime start_art_gen

**Files:**
- Modify: `backend/orchestrator/machine.py`、`backend/api/runtime.py`
- Test: `backend/tests/test_machine.py`（追加）、`backend/tests/test_runtime.py`（追加）

**Interfaces:**
- Consumes: `Stage`/`StageStatus`、`parse_art_list`（parser）、`run_art_pipeline`（orchestrator）、`ImageGenClient`（imagegen）、deps 图像配置、broker、`GameRun`/`PendingApproval`。
- Produces: `StateMachine.start_art_gen`/`complete_art_gen`（FSM；approve/reject 分 stage 已由 S2 计划搭好，S3 分支已含）、`start_art_gen(run_id, game_name)`（runtime 后台任务）。
- 注意：S2 计划的 `approve(S2)` 已返回 `(S3_art_gen, running)`。本任务补 `start_art_gen`/`complete_art_gen` FSM 方法与 runtime 后台任务，并让 S2 approve 路由在切到 S3 后启动 `start_art_gen`。

- [ ] **Step 1: 写失败测试（machine 追加）**

```python
# ---- S3 转移 ----
def test_start_art_gen():
    sm = StateMachine()
    t = sm.start_art_gen(RunState("r", Stage.S2_art_plan, StageStatus.approved))
    assert t.stage == Stage.S3_art_gen and t.status == StageStatus.running

def test_complete_art_gen():
    sm = StateMachine()
    t = sm.complete_art_gen(RunState("r", Stage.S3_art_gen, StageStatus.running))
    assert t.stage == Stage.S3_art_gen and t.status == StageStatus.awaiting_approval

def test_approve_s3_to_s4():
    sm = StateMachine()
    t = sm.approve(RunState("r", Stage.S3_art_gen, StageStatus.awaiting_approval), stage=Stage.S3_art_gen)
    assert t.stage == Stage.S4_coding and t.status == StageStatus.not_implemented
```

> 若 S2 计划 Task 5 的 `approve` 已含 S3→S4 分支，则 `test_approve_s3_to_s4` 应已通过；本任务仅补 `start_art_gen`/`complete_art_gen`。

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_machine.py -v -k "art_gen or approve_s3"`
Expected: FAIL（`start_art_gen`/`complete_art_gen` 未定义）。

- [ ] **Step 3a: machine.py 加两个方法（在 complete_art_plan 后追加）**

```python
    def start_art_gen(self, run: RunState) -> Transition:
        return Transition(Stage.S3_art_gen, StageStatus.running)

    def complete_art_gen(self, run: RunState) -> Transition:
        return Transition(Stage.S3_art_gen, StageStatus.awaiting_approval)
```

- [ ] **Step 3b: runtime.py 加 start_art_gen（在文件末尾追加）**

```python
from pipeline.parser import parse_art_list
from pipeline.imagegen import ImageGenClient
from pipeline.orchestrator import run_art_pipeline
from api.deps import ART_API_BASE as _ART_API_BASE, ART_API_KEY as _ART_API_KEY, ART_IMAGE_MODEL as _ART_IMG_MODEL, ART_GEN_CONCURRENCY as _ART_GEN_CONC

__all__ = ["start_design", "start_art_plan", "start_art_gen", "resolve_design_doc"]


async def start_art_gen(run_id: str, game_name: str) -> None:
    """启动批量文生图；完成后置 S3 awaiting_approval。"""
    game_root = games_root() / _slug(game_name)
    artlist_md = (game_root / "docs" / "美术素材.md").read_text(encoding="utf-8")
    specs = parse_art_list(artlist_md)

    async def on_progress(msg):
        broker.publish(run_id, {"type": "progress", **msg})

    client = ImageGenClient(_ART_API_BASE, _ART_API_KEY, _ART_IMG_MODEL, concurrency=_ART_GEN_CONC)
    try:
        await run_art_pipeline(game_root, specs, gen_client=client, on_progress=on_progress)
        async with _session_factory() as session:
            async with session.begin():
                run = await session.get(GameRun, run_id)
                run.current_stage = Stage.S3_art_gen.value
                run.status = StageStatus.awaiting_approval.value
                session.add(PendingApproval(
                    run_id=run_id, stage=Stage.S3_art_gen.value,
                    payload={"artifacts_dir": "assets/processed"}, status="pending",
                ))
        broker.publish(run_id, {"type": "gate", "stage": "S3_art_gen", "status": "awaiting_approval"})
    except Exception as e:
        broker.publish(run_id, {"type": "error", "message": str(e)})
        raise
    finally:
        await client.aclose()
```

- [ ] **Step 3c: routes.py 的 approve 端点，在 S2 分支后加 S3 启动**
> S2 计划 Task 8 的 approve 端点已按 stage 自动分支。在 `approve` 函数末尾（`if stage == Stage.S1_design:` 启动块后）追加：
```python
    elif stage == Stage.S2_art_plan:
        task = asyncio.create_task(start_art_gen(run_id, run.game_name))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
```
> 且 routes.py 顶部 import 改为 `from api.runtime import start_design, start_art_plan, start_art_gen`。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_machine.py -v -k "art_gen or approve_s3"`
Expected: PASS。
> runtime 的 start_art_gen 单测可省（e2e Task 10 覆盖），或加一个 mock gen_client 的轻量用例。

- [ ] **Step 5: 提交**

```bash
git add backend/orchestrator/machine.py backend/api/runtime.py backend/api/routes.py backend/tests/test_machine.py
git commit -m "feat(orchestrator+api): S3 FSM 转移 + start_art_gen 批量生图任务"
```

---

## Task 9: artifacts 路由（REST + PNG 流式端点）

**Files:**
- Modify: `backend/api/routes.py`
- Test: `backend/tests/test_artifacts_routes.py`（新建）

**Interfaces:**
- Consumes: `parse_art_list`（parser）、`cutout`（cutout）、`storage`、`ImageGenClient`/`StyleTransferClient`（imagegen/styletransfer）、deps 配置、`get_run`（repo）。
- Produces: `POST /runs/{id}/artifacts/start`、`GET /runs/{id}/artifacts`、`GET .../artifacts/{aid}/raw`、`GET .../artifacts/{aid}/processed`、`POST .../artifacts/{aid}/save`、`POST .../artifacts/{aid}/cutout`、`POST .../artifacts/{aid}/retry`、`POST .../artifacts/style-transfer`。
- retry/style-transfer 删除该资产旧 processed（避免过时）；status 由磁盘推（generated/saved/cutout/error/pending）。

- [ ] **Step 1: 写失败测试（聚焦 save/cutout/retry + 列表 status）**

```python
"""artifacts routes：save/cutout/retry + GET artifacts 状态由磁盘推。mock imagegen。"""
import pytest
from httpx import AsyncClient, ASGITransport
from agents.tools import do_write_file
import api.runtime as runtime_mod
import pipeline.imagegen as imagegen_mod


ARTLIST = ("## 美术素材清单\n\n| ID | 类别 | 文件名 | 尺寸 | 抠图 |\n|----|------|--------|------|------|\n"
           "| A01 | 角色与NPC | hero_idle | 8x8 | 是 |\n\n"
           "### A01 · 角色与NPC · hero_idle\n```yaml\n"
           "id: A01\ncategory: 角色与NPC\nfile: hero_idle\n"
           'prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"\n'
           'size: "8x8"\nmatting: true\n```\n')


@pytest.mark.asyncio
async def test_save_and_list(tmp_path, monkeypatch):
    from api.main import app, set_games_root
    set_games_root(tmp_path)
    game_root = tmp_path / "test"
    (game_root / "docs").mkdir(parents=True)
    (game_root / "docs" / "美术素材.md").write_text(ARTLIST, encoding="utf-8")
    # 直接放一个 raw 图（绕过真生图）
    from io import BytesIO; from PIL import Image
    b=BytesIO(); Image.new("RGB",(8,8),(255,0,0)).save(b,"PNG")
    (game_root / "assets" / "raw").mkdir(parents=True)
    (game_root / "assets" / "raw" / "A01_hero_idle.png").write_bytes(b.getvalue())
    # 假设 run 已建（简化：直接调路由需要 run 记录；这里用 monkeypatch 绕过 _load_run）
    import api.routes as routes_mod
    class _R: slug="test"; current_stage="S3_art_gen"; status="awaiting_approval"; game_name="test"
    monkeypatch.setattr(routes_mod, "_load_run", lambda *a,**k: _R())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # 列表：A01 状态 generated
        r = await c.get("/api/runs/x/artifacts")
        assert r.status_code == 200
        items = r.json()
        assert items[0]["aid"]=="A01" and items[0]["status"]=="generated"
        # save → processed 存在，状态 saved
        await c.post("/api/runs/x/artifacts/A01/save")
        r2 = await c.get("/api/runs/x/artifacts")
        assert r2.json()[0]["status"] in ("saved","cutout")
        assert (game_root/"assets"/"processed"/"hero_idle.png").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_artifacts_routes.py -v`
Expected: FAIL（路由未注册）。

- [ ] **Step 3: 实现 routes.py 的 artifacts 段**

顶部 import 追加：
```python
from api.runtime import start_design, start_art_plan, start_art_gen
from pipeline.parser import parse_art_list
from pipeline import storage as _storage
from pipeline.cutout import cutout
from pipeline.imagegen import ImageGenClient, ImageGenError
from pipeline.styletransfer import StyleTransferClient
from api.deps import (ART_API_BASE, ART_API_KEY, ART_IMAGE_MODEL, ART_GEN_CONCURRENCY)
from fastapi import UploadFile, File
from sqlalchemy.exc import SQLAlchemyError
```

追加路由：
```python
def _load_specs(run) -> list:
    p = games_root() / run.slug / "docs" / "美术素材.md"
    return parse_art_list(p.read_text(encoding="utf-8"))

def _spec_by_aid(specs, aid):
    for s in specs:
        if s.id == aid:
            return s
    return None

@router.post("/runs/{run_id}/artifacts/start")
async def artifacts_start(run_id: str):
    run = await _load_run(run_id)
    task = asyncio.create_task(start_art_gen(run_id, run.game_name))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"ok": True}

@router.get("/runs/{run_id}/artifacts")
async def artifacts_list(run_id: str):
    run = await _load_run(run_id)
    game_root = games_root() / run.slug
    specs = _load_specs(run)
    out = []
    for s in specs:
        raw_p = _storage.raw_path(game_root, s)
        proc_p = _storage.processed_path(game_root, s)
        # status 由磁盘推：processed 存在 → saved（直接保存）或 cutout（带 alpha）；否则 raw 存在 → generated；否则 pending
        if proc_p.exists():
            try:
                is_alpha = Image.open(proc_p).mode in ("RGBA", "LA")
            except Exception:
                is_alpha = False
            status = "cutout" if is_alpha else "saved"
        elif raw_p.exists():
            status = "generated"
        else:
            status = "pending"
        out.append({
            "aid": s.id, "file": s.file, "category": s.category, "matting": s.matting,
            "raw_url": f"/api/runs/{run_id}/artifacts/{s.id}/raw" if raw_p.exists() else None,
            "processed_url": f"/api/runs/{run_id}/artifacts/{s.id}/processed" if proc_p.exists() else None,
            "status": status,
        })
    return out

@router.get("/runs/{run_id}/artifacts/{aid}/raw")
async def artifact_raw(run_id: str, aid: str):
    run = await _load_run(run_id)
    s = _spec_by_aid(_load_specs(run), aid)
    if not s: raise HTTPException(404, "aid not found")
    p = _storage.raw_path(games_root() / run.slug, s)
    if not p.exists(): raise HTTPException(404, "raw not ready")
    return Response(p.read_bytes(), media_type="image/png")

@router.get("/runs/{run_id}/artifacts/{aid}/processed")
async def artifact_processed(run_id: str, aid: str):
    run = await _load_run(run_id)
    s = _spec_by_aid(_load_specs(run), aid)
    if not s: raise HTTPException(404, "aid not found")
    p = _storage.processed_path(games_root() / run.slug, s)
    if not p.exists(): raise HTTPException(404, "processed not ready")
    return Response(p.read_bytes(), media_type="image/png")

@router.post("/runs/{run_id}/artifacts/{aid}/save")
async def artifact_save(run_id: str, aid: str):
    run = await _load_run(run_id)
    s = _spec_by_aid(_load_specs(run), aid)
    if not s: raise HTTPException(404, "aid not found")
    game_root = games_root() / run.slug
    raw_p = _storage.raw_path(game_root, s)
    if not raw_p.exists(): raise HTTPException(409, "raw 未生成")
    _storage.save_processed(game_root, s, raw_p.read_bytes())
    return {"ok": True, "processed_url": f"/api/runs/{run_id}/artifacts/{aid}/processed"}

@router.post("/runs/{run_id}/artifacts/{aid}/cutout")
async def artifact_cutout(run_id: str, aid: str):
    run = await _load_run(run_id)
    s = _spec_by_aid(_load_specs(run), aid)
    if not s: raise HTTPException(404, "aid not found")
    game_root = games_root() / run.slug
    raw_p = _storage.raw_path(game_root, s)
    if not raw_p.exists(): raise HTTPException(409, "raw 未生成")
    png = await cutout(raw_p.read_bytes())
    _storage.save_processed(game_root, s, png)
    return {"ok": True, "processed_url": f"/api/runs/{run_id}/artifacts/{aid}/processed"}

@router.post("/runs/{run_id}/artifacts/{aid}/retry")
async def artifact_retry(run_id: str, aid: str, payload: dict):
    run = await _load_run(run_id)
    s = _spec_by_aid(_load_specs(run), aid)
    if not s: raise HTTPException(404, "aid not found")
    game_root = games_root() / run.slug
    prompt = payload.get("prompt", s.prompt)
    client = ImageGenClient(ART_API_BASE, ART_API_KEY, ART_IMAGE_MODEL, concurrency=ART_GEN_CONCURRENCY)
    try:
        data = await client.gen(prompt, f"{s.width}x{s.height}")
    except ImageGenError as e:
        raise HTTPException(502, str(e))
    finally:
        await client.aclose()
    _storage.save_raw(game_root, s, data)
    # 删除过时 processed
    proc = _storage.processed_path(game_root, s)
    if proc.exists(): proc.unlink()
    return {"ok": True, "raw_url": f"/api/runs/{run_id}/artifacts/{aid}/raw"}

@router.post("/runs/{run_id}/artifacts/style-transfer")
async def artifacts_style_transfer(run_id: str, target_aids: list[str] = Body(...), prompt: str | None = None, style_ref: UploadFile = File(...)):
    run = await _load_run(run_id)
    game_root = games_root() / run.slug
    specs = _load_specs(run)
    style_bytes = await style_ref.read()
    client = StyleTransferClient(ART_API_BASE, ART_API_KEY, ART_IMAGE_MODEL)
    results = []
    try:
        for aid in target_aids:
            s = _spec_by_aid(specs, aid)
            if not s: continue
            raw_p = _storage.raw_path(game_root, s)
            if not raw_p.exists(): continue
            data = await client.transfer(style_bytes, raw_p.read_bytes(), s.prompt if prompt is None else prompt)
            _storage.save_raw(game_root, s, data)
            proc = _storage.processed_path(game_root, s)
            if proc.exists(): proc.unlink()
            results.append({"aid": aid, "raw_url": f"/api/runs/{run_id}/artifacts/{aid}/raw"})
    finally:
        await client.aclose()
    return {"ok": True, "results": results}
```

> 需在 routes.py 顶部补 `from fastapi import Body, Response` 与 `from PIL import Image`。`Image.open` 用于 `artifacts_list` 的 saved/cutout 状态推断，已用 try/except 包裹避免损坏 PNG 读取异常。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_artifacts_routes.py -v`
Expected: PASS（save + 列表 status）。

- [ ] **Step 5: 提交**

```bash
git add backend/api/routes.py backend/tests/test_artifacts_routes.py
git commit -m "feat(api): artifacts 路由（list/save/cutout/retry/style-transfer + PNG 流式）"
```

---

## Task 10: 前端 ArtifactsBoard + client + App + e2e

**Files:**
- Create: `frontend/src/stages/ArtifactsBoard.tsx`、`backend/tests/test_e2e_s3.py`
- Modify: `frontend/src/api/client.ts`、`frontend/src/App.tsx`
- Test: `frontend/src/__tests__/artifacts_board.test.tsx`

**Interfaces:**
- Consumes: client artifacts 函数、connectWS。
- Produces: `ArtifactsBoard`（卡片网格 + 风格转绘全局面板 + 素材完成按钮）；e2e 验证 S3 全链路（mock imagegen 批量 → cutout 一张 → approve → S4）。

- [ ] **Step 1: 写前端失败测试**

```tsx
// frontend/src/__tests__/artifacts_board.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ArtifactsBoard } from '../stages/ArtifactsBoard'

vi.mock('../api/client', () => ({
  getArtifacts: vi.fn().mockResolvedValue([
    { aid: 'A01', file: 'hero_idle', category: '角色与NPC', matting: true, status: 'generated', raw_url: '/api/runs/r/artifacts/A01/raw', processed_url: null }
  ]),
  saveArtifact: vi.fn().mockResolvedValue({}),
  cutoutArtifact: vi.fn().mockResolvedValue({}),
  retryArtifact: vi.fn().mockResolvedValue({}),
  styleTransfer: vi.fn().mockResolvedValue({}),
  approveRun: vi.fn().mockResolvedValue({}),
  connectWS: () => ({ close: () => {} } as WebSocket),
}))

describe('ArtifactsBoard', () => {
  it('renders cards grouped by category + complete button', async () => {
    render(<ArtifactsBoard runId="r" status="awaiting_approval" onMessage={() => {}} />)
    await waitFor(() => expect(screen.getByText('hero_idle')).toBeInTheDocument())
    expect(screen.getByText('角色与NPC')).toBeInTheDocument()
    expect(screen.getByText('直接保存')).toBeInTheDocument()
    expect(screen.getByText('抠图并保存')).toBeInTheDocument()
    expect(screen.getByText('素材完成')).not.toBeDisabled()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test -- artifacts_board`
Expected: FAIL（`ArtifactsBoard` 未定义）。

- [ ] **Step 3a: client.ts 加 artifacts 函数（末尾追加）**

```ts
export async function getArtifacts(id: string): Promise<any[]> { return j(await fetch(`${BASE}/runs/${id}/artifacts`)) }
export async function startArtifacts(id: string) { return j(await fetch(`${BASE}/runs/${id}/artifacts/start`, { method: 'POST' })) }
export async function saveArtifact(id: string, aid: string) { return j(await fetch(`${BASE}/runs/${id}/artifacts/${aid}/save`, { method: 'POST' })) }
export async function cutoutArtifact(id: string, aid: string) { return j(await fetch(`${BASE}/runs/${id}/artifacts/${aid}/cutout`, { method: 'POST' })) }
export async function retryArtifact(id: string, aid: string, prompt: string) { return j(await fetch(`${BASE}/runs/${id}/artifacts/${aid}/retry`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) })) }
export async function styleTransfer(id: string, styleRef: File, targetAids: string[], prompt?: string) {
  const fd = new FormData(); fd.append('style_ref', styleRef)
  targetAids.forEach(a => fd.append('target_aids', a))
  if (prompt) fd.append('prompt', prompt)
  const r = await fetch(`${BASE}/runs/${id}/artifacts/style-transfer`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text()); return r.json()
}
```

- [ ] **Step 3b: 新建 ArtifactsBoard.tsx**

```tsx
import { useEffect, useState } from 'react'
import { getArtifacts, saveArtifact, cutoutArtifact, retryArtifact, approveRun, connectWS } from '../api/client'
import type { ProgressMsg } from '../types'

type Card = { aid: string; file: string; category: string; matting: boolean; status: string; raw_url: string | null; processed_url: string | null }

export function ArtifactsBoard({ runId, status, onMessage }: { runId: string; status: string; onMessage?: (m: ProgressMsg) => void }) {
  const [cards, setCards] = useState<Card[]>([])

  const refresh = () => getArtifacts(runId).then(setCards).catch(() => {})
  useEffect(() => {
    refresh()
    const ws = connectWS(runId, (m) => { onMessage?.(m); if ((m as any).type === 'asset') refresh() })
    return () => ws.close()
  }, [runId])

  // 按 category 字符串动态分组
  const groups = cards.reduce<Record<string, Card[]>>((acc, c) => { (acc[c.category] ||= []).push(c); return acc }, {})

  return (
    <div style={{ padding: 12 }}>
      <button disabled={status !== 'awaiting_approval'} onClick={() => approveRun(runId)} style={{ marginBottom: 8 }}>素材完成</button>
      {Object.entries(groups).map(([cat, items]) => (
        <div key={cat}>
          <h3>{cat}</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {items.map(c => (
              <div key={c.aid} style={{ border: '1px solid #ccc', padding: 8, width: 180 }}>
                <img src={c.processed_url || c.raw_url || ''} alt={c.file} style={{ width: 120, height: 120, objectFit: 'contain', background: '#eee' }} />
                <div>{c.file}（{c.status}）</div>
                <button onClick={async () => { await saveArtifact(runId, c.aid); refresh() }}>直接保存</button>{' '}
                <button onClick={async () => { await cutoutArtifact(runId, c.aid); refresh() }} disabled={!c.matting}>抠图并保存</button>{' '}
                <button onClick={async () => { const p = prompt('新 prompt', '') || ''; await retryArtifact(runId, c.aid, p); refresh() }}>修改 Prompt 重试</button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3c: App.tsx 按 S3 切 ArtifactsBoard（在 ArtWorkbench 分支后加）**

```tsx
import { ArtifactsBoard } from './stages/ArtifactsBoard'
// ...
      ) : run?.current_stage === 'S3_art_gen' ? (
        <ArtifactsBoard runId={run.id} status={run.status} onMessage={appendMessage} />
      ) : run?.current_stage === 'S2_art_plan' ? (
        <ArtWorkbench runId={run.id} status={run.status} onMessage={appendMessage} />
      ) : (
        <DesignWorkbench runId={run.id} status={run.status} onMessage={appendMessage} />
      )
```

- [ ] **Step 4: 运行前端测试确认通过**

Run: `cd frontend && npm test`
Expected: 全 PASS（含 artifacts_board + 原组件不回归）。

- [ ] **Step 5: 写后端 e2e（mock imagegen）**

```python
"""S3 端到端：mock imagegen 批量生图 → cutout 一张 → approve → S4。"""
import asyncio
import pytest
from io import BytesIO
from PIL import Image
from httpx import AsyncClient, ASGITransport
from agents.tools import do_write_file
from api.runtime import _slug
import pipeline.imagegen as imagegen_mod
import pipeline.orchestrator as orch_mod


def _png(c=(255,0,0)):
    b=BytesIO(); Image.new("RGB",(8,8),c).save(b,"PNG"); return b.getvalue()

ARTLIST = ("## 美术素材清单\n\n| ID | 类别 | 文件名 | 尺寸 | 抠图 |\n|----|------|--------|------|------|\n"
           "| A01 | 角色与NPC | hero_idle | 8x8 | 是 |\n\n"
           "### A01 · 角色与NPC · hero_idle\n```yaml\n"
           "id: A01\ncategory: 角色与NPC\nfile: hero_idle\n"
           'prompt: "像素风少年农夫站姿，纯白背景，无场景，无UI，仅保留角色本体"\n'
           'size: "8x8"\nmatting: true\n```\n')


@pytest.mark.asyncio
async def test_s3_full_flow(monkeypatch, tmp_path):
    # mock ImageGenClient.gen 返回 PNG
    class _FakeClient:
        async def gen(self, prompt, size): return _png()
        async def aclose(self): pass
    monkeypatch.setattr(imagegen_mod, "ImageGenClient", lambda *a, **k: _FakeClient())

    from api.main import app, set_games_root
    set_games_root(tmp_path)
    game_root = tmp_path / _slug("测试游戏")
    (game_root / "docs").mkdir(parents=True)
    (game_root / "docs" / "美术素材.md").write_text(ARTLIST, encoding="utf-8")

    import api.runtime as rt
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await rt.start_art_gen("测试游戏", "测试游戏")
        for _ in range(50):
            st = (await c.get("/api/runs/测试游戏")).json()
            if st["status"] == "awaiting_approval": break
            await asyncio.sleep(0.1)
        assert st["current_stage"] == "S3_art_gen" and st["status"] == "awaiting_approval"
        # 卡片 generated
        items = (await c.get("/api/runs/测试游戏/artifacts")).json()
        assert items[0]["status"] == "generated"
        # cutout 一张 → processed 存在
        await c.post("/api/runs/测试游戏/artifacts/A01/cutout")
        assert (game_root / "assets" / "processed" / "hero_idle.png").exists()
        # approve → S4
        await c.post("/api/runs/测试游戏/approve")
        st2 = (await c.get("/api/runs/测试游戏")).json()
        assert st2["current_stage"] == "S4_coding" and st2["status"] == "not_implemented"
```

- [ ] **Step 6: 运行 e2e + 全量确认无回归**

Run: `D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests/test_e2e_s3.py -v && D:/Anaconda3/envs/agent_env/python.exe -m pytest backend/tests -q`
Expected: e2e PASS + 全量无回归。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/stages/ArtifactsBoard.tsx frontend/src/api/client.ts frontend/src/App.tsx frontend/src/__tests__/artifacts_board.test.tsx backend/tests/test_e2e_s3.py
git commit -m "feat(frontend): ArtifactsBoard + S3 e2e flow"
```

---

## Self-Review（执行后核对）

- **spec 覆盖**：parser(Task1) ✓、imagegen(Task2) ✓、styletransfer(Task3) ✓、cutout(Task4) ✓、storage(Task5) ✓、配置(Task6) ✓、orchestrator(Task7) ✓、FSM+runtime(Task8) ✓、routes(Task9) ✓、前端+e2e(Task10) ✓。C 盘约束 REMBG_MODELS_DIR(Task4/6) ✓、类别可扩展(Task1 含 6 类别) ✓、抠图逐张按需(Task9 save/cutout) ✓、retry/风格转绘删过时 processed(Task9) ✓。
- **类型一致**：`AssetSpec`、`ImageGenClient`、`StyleTransferClient`、`cutout`、`save_raw/save_processed/raw_path/processed_path/has_processed`、`run_art_pipeline`、`start_art_gen` 跨 Task 签名一致。
- **未验证项（执行期 Task 9 / 可选手动）**：imagegen 端点 size 分隔符（默认 `*`）与返回形态、styletransfer 原生 vs 降级（默认 prompt 降级）——spec 已标，执行时真调用确认后定型。
- **占位符**：无 TBD/TODO；每个 step 含完整代码（`artifacts_list` 的 saved/cutout 状态按 PNG alpha 通道精确推断）。
