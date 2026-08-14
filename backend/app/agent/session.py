from __future__ import annotations

from pathlib import Path

from app.config.settings import get_settings


def ensure_workspace(project_key: str, base: Path | None = None) -> Path:
    """创建 `<base>/<project_key>/` 目录并返回路径，幂等。

    base 缺省时取 get_settings().workspace_base（<repo>/Games）。
    project_key 可含子路径（如 "a/b"），parents=True 保证父级一并建。
    """
    root = base if base is not None else get_settings().workspace_base
    p = root / project_key
    p.mkdir(parents=True, exist_ok=True)
    return p
