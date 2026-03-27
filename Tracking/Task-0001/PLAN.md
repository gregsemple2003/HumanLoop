# Task 0001 Plan: Local Prompt Inbox MVP

## Summary

Build a single Windows-first localhost application that receives prompts from the existing capture path, stores them durably in SQLite, and serves a lightweight operator inbox for explicit human handoff.

The MVP stack is:

- Python 3.12
- FastAPI
- SQLite
- Jinja2
- HTMX
- minimal vanilla JavaScript

The workflow is strict FIFO. Only the head prompt is actionable, copy is tracked but never terminal, and completion or dismissal stays explicit.

## Implementation Changes

### Pass 0: App Spine And Runtime Contract

Create the runnable project skeleton under `app/` and `tests/`, plus runtime-managed `data/runtime/` paths for the database and logs.

Settle on `pyproject.toml` with:

- FastAPI
- Uvicorn
- Jinja2
- SQLAlchemy or a thin repository layer
- pytest
- HTTP test tooling

Add config for host, port, database path, and logging.

Initialize the database on startup and implement `GET /healthz`.

Exit bar:

- one-command local startup on Windows
- predictable runtime paths
- a healthy app process

### Pass 1: Durable Ingest Seam

Create a single `prompt_items` table with:

- `id`
- `seq`
- `source`
- `idempotency_key`
- `body`
- `metadata_json`
- `status`
- `copy_count`
- `last_copied_at`
- `created_at`
- `updated_at`
- `completed_at`
- `dismissed_at`

Use SQLite WAL mode and a busy timeout for practical local durability.

Implement `POST /api/prompts` with required:

- `body`
- `source`
- `idempotency_key`

Allow optional `metadata`.

Enforce idempotency on `(source, idempotency_key)` and return replay-safe results:

- `201` for a new row
- `200` for a safe replay of the same prompt

Exit bar:

- prompts are durable before success is returned
- retries do not duplicate queue entries
- queue order is assigned by `seq`

### Pass 2: Queue API And State Transitions

Implement:

- `GET /api/prompts?status=pending&limit=50`
- `GET /api/prompts/next`
- `GET /api/prompts/{id}`
- `POST /api/prompts/{id}/copied`
- `POST /api/prompts/{id}/complete`
- `POST /api/prompts/{id}/dismiss`
- `POST /api/prompts/{id}/requeue`

Keep queue status limited to:

- `pending`
- `completed`
- `dismissed`

Make `copied` update only `copy_count` and `last_copied_at`.

Make `complete` and `dismiss` soft-terminal transitions that preserve history.

Allow repeated identical terminal actions to be safe, but return `409` for conflicting terminal transitions such as dismissing an already completed item.

Exit bar:

- the full lifecycle works over the API
- no manual database edits are needed
- queue history is preserved

### Pass 3: Server-Rendered Inbox Vertical Slice

Implement:

- `GET /inbox`
- `GET /inbox/current`
- `GET /inbox/queue`

Render:

- one full current-prompt card
- one pending queue rail

Keep the queue rail informational only in MVP. Non-head items are visible but not actionable.

Show:

- queue count
- source
- age
- preview
- empty-state handling

Use HTMX partial refresh for the queue rail. Do not replace the active prompt in the background while the operator is reading it.

Exit bar:

- the operator can open the inbox
- the operator can work the queue end to end from the browser

### Pass 4: Clipboard And Operator Workflow

Handle Copy in the browser with `navigator.clipboard.writeText()` from a direct user action.

After successful clipboard write, call `POST /api/prompts/{id}/copied` but keep the same prompt visible.

Add explicit Complete and Dismiss actions that wait for the server response before advancing.

Add Requeue for dismissed items as the recovery path.

Add keyboard shortcuts:

- `c` copy
- `Enter` complete
- `d` dismiss
- `?` help

Use:

- visible in-flight indicators
- status messaging
- a sticky action area for long prompts

Exit bar:

- the inbox supports a fast manual loop
- there is no surprise auto-advance
- there is no silent state desync

### Pass 5: Integration And Release Readiness

Point the existing capture path at `POST /api/prompts`.

Keep the app bound to localhost only by default and keep CORS closed.

Do not add auth in MVP. Rely on localhost-only exposure and leave auth as a future seam.

Write a Windows-first runbook in `README.md` covering:

- startup
- shutdown
- database location
- log location
- recovery expectations

Add a simple smoke path for enqueueing a sample prompt and processing it through the inbox.

Exit bar:

- the producer can enqueue locally
- the operator can process prompts locally
- the app survives restart with queue state intact

## Public Interfaces

### Ingest Request

`POST /api/prompts`

Required fields:

- `body`
- `source`
- `idempotency_key`

Optional fields:

- `metadata`

### Queue Reads

- `GET /api/prompts?status=pending&limit=50`
- `GET /api/prompts/next`
- `GET /api/prompts/{id}`

### Queue Actions

- `POST /api/prompts/{id}/copied`
- `POST /api/prompts/{id}/complete`
- `POST /api/prompts/{id}/dismiss`
- `POST /api/prompts/{id}/requeue`

### UI Routes

- `GET /inbox`
- `GET /inbox/current`
- `GET /inbox/queue`

Behavioral contract:

- the current prompt is sticky until the user explicitly completes or dismisses it

## Test Plan

Cover:

- ingest success
- duplicate idempotent ingest
- restart persistence
- FIFO next-item retrieval
- stable ordering by `seq`
- copy-not-terminal behavior
- complete flow
- dismiss flow
- requeue flow
- conflicting terminal transitions returning `409`
- inbox rendering for non-empty and empty queues
- one end-to-end smoke test from producer enqueue to browser copy to explicit completion

## Assumptions And Defaults

- Windows-first MVP
- single-user, localhost-only deployment
- no Docker, Redis, RabbitMQ, React, Electron, or browser automation in MVP
- strict FIFO operator model where only the head prompt is actionable
- no ingest auth in MVP
- the saved source of truth is `Tracking/Task-0001/TASK.md` and `Tracking/Task-0001/RESEARCH.md`
