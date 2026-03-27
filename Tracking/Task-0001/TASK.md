# Task 0001

This file is the canonical task definition and task-owned entry point for HumanLoop task tracking.

## Title

Local prompt inbox MVP for queued manual ChatGPT handoff.

## Why This Task Exists

The HumanLoop repo needs a real local backend and operator UI for prompt handoff, not just a loose architecture note.

The upstream capture path already exists outside this repo and can generate prompt payloads from local tools, but there is not yet a stable local service that:

- receives those prompts durably
- keeps them in a human-reviewed queue
- presents them in a fast local inbox
- lets the user copy, complete, or dismiss items without losing track of state

This task exists to turn the current research into the first concrete implementation target.

## Synced Baseline From Existing Repo Notes

This task is intentionally aligned with the current repo research in `Tracking/Task-0001/RESEARCH.md`.

Current assumptions already documented in the repo:

- the existing capture path is already operational outside this repo and can send prompt payloads locally
- the system must stay strictly human-in-the-loop when interacting with ChatGPT/OpenAI web products
- the right first cut is a single localhost service, not separate backend and frontend applications
- queue durability should be local and simple, with SQLite as the first persistence layer
- the inbox should be server-rendered and lightweight, with HTMX-style partial refreshes instead of a heavy SPA
- queue state should remain `pending`, `completed`, or `dismissed`
- copy activity should be tracked, but `copied` is not itself a terminal queue state
- prompt ingestion should be idempotent so retries do not create duplicate queue entries

This means `task-0001` should establish the local backend seam and operator workflow without introducing browser automation.

## Goal

Build the first working local HumanLoop service that can accept prompt submissions from the existing capture path and present them in a manual inbox UI.

For MVP, "working" means:

1. a producer can enqueue prompts over localhost
2. accepted prompts are stored durably and survive restart
3. the user can open a local inbox and see the active prompt plus the pending queue
4. the user can copy a prompt, then explicitly complete or dismiss it
5. duplicate or retried enqueue requests are safe
6. the system remains clearly on the manual side of the human-handoff boundary

## Proposed Repo Home

Keep task tracking under `Tracking/Task-0001/`.

Proposed implementation home for the first application code:

- `app/`

Recommended first-pass layout:

- `app/api/`
- `app/repo/`
- `app/templates/`
- `app/static/`
- `app/models.py`
- `app/db.py`
- `app/main.py`
- `tests/`
- `pyproject.toml` or `requirements.txt`
- `README.md`

Recommended runtime-managed paths that should not be committed:

- `data/runtime/`
- `data/runtime/humanloop.db`
- `data/runtime/logs/`

## Recommended Stack

Use Python for the MVP.

Reasons:

- the current repo has no established application stack yet, so the smallest reliable stack should win
- the research already converged on FastAPI plus SQLite as the cleanest local-first path
- Python keeps API, HTML templates, queue logic, and local tooling in one easy-to-run project
- Python also leaves room for later workflow integrations without forcing a larger frontend build system up front

Recommended MVP stack:

- FastAPI + Uvicorn for HTTP and local serving
- SQLite for durable queue state
- SQLAlchemy or a small repository layer for DB access
- Jinja2 templates for the inbox HTML
- HTMX for partial page refreshes
- minimal vanilla JavaScript for clipboard and keyboard shortcuts

Do not require Redis, RabbitMQ, React, Electron, Docker, or any browser automation layer in the first pass unless the scope is explicitly expanded.

## MVP Scope

The MVP for `task-0001` should do the following.

### 1. Prompt Ingest API

Implement:

- `POST /api/prompts`
- `GET /api/prompts?status=pending&limit=50`
- `GET /api/prompts/next`
- `GET /api/prompts/{id}`
- `GET /healthz`

`POST /api/prompts` must:

- accept prompt payloads from the existing capture path
- require `body`, `source`, and `idempotency_key`
- allow optional metadata
- validate enough input to reject obviously bad requests
- persist the prompt before returning success
- assign stable queue order
- return a replay-safe response when the same idempotency key is retried

### 2. Queue State And Actions

Implement:

- `POST /api/prompts/{id}/copied`
- `POST /api/prompts/{id}/complete`
- `POST /api/prompts/{id}/dismiss`
- `POST /api/prompts/{id}/requeue`

Minimum durable prompt fields:

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

Required state behavior:

- repeated ingest with the same idempotency key must not create duplicate active items
- `copied` must only update copy metadata
- `complete` and `dismiss` must remove items from the active queue without hard-deleting history
- repeated `complete` or repeated `dismiss` should be safe
- conflicting terminal transitions should fail clearly instead of silently flipping state

### 3. Operator Inbox UI

Implement:

- `GET /inbox`
- `GET /inbox/current`
- `GET /inbox/queue`

The inbox should provide:

- one clearly active prompt card with full text
- a pending queue rail or list with source, age, and preview
- a visible queue count
- clear Copy, Complete, and Dismiss actions
- lightweight status messaging for copy success and backend errors

### 4. Clipboard And Keyboard Workflow

The operator flow must stay fast and explicit.

Required behavior:

- copy should use browser clipboard APIs from a direct user action
- successful copy should record the copied event but keep the current prompt on screen
- completion should be explicit and separate from copy
- dismissal should be explicit and recoverable with requeue
- keyboard shortcuts should support a low-friction operator loop
- background refreshes must not unexpectedly replace the active prompt while the user is reading it

### 5. Local Durability And Operability

The MVP should also include:

- SQLite configured for practical local durability
- a simple health endpoint
- structured or at least consistent local logs
- a small runbook in `README.md`
- enough tests to keep queue behavior honest

## Important Contract Watchouts

This task must respect the manual handoff boundary described in the research.

Important consequences:

- do not automate prompt submission into ChatGPT/OpenAI web UIs
- do not infer completion just because a prompt was copied
- do not let UI polling or background refreshes steal the operator's place
- do not return success for ingest until the prompt is actually durable

Recommended stance for MVP:

- keep the service localhost-only by default
- keep CORS closed unless the producer truly requires it
- treat copy as an audit/UX event, not a workflow terminal state
- prefer explicit complete/dismiss actions over clever automation

## Non-Goals

`task-0001` MVP should not try to solve the whole long-term workflow in one pass.

Do not include these unless the task is explicitly expanded:

- automated browser submission or browser scripting against ChatGPT/OpenAI
- multi-user support
- remote hosting or cloud sync
- prompt priorities or drag-and-drop reordering
- prompt editing/version history workflows
- a React or Electron rewrite
- external queue infrastructure such as Redis or RabbitMQ
- advanced auth or public internet exposure

## Acceptance Criteria

The task should be considered complete when all of the following are true:

1. a real local application project exists under the proposed repo home
2. the current capture path can enqueue prompts to `POST /api/prompts` over localhost
3. accepted prompts are durably stored before the API returns success
4. duplicate enqueue attempts using the same idempotency key are safe
5. `/inbox` shows the current prompt and the pending queue
6. copying a prompt records copy metadata but does not auto-complete it
7. complete and dismiss remove prompts from the active queue while preserving history
8. tests cover at least:
   - happy-path enqueue
   - duplicate idempotent enqueue
   - next-item retrieval
   - copy-not-terminal behavior
   - complete flow
   - dismiss or requeue flow
   - restart persistence
9. the repo includes a minimal local runbook

## Proposed Path Forward

Keep implementation in bounded passes.

### Pass A: app scaffold and durable ingest

Build:

- application skeleton
- config loading
- SQLite setup
- `GET /healthz`
- `POST /api/prompts`
- durable prompt storage
- idempotent enqueue behavior

Exit bar:

- prompts can be enqueued end-to-end
- accepted prompts land in the database durably
- duplicate requests are safe

### Pass B: inbox UI and queue actions

Build:

- `GET /inbox`
- `GET /inbox/current`
- `GET /inbox/queue`
- copied, complete, dismiss, and requeue actions
- queue fragment refresh behavior
- clipboard and keyboard workflow

Exit bar:

- a local operator can process prompts through the inbox without touching the database manually
- the active prompt stays stable until the operator explicitly changes state

### Pass C: polish and future seams

Build only enough polish to keep the system operable:

- `README.md` run instructions
- error/status messaging
- queue-empty state
- logging cleanup
- light UX hardening around copy failures and reconnect behavior

Prepare, but do not fully implement yet:

- richer producer authentication if needed
- multiple queue views or filters
- more advanced operator analytics
- future desktop packaging or cross-platform startup polish

## Recommended First Implementation Slice

If work starts immediately, begin with this narrow slice:

1. create the `app/` and `tests/` skeleton
2. implement `GET /healthz`
3. implement `POST /api/prompts`
4. add a SQLite `prompt_items` table with idempotency support
5. implement `GET /api/prompts/next`
6. add tests for successful enqueue, duplicate enqueue, and restart persistence

This is the smallest slice that turns the current HumanLoop concept into a durable backend seam.

## References

Use these repo notes as the source of truth for the first implementation:

- `Tracking/Task-0001/RESEARCH.md`
