# HumanLoop Regression Checklist

This file is the canonical shared regression matrix for HumanLoop.

Use it when the app is being sanity-checked as a real operator workflow instead of only as isolated `TestClient` slices.

## Result Artifacts

Keep executed regression-run results under the task that owns the current work:

- `Tracking/task-<id>/Testing/REGRESSION-RUN-<N>.md`

The task-local [Tracking/task-0001/Testing/REGRESSION.md](/c:/Agent/HumanLoop/Tracking/task-0001/Testing/REGRESSION.md) file is retained as historical task context, but this repo-root file is the canonical checklist going forward.

## Environment Bootstrap

From the repo root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

Optional desktop shell support:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[desktop]
```

Expected:

- the editable install completes without dependency errors
- `pytest`, `httpx`, and `uvicorn` are available in the local virtual environment

## Automated Release Bar

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests\integration -q
```

Expected:

- the full pytest suite passes
- the live localhost integration suite passes

## Localhost Bootstrap

Start the app in one shell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

In another shell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/api/prompts/summary
```

Expected:

- `/healthz` returns `status = ok`
- `/api/prompts/summary` returns `pending_count = 0` when the queue is empty
- the configured runtime log file is created

## Required Smoke Cases

### REG-001 Empty Inbox Boot

Goal:
Confirm a fresh local app boot renders an honest empty operator state.

Steps:

1. Start the app against a clean runtime path.
2. Open `http://127.0.0.1:8000/inbox`.
3. Open `http://127.0.0.1:8000/inbox/current`.
4. Open `http://127.0.0.1:8000/inbox/queue`.

Expected result:

- the inbox loads without crashing
- the current fragment says `No pending prompts right now.`
- the queue fragment shows `0 waiting`
- no action buttons are rendered for an empty current card

### REG-002 Prompt Ingest And Duplicate Replay

Goal:
Confirm real localhost ingest works and duplicate retries stay safe.

Steps:

1. `POST /api/prompts` with a valid payload.
2. Repeat the same request with the same `source` and `idempotency_key`.
3. Fetch `/api/prompts/next`.

Expected result:

- the first request returns `201`
- the replay returns `200` with `"replayed": true`
- both responses point to the same prompt id and seq
- `/api/prompts/next` returns that same prompt

### REG-003 Current Prompt And Queue Rail Rendering

Goal:
Confirm the real rendered inbox separates the active prompt from the waiting queue.

Steps:

1. Enqueue two prompts.
2. Open `/inbox`.
3. Inspect `/inbox/current`.
4. Inspect `/inbox/queue`.

Expected result:

- the first prompt is the only actionable current item
- the second prompt appears only in the queue rail
- the Copy control is visible on the current prompt card
- the waiting count reflects the second prompt

### REG-004 Copy Does Not Hang Or Auto-Advance

Related bug note:

- [BUG1.md](/c:/Agent/HumanLoop/Tracking/task-0001/Testing/BUG1.md)

Goal:
Confirm the copy path resolves cleanly instead of hanging the action bar.

Steps:

1. Launch the running app with at least one current prompt.
2. Click `Copy`.

Expected result:

- the UI does not remain stuck on `Copying prompt...`
- the action buttons become usable again after the copy attempt resolves
- the workflow status changes to either `Copied` or a clear clipboard failure state
- the current prompt remains visible after the copy attempt
- the queue does not auto-advance on copy
- when clipboard write succeeds, the current prompt's copy count increments

### REG-005 Complete Advances Only After Explicit Action

Goal:
Confirm the queue only advances after an explicit complete action.

Steps:

1. Enqueue two prompts.
2. Complete the first prompt through the running app or live API.
3. Inspect `/inbox/current` and `/api/prompts/next`.

Expected result:

- the first prompt leaves the pending queue
- the second prompt becomes current
- the queue does not advance before the explicit complete action

### REG-006 Dismiss And Requeue Recovery

Goal:
Confirm dismiss is recoverable and requeue can restore operator place.

Steps:

1. Enqueue two prompts.
2. Dismiss the first prompt.
3. Confirm the second prompt becomes current.
4. Requeue the dismissed prompt.

Expected result:

- the first dismiss removes the prompt from the active queue without deleting history
- the second prompt becomes current after dismiss
- requeue restores the dismissed prompt to `pending`
- the requeued prompt can become current again immediately

### REG-007 Smoke Script Against A Live Server

Goal:
Confirm the bundled Windows smoke script can talk to a real running HumanLoop server.

Steps:

1. Start the app on localhost.
2. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\enqueue-sample-prompt.ps1
```

3. Fetch `/api/prompts/next` and open `/inbox`.

Expected result:

- the script exits successfully
- the sample prompt is enqueued through the live server
- the sample prompt is visible in `/inbox`

### REG-008 Desktop Wrapper Shell

Goal:
Confirm the optional native shell can still host the inbox correctly.

Steps:

1. Install desktop extras.
2. Launch:

```powershell
.\.venv\Scripts\humanloop-desktop.exe
```

3. Enqueue a prompt while the app is running.

Expected result:

- the desktop window opens without crashing
- the window title is prefixed with `HumanLoop Desktop`
- the desktop shell still reflects queue count changes

### REG-009 Real Browser Keyboard Loop

Goal:
Confirm the rendered inbox supports the low-friction keyboard loop without stealing operator place.

Steps:

1. Launch the running inbox in a real browser context with clipboard access.
2. Enqueue two prompts.
3. Press `?` to open shortcut help.
4. Press `C` to copy the current prompt.
5. Press `Enter` to complete the current prompt.

Expected result:

- the shortcut help panel opens from `?`
- `C` copies the current prompt and records the copied event without advancing the queue
- the current prompt stays visible after copy and the copy count increments
- `Enter` completes the current prompt and only then advances the second prompt into the current card

### REG-010 Background Refresh Preserves Current Prompt

Goal:
Confirm queue polling updates the rail without unexpectedly replacing the prompt the operator is reading.

Steps:

1. Launch the running inbox in a real browser context with one prompt already current.
2. Enqueue a second prompt while the first prompt remains open on screen.
3. Wait for the queue rail to refresh.
4. Dismiss the first prompt through the rendered UI.
5. Use the visible `Requeue` recovery control.

Expected result:

- the queue rail count updates to reflect the newly arrived prompt
- the original current prompt remains visible until the explicit dismiss action
- dismiss advances the second prompt into the current card
- requeue restores the original prompt as current and keeps the later prompt waiting in the rail

## Release Notes Before Commit / Push

Confirm:

- [README.md](/c:/Agent/HumanLoop/README.md) matches the current runbook and runtime paths
- [HANDOFF.md](/c:/Agent/HumanLoop/HANDOFF.md) still points at the correct canonical task handoff
- [Tracking/task-0001/HANDOFF.md](/c:/Agent/HumanLoop/Tracking/task-0001/HANDOFF.md) reflects the current local baseline
- the relevant pass audit under `Tracking/task-0001/Testing/` records the latest proof run
