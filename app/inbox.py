from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models import PromptItem
from app.repo.prompts import count_prompts, list_prompts

INBOX_WAITING_LIMIT = 50
INBOX_PENDING_FETCH_LIMIT = INBOX_WAITING_LIMIT + 1
QUEUE_PREVIEW_LENGTH = 120


@dataclass(frozen=True, slots=True)
class InboxPromptCard:
    id: str
    seq: int
    source: str
    body: str
    metadata: dict[str, Any] | None
    copy_count: int
    created_at: str
    age_label: str


@dataclass(frozen=True, slots=True)
class InboxQueueEntry:
    id: str
    seq: int
    source: str
    preview: str
    created_at: str
    age_label: str


@dataclass(frozen=True, slots=True)
class InboxView:
    current_prompt: InboxPromptCard | None
    queued_prompts: list[InboxQueueEntry]
    queue_count: int
    waiting_count: int
    window_title: str


def build_inbox_view(connection) -> InboxView:
    queue_count = count_prompts(connection, status="pending")
    pending_prompts = list_prompts(
        connection,
        status="pending",
        limit=INBOX_PENDING_FETCH_LIMIT,
    )
    current_prompt = pending_prompts[0] if pending_prompts else None
    waiting_prompts = pending_prompts[1:] if pending_prompts else []

    return InboxView(
        current_prompt=_to_prompt_card(current_prompt),
        queued_prompts=[_to_queue_entry(prompt) for prompt in waiting_prompts],
        queue_count=queue_count,
        waiting_count=max(queue_count - 1, 0),
        window_title=_window_title(queue_count),
    )


def _to_prompt_card(prompt: PromptItem | None) -> InboxPromptCard | None:
    if prompt is None:
        return None

    return InboxPromptCard(
        id=prompt.id,
        seq=prompt.seq,
        source=prompt.source,
        body=prompt.body,
        metadata=prompt.metadata,
        copy_count=prompt.copy_count,
        created_at=prompt.created_at,
        age_label=_age_label(prompt.created_at),
    )


def _to_queue_entry(prompt: PromptItem) -> InboxQueueEntry:
    return InboxQueueEntry(
        id=prompt.id,
        seq=prompt.seq,
        source=prompt.source,
        preview=_preview_text(prompt.body),
        created_at=prompt.created_at,
        age_label=_age_label(prompt.created_at),
    )


def _preview_text(value: str) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= QUEUE_PREVIEW_LENGTH:
        return collapsed
    return f"{collapsed[: QUEUE_PREVIEW_LENGTH - 3].rstrip()}..."


def _age_label(value: str) -> str:
    created_at = _parse_timestamp(value)
    delta_seconds = max(
        int((datetime.now(UTC) - created_at).total_seconds()),
        0,
    )
    if delta_seconds < 10:
        return "just now"
    if delta_seconds < 60:
        return f"{delta_seconds}s ago"

    delta_minutes = delta_seconds // 60
    if delta_minutes < 60:
        unit = "minute" if delta_minutes == 1 else "minutes"
        return f"{delta_minutes} {unit} ago"

    delta_hours = delta_minutes // 60
    if delta_hours < 24:
        unit = "hour" if delta_hours == 1 else "hours"
        return f"{delta_hours} {unit} ago"

    delta_days = delta_hours // 24
    unit = "day" if delta_days == 1 else "days"
    return f"{delta_days} {unit} ago"


def _window_title(queue_count: int) -> str:
    if queue_count <= 0:
        return "HumanLoop Inbox"

    return f"HumanLoop Inbox ({queue_count} pending)"


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
