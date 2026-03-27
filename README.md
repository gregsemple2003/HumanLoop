# HumanLoop

HumanLoop is a Windows-first localhost inbox for manually handing prompts to ChatGPT or similar browser workflows without automating the web UI.

## Quick Start

Install the app and test tooling into the local virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

Start the app on localhost:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open the operator inbox at [http://127.0.0.1:8000/inbox](http://127.0.0.1:8000/inbox).

Stop the app with `Ctrl+C` in the terminal that started Uvicorn.

## Runtime Paths

The default runtime-managed paths are:

- Database: `data/runtime/humanloop.db`
- Log file: `data/runtime/logs/humanloop.log`

You can override them with environment variables before startup:

```powershell
$env:HUMANLOOP_HOST = "127.0.0.1"
$env:HUMANLOOP_PORT = "8000"
$env:HUMANLOOP_DATABASE_PATH = "C:\Temp\humanloop.db"
$env:HUMANLOOP_LOG_PATH = "C:\Temp\humanloop.log"
$env:HUMANLOOP_LOG_LEVEL = "INFO"
```

The app stays bound to localhost by default, and it does not enable CORS middleware in MVP. That keeps the service on the local/manual side of the handoff boundary unless you intentionally widen it later.

## Producer Contract

Point the existing capture path at `POST /api/prompts` on the running local service:

- URL: `http://127.0.0.1:8000/api/prompts`
- Required JSON fields: `body`, `source`, `idempotency_key`
- Optional JSON field: `metadata`

Example payload:

```json
{
  "body": "Draft a concise handoff note for the operator.",
  "source": "capture-path",
  "idempotency_key": "capture-20260326-0001",
  "metadata": {
    "kind": "manual-handoff",
    "batch": "nightly"
  }
}
```

The ingest endpoint returns:

- `201 Created` for a newly stored prompt
- `200 OK` with `"replayed": true` when the same `source` plus `idempotency_key` is retried safely
- `409 Conflict` if the same `source` plus `idempotency_key` is reused for a different payload

## Smoke Path

Use the bundled Windows smoke script to enqueue a sample prompt through the same localhost ingest seam the producer should use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\enqueue-sample-prompt.ps1
```

The script prints the created prompt id/seq and reminds you to open `/inbox`.

Manual smoke loop:

1. Start the app.
2. Run `.\scripts\enqueue-sample-prompt.ps1`.
3. Open `http://127.0.0.1:8000/inbox`.
4. Click `Copy`, paste the prompt wherever you are doing the manual handoff, then return to the inbox.
5. Click `Complete` to advance, or `Dismiss` and optionally `Requeue` if you want to restore the prompt.

If you want to inspect the queue API during the smoke:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/prompts/next
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/prompts?status=pending
```

## Recovery Expectations

- Queue state is durable in SQLite and survives restarts as long as the database file is preserved.
- Copy is tracked for audit and UX only; it does not complete a prompt.
- Complete and Dismiss are explicit state changes. Dismissed items can be restored with `POST /api/prompts/{id}/requeue`.
- Retry-safe producers should reuse the same `idempotency_key` when resending the same prompt payload.
- If clipboard access is blocked in the browser, the inbox keeps the current prompt visible so you can copy manually without losing your place.
