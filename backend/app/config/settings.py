from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)

# backend/app/config/settings.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / "backend" / ".env", extra="ignore"
    )

    anthropic_base_url: str
    anthropic_auth_token: str
    anthropic_model: str
    db_url: str
    redis_url: str = "redis://127.0.0.1:6379/0"
    arq_queue: str = "agent"
    workspace_root: str = "workspace"
    github_repo_url: str = ""
    github_pat: str = ""
    git_branch_prefix: str = "agent"
    game_skills_dir: str = "backend/game-skills"
    temporal_host: str = "localhost"
    temporal_port: int = 7233
    temporal_namespace: str = "default"
    temporal_task_queue: str = "game-design"
    # === Phase 2: AutoDL Hunyuan-DiT 生图 ===
    # 两者皆空时 ImageGenClient 返回占位图（端到端跑通 rembg/后处理链路）。
    autodl_base_url: str = ""
    autodl_api_key: str = ""
    art_assets_parallel: int = 4
    # === seedream 文生图（金山云 KSPMAS，独立配置；默认仍指向金山云 + 复用 kimi key） ===
    # 走标准 OpenAI images 端点 {base}/v1/images/generations，返回 b64_json；与 Hunyuan 二选一（per-project art-model.txt）。
    # seedream_api_key 留空时 fallback 用 anthropic_auth_token（kimi 同 key），无需重复填写。
    seedream_base_url: str = "https://kspmas.ksyun.com"
    seedream_api_key: str = ""
    seedream_model: str = "seedream-5.0-pro-domestic"
    # === Observability (Langfuse) ===
    # 两者皆空时 get_langfuse() 返回 None，埋点静默跳过 Langfuse 上报（业务表仍写）。
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "http://localhost:3000"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # .env 文件优先于宿主环境变量：本机 kscc 会话 shell 挂了
        # ANTHROPIC_MODEL=glm-5.2 等变量，会覆盖 .env 的 kimi-k3，导致
        # runtime 子进程拿到错误模型。故 dotenv 压过 env。
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    @property
    def workspace_base(self) -> Path:
        return REPO_ROOT / self.workspace_root


@lru_cache
def get_settings() -> Settings:
    return Settings()
