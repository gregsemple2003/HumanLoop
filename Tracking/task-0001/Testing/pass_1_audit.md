# Pass 1 Audit

## Scope

Pass 1 in `Tracking/task-0001/PLAN.md` covers the durable ingest seam:

- SQLite-backed `prompt_items` storage
- `POST /api/prompts`
- required ingest validation
- optional metadata handling
- idempotent replay on `(source, idempotency_key)`
- durable queue ordering via `seq`

Baseline note:

- `Tracking/task-0001/HANDOFF.md` was not present during this pass.
- No prior `Tracking/task-0001/Testing/pass_*_audit.md` files were present to mirror.
- `exemplars/PASS_3_AUDIT.md` was not present in this workspace.

This audit therefore grounded on `Tracking/task-0001/TASK.md`, `Tracking/task-0001/PLAN.md`, and the existing ingest unit tests in `tests/test_ingest.py`.

## Expansion Summary

- Expanded the ingest unit slice from 6 tests to 14 tests.
- Added deterministic proof for SQLite durability pragmas: WAL mode, `synchronous=FULL`, `busy_timeout=5000`, and `foreign_keys=ON`.
- Added deterministic proof that the `prompt_items` schema carries the pass-1 column contract.
- Added focused validation proof for missing required fields and blank required text fields.
- Added proof that metadata is optional and persists as `NULL` when omitted.
- Added proof that idempotency is scoped to `(source, idempotency_key)` rather than `idempotency_key` alone.

## Contraction Summary

- Kept this pass strictly at the unit-test and proof layer; no production code changes were needed.
- Did not expand into pass-2 queue reads/actions, pass-3 inbox rendering, or pass-4 clipboard workflow.
- Did not add synthetic proof log lines because the repo does not currently use a proof-log pattern in the ingest path; direct DB assertions were sufficient and more precise here.

## Exact Commands Run

```powershell
pytest tests/test_ingest.py -q
```

Observed result:

- Failed before test execution because `pytest` was not on `PATH` in this shell.

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_ingest.py -q
```

Observed result:

- Baseline before edits: `6 passed in 0.39s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_ingest.py -q -k "durability or schema or optional_metadata or source_plus_key or requires_body or blank_required"
```

Observed result:

- New pass-1 proof slice after edits: `8 passed, 6 deselected in 0.39s`

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_ingest.py -q
```

Observed result:

- Final pass-1 unit slice: `14 passed in 0.58s`

```powershell
& .venv\Scripts\python.exe -m pytest -q
```

Observed result:

- Regression/unit coverage touched by this change: `14 passed in 0.57s`

## Observed Proof Logs Or Other Concrete Evidence

No dedicated proof-log lines exist in the current ingest path. Proof for this pass comes from deterministic unit assertions and the command results above.

Concrete evidence observed:

- `test_database_connections_enable_pass_one_durability_pragmas` observed `journal_mode == "wal"`, `synchronous == 2`, `busy_timeout == 5000`, and `foreign_keys == 1`.
- `test_prompt_items_schema_matches_pass_one_contract` observed `PRAGMA table_info(prompt_items)` returning the exact pass-1 column list:
  `seq`, `id`, `source`, `idempotency_key`, `body`, `metadata_json`, `status`, `copy_count`, `last_copied_at`, `created_at`, `updated_at`, `completed_at`, `dismissed_at`.
- `test_ingest_persists_a_new_prompt` observed a `201` response and then read the durable row back from SQLite with matching `seq`, `source`, `idempotency_key`, `body`, `metadata_json`, and `status`.
- `test_ingest_allows_missing_optional_metadata` observed a `201` response with `metadata == null` and a persisted DB row where `metadata_json IS NULL`.
- `test_duplicate_ingest_returns_replay_safe_response` observed `201` on first ingest, `200` with `replayed == true` on replay, identical `id` and `seq`, and `COUNT(*) == 1`.
- `test_idempotency_is_scoped_to_source_plus_key` observed the same `idempotency_key` accepted from two different `source` values as two distinct `201` rows with `seq == 1` and `seq == 2`, and `COUNT(*) == 2`.
- `test_reusing_an_idempotency_key_for_different_payload_returns_conflict` observed `409` with the conflict detail when the same `(source, idempotency_key)` was reused for a different payload.
- `test_ingest_requires_body_source_and_idempotency_key` and `test_ingest_rejects_blank_required_text_fields` observed `422` validation failures for missing and blank required fields.
- `test_prompt_survives_app_restart` observed a `201` create before app restart, a `200` replay from a fresh app instance after restart, and `COUNT(*) == 1`.

## Requirement Mapping

| Requirement | Evidence (test / proof log / artifact) | Result |
| --- | --- | --- |
| Create a single `prompt_items` table with the pass-1 durable ingest columns. | `tests/test_ingest.py::test_prompt_items_schema_matches_pass_one_contract` asserts `PRAGMA table_info(prompt_items)` exactly matches the pass-1 column contract. | Proven |
| Use SQLite WAL mode and a busy timeout for practical local durability. | `tests/test_ingest.py::test_database_connections_enable_pass_one_durability_pragmas` asserts `journal_mode == "wal"` and `busy_timeout == 5000` on opened DB connections. | Proven |
| Persist prompts durably before returning success. | `tests/test_ingest.py::test_ingest_persists_a_new_prompt` gets `201` and immediately reads the durable SQLite row with matching payload data. | Proven at unit level |
| `POST /api/prompts` requires `body`. | `tests/test_ingest.py::test_ingest_requires_body_source_and_idempotency_key` and `tests/test_ingest.py::test_ingest_rejects_blank_required_text_fields` both observe `422` when `body` is missing or blank. | Proven |
| `POST /api/prompts` requires `source`. | `tests/test_ingest.py::test_ingest_requires_body_source_and_idempotency_key` and `tests/test_ingest.py::test_ingest_rejects_blank_required_text_fields` both observe `422` when `source` is missing or blank. | Proven |
| `POST /api/prompts` requires `idempotency_key`. | `tests/test_ingest.py::test_ingest_requires_body_source_and_idempotency_key` and `tests/test_ingest.py::test_ingest_rejects_blank_required_text_fields` both observe `422` when `idempotency_key` is missing or blank. | Proven |
| Optional metadata is allowed. | `tests/test_ingest.py::test_ingest_allows_missing_optional_metadata` observes `201`, `metadata == null`, and `metadata_json IS NULL`. | Proven |
| Idempotency is enforced on `(source, idempotency_key)`. | `tests/test_ingest.py::test_duplicate_ingest_returns_replay_safe_response` proves replay collapse for the same `(source, idempotency_key)`, while `tests/test_ingest.py::test_idempotency_is_scoped_to_source_plus_key` proves the same key across different sources creates distinct rows. | Proven |
| A new ingest returns `201`. | `tests/test_ingest.py::test_ingest_persists_a_new_prompt` and `tests/test_ingest.py::test_ingest_allows_missing_optional_metadata` both observe `201` on first ingest. | Proven |
| A safe replay returns `200`. | `tests/test_ingest.py::test_duplicate_ingest_returns_replay_safe_response` observes `200` with `replayed == true` for an identical retry. | Proven |
| Retries do not duplicate queue entries. | `tests/test_ingest.py::test_duplicate_ingest_returns_replay_safe_response` and `tests/test_ingest.py::test_prompt_survives_app_restart` both observe `COUNT(*) == 1` after replay. | Proven |
| Queue order is assigned by `seq`. | `tests/test_ingest.py::test_ingest_persists_a_new_prompt` observes `seq == 1`; `tests/test_ingest.py::test_new_prompts_get_monotonic_seq_values` observes the next prompt at `seq == 2`. | Proven |
| Reusing the same `(source, idempotency_key)` for a different payload fails clearly. | `tests/test_ingest.py::test_reusing_an_idempotency_key_for_different_payload_returns_conflict` observes `409` and the conflict detail. | Proven |
| Durable ingest survives app restart. | `tests/test_ingest.py::test_prompt_survives_app_restart` replays the same prompt from a fresh app instance and confirms the DB still has exactly one row. | Proven at restart/unit boundary |

## Intentional Non-Goals

- No proof for `GET /api/prompts`, `GET /api/prompts/next`, prompt detail reads, or any queue transition routes; those are later-pass concerns.
- No proof for inbox rendering, HTMX refresh behavior, clipboard behavior, or keyboard shortcuts.
- No proof for README/runbook completeness in this pass audit.
- No proof for remote access, auth, or multi-user behavior, which remain explicit non-goals for the MVP.

## Remaining Risks

- The pass-1 unit suite proves restart persistence and configured SQLite durability pragmas, but it does not simulate crash recovery, abrupt power loss, or cross-process contention under load.
- The pass-1 unit suite does not exercise true concurrent duplicate-ingest races; it proves the idempotency contract functionally but not under stress.
- The pass-1 unit suite uses `TestClient`, so it does not yet prove that the external capture path can enqueue over a real localhost network boundary.

## Integration-Level Proof Still Needed

- An integration proof that the existing upstream capture path can successfully call `POST /api/prompts` over localhost.
- A live-process proof that the real app process binds locally, initializes the database, accepts an ingest request, and leaves the durable row in place across a real process restart.

## Pass Status

Pass 1 should remain open.

Reason:

- The unit-proof surface for the durable ingest seam is now strong and green.
- The integration evidence needed to show the real upstream capture path working over localhost is still absent in this repo.
