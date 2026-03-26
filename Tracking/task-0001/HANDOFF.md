# Task 0001 Handoff

## Current State

- Pass 1 durable-ingest proof remains green in `tests/test_ingest.py`.
- Pass 2 queue-proof coverage was expanded this turn from 11 tests to 16 tests in `tests/test_queue_api.py`.
- Pass 3 inbox-proof coverage was expanded this turn from 4 tests to 7 tests in `tests/test_inbox_ui.py`.
- A real pass-3 inbox bug was fixed while adding proof: the inbox now reports accurate durable pending counts at the rail-limit boundary via `app/inbox.py` and `app/repo/prompts.py`.

## Leftover Cleanup Work

- Add live localhost integration proof for the pass-2 queue reads and action routes and for the pass-3 inbox routes against a real app process, not just `TestClient`.
- Carry the pass-3 sticky-current contract into pass 4 with browser-level proof that copy, complete, dismiss, and requeue keep operator place and do not let background refreshes replace the active prompt.
- Decide whether the queue rail should explicitly communicate that only the first 50 waiting items are rendered when the durable waiting count is larger.
- Decide and document the intended policy for `copied` on terminal prompts and for repeated `requeue` on already pending prompts so later passes do not rely on an accidental behavior.

## Follow-Up Bugs Or Questions

- No new production bug remains open from this pass; the inbox pending-count underflow at the 51-item boundary was fixed in this turn.
- The main open questions are product-policy and UI-contract ambiguity rather than current failing tests: terminal-copy semantics, pending-requeue semantics, and whether the queue rail needs an explicit truncation indicator when more than 50 waiting items exist.

## Known Risks

- Current pass-2 and pass-3 proof stops at the app-test boundary; it does not yet prove the queue API or inbox routes over a real localhost network hop.
- There is still no concurrency stress proof for simultaneous queue transitions against the same prompt.
- There is still no browser-driven proof that the inbox UI triggers the correct queue actions while preserving operator place.
- The inbox now shows accurate total pending counts, but the rendered queue rail itself is still capped to the first 50 waiting entries.

## Recommended Next Step

- Start the next proof layer with a live-process localhost smoke for the queue API and inbox routes, then move into pass-4 browser/operator-flow proof for clipboard and explicit queue actions.
