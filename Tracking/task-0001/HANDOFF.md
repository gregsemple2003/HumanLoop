# Task 0001 Handoff

## Current State

- Pass 1 durable-ingest proof remains green in `tests/test_ingest.py`.
- Pass 2 queue-proof coverage was expanded this turn from 11 tests to 16 tests in `tests/test_queue_api.py`.
- Pass 3 inbox-proof coverage remains green, and pass 4 inbox/operator proof coverage was expanded again this turn from 10 tests to 13 tests in `tests/test_inbox_ui.py`.
- The inbox now has a real pass-4 operator workflow layer in `app/templates/inbox.html` and `app/templates/partials/current_prompt.html`: clipboard-first Copy, explicit Complete and Dismiss actions, a Requeue recovery control, keyboard shortcuts, status messaging, and a sticky action bar.
- Pass-4 proof is now stronger at the rendered workflow-contract layer: the inbox tests explicitly prove clipboard-before-record ordering, server-confirmed transition-before-refresh ordering, shortcut gating for editable targets, and operator-facing recovery messaging when actions fail.
- The earlier pass-3 inbox bug fix remains in place: the inbox still reports accurate durable pending counts at the rail-limit boundary via `app/inbox.py` and `app/repo/prompts.py`.

## Leftover Cleanup Work

- Add live localhost integration proof for the pass-2 queue reads and action routes and for the pass-3/pass-4 inbox routes against a real app process, not just `TestClient`.
- Add browser-level proof that the new pass-4 clipboard, keyboard, complete, dismiss, and requeue flow behaves correctly in a real localhost browser session and preserves operator place.
- Decide whether the queue rail should explicitly communicate that only the first 50 waiting items are rendered when the durable waiting count is larger.
- Decide and document the intended policy for `copied` on terminal prompts and for repeated `requeue` on already pending prompts so later passes do not rely on an accidental behavior.

## Follow-Up Bugs Or Questions

- No new failing test or known production bug remains open from this pass.
- The main open questions are still product-policy and proof-layer ambiguity rather than current broken behavior: terminal-copy semantics, pending-requeue semantics, whether the queue rail needs an explicit truncation indicator when more than 50 waiting items exist, and how much live-browser proof is required before treating pass 4 as closed.

## Known Risks

- Current pass-2 and pass-3 proof still stops at the app-test boundary; it does not yet prove the queue API or inbox routes over a real localhost network hop.
- There is still no concurrency stress proof for simultaneous queue transitions against the same prompt.
- There is still no browser-driven proof that the new inbox UI controls trigger the correct queue actions while preserving operator place, even though the rendered workflow-script contract is now directly covered by unit tests.
- The inbox now shows accurate total pending counts, but the rendered queue rail itself is still capped to the first 50 waiting entries.

## Recommended Next Step

- Start the next proof layer with a live-process localhost smoke for the queue API and inbox routes, then add real-browser proof for the pass-4 clipboard and explicit queue-action workflow before moving on to pass 5 release-readiness work.
