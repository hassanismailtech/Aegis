"""Environment for Aegis: every variable in PRD 7.5, loaded from .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    upstream_base_url: str = "http://localhost:9000/v1"
    upstream_api_key: str = ""
    upstream_model_override: str = ""
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 300
    ner_enabled: bool = True
    ner_model: str = "urchade/gliner_small-v2.1"
    ner_threshold: float = 0.5
    ner_timeout_ms: int = 2000
    fee_usd_per_1k_tokens: float = 0.001
    cors_origins: str = "http://localhost:3000"


settings = Settings()
