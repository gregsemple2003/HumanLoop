from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_DATABASE_PATH, DEFAULT_LOG_PATH, Settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "enqueue-sample-prompt.ps1"


def test_settings_default_to_localhost_runtime_paths(monkeypatch) -> None:
    monkeypatch.delenv("HUMANLOOP_HOST", raising=False)
    monkeypatch.delenv("HUMANLOOP_PORT", raising=False)
    monkeypatch.delenv("HUMANLOOP_DATABASE_PATH", raising=False)
    monkeypatch.delenv("HUMANLOOP_LOG_LEVEL", raising=False)
    monkeypatch.delenv("HUMANLOOP_LOG_PATH", raising=False)

    settings = Settings.from_env()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.database_path == DEFAULT_DATABASE_PATH
    assert settings.log_path == DEFAULT_LOG_PATH


def test_app_does_not_emit_cors_headers_by_default(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/healthz", headers={"Origin": "http://example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_app_startup_writes_runtime_logs_to_the_configured_log_path(
    tmp_path: Path,
) -> None:
    settings = Settings(
        database_path=tmp_path / "humanloop.db",
        log_level="INFO",
        log_path=tmp_path / "logs" / "humanloop.log",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert settings.log_path.exists()

    log_text = settings.log_path.read_text(encoding="utf-8")

    assert "HumanLoop database ready at" in log_text
    assert "HumanLoop logs writing to" in log_text


def test_readme_documents_the_pass_five_runbook_contract() -> None:
    readme_text = README_PATH.read_text(encoding="utf-8")

    assert "# HumanLoop" in readme_text
    assert "## Quick Start" in readme_text
    assert ".\\.venv\\Scripts\\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000" in readme_text
    assert "Stop the app with `Ctrl+C`" in readme_text
    assert "## Runtime Paths" in readme_text
    assert "data/runtime/humanloop.db" in readme_text
    assert "data/runtime/logs/humanloop.log" in readme_text
    assert "## Producer Contract" in readme_text
    assert "POST /api/prompts" in readme_text
    assert "`201 Created`" in readme_text
    assert "`200 OK` with `\"replayed\": true`" in readme_text
    assert "`409 Conflict`" in readme_text
    assert "## Smoke Path" in readme_text
    assert ".\\scripts\\enqueue-sample-prompt.ps1" in readme_text
    assert "## Recovery Expectations" in readme_text
    assert "Queue state is durable in SQLite and survives restarts" in readme_text
    assert "Copy is tracked for audit and UX only; it does not complete a prompt." in readme_text


@pytest.mark.skipif(
    shutil.which("powershell.exe") is None and shutil.which("powershell") is None,
    reason="PowerShell is required to execute the Windows smoke script.",
)
def test_enqueue_sample_prompt_script_posts_expected_payload_to_localhost_smoke_seam() -> None:
    captured_request: dict[str, object] = {}

    class CaptureHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            captured_request["method"] = self.command
            captured_request["path"] = self.path
            captured_request["content_type"] = self.headers.get("Content-Type")
            captured_request["payload"] = json.loads(raw_body)

            response_body = json.dumps({"id": "prompt-smoke", "seq": 1}).encode("utf-8")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    assert powershell is not None

    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        completed = subprocess.run(
            [
                powershell,
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SMOKE_SCRIPT_PATH),
                "-BaseUrl",
                base_url,
                "-Source",
                "release-readiness-tests",
                "-IdempotencyKey",
                "smoke-proof-001",
                "-Body",
                "Script smoke body.",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    assert completed.returncode == 0
    assert captured_request["method"] == "POST"
    assert captured_request["path"] == "/api/prompts"
    assert captured_request["content_type"] == "application/json"

    payload = captured_request["payload"]
    assert isinstance(payload, dict)
    assert payload == {
        "body": "Script smoke body.",
        "source": "release-readiness-tests",
        "idempotency_key": "smoke-proof-001",
        "metadata": {
            "kind": "smoke",
            "created_by": "scripts/enqueue-sample-prompt.ps1",
        },
    }
