from __future__ import annotations

from pathlib import Path

from app.config.settings import REPO_ROOT

# 本地 rembg 模型（项目根 .rembg_models/u2net.onnx），避免 rembg 默认下载到
# C 盘 ~/.u2net（C 盘空间约束，见 memory c-drive-space-constraint）。
_REMBG_MODEL = REPO_ROOT / ".rembg_models" / "u2net.onnx"

_rembg_session = None  # 进程级缓存（rembg session 加载 ONNX 重，只建一次）


def _get_rembg_session():
    """懒加载 rembg u2net session，复用本地 .onnx。"""
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session

        _rembg_session = new_session("u2net", model_path=str(_REMBG_MODEL))
    return _rembg_session


def remove_background(image) -> "Image":
    """rembg 抠图：PIL Image (RGB) → RGBA（背景透明）。"""
    from rembg import remove

    return remove(image, session=_get_rembg_session())


def _alpha_bbox(image) -> tuple[int, int, int, int] | None:
    """算 alpha 通道非零像素的 bbox (left, top, right, bottom)；无内容返 None。"""
    import numpy as np

    if image.mode != "RGBA":
        return None
    arr = np.array(image)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def _autocrop(image) -> "Image":
    """按 alpha bbox 裁剪掉透明边距，只留有内容区域。"""
    bbox = _alpha_bbox(image)
    if bbox is None:
        return image
    return image.crop(bbox)


def _pad_to_square(image, fill=(0, 0, 0, 0)) -> "Image":
    """把非正方形图居中 padding 成正方形（透明填充）。"""
    from PIL import Image

    w, h = image.size
    if w == h:
        return image
    side = max(w, h)
    canvas = Image.new(image.mode, (side, side), fill)
    canvas.paste(image, ((side - w) // 2, (side - h) // 2))
    return canvas


def _resize(image, size: int) -> "Image":
    """缩放到 size×size（LANCZOS）。"""
    return image.resize((size, size), __import__("PIL.Image", fromlist=["LANCZOS"]).LANCZOS)


def run_image_pipeline(
    raw_path: Path,
    post_process: dict,
    cwd: Path,
    asset_id: str,
    category: str,
    final_size: int = 256,
) -> dict:
    """生图后处理：rembg(按需) → alpha校验 → autocrop → pad → resize → PNG。

    写 processed/{cat}/{id}.png（去背景后）和 final/{cat}/{id}.png（标准化尺寸）。
    幂等：输入 raw 不动；输出存在则覆盖（重新后处理）。

    返 {processed_path, final_path, status}。
    """
    from PIL import Image

    raw_path = Path(raw_path)
    cwd = Path(cwd)
    img = Image.open(raw_path).convert("RGBA")
    # map/ui 等 remove_background=False 时跳过 rembg
    if post_process.get("remove_background", True):
        try:
            img = remove_background(img)
        except Exception:
            # rembg 失败不阻断（占位图或同机未装时），用原图 RGBA 继续
            pass
    else:
        # 保留底色，不抠
        img = img.convert("RGBA")

    # crop + pad + resize（post_process 控制每步开关，默认全开）
    if post_process.get("crop", True):
        img = _autocrop(img)
    if post_process.get("resize", True):
        img = _pad_to_square(img)
        img = _resize(img, final_size)

    fmt = post_process.get("format", "png")
    cat_dir = _category_dir(category)
    processed_path = cwd / "assets" / "processed" / cat_dir / f"{asset_id}.{fmt}"
    final_path = cwd / "assets" / "final" / cat_dir / f"{asset_id}.{fmt}"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(processed_path, fmt.upper() if fmt != "png" else "PNG")
    # processed 与 final 同物（本方案简化：processed=去背景图，final=标准化图）；
    # 若 resize 关闭则 processed 即 final。
    if post_process.get("resize", True):
        img.save(final_path, "PNG")
    else:
        # 关闭 resize 时 final 复制 processed
        final_path.write_bytes(processed_path.read_bytes())
    return {
        "processed_path": str(processed_path),
        "final_path": str(final_path),
        "status": "PROCESSED",
    }


def _category_dir(category: str) -> str:
    """category → assets 子目录名（复数化，对齐文档 §13 目录结构）。"""
    plurals = {
        "character": "characters",
        "npc": "npcs",
        "building": "buildings",
        "animal": "animals",
        "plant": "plants",
        "prop": "props",
        "map": "maps",
        "ui": "ui",
        "icon": "icons",
    }
    return plurals.get(category, category)
