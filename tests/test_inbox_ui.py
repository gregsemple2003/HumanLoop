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
    assert 'data-workflow-action="copy"' not in html
    assert 'data-workflow-action="complete"' not in html
    assert 'data-workflow-action="dismiss"' not in html


def test_inbox_renders_pass_four_operator_controls_and_shortcut_contract(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        created = _enqueue_prompt(client, "175", body="Current prompt body")

        response = client.get("/inbox")

    html = response.text

    assert response.status_code == 200
    assert f'data-prompt-id="{created["id"]}"' in html
    assert f'data-prompt-seq="{created["seq"]}"' in html
    assert 'id="workflow-status"' in html
    assert 'aria-live="polite"' in html
    assert 'id="requeue-dismissed-button"' in html
    assert 'id="shortcut-help"' in html
    assert 'data-workflow-action="copy"' in html
    assert 'data-workflow-action="complete"' in html
    assert 'data-workflow-action="dismiss"' in html
    assert "Shortcuts: C copy, Enter complete, D dismiss, ? help." in html
    assert "navigator.clipboard.writeText(promptText)" in html
    assert "Copy keeps the current prompt on screen." in html
    assert "position: sticky;" in html


def test_inbox_copy_workflow_uses_clipboard_before_recording_copy_event(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        _enqueue_prompt(client, "175b", body="Clipboard contract prompt")

        response = client.get("/inbox")

    html = response.text
    clipboard_call = html.index("await navigator.clipboard.writeText(promptText);")
    copied_call = html.index('const prompt = await postPromptAction(promptId, "copied");')

    assert response.status_code == 200
    assert clipboard_call < copied_call
    assert "Copied locally, but not recorded" in html
    assert "Copy failed" in html
    assert "Select the prompt text manually and press Ctrl+C." in html
    assert "The current prompt stayed visible so you can retry without losing your place." in html
    assert "The current prompt stayed visible so you can try again or copy manually." in html


def test_inbox_transition_workflow_refreshes_only_after_server_confirmed_actions(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        _enqueue_prompt(client, "175c", body="Transition contract prompt")

        response = client.get("/inbox")

    html = response.text
    transition_post = html.index("const prompt = await postPromptAction(promptId, action);")
    transition_refresh = html.index("await refreshInboxFragments();")

    assert response.status_code == 200
    assert transition_post < transition_refresh
    assert "Complete or Dismiss advances only after the server confirms the queue change." in html
    assert "The visible prompt stayed in place so the UI does not drift from server state." in html
    assert 'data-workflow-action="requeue"' in html
    assert "Prompt ${prompt.seq} was completed. The queue advanced only after the server confirmed the change." in html
    assert "Prompt ${prompt.seq} left the active queue. Use Requeue if you want to restore it." in html
    assert "Prompt ${prompt.seq} returned to the pending queue. It can become current again immediately if it is still first in line." in html


def test_inbox_keyboard_shortcuts_ignore_text_entry_targets_and_drive_actions(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        _enqueue_prompt(client, "175d", body="Keyboard contract prompt")

        response = client.get("/inbox")

    html = response.text

    assert response.status_code == 200
    assert 'target.closest("input, textarea, select, [contenteditable=\'true\']")' in html
    assert 'if (event.key === "?" || (event.key === "/" && event.shiftKey)) {' in html
    assert 'if (event.key === "c" || event.key === "C") {' in html
    assert 'if (event.key === "d" || event.key === "D") {' in html
    assert 'if (event.key === "Enter") {' in html
    assert "toggleShortcutHelp();" in html
    assert "copyButton.click();" in html
    assert "dismissButton.click();" in html
    assert "completeButton.click();" in html


def test_inbox_current_keeps_same_prompt_visible_after_copy_event(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "176", body="Current prompt body")
        second = _enqueue_prompt(client, "177", body="Next prompt body")

        before_current = client.get("/inbox/current")
        copied = client.post(f"/api/prompts/{first['id']}/copied")
        after_current = client.get("/inbox/current")
        after_queue = client.get("/inbox/queue")

    assert before_current.status_code == 200
    assert "Current prompt body" in before_current.text
    assert "Next prompt body" not in before_current.text

    assert copied.status_code == 200
    assert copied.json()["copy_count"] == 1

    assert after_current.status_code == 200
    assert "Current prompt body" in after_current.text
    assert "Next prompt body" not in after_current.text
    assert 'id="current-copy-count">1<' in after_current.text

    assert after_queue.status_code == 200
    assert "Next prompt body" in after_queue.text
    assert "Current prompt body" not in after_queue.text


def test_inbox_requeue_recovery_restores_dismissed_prompt_to_current_card(
    test_settings,
) -> None:
    with TestClient(create_app(test_settings)) as client:
        first = _enqueue_prompt(client, "178", body="Dismissed prompt body")
        second = _enqueue_prompt(client, "179", body="Still pending prompt body")

        dismissed = client.post(f"/api/prompts/{first['id']}/dismiss")
        after_dismiss_current = client.get("/inbox/current")
        requeued = client.post(f"/api/prompts/{first['id']}/requeue")
        after_requeue_current = client.get("/inbox/current")
        after_requeue_queue = client.get("/inbox/queue")

    assert dismissed.status_code == 200
    assert after_dismiss_current.status_code == 200
    assert "Still pending prompt body" in after_dismiss_current.text
    assert "Dismissed prompt body" not in after_dismiss_current.text

    assert requeued.status_code == 200
    assert after_requeue_current.status_code == 200
    assert "Dismissed prompt body" in after_requeue_current.text
    assert "Still pending prompt body" not in after_requeue_current.text

    assert after_requeue_queue.status_code == 200
    assert "Still pending prompt body" in after_requeue_queue.text
    assert "Dismissed prompt body" not in after_requeue_queue.text


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
