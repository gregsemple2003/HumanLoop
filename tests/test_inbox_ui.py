from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db import open_connection
from app.main import create_app


def _enqueue_prompt(
    client: TestClient,
    suffix: str,
    *,
    source: str = "tests",
    body: str | None = None,
) -> dict:
    response = client.post(
        "/api/prompts",
        json={
            "body": body or f"Prompt body {suffix}",
            "source": source,
            "idempotency_key": f"prompt-{suffix}",
        },
    )
    assert response.status_code == 201
    return response.json()


def _set_prompt_created_at(
    test_settings,
    prompt_id: str,
    timestamp: str,
) -> None:
    connection = open_connection(test_settings.database_path)
    try:
        connection.execute(
            """
            UPDATE prompt_items
            SET created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, prompt_id),
        )
    finally:
        connection.close()


def test_inbox_renders_current_prompt_and_waiting_queue(test_settings) -> None:
    first_body = "First prompt body with full detail.\nKeep this visible."
    second_body = "Second prompt body for the queue rail preview."
    third_body = "Third prompt body for the queue rail preview."

    with TestClient(create_app(test_settings)) as client:
        _enqueue_prompt(client, "101", source="capture-alpha", body=first_body)
        _enqueue_prompt(client, "102", source="capture-beta", body=second_body)
        _enqueue_prompt(client, "103", source="capture-gamma", body=third_body)

        response = client.get("/inbox")

    html = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Operator inbox" in html
    assert "Current prompt" in html
    assert first_body in html
    assert "capture-alpha" in html
    assert "Pending queue" in html
    assert second_body in html
    assert third_body in html
    assert "3 total pending" in html
    assert "2 waiting" in html
    assert 'hx-get="/inbox/queue"' in html
    assert 'hx-trigger="every 5s"' in html
    assert 'hx-get="/inbox/current"' not in html


def test_inbox_queue_renders_source_age_and_collapsed_preview(
    test_settings,
    monkeypatch,
) -> None:
    frozen_now = datetime(2026, 3, 26, 12, 0, 0, tzinfo=UTC)

    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now.replace(tzinfo=None)
            return frozen_now.astimezone(tz)

        @classmethod
        def fromisoformat(cls, value: str):
            return datetime.fromisoformat(value)

    waiting_body = "Second queue line one.\n\nLine two keeps waiting."

    monkeypatch.setattr("app.inbox.datetime", FrozenDateTime)

    with TestClient(create_app(test_settings)) as client:
        _enqueue_prompt(client, "151", source="capture-alpha", body="Current prompt body")
        second = _enqueue_prompt(
            client,
            "152",
            source="capture-beta",
            body=waiting_body,
        )
        third = _enqueue_prompt(
            client,
            "153",
            source="capture-gamma",
            body="Third queue body stays visible in the rail.",
        )

        _set_prompt_created_at(
            test_settings,
            second["id"],
            "2026-03-26T11:58:00Z",
        )
        _set_prompt_created_at(
            test_settings,
            third["id"],
            "2026-03-24T12:00:00Z",
        )

        response = client.get("/inbox/queue")

    html = response.text

    assert response.status_code == 200
    assert "capture-beta" in html
    assert "capture-gamma" in html
    assert "2 minutes ago" in html
    assert "2 days ago" in html
    assert "Second queue line one. Line two keeps waiting." in html
    assert waiting_body not in html


def test_inbox_current_renders_empty_state_when_queue_is_empty(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/inbox/current")

    html = response.text

    assert response.status_code == 200
    assert "No pending prompts right now." in html
    assert "0 total pending" in html


def test_inbox_queue_renders_empty_state_with_polling_contract(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/inbox/queue")

    html = response.text

    assert response.status_code == 200
    assert "The queue is empty. This rail will populate as new prompts arrive." in html
    assert "0 waiting" in html
    assert "0 total pending" in html
    assert 'hx-get="/inbox/queue"' in html
    assert 'hx-trigger="every 5s"' in html


def test_inbox_counts_all_pending_items_at_queue_limit_boundary(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        for index in range(1, 52):
            _enqueue_prompt(client, f"limit-{index:03d}")

        response = client.get("/inbox")

    html = response.text

    assert response.status_code == 200
    assert "51 total pending" in html
    assert "50 waiting" in html
    assert html.count('class="queue-item"') == 50
    assert "Prompt body limit-051" in html


def test_inbox_routes_advance_only_after_explicit_queue_transition(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "201", body="Current prompt body")
        second = _enqueue_prompt(client, "202", body="Next prompt body")

        before_current = client.get("/inbox/current")
        before_queue = client.get("/inbox/queue")
        complete = client.post(f"/api/prompts/{first['id']}/complete")
        after_current = client.get("/inbox/current")
        after_queue = client.get("/inbox/queue")

    assert before_current.status_code == 200
    assert "Current prompt body" in before_current.text
    assert "Next prompt body" not in before_current.text
    assert before_queue.status_code == 200
    assert "Next prompt body" in before_queue.text
    assert "Current prompt body" not in before_queue.text

    assert complete.status_code == 200
    assert after_current.status_code == 200
    assert "Next prompt body" in after_current.text
    assert "Current prompt body" not in after_current.text
    assert after_queue.status_code == 200
    assert "No additional prompts are waiting behind the current item." in after_queue.text


def test_inbox_fragments_exclude_terminal_history_and_keep_queue_informational(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        current = _enqueue_prompt(client, "301", body="Current pending prompt")
        dismissed = _enqueue_prompt(client, "302", body="Dismissed prompt body")
        waiting = _enqueue_prompt(client, "303", body="Still waiting prompt body")
        completed = _enqueue_prompt(client, "304", body="Completed prompt body")

        dismiss_response = client.post(f"/api/prompts/{dismissed['id']}/dismiss")
        complete_response = client.post(f"/api/prompts/{completed['id']}/complete")
        current_fragment = client.get("/inbox/current")
        queue_fragment = client.get("/inbox/queue")

    assert dismiss_response.status_code == 200
    assert complete_response.status_code == 200
    assert current_fragment.status_code == 200
    assert current["body"] in current_fragment.text
    assert dismissed["body"] not in current_fragment.text
    assert completed["body"] not in current_fragment.text

    assert queue_fragment.status_code == 200
    assert waiting["body"] in queue_fragment.text
    assert dismissed["body"] not in queue_fragment.text
    assert completed["body"] not in queue_fragment.text
    assert "/api/prompts/" not in queue_fragment.text
