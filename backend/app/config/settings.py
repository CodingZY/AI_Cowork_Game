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
