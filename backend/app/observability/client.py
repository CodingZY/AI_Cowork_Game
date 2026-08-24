from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.config.settings import get_settings


@lru_cache
def get_langfuse() -> Optional["Langfuse"]:  # noqa: F821
    """进程级 Langfuse 单例。

    public_key/secret_key 皆空时返回 None —— 不初始化 Langfuse，
    避免每次调用打印 "Client will be disabled" warning 噪音。
    tracing 层据此跳过 Langfuse 上报；业务表（聚合源）仍照常写。
    """
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        base_url=s.langfuse_base_url,
        tracing_enabled=True,
    )
