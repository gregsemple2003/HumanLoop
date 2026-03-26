# Pass 2 Audit

## Scope

Pass 2 in `Tracking/task-0001/PLAN.md` covers the queue read API and durable state transitions:

- `GET /api/prompts?status=pending&limit=50`
- `GET /api/prompts/next`
- `GET /api/prompts/{id}`
- `POST /api/prompts/{id}/copied`
- `POST /api/prompts/{id}/complete`
- `POST /api/prompts/{id}/dismiss`
- `POST /api/prompts/{id}/requeue`
- queue status limited to `pending`, `completed`, or `dismissed`
- repeated identical terminal actions staying safe
- conflicting terminal transitions failing clearly with `409`

Grounding note:

- `Tracking/task-0001/HANDOFF.md` did not exist when this proof pass started and was added at close-out to capture the remaining risks and follow-up work.
- `exemplars/pass_3_audit.md` was not present in this workspace.
- This audit grounded on `Tracking/task-0001/TASK.md`, `Tracking/task-0001/PLAN.md`, `Tracking/task-0001/Testing/pass_1_audit.md`, the current queue implementation under `app/`, and the closest existing unit slices in `tests/test_ingest.py` and `tests/test_queue_api.py`.

## Expansion Summary

- Expanded the pass-2 queue unit slice from 11 tests to 16 tests.
- Added direct durable-row proof for `copied`, `complete`, `dismiss`, and `requeue` so the pass now proves history preservation without inferring from response shapes alone.
- Added explicit API-boundary proof that unknown queue status values are rejected instead of silently widening the contract.
- Added focused proof that all queue action endpoints return `404` for unknown prompt IDs.

## Contraction Summary

- Kept this pass strictly in the unit-test, audit, and handoff layer; no production code changes were needed.
- Did not add proof-log lines because the repo does not currently use dedicated proof logging in the queue path; deterministic API assertions plus direct SQLite row reads were more precise.
- Did not expand into pass-3 inbox rendering, pass-4 clipboard/keyboard workflow, or live localhost/browser integration proof.

## Exact Commands Run

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_queue_api.py -q
```

Observed result:

- Baseline before edits: `11 passed in 0.67s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_queue_api.py -q -k "copied_records or complete_is_idempotent or dismiss_is_idempotent or prompt_actions_return_404"
```

Observed result:

- Focused edited pass-2 proof slice: `7 passed, 8 deselected in 0.51s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_queue_api.py -q -k "rejects_unknown_status_value"
```

Observed result:

- Added queue-status contract proof: `1 passed, 15 deselected in 0.29s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_queue_api.py -q
```

Observed result:

- Final pass-2 unit slice: `16 passed in 0.89s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_ingest.py tests/test_queue_api.py -q
```

Observed result:

- Touched regression/unit coverage after this change: `30 passed in 1.30s`

## Observed Proof Logs Or Other Concrete Evidence

No dedicated proof-log lines exist in the current queue path. Proof for this pass comes from deterministic unit assertions, direct SQLite row reads, and the command results above.

Concrete evidence observed:

- `tests/test_queue_api.py::test_list_prompts_returns_pending_items_in_fifo_order_and_honors_limit` observed FIFO ordering for pending prompts and enforced the requested `limit`.
- `tests/test_queue_api.py::test_list_prompts_filters_by_status` observed pending, completed, and dismissed views returning the correct records after explicit state transitions.
- `tests/test_queue_api.py::test_list_prompts_rejects_unknown_status_value` observed `422` for `status=archived`, proving the queue-read API does not widen status beyond the pass contract.
- `tests/test_queue_api.py::test_get_next_prompt_returns_fifo_head_and_skips_completed_items` observed `/api/prompts/next` returning the head pending prompt, then the next pending prompt after explicit completion.
- `tests/test_queue_api.py::test_get_next_prompt_returns_404_when_queue_is_empty` observed a clear `404` with `No pending prompts found.` when the queue is empty.
- `tests/test_queue_api.py::test_get_prompt_by_id_returns_prompt_and_404_for_unknown_id` observed durable detail reads by ID and a `404` for unknown IDs.
- `tests/test_queue_api.py::test_copied_records_copy_metadata_without_changing_status` observed `copy_count` incrementing to `2`, `last_copied_at` being stamped, `status` remaining `pending`, both terminal timestamps staying `NULL`, and the durable SQLite row count remaining `1` for the same prompt ID and `seq`.
- `tests/test_queue_api.py::test_complete_is_idempotent_and_removes_prompt_from_pending_queue` observed `completed_at` being stamped, the prompt leaving the pending list, the prompt remaining readable by ID, the durable SQLite row count remaining `1`, and repeated `complete` returning the same terminal record safely.
- `tests/test_queue_api.py::test_dismiss_is_idempotent_and_requeue_restores_pending_state` observed `dismissed_at` being stamped on the existing durable row, repeated `dismiss` preserving the same dismissal timestamp, `requeue` restoring the same prompt ID and `seq` to `pending`, `dismissed_at` being cleared, and the durable SQLite row count remaining `1`.
- `tests/test_queue_api.py::test_conflicting_transitions_return_409` observed `409` conflicts for dismiss-after-complete, complete-after-dismiss, and requeue-after-complete.
- `tests/test_queue_api.py::test_prompt_actions_return_404_for_unknown_id` observed `404` for `copied`, `complete`, `dismiss`, and `requeue` against a missing prompt ID, proving the action endpoints fail clearly instead of silently succeeding.

## Requirement Mapping

| Requirement | Evidence (test / proof log / artifact) | Result |
| --- | --- | --- |
| Implement `GET /api/prompts?status=pending&limit=50`. | `tests/test_queue_api.py::test_list_prompts_returns_pending_items_in_fifo_order_and_honors_limit` proves pending FIFO reads plus limit handling, and `tests/test_queue_api.py::test_list_prompts_filters_by_status` proves the same endpoint serves completed and dismissed views. | Proven |
| Implement `GET /api/prompts/next`. | `tests/test_queue_api.py::test_get_next_prompt_returns_fifo_head_and_skips_completed_items` and `tests/test_queue_api.py::test_get_next_prompt_returns_404_when_queue_is_empty` | Proven |
| Implement `GET /api/prompts/{id}`. | `tests/test_queue_api.py::test_get_prompt_by_id_returns_prompt_and_404_for_unknown_id` | Proven |
| Keep queue status limited to `pending`, `completed`, or `dismissed`. | `tests/test_queue_api.py::test_list_prompts_rejects_unknown_status_value` proves the API rejects `status=archived`, and the durable backstop remains the `CHECK (status IN ('pending', 'completed', 'dismissed'))` constraint in `app/db.py`. | Proven |
| `copied` updates only copy metadata and does not become terminal. | `tests/test_queue_api.py::test_copied_records_copy_metadata_without_changing_status` proves `copy_count` and `last_copied_at` change while `status` stays `pending`, `completed_at` and `dismissed_at` stay `NULL`, and the same prompt remains the `/api/prompts/next` head. | Proven |
| `complete` removes the prompt from the active queue without hard-deleting history. | `tests/test_queue_api.py::test_complete_is_idempotent_and_removes_prompt_from_pending_queue` proves the prompt leaves the pending list, remains readable by ID, and remains represented by a single durable SQLite row with `status='completed'`. | Proven |
| `dismiss` removes the prompt from the active queue without hard-deleting history. | `tests/test_queue_api.py::test_dismiss_is_idempotent_and_requeue_restores_pending_state` proves the prompt is marked `dismissed` on the existing durable row before requeue, with row count still `1`. | Proven |
| `requeue` restores a dismissed prompt to the active queue. | `tests/test_queue_api.py::test_dismiss_is_idempotent_and_requeue_restores_pending_state` proves the same prompt ID and `seq` return to `pending`, `dismissed_at` is cleared, and `/api/prompts/next` returns that prompt again. | Proven |
| Repeated `complete` is safe. | `tests/test_queue_api.py::test_complete_is_idempotent_and_removes_prompt_from_pending_queue` proves repeated `complete` returns `200` and preserves the original `completed_at` timestamp. | Proven |
| Repeated `dismiss` is safe. | `tests/test_queue_api.py::test_dismiss_is_idempotent_and_requeue_restores_pending_state` proves repeated `dismiss` returns `200` and preserves the original `dismissed_at` timestamp. | Proven |
| Conflicting terminal transitions fail clearly with `409`. | `tests/test_queue_api.py::test_conflicting_transitions_return_409` proves `409` for dismiss-after-complete, complete-after-dismiss, and requeue-after-complete with explicit detail strings. | Proven |
| The queue lifecycle works over the API without manual database edits. | The pass-2 slice exercises enqueue, list, next, detail, copied, complete, dismiss, and requeue entirely through HTTP calls in `tests/test_queue_api.py`, with direct SQLite reads used only as proof artifacts after the fact. | Proven at unit/API level |

## Intentional Non-Goals

- No inbox HTML, HTMX fragment refresh, clipboard API, keyboard shortcut, or browser-flow proof was added here; those remain later-pass work.
- No live-process localhost proof was added for queue reads or actions; this pass stayed within `TestClient` plus SQLite verification.
- No production behavior was changed for ambiguities the task docs do not yet resolve, such as whether terminal prompts should reject future `copied` calls or whether `requeue` on an already pending prompt should remain a safe no-op.

## Remaining Risks

- The pass-2 proof is strong at the FastAPI `TestClient` boundary, but it does not yet prove the queue API over a real localhost socket or across a long-lived app process.
- The queue transition tests do not yet exercise true concurrent action races, such as simultaneous complete/dismiss requests against the same prompt.
- The current task docs still leave two policy seams open for later clarification: whether `copied` should be allowed after a prompt is terminal, and whether repeated `requeue` on a pending prompt is part of the intended operator contract.

## Integration-Level Proof Still Needed

- A live localhost proof that a real app process serves `GET /api/prompts`, `GET /api/prompts/next`, `GET /api/prompts/{id}`, and the queue action routes with the same semantics observed in the unit suite.
- A browser-level proof in later passes that the inbox UI drives these queue actions correctly without unexpected active-prompt replacement while the operator is reading.
- An end-to-end proof that the existing capture path can enqueue prompts and that the operator can process them through the eventual inbox without touching SQLite directly.

## Pass Status

Pass 2 should remain open.

Reason:

- The unit-proof surface for the queue API and state transitions is now strong, explicit, and green.
- Real localhost and browser integration evidence for this pass is still absent, so the pass is not fully proven end to end yet.
