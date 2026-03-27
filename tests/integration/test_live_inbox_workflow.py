from __future__ import annotations

import httpx


def _enqueue_prompt(
    client: httpx.Client,
    suffix: str,
    *,
    body: str | None = None,
) -> dict:
    response = client.post(
        "/api/prompts",
        json={
            "body": body or f"Workflow prompt body {suffix}",
            "source": "integration-tests",
            "idempotency_key": f"workflow-{suffix}",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_live_copy_keeps_current_prompt_visible_and_updates_copy_count(
    live_server,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        first = _enqueue_prompt(client, "copy-001", body="Current prompt body")
        _enqueue_prompt(client, "copy-002", body="Next prompt body")

        inbox = client.get("/inbox")
        before_current = client.get("/inbox/current")
        copied = client.post(f"/api/prompts/{first['id']}/copied")
        after_current = client.get("/inbox/current")
        after_queue = client.get("/inbox/queue")

    assert inbox.status_code == 200
    assert "Current prompt body" in inbox.text
    assert 'data-workflow-action="copy"' in inbox.text

    assert before_current.status_code == 200
    assert "Current prompt body" in before_current.text
    assert "Next prompt body" not in before_current.text

    assert copied.status_code == 200
    assert copied.json()["copy_count"] == 1
    assert copied.json()["status"] == "pending"

    assert after_current.status_code == 200
    assert "Current prompt body" in after_current.text
    assert "Next prompt body" not in after_current.text
    assert 'id="current-copy-count">1<' in after_current.text

    assert after_queue.status_code == 200
    assert "Next prompt body" in after_queue.text
    assert "Current prompt body" not in after_queue.text


def test_live_complete_advances_the_queue_after_explicit_action(
    live_server,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        first = _enqueue_prompt(client, "complete-001", body="Complete current body")
        second = _enqueue_prompt(client, "complete-002", body="Complete next body")

        before_current = client.get("/inbox/current")
        completed = client.post(f"/api/prompts/{first['id']}/complete")
        next_prompt = client.get("/api/prompts/next")
        after_current = client.get("/inbox/current")
        after_queue = client.get("/inbox/queue")

    assert before_current.status_code == 200
    assert "Complete current body" in before_current.text
    assert "Complete next body" not in before_current.text

    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    assert next_prompt.status_code == 200
    assert next_prompt.json()["id"] == second["id"]

    assert after_current.status_code == 200
    assert "Complete next body" in after_current.text
    assert "Complete current body" not in after_current.text

    assert after_queue.status_code == 200
    assert "No additional prompts are waiting behind the current item." in after_queue.text


def test_live_dismiss_and_requeue_restore_the_original_current_prompt(
    live_server,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        first = _enqueue_prompt(client, "dismiss-001", body="Dismissed prompt body")
        _enqueue_prompt(client, "dismiss-002", body="Still pending prompt body")

        dismissed = client.post(f"/api/prompts/{first['id']}/dismiss")
        after_dismiss_current = client.get("/inbox/current")
        requeued = client.post(f"/api/prompts/{first['id']}/requeue")
        after_requeue_current = client.get("/inbox/current")
        after_requeue_queue = client.get("/inbox/queue")

    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"

    assert after_dismiss_current.status_code == 200
    assert "Still pending prompt body" in after_dismiss_current.text
    assert "Dismissed prompt body" not in after_dismiss_current.text

    assert requeued.status_code == 200
    assert requeued.json()["status"] == "pending"

    assert after_requeue_current.status_code == 200
    assert "Dismissed prompt body" in after_requeue_current.text
    assert "Still pending prompt body" not in after_requeue_current.text

    assert after_requeue_queue.status_code == 200
    assert "Still pending prompt body" in after_requeue_queue.text
    assert "Dismissed prompt body" not in after_requeue_queue.text
