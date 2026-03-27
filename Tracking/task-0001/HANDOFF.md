# Task 0001 Handoff

## Current State

- Pass 1 through pass 5 behavior remains green, and the repo test suite now passes at `71 passed`, including `11` live localhost integration tests.
- The app now has an explicit runtime log path via `app/config.py` and `app/main.py`, with startup log lines written to a real local log file.
- A Windows-first runbook now exists at the repo root in `README.md`, covering startup, shutdown, runtime paths, producer contract details, smoke commands, and recovery expectations.
- A concrete localhost smoke helper now exists in `scripts/enqueue-sample-prompt.ps1`, which enqueues a sample prompt through `POST /api/prompts` and prints the next operator steps.
- Pass-5 release-readiness proof now includes `tests/test_release_readiness.py`, which covers localhost-default settings, closed-by-default CORS behavior, runtime log creation, required `README.md` runbook content, and execution of the PowerShell smoke script against a local capture server.
- Pass-5 live localhost proof now covers the inbox seam more explicitly: a real Uvicorn process was started against a throwaway runtime path, the smoke script created a prompt successfully, `/api/prompts/next` returned that same prompt, `/inbox` rendered the smoke prompt and Copy control, explicit completion drained `/inbox/current`, and the runtime log file contained the expected startup lines.
- Real browser-style operator proof now exists in `tests/integration/test_desktop_clipboard.py`: the configured `QWebEngineView` flow proves the rendered keyboard loop can open shortcut help, copy without auto-advancing, complete only on explicit `Enter`, keep the current prompt sticky while the queue rail polls in a newly arrived prompt, and dismiss plus requeue through the rendered recovery control.

## Leftover Cleanup Work

- Wire the external capture path to this repo’s `POST /api/prompts` endpoint; the producer itself lives outside this workspace, so that seam remains unclosed here.
- Decide whether the queue rail should explicitly communicate that only the first 50 waiting items are rendered when the durable waiting count is larger.
- Decide and document the intended policy for `copied` on terminal prompts and for repeated `requeue` on already pending prompts so later passes do not rely on an accidental behavior.
- Add concurrency stress proof for simultaneous transitions or overlapping fragment refreshes against the same prompt.

## Follow-Up Bugs Or Questions

- No known failing test remains open after the browser-proof expansion and full-suite rerun.
- The main unresolved seams are now out-of-repo producer wiring plus product-policy ambiguity rather than proof-layer ambiguity: terminal-copy semantics, pending-requeue semantics, whether the queue rail needs an explicit truncation indicator when more than 50 waiting items exist, and whether overlapping queue transitions need stronger guarantees than the current single-user flow assumes.

## Known Risks

- There is still no concurrency stress proof for simultaneous queue transitions against the same prompt.
- The external capture path is still not wired from its own codebase into this repo’s running service.
- The inbox now shows accurate total pending counts, but the rendered queue rail itself is still capped to the first 50 waiting entries.

## Recommended Next Step

- Start with the out-of-repo producer wiring seam and a concurrency-focused proof layer for overlapping queue actions, rather than widening the MVP feature surface further.
