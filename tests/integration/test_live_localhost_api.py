from __future__ import annotations

import httpx


def _enqueue_prompt(
    client: httpx.Client,
    suffix: str,
    *,
    source: str = "integration-tests",
    body: str | None = None,
) -> dict:
    response = client.post(
        "/api/prompts",
        json={
            "body": body or f"Integration prompt body {suffix}",
            "source": source,
            "idempotency_key": f"integration-{suffix}",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_live_server_boots_with_empty_operator_surfaces_and_runtime_log(
    live_server,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        healthz = client.get("/healthz")
        summary = client.get("/api/prompts/summary")
        manifest = client.get("/static/manifest.webmanifest")
        current = client.get("/inbox/current")
        queue = client.get("/inbox/queue")

    assert healthz.status_code == 200
    assert healthz.json() == {"status": "ok"}

    assert summary.status_code == 200
    assert summary.json() == {
        "pending_count": 0,
        "current_prompt": None,
        "latest_pending_seq": None,
    }

    assert manifest.status_code == 200
    assert manifest.json()["name"] == "HumanLoop Inbox"
    assert manifest.json()["start_url"] == "/inbox"

    assert current.status_code == 200
    assert "No pending prompts right now." in current.text
    assert 'data-workflow-action="copy"' not in current.text

    assert queue.status_code == 200
    assert "0 waiting" in queue.text
    assert "The queue is empty. This rail will populate as new prompts arrive." in queue.text

    assert live_server.log_path.exists()
    log_text = live_server.log_path.read_text(encoding="utf-8")
    assert "HumanLoop database ready at" in log_text
    assert "HumanLoop logs writing to" in log_text


def test_live_ingest_is_idempotent_and_survives_server_restart(
    live_server_factory,
) -> None:
    initial_server = live_server_factory("restart-initial")
    payload = {
        "body": "Persist me across a real localhost restart.",
        "source": "integration-tests",
        "idempotency_key": "restart-proof-001",
        "metadata": {"kind": "restart-proof"},
    }

    with httpx.Client(base_url=initial_server.base_url, timeout=5.0) as client:
        created = client.post("/api/prompts", json=payload)
        replayed = client.post("/api/prompts", json=payload)
        next_prompt = client.get("/api/prompts/next")

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True
    assert replayed.json()["id"] == created.json()["id"]
    assert next_prompt.status_code == 200
    assert next_prompt.json()["id"] == created.json()["id"]

    database_path = initial_server.database_path
    log_path = initial_server.log_path
    initial_server.stop()

    restarted_server = live_server_factory(
        "restart-followup",
        database_path=database_path,
        log_path=log_path,
    )

    with httpx.Client(base_url=restarted_server.base_url, timeout=5.0) as client:
        after_restart = client.get("/api/prompts/next")
        replay_after_restart = client.post("/api/prompts", json=payload)

    assert after_restart.status_code == 200
    assert after_restart.json()["id"] == created.json()["id"]
    assert replay_after_restart.status_code == 200
    assert replay_after_restart.json()["replayed"] is True
    assert replay_after_restart.json()["id"] == created.json()["id"]


def test_live_conflicting_transition_returns_409(live_server) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        created = _enqueue_prompt(client, "conflict")
        completed = client.post(f"/api/prompts/{created['id']}/complete")
        conflicting = client.post(f"/api/prompts/{created['id']}/dismiss")

    assert completed.status_code == 200
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"] == "Cannot dismiss a completed prompt."
