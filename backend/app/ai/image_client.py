from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx

from app.config.settings import get_settings, REPO_ROOT


# category → 占位图配色（让 rembg 有彩色形状可抠、留 alpha）。
# 9 类对应 art-asset-spec SKILL 的 Asset Categories。
_CATEGORY_COLORS = {
    "character": "#e8a87c",  # 暖肤色
    "npc": "#c38d9e",
    "building": "#85929e",
    "animal": "#f6b93b",
    "plant": "#78e08f",
    "prop": "#82ccdd",
    "map": "#bdc3c7",
    "ui": "#9b59b6",
    "icon": "#48dbfb",
}


def _normalize_size(width: int, height: int) -> str:
    """AutoDL Hunyuan 网关要求 size 256..1536 且对 8 取整，返 "WxH" 字符串。"""
    def clamp8(v: int) -> int:
        v = max(256, min(1536, int(v)))
        return v - (v % 8)
    return f"{clamp8(width)}x{clamp8(height)}"


def _seedream_size(width: int, height: int) -> str:
    """金山云 seedream 要求图像面积 ≥ 921600 且边长 16 倍数；clamp 每边 [960, 2048]。
    面积不足 921600 时提到 1024×1024（实测 768²=589824 会 400）。"""
    def clamp16(v: int) -> int:
        v = max(960, min(2048, int(v)))
        return v - (v % 16)
    w, h = clamp16(width), clamp16(height)
    if w * h < 921600:
        w = h = 1024
    return f"{w}x{h}"


class ImageGenClient:
    """文生图客户端，按 model 分派 Hunyuan-DiT 或 seedream 后端。

    - ``model="hunyuan"``（默认）：AutoDL Hunyuan 网关 ``/v1/images/generations``，
      ``response_format=raw`` 直接返 PNG 二进制。配置取 ``autodl_base_url``/``autodl_api_key``。
    - ``model="seedream"``：金山云 KSPMAS ``/v1/images/generations``，``response_format=b64_json``
      返 base64 解码写盘。配置取独立的 ``seedream_base_url``/``seedream_api_key``/``seedream_model``；
      ``seedream_api_key`` 留空时 fallback 用 ``anthropic_auth_token``（kimi 同 key，无需重复填）。

    任一后端未配置（对应 key/base 空）返**占位图**——按 category 上色 + asset_id 水印的白底 PNG。
    换 API / 换模型只改本类，上层（activity/workflow）零改动（model 由调用方传入）。
    """

    def __init__(self, settings=None, model: str = "hunyuan"):
        s = settings or get_settings()
        self.model = model
        if self.model == "seedream":
            self.base_url = s.seedream_base_url.rstrip("/") if s.seedream_base_url else ""
            # seedream_api_key 留空时 fallback 用 kimi key（anthropic_auth_token）
            self.api_key = s.seedream_api_key or s.anthropic_auth_token or ""
            self.seedream_model = s.seedream_model
            self.enabled = bool(self.base_url and self.api_key)
        else:
            self.base_url = s.autodl_base_url.rstrip("/") if s.autodl_base_url else ""
            self.api_key = s.autodl_api_key or "sk-anything"
            self.enabled = bool(s.autodl_base_url)

    async def generate(
        self,
        asset_id: str,
        category: str,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        cfg: float = 7.5,
        seed: Optional[int] = None,
        out_path: Path | None = None,
    ) -> dict:
        """生图写到 out_path。返回 {asset_id, status, image_path, seed, model}。

        out_path 缺省取 .env/调用方指定；调用方（activity）负责拼绝对路径并传入。
        """
        if out_path is None:
            raise ValueError("out_path is required")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.enabled:
            return await self._placeholder(asset_id, category, width, height, out_path)

        # getattr 兜底：测试用 __new__ 跳过 __init__ 时不设 model，默认走 hunyuan
        if getattr(self, "model", "hunyuan") == "seedream":
            return await self._seedream_generate(
                asset_id, prompt, negative_prompt, width, height, seed, out_path
            )
        return await self._autodl_generate(
            asset_id, prompt, negative_prompt, width, height, steps, cfg, seed, out_path
        )

    # ── 真实 API（AutoDL Hunyuan 网关，OpenAI 兼容，raw 模式）─────────
    async def _autodl_generate(
        self, asset_id, prompt, negative_prompt, width, height, steps, cfg, seed, out_path
    ) -> dict:
        body = {
            "prompt": prompt,
            "model": "hunyuan-dit-v1.1",
            "n": 1,
            "size": _normalize_size(width, height),
            "response_format": "raw",  # 直接返 PNG 二进制，无需 base64
            "negative_prompt": negative_prompt or
                "blurry, lowres, watermark, text, signature, deformed, extra limbs",
            "steps": max(1, min(50, int(steps))),
            "cfg": max(1.0, min(20.0, float(cfg))),
        }
        if seed is not None:
            body["seed"] = int(seed)
        # 网关全局串行锁，单图 3-30s，排队超时 120s；timeout 留足
        async with httpx.AsyncClient(timeout=300) as c:
            r = await c.post(
                f"{self.base_url}/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code != 200:
                # 503 排队超时 / 504 生成超时 / 502 ComfyUI 失败 → 上层 RetryPolicy 重试
                raise RuntimeError(
                    f"AutoDL generate failed: HTTP {r.status_code} {r.text[:200]}"
                )
            # raw 模式：响应体即 PNG 字节
            out_path.write_bytes(r.content)
        return {
            "asset_id": asset_id,
            "status": "success",
            "image_path": str(out_path),
            "seed": int(seed) if seed is not None else 0,
            "model": "Hunyuan-DiT",
        }

    # ── 真实 API（金山云 KSPMAS seedream，OpenAI images 兼容，b64_json）──
    async def _seedream_generate(
        self, asset_id, prompt, negative_prompt, width, height, seed, out_path
    ) -> dict:
        """金山云 seedream：POST {host}/v1/images/generations，response_format=b64_json。

        实测（spike）：端点是 images/generations（非 chat/completions）；返回 data[0].b64_json
        或 data[0].url（24h 签名）；size 面积须 ≥921600（边长 clamp ≥960）。
        """
        body = {
            "model": self.seedream_model,
            "prompt": prompt,
            "n": 1,
            "size": _seedream_size(width, height),
            "response_format": "b64_json",
        }
        if negative_prompt:
            body["negative_prompt"] = negative_prompt
        if seed is not None:
            body["seed"] = int(seed)
        async with httpx.AsyncClient(timeout=300) as c:
            r = await c.post(
                f"{self.base_url}/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code != 200:
                raise RuntimeError(
                    f"seedream generate failed: HTTP {r.status_code} {r.text[:200]}"
                )
            import base64
            data = r.json().get("data") or []
            if not data:
                raise RuntimeError("seedream: empty data in response")
            item = data[0]
            b64 = item.get("b64_json")
            if b64:
                out_path.write_bytes(base64.b64decode(b64))
            elif item.get("url"):
                # 兜底：b64 缺则下载 url（签名 24h 有效）
                img = await c.get(item["url"])
                if img.status_code != 200:
                    raise RuntimeError(f"seedream url download failed: HTTP {img.status_code}")
                out_path.write_bytes(img.content)
            else:
                raise RuntimeError("seedream: no b64_json or url in data[0]")
        return {
            "asset_id": asset_id,
            "status": "success",
            "image_path": str(out_path),
            "seed": int(seed) if seed is not None else 0,
            "model": "seedream",
        }

    # ── 占位图（未配置 API）────────────────────────────────────────
    async def _placeholder(self, asset_id, category, width, height, out_path) -> dict:
        """按 category 上色 + asset_id 水印的白底 PNG。

        白底 + 彩色圆角矩形（中心，留白边），让 rembg 能去白底留彩色形状 →
        下游 alpha 校验 / crop / resize 全链路可跑通。
        """
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (width, height), "white")
        d = ImageDraw.Draw(img)
        color = _CATEGORY_COLORS.get(category, "#888888")
        # 中心圆角矩形占 70%，留 15% 白边（rembg 去白底后剩彩色形状带 alpha）
        margin_x, margin_y = int(width * 0.15), int(height * 0.15)
        d.rounded_rectangle(
            (margin_x, margin_y, width - margin_x, height - margin_y),
            radius=min(width, height) // 12,
            fill=color,
        )
        # asset_id 水印（白色文字居中，大字）
        try:
            d.text(
                (width // 2, height // 2), asset_id, fill="white", anchor="mm"
            )
        except Exception:
            pass  # 默认字体缺失时跳过文字，不影响形状
        img.save(out_path, "PNG")
        return {
            "asset_id": asset_id,
            "status": "success",
            "image_path": str(out_path),
            "seed": 0,
            "model": "placeholder",
        }
