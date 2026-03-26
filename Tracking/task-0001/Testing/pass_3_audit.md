# Pass 3 Audit

## Scope

Pass 3 in `Tracking/task-0001/PLAN.md` covers the server-rendered inbox vertical slice:

- `GET /inbox`
- `GET /inbox/current`
- `GET /inbox/queue`
- one full current-prompt card
- one pending queue rail
- queue count, source, age, preview, and empty-state rendering
- HTMX polling on the queue rail without background replacement of the active prompt
- non-head prompts remaining informational only in the queue rail

Grounding note:

- `exemplars/pass_3_audit.md` was not present in this workspace.
- This audit grounded on `Tracking/task-0001/TASK.md`, `Tracking/task-0001/PLAN.md`, `Tracking/task-0001/HANDOFF.md`, the prior audits in `Tracking/task-0001/Testing/pass_1_audit.md` and `Tracking/task-0001/Testing/pass_2_audit.md`, the existing inbox implementation under `app/`, and the closest unit slice in `tests/test_inbox_ui.py`.

## Expansion Summary

- Expanded the pass-3 inbox unit slice from 4 tests to 7 tests.
- Added deterministic proof that `/inbox/queue` renders waiting-prompt source labels, stable age labels, and collapsed one-line previews instead of raw multiline bodies.
- Added proof that the inbox fragments exclude completed and dismissed history while the queue rail stays informational only for non-head items.
- Added limit-boundary proof for the pending-count badge and visible waiting window at 51 pending prompts.
- Fixed a real pass-3 inbox bug exposed by the new proof: the inbox was undercounting `total pending` and `waiting` once the rail hit its fetch limit because the view was using the fetched slice length instead of the durable pending count.

## Contraction Summary

- Kept the new proof deterministic and unit-scoped with `TestClient`, direct SQLite setup, and a frozen inbox clock; no browser automation or live localhost process was added in this pass.
- Did not add proof-log lines because the repo still does not use a dedicated proof-log pattern in the inbox path; deterministic HTML assertions and direct state setup were more precise.
- Did not expand into pass-4 clipboard, keyboard shortcut, or end-to-end operator-action proof.

## Exact Commands Run

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_inbox_ui.py -q
```

Observed result:

- Baseline before edits: `4 passed in 0.44s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_inbox_ui.py -q -k "collapsed_preview or limit_boundary or terminal_history"
```

Observed result:

- First focused edited pass-3 slice before the production fix: `1 failed, 2 passed, 4 deselected in 0.84s`
- The failure was `tests/test_inbox_ui.py::test_inbox_counts_all_pending_items_at_queue_limit_boundary`, which proved the inbox was rendering an incorrect `total pending` count at 51 queued prompts.

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_inbox_ui.py -q -k "collapsed_preview or limit_boundary or terminal_history"
```

Observed result:

- Focused edited pass-3 slice after the production fix: `3 passed, 4 deselected in 0.77s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_inbox_ui.py -q
```

Observed result:

- Final pass-3 unit slice: `7 passed in 0.84s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_ingest.py tests/test_queue_api.py -q
```

Observed result:

- Earlier regression/unit coverage touched by this change: `30 passed in 1.13s`

```powershell
& .venv\Scripts\python.exe -m pytest -q
```

Observed result:

- Final repo unit suite after this pass: `37 passed in 2.13s`

## Observed Proof Logs Or Other Concrete Evidence

No dedicated proof-log lines exist in the current inbox path. Proof for this pass comes from deterministic HTML assertions, frozen-clock unit setup, the pending-count boundary failure-and-fix cycle above, and the command results.

Concrete evidence observed:

- `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` observed `/inbox` returning HTML with the full current prompt body, the pending queue rail, `3 total pending`, `2 waiting`, and the HTMX polling contract on `/inbox/queue` without any background polling contract for `/inbox/current`.
- `tests/test_inbox_ui.py::test_inbox_queue_renders_source_age_and_collapsed_preview` observed `capture-beta`, `capture-gamma`, `2 minutes ago`, `2 days ago`, and the collapsed preview string `Second queue line one. Line two keeps waiting.` while the raw multiline body with embedded newlines was absent from the queue rail HTML.
- `tests/test_inbox_ui.py::test_inbox_current_renders_empty_state_when_queue_is_empty` observed `/inbox/current` returning `No pending prompts right now.` and `0 total pending`.
- `tests/test_inbox_ui.py::test_inbox_queue_renders_empty_state_with_polling_contract` observed `/inbox/queue` returning `The queue is empty. This rail will populate as new prompts arrive.`, `0 waiting`, `0 total pending`, and the queue polling attributes `hx-get="/inbox/queue"` plus `hx-trigger="every 5s"`.
- `tests/test_inbox_ui.py::test_inbox_counts_all_pending_items_at_queue_limit_boundary` first failed against the old implementation, proving the count badge was wrong at 51 pending prompts; after the fix in `app/inbox.py` and `app/repo/prompts.py`, the same test observed `51 total pending`, `50 waiting`, exactly 50 rendered queue items, and the tail entry `Prompt body limit-051`.
- `tests/test_inbox_ui.py::test_inbox_routes_advance_only_after_explicit_queue_transition` observed the active prompt staying on `/inbox/current` until an explicit `POST /api/prompts/{id}/complete`, after which the next prompt became current and the queue rail emptied behind it.
- `tests/test_inbox_ui.py::test_inbox_fragments_exclude_terminal_history_and_keep_queue_informational` observed completed and dismissed prompt bodies absent from both inbox fragments while the remaining waiting prompt still appeared in `/inbox/queue`, and the queue rail HTML contained no `/api/prompts/` action endpoints.
- The production fix itself is visible in `app/inbox.py`, where `build_inbox_view()` now uses durable pending counts instead of the fetched slice length, and in `app/repo/prompts.py`, which now exposes `count_prompts()` for that proof-backed count contract.

## Requirement Mapping

| Requirement | Evidence (test / proof log / artifact) | Result |
| --- | --- | --- |
| Implement `GET /inbox`. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` observes a `200` HTML response from `/inbox` with both current and queue sections rendered. | Proven |
| Implement `GET /inbox/current`. | `tests/test_inbox_ui.py::test_inbox_current_renders_empty_state_when_queue_is_empty` and `tests/test_inbox_ui.py::test_inbox_routes_advance_only_after_explicit_queue_transition` both observe `200` HTML responses from `/inbox/current`. | Proven |
| Implement `GET /inbox/queue`. | `tests/test_inbox_ui.py::test_inbox_queue_renders_empty_state_with_polling_contract`, `tests/test_inbox_ui.py::test_inbox_queue_renders_source_age_and_collapsed_preview`, and `tests/test_inbox_ui.py::test_inbox_fragments_exclude_terminal_history_and_keep_queue_informational` all observe `200` HTML responses from `/inbox/queue`. | Proven |
| Render one full current-prompt card. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` proves the full current body renders on `/inbox`, and `tests/test_inbox_ui.py::test_inbox_routes_advance_only_after_explicit_queue_transition` proves `/inbox/current` holds the active prompt body until an explicit queue transition. | Proven |
| Render one pending queue rail. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` and `tests/test_inbox_ui.py::test_inbox_queue_renders_empty_state_with_polling_contract` prove the rail renders in both populated and empty states. | Proven |
| Show a visible queue count. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` proves the basic count rendering, and `tests/test_inbox_ui.py::test_inbox_counts_all_pending_items_at_queue_limit_boundary` plus the production fix in `app/inbox.py` and `app/repo/prompts.py` prove the count remains accurate at the 51-item limit boundary. | Proven |
| Show source labels in the queue rail. | `tests/test_inbox_ui.py::test_inbox_queue_renders_source_age_and_collapsed_preview` observes `capture-beta` and `capture-gamma` in `/inbox/queue`. | Proven |
| Show age labels in the queue rail. | `tests/test_inbox_ui.py::test_inbox_queue_renders_source_age_and_collapsed_preview` freezes the inbox clock and observes `2 minutes ago` and `2 days ago`. | Proven |
| Show preview text in the queue rail. | `tests/test_inbox_ui.py::test_inbox_queue_renders_source_age_and_collapsed_preview` observes the collapsed preview string and proves the raw multiline waiting body is not rendered directly. | Proven |
| Handle empty queue states. | `tests/test_inbox_ui.py::test_inbox_current_renders_empty_state_when_queue_is_empty` and `tests/test_inbox_ui.py::test_inbox_queue_renders_empty_state_with_polling_contract` prove the current-card and queue-rail empty states. | Proven |
| Keep the queue rail informational only in MVP so non-head items are visible but not actionable. | `tests/test_inbox_ui.py::test_inbox_fragments_exclude_terminal_history_and_keep_queue_informational` proves the waiting prompt still renders in `/inbox/queue` while the rail HTML contains no `/api/prompts/` action endpoints. | Proven at HTML/unit level |
| Use HTMX partial refresh for the queue rail. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` and `tests/test_inbox_ui.py::test_inbox_queue_renders_empty_state_with_polling_contract` both observe `hx-get="/inbox/queue"` and `hx-trigger="every 5s"` in the rendered HTML. | Proven |
| Do not replace the active prompt in the background while the operator is reading it. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` proves there is no `hx-get="/inbox/current"` polling contract, and `tests/test_inbox_ui.py::test_inbox_routes_advance_only_after_explicit_queue_transition` proves the active prompt changes only after an explicit queue transition. | Proven at unit/app boundary |
| The operator can open the inbox. | `tests/test_inbox_ui.py::test_inbox_renders_current_prompt_and_waiting_queue` proves `/inbox` renders successfully with pending prompts, and the empty-state tests prove the routes remain usable when the queue is empty. | Proven |
| The operator can work the queue end to end from the browser. | No pass-3 browser-flow proof exists yet. The current pass proves rendering and sticky-current behavior, but not browser-driven copy, complete, dismiss, requeue, or clipboard behavior. | Not yet proven |

## Intentional Non-Goals

- No browser automation or live DOM interaction proof was added for HTMX polling behavior, clipboard access, or operator action flows.
- No live localhost process proof was added for the inbox routes; this pass stayed at the `TestClient` plus deterministic HTML layer.
- No new JavaScript, clipboard, keyboard-shortcut, or action-button tests were added because those belong to the later operator-workflow pass.

## Remaining Risks

- The pass-3 proof is strong at the FastAPI app-test boundary, but it does not yet prove the inbox over a real localhost socket, a real browser, or a long-lived process with ongoing polling.
- The queue rail now reports an accurate total waiting count even beyond the 50-entry visible rail window, but the UI does not yet explain that only the first 50 waiting entries are rendered at once.
- There is still no browser-driven proof that the later copy, complete, dismiss, and requeue controls preserve operator place and interact correctly with the sticky-current contract.

## Integration-Level Proof Still Needed

- A live localhost proof that a real app process serves `/inbox`, `/inbox/current`, and `/inbox/queue` with the same semantics observed in the unit suite.
- A browser-level proof that HTMX polling refreshes only the queue rail while the active prompt remains stable until an explicit operator action changes state.
- An end-to-end operator proof that copy, complete, dismiss, and requeue work correctly from the rendered inbox once the pass-4 workflow controls exist.

## Pass Status

Pass 3 should remain open.

Reason:

- The unit-proof surface for the server-rendered inbox is now stronger, more explicit, and green, and it exposed and closed one real count-boundary defect.
- The real-browser and live-localhost evidence needed to prove the full operator workflow from the inbox is still absent.
