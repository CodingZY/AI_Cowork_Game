from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.ai.image_client import ImageGenClient


def _unconfigured() -> ImageGenClient:
    """构造未配置的 client（enabled=False → 占位图），不受 .env 真值影响。"""
    c = ImageGenClient.__new__(ImageGenClient)
    c.base_url = ""
    c.api_key = "sk-anything"
    c.enabled = False
    return c


# --- 占位图（未配置 API）---


async def test_placeholder_when_not_configured(tmp_path):
    """未配置 → enabled=False → 生占位图 PNG。"""
    c = _unconfigured()
    assert c.enabled is False
    out = tmp_path / "ANIMAL-001.png"
    res = await c.generate("ANIMAL-001", "animal", "a cow", width=256, height=256, out_path=out)
    assert res["model"] == "placeholder"
    assert res["status"] == "success"
    assert Path(res["image_path"]).exists()
    im = Image.open(out)
    assert im.size == (256, 256)
    # 占位图非全白（rembg 有东西可抠）
    import numpy as np
    arr = np.array(im.convert("RGB"))
    assert (arr != 255).any()


async def test_placeholder_category_coloring(tmp_path):
    """不同 category 不同配色（图内容不同）。"""
    c = _unconfigured()
    out1 = tmp_path / "a.png"
    out2 = tmp_path / "b.png"
    await c.generate("ANIMAL-001", "animal", "cow", width=64, height=64, out_path=out1)
    await c.generate("PLANT-001", "plant", "tree", width=64, height=64, out_path=out2)
    import numpy as np
    a1 = np.array(Image.open(out1).convert("RGB"))
    a2 = np.array(Image.open(out2).convert("RGB"))
    assert not (a1 == a2).all()


# --- 真模式（mock httpx，raw 返回 PNG 二进制）---


class _FakeRawResponse:
    """模拟 raw 模式响应：status_code + content（PNG 字节）+ text。"""
    def __init__(self, content: bytes, status=200):
        self.content = content
        self.status_code = status
        self.text = content.decode("utf-8", "replace") if status >= 400 else ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, png_bytes: bytes, status: int = 200):
        self._png = png_bytes
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        return _FakeRawResponse(self._png, status=self._status)


async def test_autodl_raw_writes_png(tmp_path, monkeypatch):
    """enabled=True + raw 模式 → r.content 即 PNG 字节，直接写盘。"""
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    c = ImageGenClient.__new__(ImageGenClient)
    c.base_url = "https://autodl.example.com"
    c.api_key = "sk-anything"
    c.enabled = True
    monkeypatch.setattr(
        "app.ai.image_client.httpx.AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(png),
    )
    out = tmp_path / "CHAR-001.png"
    res = await c.generate("CHAR-001", "character", "a hero", seed=42, out_path=out)
    assert res["model"] == "Hunyuan-DiT"
    assert res["seed"] == 42
    assert Path(res["image_path"]).exists()
    assert Path(res["image_path"]).read_bytes() == png


async def test_autodl_503_raises_for_retry(tmp_path, monkeypatch):
    """503 排队超时 → raise，让 workflow RetryPolicy 重试。"""
    c = ImageGenClient.__new__(ImageGenClient)
    c.base_url = "https://autodl.example.com"
    c.api_key = "sk-anything"
    c.enabled = True
    monkeypatch.setattr(
        "app.ai.image_client.httpx.AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(b"not png", status=503),
    )
    out = tmp_path / "x.png"
    raised = False
    try:
        await c.generate("X-001", "prop", "x", out_path=out)
    except RuntimeError as e:
        raised = True
        assert "503" in str(e)
    assert raised


# --- seedream（金山云 KSPMAS，images/generations + b64_json）---


def _seedream_client():
    """构造 seedream client（enabled=True）。"""
    c = ImageGenClient.__new__(ImageGenClient)
    c.model = "seedream"
    c.base_url = "https://kspmas.ksyun.com"
    c.api_key = "sk-kimi"
    c.seedream_model = "seedream-5.0-pro-domestic"
    c.enabled = True
    return c


class _FakeSeedreamResponse:
    """模拟 seedream 响应：JSON 含 data[0].b64_json 或 data[0].url。"""
    def __init__(self, payload: dict, status=200):
        import json
        self.content = json.dumps(payload).encode()
        self.status_code = status
        self.text = "" if status < 400 else "err"

    def json(self):
        import json
        return json.loads(self.content)


class _FakeSeedreamAsyncClient:
    """seedream 两次调用：POST 生成 + 可能 GET 下载 url。b64 模式只 POST。"""
    def __init__(self, payload: dict):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        return _FakeSeedreamResponse(self._payload)

    async def get(self, url):
        return _FakeRawResponse(b"\x89PNG fake", status=200)


async def test_seedream_b64_json_writes_png(tmp_path, monkeypatch):
    """seedream + b64_json → 解码 base64 写盘。"""
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    payload = {"data": [{"b64_json": base64.b64encode(png).decode()}]}
    c = _seedream_client()
    monkeypatch.setattr(
        "app.ai.image_client.httpx.AsyncClient",
        lambda *a, **kw: _FakeSeedreamAsyncClient(payload),
    )
    out = tmp_path / "CHAR-001.png"
    res = await c.generate("CHAR-001", "character", "a hero", seed=7, out_path=out)
    assert res["model"] == "seedream"
    assert res["seed"] == 7
    assert Path(res["image_path"]).read_bytes() == png


async def test_seedream_url_fallback_downloads(tmp_path, monkeypatch):
    """seedream 无 b64_json 只有 url → 下载 url 写盘。"""
    payload = {"data": [{"url": "https://tos.example.com/img.png"}]}
    c = _seedream_client()
    monkeypatch.setattr(
        "app.ai.image_client.httpx.AsyncClient",
        lambda *a, **kw: _FakeSeedreamAsyncClient(payload),
    )
    out = tmp_path / "PLANT-001.png"
    res = await c.generate("PLANT-001", "plant", "a tree", out_path=out)
    assert res["model"] == "seedream"
    assert Path(res["image_path"]).read_bytes() == b"\x89PNG fake"


def test_seedream_size_floor():
    """size 面积 < 921600 会被 clamp：256² → 960×960（边长下限 960，面积正好 921600 满足约束）。"""
    from app.ai.image_client import _seedream_size
    assert _seedream_size(256, 256) == "960x960"
    assert _seedream_size(1024, 1024) == "1024x1024"
    assert _seedream_size(960, 960) == "960x960"
    # 768×768=589824 <921600 → clamp 到 960×960
    assert _seedream_size(768, 768) == "960x960"
