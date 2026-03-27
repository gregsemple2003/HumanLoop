from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from app.models import PromptIngestRequest, PromptItem


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused for a different payload."""


class PromptNotFoundError(Exception):
    """Raised when a prompt item does not exist."""


class PromptStateConflictError(Exception):
    """Raised when a prompt transition conflicts with the current state."""


def ingest_prompt(
    connection: sqlite3.Connection,
    payload: PromptIngestRequest,
) -> tuple[PromptItem, bool]:
    timestamp = _utc_timestamp()
    prompt_id = str(uuid.uuid4())
    metadata_json = payload.metadata_json()

    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            INSERT INTO prompt_items (
                id,
                source,
                idempotency_key,
                body,
                metadata_json,
                status,
                copy_count,
                last_copied_at,
                created_at,
                updated_at,
                completed_at,
                dismissed_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', 0, NULL, ?, ?, NULL, NULL)
            """,
            (
                prompt_id,
                payload.source,
                payload.idempotency_key,
                payload.body,
                metadata_json,
                timestamp,
                timestamp,
            ),
        )
        row = connection.execute(
            "SELECT * FROM prompt_items WHERE seq = ?",
            (cursor.lastrowid,),
        ).fetchone()
        connection.commit()
        if row is None:
            raise RuntimeError("Inserted prompt row was not found.")
        return _row_to_prompt_item(row), False
    except sqlite3.IntegrityError:
        connection.rollback()
        existing_row = connection.execute(
            """
            SELECT *
            FROM prompt_items
            WHERE source = ? AND idempotency_key = ?
            """,
            (payload.source, payload.idempotency_key),
        ).fetchone()
        if existing_row is None:
            raise

        prompt = _row_to_prompt_item(existing_row)
        if prompt.body != payload.body or prompt.metadata != payload.normalized_metadata():
            raise IdempotencyConflictError(
                "The idempotency key was already used for a different prompt payload."
            )

        return prompt, True
    except Exception:
        connection.rollback()
        raise


def list_prompts(
    connection: sqlite3.Connection,
    *,
    status: str = "pending",
    limit: int = 50,
) -> list[PromptItem]:
    rows = connection.execute(
        """
        SELECT *
        FROM prompt_items
        WHERE status = ?
        ORDER BY seq ASC
        LIMIT ?
        """,
        (status, limit),
    ).fetchall()
    return [_row_to_prompt_item(row) for row in rows]


def count_prompts(
    connection: sqlite3.Connection,
    *,
    status: str = "pending",
) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM prompt_items
        WHERE status = ?
        """,
        (status,),
    ).fetchone()
    if row is None:
        return 0
    return int(row["count"])


def latest_prompt_seq(
    connection: sqlite3.Connection,
    *,
    status: str = "pending",
) -> int | None:
    row = connection.execute(
        """
        SELECT MAX(seq) AS seq
        FROM prompt_items
        WHERE status = ?
        """,
        (status,),
    ).fetchone()
    if row is None or row["seq"] is None:
        return None
    return int(row["seq"])


def get_prompt_by_id(
    connection: sqlite3.Connection,
    prompt_id: str,
) -> PromptItem | None:
    row = connection.execute(
        """
        SELECT *
        FROM prompt_items
        WHERE id = ?
        """,
        (prompt_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_prompt_item(row)


def get_next_prompt(connection: sqlite3.Connection) -> PromptItem | None:
    rows = list_prompts(connection, status="pending", limit=1)
    if not rows:
        return None
    return rows[0]


def record_prompt_copied(
    connection: sqlite3.Connection,
    prompt_id: str,
) -> PromptItem:
    timestamp = _utc_timestamp()
    try:
        connection.execute("BEGIN IMMEDIATE")
        _get_prompt_for_update(connection, prompt_id)
        connection.execute(
            """
            UPDATE prompt_items
            SET copy_count = copy_count + 1,
                last_copied_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, prompt_id),
        )
        row = connection.execute(
            """
            SELECT *
            FROM prompt_items
            WHERE id = ?
            """,
            (prompt_id,),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    if row is None:
        raise RuntimeError("Updated prompt row was not found after copy.")
    return _row_to_prompt_item(row)


def complete_prompt(
    connection: sqlite3.Connection,
    prompt_id: str,
) -> PromptItem:
    return _set_prompt_status(
        connection,
        prompt_id,
        target_status="completed",
        conflict_status="dismissed",
        conflict_message="Cannot complete a dismissed prompt.",
    )


def dismiss_prompt(
    connection: sqlite3.Connection,
    prompt_id: str,
) -> PromptItem:
    return _set_prompt_status(
        connection,
        prompt_id,
        target_status="dismissed",
        conflict_status="completed",
        conflict_message="Cannot dismiss a completed prompt.",
    )


def requeue_prompt(
    connection: sqlite3.Connection,
    prompt_id: str,
) -> PromptItem:
    timestamp = _utc_timestamp()
    try:
        connection.execute("BEGIN IMMEDIATE")
        prompt = _get_prompt_for_update(connection, prompt_id)
        if prompt.status == "pending":
            connection.rollback()
            return prompt
        if prompt.status == "completed":
            raise PromptStateConflictError("Cannot requeue a completed prompt.")

        connection.execute(
            """
            UPDATE prompt_items
            SET status = 'pending',
                updated_at = ?,
                dismissed_at = NULL
            WHERE id = ?
            """,
            (timestamp, prompt_id),
        )
        row = connection.execute(
            """
            SELECT *
            FROM prompt_items
            WHERE id = ?
            """,
            (prompt_id,),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    if row is None:
        raise RuntimeError("Requeued prompt row was not found after update.")
    return _row_to_prompt_item(row)


def _row_to_prompt_item(row: sqlite3.Row) -> PromptItem:
    metadata_json = row["metadata_json"]
    metadata = json.loads(metadata_json) if metadata_json else None
    return PromptItem(
        id=row["id"],
        seq=row["seq"],
        source=row["source"],
        idempotency_key=row["idempotency_key"],
        body=row["body"],
        metadata=metadata,
        status=row["status"],
        copy_count=row["copy_count"],
        last_copied_at=row["last_copied_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        dismissed_at=row["dismissed_at"],
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _get_prompt_for_update(
    connection: sqlite3.Connection,
    prompt_id: str,
) -> PromptItem:
    prompt = get_prompt_by_id(connection, prompt_id)
    if prompt is None:
        raise PromptNotFoundError("Prompt not found.")
    return prompt


def _set_prompt_status(
    connection: sqlite3.Connection,
    prompt_id: str,
    *,
    target_status: str,
    conflict_status: str,
    conflict_message: str,
) -> PromptItem:
    timestamp = _utc_timestamp()
    timestamp_column = f"{target_status}_at"

    try:
        connection.execute("BEGIN IMMEDIATE")
        prompt = _get_prompt_for_update(connection, prompt_id)
        if prompt.status == target_status:
            connection.rollback()
            return prompt
        if prompt.status == conflict_status:
            raise PromptStateConflictError(conflict_message)

        connection.execute(
            f"""
            UPDATE prompt_items
            SET status = ?,
                updated_at = ?,
                {timestamp_column} = ?
            WHERE id = ?
            """,
            (target_status, timestamp, timestamp, prompt_id),
        )
        row = connection.execute(
            """
            SELECT *
            FROM prompt_items
            WHERE id = ?
            """,
            (prompt_id,),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    if row is None:
        raise RuntimeError("Updated prompt row was not found after status change.")
    return _row_to_prompt_item(row)
