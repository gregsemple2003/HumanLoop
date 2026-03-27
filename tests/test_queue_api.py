from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import open_connection
from app.main import create_app


def _enqueue_prompt(
    client: TestClient,
    suffix: str,
    *,
    source: str = "tests",
) -> dict:
    response = client.post(
        "/api/prompts",
        json={
            "body": f"Prompt body {suffix}",
            "source": source,
            "idempotency_key": f"prompt-{suffix}",
        },
    )
    assert response.status_code == 201
    return response.json()


def _fetch_prompt_row(
    test_settings,
    prompt_id: str,
) -> dict[str, object] | None:
    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            "SELECT * FROM prompt_items WHERE id = ?",
            (prompt_id,),
        ).fetchone()
    finally:
        connection.close()

    return dict(row) if row is not None else None


def _count_prompt_rows(test_settings) -> int:
    connection = open_connection(test_settings.database_path)
    try:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM prompt_items",
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    return int(row["count"])


def test_list_prompts_returns_pending_items_in_fifo_order_and_honors_limit(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "001")
        second = _enqueue_prompt(client, "002")
        _enqueue_prompt(client, "003")

        response = client.get("/api/prompts", params={"status": "pending", "limit": 2})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [first["id"], second["id"]]


def test_list_prompts_filters_by_status(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "010")
        second = _enqueue_prompt(client, "011")
        third = _enqueue_prompt(client, "012")

        complete = client.post(f"/api/prompts/{first['id']}/complete")
        dismiss = client.post(f"/api/prompts/{second['id']}/dismiss")
        pending = client.get("/api/prompts")
        completed = client.get("/api/prompts", params={"status": "completed"})
        dismissed = client.get("/api/prompts", params={"status": "dismissed"})

    assert complete.status_code == 200
    assert dismiss.status_code == 200
    assert [item["id"] for item in pending.json()] == [third["id"]]
    assert [item["id"] for item in completed.json()] == [first["id"]]
    assert [item["id"] for item in dismissed.json()] == [second["id"]]


def test_list_prompts_rejects_unknown_status_value(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/api/prompts", params={"status": "archived"})

    assert response.status_code == 422
    assert any(error["loc"][-1] == "status" for error in response.json()["detail"])


def test_get_next_prompt_returns_fifo_head_and_skips_completed_items(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "020")
        second = _enqueue_prompt(client, "021")

        initial = client.get("/api/prompts/next")
        complete = client.post(f"/api/prompts/{first['id']}/complete")
        after_complete = client.get("/api/prompts/next")

    assert initial.status_code == 200
    assert initial.json()["id"] == first["id"]
    assert complete.status_code == 200
    assert after_complete.status_code == 200
    assert after_complete.json()["id"] == second["id"]


def test_get_next_prompt_returns_404_when_queue_is_empty(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/api/prompts/next")

    assert response.status_code == 404
    assert response.json()["detail"] == "No pending prompts found."


def test_get_prompt_summary_reports_pending_count_current_head_and_latest_seq(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "025")
        second = _enqueue_prompt(client, "026")
        _enqueue_prompt(client, "027")

        dismiss = client.post(f"/api/prompts/{second['id']}/dismiss")
        response = client.get("/api/prompts/summary")

    assert dismiss.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "pending_count": 2,
        "current_prompt": {
            "id": first["id"],
            "seq": first["seq"],
            "source": first["source"],
        },
        "latest_pending_seq": 3,
    }


def test_get_prompt_summary_returns_empty_shape_when_queue_is_empty(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/api/prompts/summary")

    assert response.status_code == 200
    assert response.json() == {
        "pending_count": 0,
        "current_prompt": None,
        "latest_pending_seq": None,
    }


def test_get_prompt_by_id_returns_prompt_and_404_for_unknown_id(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        created = _enqueue_prompt(client, "030")
        found = client.get(f"/api/prompts/{created['id']}")
        missing = client.get("/api/prompts/does-not-exist")

    assert found.status_code == 200
    assert found.json()["id"] == created["id"]
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Prompt not found."


def test_copied_records_copy_metadata_without_changing_status(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        created = _enqueue_prompt(client, "040")

        first_copy = client.post(f"/api/prompts/{created['id']}/copied")
        second_copy = client.post(f"/api/prompts/{created['id']}/copied")
        next_prompt = client.get("/api/prompts/next")

    row = _fetch_prompt_row(test_settings, created["id"])

    assert first_copy.status_code == 200
    assert second_copy.status_code == 200
    assert first_copy.json()["copy_count"] == 1
    assert second_copy.json()["copy_count"] == 2
    assert second_copy.json()["status"] == "pending"
    assert second_copy.json()["last_copied_at"] is not None
    assert next_prompt.status_code == 200
    assert next_prompt.json()["id"] == created["id"]
    assert next_prompt.json()["copy_count"] == 2
    assert row == {
        "seq": created["seq"],
        "id": created["id"],
        "source": created["source"],
        "idempotency_key": created["idempotency_key"],
        "body": created["body"],
        "metadata_json": None,
        "status": "pending",
        "copy_count": 2,
        "last_copied_at": second_copy.json()["last_copied_at"],
        "created_at": created["created_at"],
        "updated_at": second_copy.json()["updated_at"],
        "completed_at": None,
        "dismissed_at": None,
    }
    assert _count_prompt_rows(test_settings) == 1


def test_complete_is_idempotent_and_removes_prompt_from_pending_queue(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        created = _enqueue_prompt(client, "050")

        first_complete = client.post(f"/api/prompts/{created['id']}/complete")
        second_complete = client.post(f"/api/prompts/{created['id']}/complete")
        pending = client.get("/api/prompts")
        completed = client.get("/api/prompts", params={"status": "completed"})
        detail = client.get(f"/api/prompts/{created['id']}")

    row = _fetch_prompt_row(test_settings, created["id"])

    assert first_complete.status_code == 200
    assert second_complete.status_code == 200
    assert first_complete.json()["status"] == "completed"
    assert first_complete.json()["completed_at"] is not None
    assert first_complete.json()["dismissed_at"] is None
    assert second_complete.json()["completed_at"] == first_complete.json()["completed_at"]
    assert pending.json() == []
    assert [item["id"] for item in completed.json()] == [created["id"]]
    assert detail.json()["status"] == "completed"
    assert detail.json()["completed_at"] == first_complete.json()["completed_at"]
    assert row == {
        "seq": created["seq"],
        "id": created["id"],
        "source": created["source"],
        "idempotency_key": created["idempotency_key"],
        "body": created["body"],
        "metadata_json": None,
        "status": "completed",
        "copy_count": 0,
        "last_copied_at": None,
        "created_at": created["created_at"],
        "updated_at": first_complete.json()["updated_at"],
        "completed_at": first_complete.json()["completed_at"],
        "dismissed_at": None,
    }
    assert _count_prompt_rows(test_settings) == 1


def test_dismiss_is_idempotent_and_requeue_restores_pending_state(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        created = _enqueue_prompt(client, "060")

        first_dismiss = client.post(f"/api/prompts/{created['id']}/dismiss")
        dismissed_detail = client.get(f"/api/prompts/{created['id']}")
        dismissed_row = _fetch_prompt_row(test_settings, created["id"])
        second_dismiss = client.post(f"/api/prompts/{created['id']}/dismiss")
        requeue = client.post(f"/api/prompts/{created['id']}/requeue")
        next_prompt = client.get("/api/prompts/next")

    final_row = _fetch_prompt_row(test_settings, created["id"])

    assert first_dismiss.status_code == 200
    assert dismissed_detail.status_code == 200
    assert dismissed_detail.json()["status"] == "dismissed"
    assert second_dismiss.status_code == 200
    assert first_dismiss.json()["status"] == "dismissed"
    assert first_dismiss.json()["dismissed_at"] is not None
    assert second_dismiss.json()["dismissed_at"] == first_dismiss.json()["dismissed_at"]
    assert requeue.status_code == 200
    assert requeue.json()["status"] == "pending"
    assert requeue.json()["dismissed_at"] is None
    assert next_prompt.status_code == 200
    assert next_prompt.json()["id"] == created["id"]
    assert dismissed_row == {
        "seq": created["seq"],
        "id": created["id"],
        "source": created["source"],
        "idempotency_key": created["idempotency_key"],
        "body": created["body"],
        "metadata_json": None,
        "status": "dismissed",
        "copy_count": 0,
        "last_copied_at": None,
        "created_at": created["created_at"],
        "updated_at": first_dismiss.json()["updated_at"],
        "completed_at": None,
        "dismissed_at": first_dismiss.json()["dismissed_at"],
    }
    assert final_row == {
        "seq": created["seq"],
        "id": created["id"],
        "source": created["source"],
        "idempotency_key": created["idempotency_key"],
        "body": created["body"],
        "metadata_json": None,
        "status": "pending",
        "copy_count": 0,
        "last_copied_at": None,
        "created_at": created["created_at"],
        "updated_at": requeue.json()["updated_at"],
        "completed_at": None,
        "dismissed_at": None,
    }
    assert _count_prompt_rows(test_settings) == 1


@pytest.mark.parametrize(
    ("first_action", "conflicting_action", "expected_detail"),
    [
        ("complete", "dismiss", "Cannot dismiss a completed prompt."),
        ("dismiss", "complete", "Cannot complete a dismissed prompt."),
        ("complete", "requeue", "Cannot requeue a completed prompt."),
    ],
)
def test_conflicting_transitions_return_409(
    test_settings,
    first_action: str,
    conflicting_action: str,
    expected_detail: str,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        created = _enqueue_prompt(client, f"070-{first_action}-{conflicting_action}")

        first = client.post(f"/api/prompts/{created['id']}/{first_action}")
        conflicting = client.post(f"/api/prompts/{created['id']}/{conflicting_action}")

    assert first.status_code == 200
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"] == expected_detail


@pytest.mark.parametrize("action", ["copied", "complete", "dismiss", "requeue"])
def test_prompt_actions_return_404_for_unknown_id(
    test_settings,
    action: str,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.post(f"/api/prompts/does-not-exist/{action}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Prompt not found."
