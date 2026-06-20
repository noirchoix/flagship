from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_name: str = "ShipGate Launch Readiness Auditor API"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_path: str = "data/shipgate/shipgate.sqlite3"
    upload_dir: str = "data/shipgate/uploads"
    max_upload_mb: int = 25
    max_file_count: int = 2500
    max_read_file_kb: int = 512
    max_context_chars: int = 60000
    llm_provider: str = "offline"
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: int = 45
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="SHIPGATE_",
    )

    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def uploads_path(self) -> Path:
        p = Path(self.upload_dir)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def cors_list(self) -> list[str]:
        return [x.strip().rstrip("/") for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()

# Allow ShipGate to use the suite-level API keys when module-specific values are blank.
if not settings.deepseek_api_key:
    settings.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
if not settings.gemini_api_key:
    settings.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

settings.uploads_path.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
