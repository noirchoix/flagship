from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="production", alias="ENVIRONMENT")
    api_prefix: str = Field(default="/api/v1", alias="AI_SUITE_API_PREFIX")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", alias="AI_SUITE_CORS_ORIGINS")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")
    trusted_hosts: str = Field(default="*", alias="TRUSTED_HOSTS")
    request_id_header: str = Field(default="X-Request-ID", alias="REQUEST_ID_HEADER")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    memory_debug: bool = Field(default=False, alias="AI_SUITE_MEMORY_DEBUG")
    memory_safe_mode: bool = Field(default=True, alias="AI_SUITE_MEMORY_SAFE_MODE")
    max_upload_bytes: int = Field(default=80 * 1024 * 1024, alias="AI_SUITE_MAX_UPLOAD_BYTES")

    @property
    def cors_list(self) -> list[str]:
        origins = [x.strip().rstrip("/") for x in self.cors_origins.split(",") if x.strip()]
        return origins or ["*"]

    @property
    def trusted_hosts_list(self) -> list[str]:
        hosts = [x.strip() for x in self.trusted_hosts.split(",") if x.strip()]
        return hosts or ["*"]

settings = Settings()
