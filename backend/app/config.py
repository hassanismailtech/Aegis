"""Environment for Aegis: every variable in PRD 7.5, loaded from .env."""

from typing import Literal

from pydantic import Field
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
    ner_runtime: Literal["torch", "onnx"] = "torch"
    ner_onnx_dir: str = "data/ner_onnx"
    ner_onnx_file: str = "model_quantized.onnx"
    ner_cache_ttl_seconds: int = Field(default=300, ge=0)
    ner_cache_max_entries: int = Field(default=512, ge=1)
    eval_recall_floor: float = Field(default=0.85, ge=0, le=1)
    fee_usd_per_1k_tokens: float = 0.001
    cors_origins: str = "http://localhost:3000"
    detector_packs: list[str] = ["ng"]
    aegis_demo_token: str = ""
    aegis_keys_file: str = ""
    aegis_ticket_secret: str = ""
    aegis_insecure_dev: bool = False
    bind_host: str = "0.0.0.0"
    max_body_bytes: int = Field(default=1_048_576, ge=1)
    max_messages: int = Field(default=200, ge=1)
    rate_limit_capacity: int = Field(default=60, ge=1)
    rate_limit_refill_per_second: float = Field(default=1.0, gt=0)
    audit_db_path: str = "data/audit.db"


settings = Settings()
