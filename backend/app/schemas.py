"""Wire contracts: request model (PRD 5.1), entity types (PRD 6), telemetry (PRD 7.3)."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EntityType(str, Enum):
    PERSON = "PERSON"
    PHONE = "PHONE"
    BVN = "BVN"
    NIN = "NIN"
    ACCOUNT_NO = "ACCOUNT_NO"
    EMAIL = "EMAIL"


class ChatRequest(BaseModel):
    """Unknown fields pass through untouched (PRD 5.1)."""

    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[dict[str, Any]]
    stream: bool = False


class MessagesRequest(BaseModel):
    """Anthropic Messages request; unknown fields pass through untouched."""

    model_config = ConfigDict(extra="allow")

    model: str
    max_tokens: int = Field(gt=0)
    messages: list[dict[str, Any]]
    system: str | list[dict[str, Any]] | None = None
    stream: bool = False


class TelemetryEvent(BaseModel):
    """Exactly the JSON in PRD 7.3."""

    request_id: str
    ts: str
    session: str
    model: str
    stream_requested: bool = False
    entities: dict[EntityType, int] = Field(
        default_factory=lambda: {entity_type: 0 for entity_type in EntityType}
    )
    entities_total: int
    scrub_ms: float
    reinject_ms: float
    upstream_ms: float
    overhead_ms: float
    unresolved: int
    status: Literal["ok", "state_loss", "scrub_blocked", "upstream_error"]
    fee_usd: float
