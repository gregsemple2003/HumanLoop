# Task 0001 Handoff

## Current State

- Pass 1 through pass 4 behavior remains green, and the repo test suite now passes at `48 passed` after the pass-5 proof expansion.
- The app now has an explicit runtime log path via `app/config.py` and `app/main.py`, with startup log lines written to a real local log file.
- A Windows-first runbook now exists at the repo root in `README.md`, covering startup, shutdown, runtime paths, producer contract details, smoke commands, and recovery expectations.
- A concrete localhost smoke helper now exists in `scripts/enqueue-sample-prompt.ps1`, which enqueues a sample prompt through `POST /api/prompts` and prints the next operator steps.
- Pass-5 release-readiness proof now includes `tests/test_release_readiness.py`, which covers localhost-default settings, closed-by-default CORS behavior, runtime log creation, required `README.md` runbook content, and execution of the PowerShell smoke script against a local capture server.
- Pass-5 live localhost proof now covers the inbox seam more explicitly: a real Uvicorn process was started against a throwaway runtime path, the smoke script created a prompt successfully, `/api/prompts/next` returned that same prompt, `/inbox` rendered the smoke prompt and Copy control, explicit completion drained `/inbox/current`, and the runtime log file contained the expected startup lines.

## Leftover Cleanup Work

- Wire the external capture path to this repo’s `POST /api/prompts` endpoint; the producer itself lives outside this workspace, so that seam remains unclosed here.
- Add browser-level proof that the pass-4 clipboard, keyboard, complete, dismiss, and requeue flow behaves correctly in a real localhost browser session and preserves operator place.
- Decide whether the queue rail should explicitly communicate that only the first 50 waiting items are rendered when the durable waiting count is larger.
- Decide and document the intended policy for `copied` on terminal prompts and for repeated `requeue` on already pending prompts so later passes do not rely on an accidental behavior.

## Follow-Up Bugs Or Questions

- No known failing test remains open after the pass-5 proof updates.
- The main unresolved seams are still out-of-repo producer wiring and proof-layer ambiguity rather than a current broken app behavior: terminal-copy semantics, pending-requeue semantics, whether the queue rail needs an explicit truncation indicator when more than 50 waiting items exist, and how much real-browser proof is required before treating the inbox workflow as fully closed.

## Known Risks

- The repo now has a stronger live localhost inbox smoke, but it still does not have a real browser harness proving the rendered clipboard/manual workflow against a running page.
- There is still no concurrency stress proof for simultaneous queue transitions against the same prompt.
- The external capture path is still not wired from its own codebase into this repo’s running service.
- The inbox now shows accurate total pending counts, but the rendered queue rail itself is still capped to the first 50 waiting entries.

## Recommended Next Step

- Start with the out-of-repo producer wiring seam and a real-browser proof layer for the inbox workflow, rather than widening the MVP feature surface further.
