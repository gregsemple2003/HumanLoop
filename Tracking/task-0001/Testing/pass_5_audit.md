# Pass 5 Audit

## Scope

Pass 5 in `Tracking/task-0001/PLAN.md` covers integration and release-readiness work on top of the implemented inbox MVP:

- point the existing capture path at `POST /api/prompts`
- keep the app bound to localhost only by default
- keep CORS closed in MVP
- keep auth out of MVP and rely on localhost-only exposure as the current seam
- add a Windows-first runbook in `README.md`
- cover startup, shutdown, database location, log location, and recovery expectations
- add a simple smoke path for enqueueing a sample prompt and processing it through the inbox
- keep queue state durable across restarts

Grounding note:

- `AGENTS.md` was not present as a physical workspace file, so this pass followed the instructions provided in the task prompt.
- `Tracking/task-0001/exemplars/PASS_3_AUDIT.md` was not present in this workspace, so this audit grounded on `Tracking/task-0001/TASK.md`, `Tracking/task-0001/PLAN.md`, `Tracking/task-0001/HANDOFF.md`, the earlier audits under `Tracking/task-0001/Testing/`, the current app under `app/`, the release-readiness slice in `tests/test_release_readiness.py`, and the existing durability proof in `tests/test_ingest.py`.

## Expansion Summary

- Expanded the focused pass-5 release-readiness slice from 3 tests to 5 tests.
- Added deterministic proof that `README.md` covers the runbook contract called out in pass 5: startup, shutdown, runtime paths, producer contract, smoke path, and recovery expectations.
- Added deterministic proof that `scripts/enqueue-sample-prompt.ps1` executes successfully, posts the expected JSON payload to `/api/prompts`, and keeps its default behavior on the localhost smoke seam.
- Re-ran the pass-5 slice together with the existing restart-durability proof in `tests/test_ingest.py`, then re-ran the full repo test suite.
- Added one live localhost smoke run against a real Uvicorn process on a throwaway runtime path, confirming the sample script can enqueue a prompt, `/inbox` renders that prompt with the pass-4 Copy control, explicit completion drains the current prompt, and runtime logs are written to the configured file.

## Contraction Summary

- Did not widen the production app surface for this pass; the work stayed on proof coverage and audit tightening.
- Did not add browser automation, clipboard harnesses, or desktop packaging.
- Did not wire the external producer/capture path itself, because that code lives outside this workspace.
- Kept the new proof deterministic and local: the script test uses a local HTTP capture server, and the live smoke uses a throwaway localhost runtime path rather than shared machine state.

## Exact Commands Run

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_release_readiness.py -q
```

Observed result before the proof expansion:

- `3 passed in 0.32s`

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_release_readiness.py -q
```

Observed result after the proof expansion:

- `5 passed in 1.07s`

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_ingest.py tests\test_release_readiness.py -q
```

Observed result:

- `19 passed in 1.39s`

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Observed result:

- `48 passed in 2.75s`

```powershell
$port = 8011
$baseUrl = "http://127.0.0.1:$port"
$runtimeRoot = Join-Path $env:TEMP ("humanloop-pass5-smoke-" + [guid]::NewGuid().ToString())
$env:HUMANLOOP_DATABASE_PATH = Join-Path $runtimeRoot "humanloop.db"
$env:HUMANLOOP_LOG_PATH = Join-Path $runtimeRoot "logs\humanloop.log"
$env:HUMANLOOP_LOG_LEVEL = "INFO"
$process = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:create_app","--factory","--host","127.0.0.1","--port",$port -WorkingDirectory (Get-Location) -PassThru
try {
    $healthy = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $health = Invoke-RestMethod -Uri "$baseUrl/healthz"
            $healthy = $true
            break
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $healthy) {
        throw "App failed to become healthy at $baseUrl"
    }

    $scriptOutput = powershell -ExecutionPolicy Bypass -File ".\scripts\enqueue-sample-prompt.ps1" -BaseUrl $baseUrl
    $next = Invoke-RestMethod -Uri "$baseUrl/api/prompts/next"
    $inboxHtml = (Invoke-WebRequest -Uri "$baseUrl/inbox").Content
    $complete = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/prompts/$($next.id)/complete"
    $currentHtml = (Invoke-WebRequest -Uri "$baseUrl/inbox/current").Content
    $logText = Get-Content -Raw $env:HUMANLOOP_LOG_PATH

    [pscustomobject]@{
        health_status = $health.status
        smoke_output = ($scriptOutput -join " || ")
        prompt_id = $next.id
        prompt_seq = $next.seq
        inbox_contains_prompt = $inboxHtml -like '*Smoke test prompt from HumanLoop pass 5.*'
        inbox_contains_copy = $inboxHtml -like '*data-workflow-action="copy"*'
        complete_status = $complete.status
        current_empty_after_complete = $currentHtml -like '*No pending prompts right now.*'
        log_has_database_line = $logText -like '*HumanLoop database ready at*'
        log_has_logpath_line = $logText -like '*HumanLoop logs writing to*'
    } | ConvertTo-Json -Compress
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    Remove-Item Env:HUMANLOOP_DATABASE_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:HUMANLOOP_LOG_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:HUMANLOOP_LOG_LEVEL -ErrorAction SilentlyContinue
}
```

Observed result:

- `health_status` was `ok`
- the smoke script printed an enqueue success message, a concrete prompt id, `seq: 1`, and the inbox URL
- `/api/prompts/next` returned the same prompt id created by the smoke script
- `/inbox` contained the smoke prompt body and the pass-4 `data-workflow-action="copy"` control
- `POST /api/prompts/{id}/complete` returned `status: completed`
- `/inbox/current` rendered `No pending prompts right now.` after completion
- the configured log file contained both startup lines for the database path and log path

## Observed Proof Logs Or Other Concrete Evidence

No dedicated proof-log line pattern exists in the current repo. Proof for this pass comes from deterministic unit tests, concrete artifact assertions, the existing restart-durability test, and the live localhost smoke command above.

Concrete evidence observed from the unit slice:

- `tests/test_release_readiness.py::test_settings_default_to_localhost_runtime_paths` proves `Settings.from_env()` defaults the app to `127.0.0.1:8000` and the expected runtime-managed database/log paths.
- `tests/test_release_readiness.py::test_app_does_not_emit_cors_headers_by_default` proves the app does not emit `access-control-allow-origin` or credentials CORS headers by default.
- `tests/test_release_readiness.py::test_app_startup_writes_runtime_logs_to_the_configured_log_path` proves startup writes `HumanLoop database ready at ...` and `HumanLoop logs writing to ...` to the configured log file.
- `tests/test_release_readiness.py::test_readme_documents_the_pass_five_runbook_contract` proves `README.md` contains the Windows-first startup command, `Ctrl+C` shutdown guidance, runtime paths, producer contract details, the smoke-script command, and recovery expectations.
- `tests/test_release_readiness.py::test_enqueue_sample_prompt_script_posts_expected_payload_to_localhost_smoke_seam` executes `scripts/enqueue-sample-prompt.ps1` against a local capture server and proves it posts to `/api/prompts` with the expected `body`, `source`, `idempotency_key`, and smoke metadata payload.
- `tests/test_ingest.py::test_prompt_survives_app_restart` remains green and proves queue durability across app restarts.

Concrete evidence observed from the live localhost smoke:

- The live smoke summary returned `{"health_status":"ok",...,"prompt_seq":1,...,"inbox_contains_prompt":true,"inbox_contains_copy":true,"complete_status":"completed","current_empty_after_complete":true,"log_has_database_line":true,"log_has_logpath_line":true}`.
- The smoke script output included `Enqueued sample prompt.`, a concrete prompt id, `seq: 1`, and the next-step reminders for opening `/inbox`, copying the prompt, and completing or dismissing it explicitly.
- The real inbox HTML contained the smoke prompt body and the Copy control, which proves the sample prompt reaches the operator surface over localhost.

## Requirement Mapping

| Requirement | Evidence (test / proof log / artifact) | Result |
| --- | --- | --- |
| Point the existing capture path at `POST /api/prompts`. | No in-repo evidence exists because the external capture path lives outside this workspace. The repo runbook documents the target URL in `README.md`, but the actual upstream wiring was not performed here. | Not yet proven |
| Keep the app bound to localhost only by default. | `app/config.py` defaults `host` to `127.0.0.1`, and `tests/test_release_readiness.py::test_settings_default_to_localhost_runtime_paths` proves that default. | Proven |
| Keep CORS closed in MVP. | `tests/test_release_readiness.py::test_app_does_not_emit_cors_headers_by_default` proves the app does not emit CORS headers by default. | Proven |
| Keep auth out of MVP and rely on localhost-only exposure as the current seam. | The release-readiness tests and the live smoke both hit `/healthz`, `/api/prompts`, `/api/prompts/next`, `/inbox`, and `/api/prompts/{id}/complete` without auth headers or tokens and succeed, while `tests/test_release_readiness.py::test_settings_default_to_localhost_runtime_paths` proves the default localhost binding. | Proven at current repo boundary |
| Add a Windows-first runbook in `README.md`. | `README.md` exists at the repo root, and `tests/test_release_readiness.py::test_readme_documents_the_pass_five_runbook_contract` proves it contains the required Windows-first runbook sections. | Proven |
| Cover startup, shutdown, database location, log location, and recovery expectations in the runbook. | `tests/test_release_readiness.py::test_readme_documents_the_pass_five_runbook_contract` proves the startup command, `Ctrl+C` shutdown note, `data/runtime/humanloop.db`, `data/runtime/logs/humanloop.log`, and recovery expectations are all documented in `README.md`. | Proven |
| Document the producer contract for `POST /api/prompts`. | `tests/test_release_readiness.py::test_readme_documents_the_pass_five_runbook_contract` proves `README.md` documents the `POST /api/prompts` URL plus the `201`, replay-safe `200`, and conflict `409` response contract. | Proven |
| Add a simple smoke path for enqueueing a sample prompt and processing it through the inbox. | `scripts/enqueue-sample-prompt.ps1` is executed by `tests/test_release_readiness.py::test_enqueue_sample_prompt_script_posts_expected_payload_to_localhost_smoke_seam`, and the live localhost smoke proves that same script-created prompt appears in `/inbox` and can be explicitly completed. | Proven at script plus localhost app boundary |
| The producer can enqueue locally. | The live localhost smoke proves the repo-provided sample producer script can enqueue locally through `POST /api/prompts`, and `tests/test_release_readiness.py::test_enqueue_sample_prompt_script_posts_expected_payload_to_localhost_smoke_seam` proves the exact request contract. | Proven for the in-repo smoke producer only |
| The operator can process prompts locally. | The live localhost smoke proves the prompt reached `/inbox`, rendered the Copy control, and could be explicitly completed so `/inbox/current` became empty. | Proven at localhost app boundary; real-browser/manual copy loop still unproven |
| The app survives restart with queue state intact. | `tests/test_ingest.py::test_prompt_survives_app_restart` proves a prompt remains durable across app restarts and replays safely afterward. | Proven |

## Intentional Non-Goals

- No Playwright, Selenium, or other real-browser harness was added.
- No auth layer, public exposure, or non-localhost deployment support was introduced.
- No external producer code outside this repo was modified.

## Remaining Risks

- The actual upstream capture path still is not wired from its own codebase into this repo’s running `POST /api/prompts` endpoint.
- The pass-4 browser-proof gaps still remain: this pass now proves the inbox seam over localhost, but not a real clipboard/manual operator loop in Chromium or Edge.
- The product-policy seams still remain open from earlier passes: terminal-copy semantics, repeated `requeue` semantics, and whether the queue rail should explicitly call out its 50-item visible cap.

## Integration-Level Proof Still Needed

- External producer wiring proof from the out-of-repo capture path into this repo’s running service.
- Browser-level proof that a human operator can copy from the rendered inbox, complete or dismiss explicitly, and keep their place while the queue rail refreshes in a real browser session.

## Pass Status

Pass 5 should remain open.

Reason:

- The repo now has stronger deterministic unit proof for release readiness plus a concrete localhost smoke path that reaches the inbox and completes a prompt.
- The out-of-repo capture-path wiring requirement is still unproven here, and the real-browser operator loop remains unproven.
