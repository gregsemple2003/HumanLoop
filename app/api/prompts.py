from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db import get_connection
from app.models import PromptIngestRequest, PromptItem, PromptResponse, PromptStatus
from app.repo.prompts import (
    IdempotencyConflictError,
    PromptNotFoundError,
    PromptStateConflictError,
    complete_prompt,
    dismiss_prompt,
    get_next_prompt,
    get_prompt_by_id,
    ingest_prompt,
    list_prompts,
    record_prompt_copied,
    requeue_prompt,
)

router = APIRouter(tags=["prompts"])
DatabaseConnection = Annotated[sqlite3.Connection, Depends(get_connection)]


@router.post(
    "/api/prompts",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt(
    payload: PromptIngestRequest,
    response: Response,
    connection: DatabaseConnection,
) -> PromptResponse:
    try:
        prompt, replayed = ingest_prompt(connection, payload)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if replayed:
        response.status_code = status.HTTP_200_OK

    return PromptResponse.from_prompt(prompt, replayed=replayed)


@router.get(
    "/api/prompts",
    response_model=list[PromptResponse],
)
def get_prompts(
    connection: DatabaseConnection,
    prompt_status: Annotated[
        PromptStatus,
        Query(alias="status"),
    ] = "pending",
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> list[PromptResponse]:
    prompts = list_prompts(connection, status=prompt_status, limit=limit)
    return [PromptResponse.from_prompt(prompt) for prompt in prompts]


@router.get(
    "/api/prompts/next",
    response_model=PromptResponse,
)
def get_next_pending_prompt(
    connection: DatabaseConnection,
) -> PromptResponse:
    prompt = get_next_prompt(connection)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending prompts found.",
        )
    return PromptResponse.from_prompt(prompt)


@router.get(
    "/api/prompts/{prompt_id}",
    response_model=PromptResponse,
)
def get_prompt(
    prompt_id: str,
    connection: DatabaseConnection,
) -> PromptResponse:
    prompt = get_prompt_by_id(connection, prompt_id)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found.",
        )
    return PromptResponse.from_prompt(prompt)


@router.post(
    "/api/prompts/{prompt_id}/copied",
    response_model=PromptResponse,
)
def copied_prompt(
    prompt_id: str,
    connection: DatabaseConnection,
) -> PromptResponse:
    prompt = _run_prompt_action(
        lambda: record_prompt_copied(connection, prompt_id),
    )
    return PromptResponse.from_prompt(prompt)


@router.post(
    "/api/prompts/{prompt_id}/complete",
    response_model=PromptResponse,
)
def complete_prompt_item(
    prompt_id: str,
    connection: DatabaseConnection,
) -> PromptResponse:
    prompt = _run_prompt_action(
        lambda: complete_prompt(connection, prompt_id),
    )
    return PromptResponse.from_prompt(prompt)


@router.post(
    "/api/prompts/{prompt_id}/dismiss",
    response_model=PromptResponse,
)
def dismiss_prompt_item(
    prompt_id: str,
    connection: DatabaseConnection,
) -> PromptResponse:
    prompt = _run_prompt_action(
        lambda: dismiss_prompt(connection, prompt_id),
    )
    return PromptResponse.from_prompt(prompt)


@router.post(
    "/api/prompts/{prompt_id}/requeue",
    response_model=PromptResponse,
)
def requeue_prompt_item(
    prompt_id: str,
    connection: DatabaseConnection,
) -> PromptResponse:
    prompt = _run_prompt_action(
        lambda: requeue_prompt(connection, prompt_id),
    )
    return PromptResponse.from_prompt(prompt)


def _run_prompt_action(action: Callable[[], PromptItem]) -> PromptItem:
    try:
        return action()
    except PromptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PromptStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
