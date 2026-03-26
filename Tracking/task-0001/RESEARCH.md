# HumanLoop Queueing

## User

For repo - HumanLoop

### **task-0001/TASK.md**

**Title:** Backend Architecture - Prompt Queue & Manual Handoff System

**Context & Background**
We are building a local "Prompt Inbox" to streamline bulk workflows with the ChatGPT Pro web interface. To strictly comply with OpenAI's Terms of Service (which prohibit automated or programmatic interaction with their web UI), we cannot automate the actual submission of prompts to the browser.

Instead, we are building a local middleman application. The frontend capture mechanism is already operational—it successfully intercepts/generates prompt requests from our local tools. We now need a backend to receive, queue, and serve these prompts so a human user can manually copy-paste them into the ChatGPT web interface efficiently, without context-switching constantly.

**Core Objectives**
1. **Ingestion:** Provide a reliable endpoint/mechanism to receive incoming text payloads (the prompts) from the existing frontend capture path.
2. **Queue Management:** Establish a system to hold these pending prompts in a queue until the user is ready for them.
3. **User Interface Delivery:** Serve a lightweight local UI (the "Inbox") that displays the pending queue in an easily readable format.
4. **State Management:** Allow the user to interact with the UI to easily copy a prompt to their clipboard and mark it as "completed" or "dismissed," removing it from the active queue.

**The Ask**
Based on this context, please propose a high-level architectural path and an implementation plan. Recommend the most appropriate lightweight, local tech stack for this use case, and outline the sequence of steps required to build the backend and wire it up to the UI.

---

Would you like me to add any specific environmental constraints (like ensuring it runs easily on a specific OS) before you copy this over?

## Assistant

I’m checking the repo structure first so I can anchor the recommendation to what’s already there, then I’ll lay out a concrete backend/UI plan instead of a generic stack suggestion.

The repo doesn’t appear to be mounted here, so I’m grounding this in the task itself. I’m converging on a single localhost service with SQLite-backed queue state and a thin server-rendered inbox, while pinning down the endpoint contract and state model.

The single-server route now looks like the best first cut because it keeps queue, API, and inbox in one process, making local shipping, testing, and crash recovery simpler. One key state-model detail: “copied” should be tracked as an event for UX/audit, while the queue itself stays pending/completed/dismissed.

I couldn’t inspect the HumanLoop repo contents here, so I’m optimizing for the task as written.

For this job, I’d take the smallest reliable path: a single local service, not separate backend/frontend apps. My default stack would be Python 3.12 + FastAPI for the HTTP layer, SQLite for persistence, Jinja2 templates plus HTMX for the inbox UI, and a tiny amount of vanilla JS for clipboard and keyboard shortcuts. FastAPI can serve templates and static files from the same app, HTMX supports HTML-driven requests and interval polling, SQLite’s WAL mode improves local read/write concurrency, and the browser Clipboard API is available through `navigator.clipboard`; browsers also treat `http://localhost` and `http://127.0.0.1` as potentially trustworthy local origins.

I would not introduce Redis, RabbitMQ, React, or Electron in v1. This is a single-user local inbox with manual handoff, so one process and one local DB is the right complexity level.

Recommended architecture path

```text
Existing capture path
        |
        |  POST /api/prompts
        v
+---------------------------+
| Local FastAPI service     |
| - validation              |
| - idempotent enqueue      |
| - queue actions           |
| - serves /inbox           |
+-------------+-------------+
              |
              v
        SQLite database
       (prompt_items table)
              ^
              |
     HTMX-polled local Inbox UI
     - copy to clipboard
     - complete
     - dismiss
     - optional requeue
```

The system boundary should stop at the inbox. Producers enqueue prompts; the backend stores and renders them; the human manually copies and pastes into ChatGPT. No downstream browser automation, auto-submit, or UI scripting.

Have `/inbox` render a full page and a queue fragment that refreshes every 1–2 seconds with HTMX. Keep WebSockets as a later upgrade only if you discover that polling is too chatty or you want instant multi-tab sync; FastAPI does support WebSockets, but they are not necessary for the first cut. Copy should be a distinct UI action calling `navigator.clipboard.writeText()` from the button click handler, and completion/dismissal should be separate so a copied item is not auto-removed before the user actually submits it.

Queue/state model

Use one primary table, `prompt_items`, with fields like:

- `seq` integer autoincrement for FIFO ordering
- `id` UUID for public/API identity
- `source`
- `external_id` or `idempotency_key`
- `body`
- `metadata_json`
- `status = pending | completed | dismissed`
- `copy_count`
- `last_copied_at`
- `created_at`, `updated_at`
- `completed_at`, `dismissed_at`

Two design choices matter here:

First, do not make “copied” a terminal state. Copying is just a user assist, not proof that the prompt was actually pasted or used. Track copy metadata separately.

Second, do not hard-delete rows when the user completes or dismisses them. Soft-state them out of the active queue. That preserves history, makes retries safer, and helps debug accidental duplicate ingestion.

For SQLite, enable WAL and set a modest busy timeout or retry policy. WAL improves concurrency and is often faster than rollback journaling, but busy errors can still happen in edge cases.

Endpoint shape

A simple contract is enough:

- `POST /api/prompts`
  Accept a new prompt from the existing capture path. Payload should include `body`, `source`, optional `metadata`, and ideally an `idempotency_key`.
- `GET /api/prompts?status=pending`
  Return active queue items in FIFO order.
- `GET /api/prompts/next`
  Return the next pending prompt for the “current card” view.
- `POST /api/prompts/{id}/copied`
  Increment `copy_count`, set `last_copied_at`.
- `POST /api/prompts/{id}/complete`
  Mark done and remove from active queue.
- `POST /api/prompts/{id}/dismiss`
  Mark dismissed and remove from active queue.
- `POST /api/prompts/{id}/requeue`
  Optional, but worth having early.
- `GET /inbox`
  Serve the local UI.
- `GET /healthz`
  Simple local readiness check.

If the current capture path can retry on failure, make `POST /api/prompts` idempotent. That gives you “reliable enough” ingestion without adding a real message broker.

UI behavior

The best inbox layout for this workflow is:

- top/current prompt card with full text
- pending queue list below or beside it
- big Copy button
- separate Complete and Dismiss buttons
- source label, created time, and a short preview in the queue list
- keyboard shortcuts like `C = copy`, `Enter = complete`, `D = dismiss`, `J/K = move selection`

That keeps the manual handoff loop very fast while staying clearly on the right side of the “human in the loop” boundary.

Implementation sequence

Bootstrap the local service
Create the FastAPI app, dependency wiring, config, logging, and `/healthz`. Bind to `127.0.0.1` by default.

Add persistence
Create the SQLite schema and repository layer. Turn on WAL, busy timeout, and indexes on `status`, `seq`, and `external_id`/`idempotency_key`.

Implement ingestion
Build `POST /api/prompts` with validation, max payload size, and idempotency handling. Return the prompt ID plus queue position.

Implement queue actions
Add list/next/copy/complete/dismiss/requeue endpoints. Make action endpoints idempotent where practical.

Serve the inbox UI
Add `/inbox`, server-rendered templates, and HTMX fragments for the queue list and current item.

Wire clipboard + UX
Add the copy button with `navigator.clipboard.writeText()`, success/error toast, and keyboard shortcuts.

Connect the existing capture path
Point the current frontend capture mechanism at `POST /api/prompts`. If it can retry, ensure it reuses the same idempotency key.

Add tests
Cover enqueue idempotency, FIFO ordering, state transitions, restart persistence, and the “copy does not auto-complete” rule.

Add minimal hardening
Keep it localhost-only, keep CORS closed unless the producer truly needs it, and add an optional local bearer token for ingestion if multiple local processes or an extension can hit the endpoint.

Scope guidance

For v1, I would explicitly keep these out of scope:

- multi-user access
- remote hosting
- cloud sync
- automatic ChatGPT submission
- prompt editing/versioning
- queue priorities or drag-and-drop reordering

Those can all come later if the manual inbox proves useful.

What I’d add to the task before copying it over

Yes — I would add a few constraints, because they affect the implementation a lot:

- Single-user, local-only
- Must bind to localhost only
- Persistence across restarts is required
- No automation of the ChatGPT/OpenAI web UI; human copy/paste only
- Specify OS target: either “macOS first” or “must run on macOS + Windows”
- Specify install model: “no Docker required” vs “Docker is acceptable”
- Ingestion must be idempotent and tolerate retries

If you only add one extra constraint, make it the OS/install target. That choice affects packaging, startup scripts, and how much polish you want around the local runtime.

If HumanLoop is already heavily TypeScript, I’d keep the same architecture but implement it in the repo’s existing stack rather than forcing Python. The important decisions are the single local service, SQLite-backed queue, and server-rendered manual inbox.

## User

Okay, can you sketch out the endpoint implementation more?

## Assistant

I’m going to check the HumanLoop repo shape first so the endpoint sketch fits the existing stack, then I’ll turn that into concrete route handlers, request/response models, and state transitions.

I couldn’t find a local HumanLoop checkout here, so I’m drafting this as a portable FastAPI + SQLite vertical slice: concrete request models, route contracts, SQL constraints, and a small service/repository split. I’ve narrowed it to one ingest route, two read routes, three action routes, and one HTMX fragment route.

Yes — I’d make the backend a very small JSON API for two clients: the prompt producer and the local inbox UI. FastAPI fits this nicely because request bodies map cleanly to Pydantic models, routes can declare explicit `status_code` values, and `response_model` shapes/validates the returned payload; for reads, keep filters on query params instead of GET bodies.

For persistence, I’d keep one SQLite connection per request, enable WAL on the DB file, and set a modest `busy_timeout`. WAL is intended to improve concurrency over rollback journaling for local read/write workloads, and once WAL mode is set on a database file it persists across connections and restarts.

I don’t have the HumanLoop repo checked out here, so this is a clean drop-in sketch.

Endpoint shape I’d implement first

- `POST /api/prompts`
  producer enqueue
  `201` when a new prompt is created
  `200` when the same (`source`, `idempotency_key`) is replayed
- `GET /api/prompts?status=pending&limit=50`
  list queue items
- `GET /api/prompts/next`
  fetch the next pending item
- `GET /api/prompts/{id}`
  fetch one item
- `POST /api/prompts/{id}/copied`
  increment `copy_count` and stamp `last_copied_at`
- `POST /api/prompts/{id}/complete`
  mark terminal state `completed`
- `POST /api/prompts/{id}/dismiss`
  mark terminal state `dismissed`

I’d keep complete and dismiss as explicit POST actions instead of DELETE, because these are domain state transitions, not record destruction.

Minimal schema

FastAPI sketch

A few implementation choices I’d keep

- `idempotency_key` should be required on ingest. That turns retries into a safe replay path instead of duplicate queue entries.
- I’d make `POST /api/prompts` return `201` for a true insert and `200` for a duplicate replay of the same idempotency key. That makes producer behavior very simple: retry freely.
- For terminal actions, I’d make them idempotent only when repeated with the same target. So:
  `calling complete twice returns the same completed item`
  `calling dismiss twice returns the same dismissed item`
  `calling dismiss after complete returns 409`

That prevents accidental “flip-flopping” after a human already made a decision.

Example producer payload

UI wiring

For the inbox page, I’d keep JSON for producer endpoints and add a tiny HTML layer for the operator UI:

- `GET /inbox` → full page
- `GET /inbox/current` → current prompt card partial
- `GET /inbox/queue` → pending queue partial

The HTMX buttons on the page can call:

- `POST /api/prompts/{id}/copied`
- `POST /api/prompts/{id}/complete`
- `POST /api/prompts/{id}/dismiss`

Or, if you want the UI even thinner, make parallel HTML action routes that call the same repository helpers and return the updated fragment instead of JSON.

The first refactor I’d do after this sketch

Split it into:

- `app/models.py`
- `app/db.py`
- `app/repo/prompts.py`
- `app/api/prompts.py`
- `app/templates/inbox.html`

That gives you a clean seam between transport, persistence, and UI without changing the endpoint contract.

Next useful step would be turning this into the exact file layout and conventions HumanLoop already uses.

## User

Wonderful and talk to me about the frontend behaviour?

## Assistant

I’m mapping the operator loop now: the Inbox should optimize for a zero-friction manual flow with safe clipboard use, quick state changes, and fast UI updates without ever feeling automatic.

I’ve got the interaction model pinned down: center it on one active prompt, preserve the user’s place at all times, and keep completion explicit so nothing gets marked done by accident.

Yes — I’d make the Inbox behave like a tiny operator console, not a generic list view. The user’s loop is simple: see the current prompt, copy it, paste it into ChatGPT, come back, and then explicitly mark that prompt complete or dismiss it. The frontend should protect that loop, which means one clearly active item, no surprise auto-advance, and fast keyboard access.

Page anatomy

At the top or left: a large current prompt card with the full body text. To the side or below: a compact pending queue rail showing count, source, age, and a one-line preview. Above or below: a small status strip for “Copied”, “Completed”, or connection issues.

In v1, I’d make only the head-of-queue card actionable. The queue rail is informational or preview-only. That keeps FIFO behavior obvious and removes ambiguity about what “next” means.

How it updates

Keep the initial `/inbox` page fully server-rendered, then let HTMX refresh fragments instead of the whole page. The queue rail can poll every ~2 seconds, while the current card only refreshes on page load and after explicit actions. HTMX supports timed polling with `hx-trigger="every …"`, request synchronization with `hx-sync`, in-flight indicators with `hx-indicator`, targeted partial swaps with `hx-target`, and swap strategies like `outerHTML`. A response can also update multiple regions at once with `hx-swap-oob`, or fire a custom client event via `HX-Trigger` that other elements listen for using `from:body`.

That split matters because polling the queue rail is harmless, but repeatedly replacing the active prompt while the user is reading it is irritating. So I’d treat the current card as sticky until the user clicks Complete or Dismiss.

Copy behavior

Copy should be a real browser copy action, not an HTMX post. The Copy button should call `navigator.clipboard.writeText(rawPrompt)` directly inside the user’s click or keyboard handler, and only after a successful write should the UI `POST /api/prompts/{id}/copied`. Clipboard writes are async, happen through `Navigator.clipboard`, and require a secure context; browsers can also require recent user activation, and `writeText()` can reject with `NotAllowedError` if clipboard access isn’t allowed. For a local app, `http://localhost` and `http://127.0.0.1` are treated as potentially trustworthy origins, which is why this works cleanly for a localhost inbox.

If copy fails, I would not try to be clever with legacy fallbacks. `document.execCommand("copy")` is deprecated and not guaranteed to work, so the fallback should be a modal or drawer that shows the raw prompt in a selectable `<textarea>`, auto-selects it, and tells the user “Press Cmd/Ctrl+C.”

The visual behavior after copy should be lightweight: change the button label to “Copied”, add a subtle chip or timestamp, and keep the same prompt on screen. Copy is not completion.

Complete and dismiss behavior

Complete and Dismiss should be explicit, server-backed actions. I would not optimistically remove the item before the server responds, because the canonical next prompt is determined by queue state and local latency here is tiny. On click, disable the action buttons, show the HTMX request indicator, post to the backend, and let the server return the next current card plus an updated queue rail. Using `outerHTML` for the current card makes the swap simple, and `hx-swap-oob` is perfect for piggybacking the updated queue count or flash message in the same response.

Dismiss deserves a soft recovery path. I’d make it visually secondary and show an “Undo” toast for a few seconds that calls `POST /api/prompts/{id}/requeue`. That is faster than a confirm dialog and safer than a one-way dismissal.

A good response shape for complete or dismiss is:

```html
...
```

Keyboard behavior

This screen should be keyboard-first. I’d wire `c` to copy, `Enter` to complete, `d` to dismiss, `j` and `k` to move through queue previews later if you add selection, and `?` to show the shortcut sheet.

Use `keydown` and `event.key`, not deprecated keycode-based handling. Also ignore shortcuts whenever focus is inside an `input`, `textarea`, or `contenteditable` region, and when `Ctrl`/`Cmd`/`Alt` modifiers are held.

After Complete or Dismiss, move focus to the next prompt’s Copy button. After Copy, keep focus on the action bar so the user can immediately press Enter or D.

Accessibility and feedback

Use real `<button>` elements, not clickable `<div>`s. For dynamic updates, make the normal status strip a live region with `aria-live="polite"` so “Copied” or “Queue updated” is announced without being disruptive. Use `role="alert"` only for urgent failures like “Clipboard access blocked” or “Backend unavailable.”

I’d also preserve prompt formatting with wrapped, preformatted text and keep the action bar sticky so long prompts do not force the user to scroll back up just to hit Copy or Complete.

Failure behavior

When the backend is unreachable, don’t clear the current prompt. Freeze the UI in place, show a red banner, and disable only the actions that would desync state. If the prompt text is already visible, the user can still manually copy it. For poll failures, keep stale queue data on screen and retry quietly; for action failures, restore the button state and keep focus where it was.

The main things I would not do in v1 are auto-copy, auto-advance after copy, or let background refreshes steal the active card. Those are the behaviors that make a manual handoff tool feel flaky.

Next useful step is to sketch the exact `/inbox`, `/inbox/current`, and `/inbox/queue` fragment templates plus the HTML returned by complete and dismiss.
