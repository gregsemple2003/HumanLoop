from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import initialize_database, open_connection
from app.main import create_app


def test_healthz_reports_ok_and_initializes_database(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert test_settings.database_path.exists()


def test_database_connections_enable_pass_one_durability_pragmas(
    test_settings,
) -> None:
    initialize_database(test_settings.database_path)
    connection = open_connection(test_settings.database_path)
    try:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert journal_mode == "wal"
    assert synchronous == 2
    assert busy_timeout == 5000
    assert foreign_keys == 1


def test_prompt_items_schema_matches_pass_one_contract(test_settings) -> None:
    initialize_database(test_settings.database_path)
    connection = open_connection(test_settings.database_path)
    try:
        rows = connection.execute("PRAGMA table_info(prompt_items)").fetchall()
    finally:
        connection.close()

    assert [row["name"] for row in rows] == [
        "seq",
        "id",
        "source",
        "idempotency_key",
        "body",
        "metadata_json",
        "status",
        "copy_count",
        "last_copied_at",
        "created_at",
        "updated_at",
        "completed_at",
        "dismissed_at",
    ]


def test_ingest_persists_a_new_prompt(test_settings) -> None:
    payload = {
        "body": "Write a release note for pass 1.",
        "source": "tests",
        "idempotency_key": "prompt-001",
        "metadata": {"kind": "smoke"},
    }

    with TestClient(create_app(test_settings)) as client:
        response = client.post("/api/prompts", json=payload)

    data = response.json()
    assert response.status_code == 201
    assert data["replayed"] is False
    assert data["seq"] == 1
    assert data["status"] == "pending"
    assert data["copy_count"] == 0

    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            """
            SELECT seq, source, idempotency_key, body, metadata_json, status
            FROM prompt_items
            """
        ).fetchone()
    finally:
        connection.close()

    assert row["seq"] == 1
    assert row["source"] == payload["source"]
    assert row["idempotency_key"] == payload["idempotency_key"]
    assert row["body"] == payload["body"]
    assert row["metadata_json"] == '{"kind":"smoke"}'
    assert row["status"] == "pending"


def test_ingest_allows_missing_optional_metadata(test_settings) -> None:
    payload = {
        "body": "No metadata is still valid.",
        "source": "tests",
        "idempotency_key": "prompt-001b",
    }

    with TestClient(create_app(test_settings)) as client:
        response = client.post("/api/prompts", json=payload)

    assert response.status_code == 201
    assert response.json()["metadata"] is None

    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            "SELECT metadata_json FROM prompt_items WHERE id = ?",
            (response.json()["id"],),
        ).fetchone()
    finally:
        connection.close()

    assert row["metadata_json"] is None


def test_duplicate_ingest_returns_replay_safe_response(test_settings) -> None:
    payload = {
        "body": "Summarize the nightly failures.",
        "source": "tests",
        "idempotency_key": "prompt-002",
    }

    with TestClient(create_app(test_settings)) as client:
        first = client.post("/api/prompts", json=payload)
        second = client.post("/api/prompts", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["seq"] == first.json()["seq"]

    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM prompt_items"
        ).fetchone()
    finally:
        connection.close()

    assert row["count"] == 1


def test_idempotency_is_scoped_to_source_plus_key(test_settings) -> None:
    first_payload = {
        "body": "Prompt from the first source.",
        "source": "tests",
        "idempotency_key": "shared-key",
    }
    second_payload = {
        "body": "Prompt from the second source.",
        "source": "other-tests",
        "idempotency_key": "shared-key",
    }

    with TestClient(create_app(test_settings)) as client:
        first = client.post("/api/prompts", json=first_payload)
        second = client.post("/api/prompts", json=second_payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["seq"] == 1
    assert second.json()["seq"] == 2

    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM prompt_items"
        ).fetchone()
    finally:
        connection.close()

    assert row["count"] == 2


def test_reusing_an_idempotency_key_for_different_payload_returns_conflict(
    test_settings,
) -> None:
    first_payload = {
        "body": "First prompt body.",
        "source": "tests",
        "idempotency_key": "prompt-003",
    }
    conflicting_payload = {
        "body": "Changed prompt body.",
        "source": "tests",
        "idempotency_key": "prompt-003",
    }

    with TestClient(create_app(test_settings)) as client:
        first = client.post("/api/prompts", json=first_payload)
        conflict = client.post("/api/prompts", json=conflicting_payload)

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert "different prompt payload" in conflict.json()["detail"]


def test_ingest_requires_body_source_and_idempotency_key(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.post("/api/prompts", json={"metadata": {"kind": "smoke"}})

    assert response.status_code == 422
    assert {
        error["loc"][-1] for error in response.json()["detail"]
    } >= {"body", "source", "idempotency_key"}


@pytest.mark.parametrize("field_name", ["body", "source", "idempotency_key"])
def test_ingest_rejects_blank_required_text_fields(
    test_settings,
    field_name: str,
) -> None:
    payload = {
        "body": "A valid prompt body.",
        "source": "tests",
        "idempotency_key": "prompt-blank-check",
    }
    payload[field_name] = "   "

    with TestClient(create_app(test_settings)) as client:
        response = client.post("/api/prompts", json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == field_name for error in response.json()["detail"]
    )


def test_new_prompts_get_monotonic_seq_values(test_settings) -> None:
    first_payload = {
        "body": "Prompt one.",
        "source": "tests",
        "idempotency_key": "prompt-004",
    }
    second_payload = {
        "body": "Prompt two.",
        "source": "tests",
        "idempotency_key": "prompt-005",
    }

    with TestClient(create_app(test_settings)) as client:
        first = client.post("/api/prompts", json=first_payload)
        second = client.post("/api/prompts", json=second_payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["seq"] == 1
    assert second.json()["seq"] == 2


def test_prompt_survives_app_restart(test_settings) -> None:
    payload = {
        "body": "Persist me across app restarts.",
        "source": "tests",
        "idempotency_key": "prompt-006",
        "metadata": {"batch": 1},
    }

    with TestClient(create_app(test_settings)) as client:
        created = client.post("/api/prompts", json=payload)

    with TestClient(create_app(test_settings)) as client:
        replay = client.post("/api/prompts", json=payload)

    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == created.json()["id"]
    assert replay.json()["seq"] == created.json()["seq"]

    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM prompt_items"
        ).fetchone()
    finally:
        connection.close()

    assert row["count"] == 1
