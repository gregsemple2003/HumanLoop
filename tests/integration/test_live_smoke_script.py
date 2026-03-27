from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "enqueue-sample-prompt.ps1"


@pytest.mark.skipif(
    shutil.which("powershell.exe") is None and shutil.which("powershell") is None,
    reason="PowerShell is required to execute the Windows smoke script.",
)
def test_smoke_script_enqueues_a_prompt_against_a_live_humanloop_server(
    live_server,
) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    assert powershell is not None

    completed = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SMOKE_SCRIPT_PATH),
            "-BaseUrl",
            live_server.base_url,
            "-Source",
            "integration-live-smoke",
            "-IdempotencyKey",
            "integration-live-smoke-001",
            "-Body",
            "Live smoke script prompt body.",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )

    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        next_prompt = client.get("/api/prompts/next")
        inbox = client.get("/inbox")

    assert completed.returncode == 0
    assert "Enqueued sample prompt." in completed.stdout
    assert f"url: {live_server.base_url}/inbox" in completed.stdout

    assert next_prompt.status_code == 200
    assert next_prompt.json()["source"] == "integration-live-smoke"
    assert next_prompt.json()["body"] == "Live smoke script prompt body."

    assert inbox.status_code == 200
    assert "Live smoke script prompt body." in inbox.text
    assert 'data-workflow-action="copy"' in inbox.text
