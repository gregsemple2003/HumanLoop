from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PromptStatus = Literal["pending", "completed", "dismissed"]

MAX_BODY_LENGTH = 200_000
MAX_SOURCE_LENGTH = 128
MAX_IDEMPOTENCY_KEY_LENGTH = 256


def _require_non_blank_text(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


def _normalize_identifier(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class PromptIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=MAX_BODY_LENGTH)
    source: str = Field(min_length=1, max_length=MAX_SOURCE_LENGTH)
    idempotency_key: str = Field(
        min_length=1,
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
    )
    metadata: dict[str, Any] | None = None

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return _require_non_blank_text(value)

    @field_validator("source", "idempotency_key")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return _normalize_identifier(value)

    def normalized_metadata(self) -> dict[str, Any] | None:
        return self.metadata or None

    def metadata_json(self) -> str | None:
        metadata = self.normalized_metadata()
        if metadata is None:
            return None
        return json.dumps(metadata, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class PromptItem:
    id: str
    seq: int
    source: str
    idempotency_key: str
    body: str
    metadata: dict[str, Any] | None
    status: PromptStatus
    copy_count: int
    last_copied_at: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    dismissed_at: str | None


class PromptResponse(BaseModel):
    id: str
    seq: int
    source: str
    idempotency_key: str
    body: str
    metadata: dict[str, Any] | None = None
    status: PromptStatus
    copy_count: int
    last_copied_at: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    dismissed_at: str | None = None
    replayed: bool = False

    @classmethod
    def from_prompt(
        cls,
        prompt: PromptItem,
        replayed: bool = False,
    ) -> "PromptResponse":
        return cls(
            id=prompt.id,
            seq=prompt.seq,
            source=prompt.source,
            idempotency_key=prompt.idempotency_key,
            body=prompt.body,
            metadata=prompt.metadata,
            status=prompt.status,
            copy_count=prompt.copy_count,
            last_copied_at=prompt.last_copied_at,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
            completed_at=prompt.completed_at,
            dismissed_at=prompt.dismissed_at,
            replayed=replayed,
        )


class PromptQueueHeadResponse(BaseModel):
    id: str
    seq: int
    source: str

    @classmethod
    def from_prompt(cls, prompt: PromptItem) -> "PromptQueueHeadResponse":
        return cls(
            id=prompt.id,
            seq=prompt.seq,
            source=prompt.source,
        )


class PromptQueueSummaryResponse(BaseModel):
    pending_count: int
    current_prompt: PromptQueueHeadResponse | None = None
    latest_pending_seq: int | None = None


class HealthzResponse(BaseModel):
    status: Literal["ok"] = "ok"
