# REGRESSION-RUN-1

## Summary

- Task: `task-0001`
- Date: `2026-03-27`
- Timezone: `America/Toronto`
- Tester: `Codex`
- Checklist source: [REGRESSION.md](/c:/Agent/HumanLoop/REGRESSION.md)
- Overall result: `PARTIAL PASS`
- Scope of this slice: the live localhost integration suite plus the new real-browser operator cases for keyboard flow and background queue refresh.

## Environment / Preflight

- Repo root: `C:\Agent\HumanLoop`
- OS: `Windows-11-10.0.26200-SP0`
- Python: `3.13.12` from `.\.venv\Scripts\python.exe`
- Key test packages present: `pytest 8.4.2`, `httpx 0.28.1`, `PySide6 6.11.0`
- Desktop/browser precondition: PySide6 WebEngine was available, so the rendered inbox could be exercised in a real `QWebEngineView` rather than a pure `TestClient` HTML slice.

## Exact Steps Run

```powershell
& .\.venv\Scripts\python.exe --version
```

Observed:

- `Python 3.13.12`

```powershell
@'
import platform
import PySide6
import pytest
import httpx
print(platform.platform())
print('PySide6', PySide6.__version__)
print('pytest', pytest.__version__)
print('httpx', httpx.__version__)
'@ | .\.venv\Scripts\python.exe -
```

Observed:

- `Windows-11-10.0.26200-SP0`
- `PySide6 6.11.0`
- `pytest 8.4.2`
- `httpx 0.28.1`

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\integration\test_desktop_clipboard.py -q
```

Observed:

- First collection attempt failed because the newly added helper had an f-string JavaScript escaping mistake in the test file itself.
- After fixing the helper, the same command passed at `4 passed in 22.98s`.

```powershell
1..3 | ForEach-Object { & .\.venv\Scripts\python.exe -m pytest tests\integration\test_desktop_clipboard.py -k "polling_keeps_current_sticky" -q }
```

Observed:

- The new queue-polling test passed on three consecutive reruns.

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\integration -q
```

Observed:

- `11 passed in 35.09s`

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Observed:

- `71 passed in 38.68s`

## Expected Result

- The repo should have a real-browser-style proof layer for the operator loop, not just API calls and static HTML assertions.
- Copy should stay non-terminal in the rendered inbox.
- Keyboard shortcuts should work from the live page.
- Queue polling should update the rail without stealing the current prompt.
- Dismiss plus rendered requeue should restore operator place.
- The existing live localhost integration suite should remain green.

## Actual Result

- Added two new end-to-end browser/operator proofs to [test_desktop_clipboard.py](/c:/Agent/HumanLoop/tests/integration/test_desktop_clipboard.py):
- `test_configured_desktop_keyboard_loop_copies_and_completes_without_losing_place`
- `test_configured_desktop_queue_polling_keeps_current_sticky_until_dismiss_and_requeue`
- Updated the shared checklist in [REGRESSION.md](/c:/Agent/HumanLoop/REGRESSION.md) with `REG-009` and `REG-010`.
- The live integration suite passed with the new browser/operator coverage in place.
- The full pytest suite also passed after the new tests were added.

## Case Results

| Case | Status | Evidence |
| --- | --- | --- |
| `REG-001 Empty Inbox Boot` | `PASS` | `tests/integration/test_live_localhost_api.py::test_live_server_boots_with_empty_operator_surfaces_and_runtime_log` |
| `REG-002 Prompt Ingest And Duplicate Replay` | `PASS` | `tests/integration/test_live_localhost_api.py::test_live_ingest_is_idempotent_and_survives_server_restart` |
| `REG-003 Current Prompt And Queue Rail Rendering` | `PASS` | `tests/integration/test_live_inbox_workflow.py::test_live_copy_keeps_current_prompt_visible_and_updates_copy_count` |
| `REG-004 Copy Does Not Hang Or Auto-Advance` | `PASS` | `tests/integration/test_desktop_clipboard.py::test_configured_desktop_webview_mouse_copy_resolves_cleanly` and `tests/integration/test_desktop_clipboard.py::test_configured_desktop_keyboard_loop_copies_and_completes_without_losing_place` |
| `REG-005 Complete Advances Only After Explicit Action` | `PASS` | `tests/integration/test_live_inbox_workflow.py::test_live_complete_advances_the_queue_after_explicit_action` and `tests/integration/test_desktop_clipboard.py::test_configured_desktop_keyboard_loop_copies_and_completes_without_losing_place` |
| `REG-006 Dismiss And Requeue Recovery` | `PASS` | `tests/integration/test_live_inbox_workflow.py::test_live_dismiss_and_requeue_restore_the_original_current_prompt` and `tests/integration/test_desktop_clipboard.py::test_configured_desktop_queue_polling_keeps_current_sticky_until_dismiss_and_requeue` |
| `REG-007 Smoke Script Against A Live Server` | `PASS` | `tests/integration/test_live_smoke_script.py::test_smoke_script_enqueues_a_prompt_against_a_live_humanloop_server` |
| `REG-008 Desktop Wrapper Shell` | `NOT RUN` | This slice did not launch `.\.venv\Scripts\humanloop-desktop.exe`; the rendered browser proof used a configured `QWebEngineView` harness instead. |
| `REG-009 Real Browser Keyboard Loop` | `PASS` | `tests/integration/test_desktop_clipboard.py::test_configured_desktop_keyboard_loop_copies_and_completes_without_losing_place` |
| `REG-010 Background Refresh Preserves Current Prompt` | `PASS` | `tests/integration/test_desktop_clipboard.py::test_configured_desktop_queue_polling_keeps_current_sticky_until_dismiss_and_requeue` |

## Evidence Gathered

- [test_desktop_clipboard.py](/c:/Agent/HumanLoop/tests/integration/test_desktop_clipboard.py) now drives the rendered inbox through real `QWebEngineView` input events instead of only calling APIs directly.
- The keyboard-loop proof opened shortcut help with `?`, copied with `C`, kept the same prompt visible with `copy_count = 1`, and advanced only after explicit `Enter`.
- The queue-refresh proof loaded one prompt, enqueued a second prompt while the first remained on screen, waited for the queue rail to poll to `2 total pending / 1 waiting`, then dismissed and requeued through the rendered UI.
- Three extra reruns of the queue-refresh proof all passed, which mattered because the first proof-development run briefly showed a non-reproducing UI refresh error before the helper fix.
- The live-localhost suite passed end to end, and the repo-wide suite stayed green at `71 passed`.

## Failures, Limitations, Or NOT RUN

- `REG-008` remains `NOT RUN` in this slice. No packaged `humanloop-desktop.exe` launch was exercised here.
- The first attempt to collect the new test file failed because of a JavaScript string escaping mistake in the new test helper. That was a test-authoring issue, not a repo behavior failure.
- A one-off requeue-refresh failure appeared during the very first focused browser run, but it did not reproduce in manual browser-sequence debugging or in three targeted reruns, so it is not being claimed as an open repo bug from this slice.
- This slice still does not prove out-of-repo producer wiring, multi-operator behavior, or concurrency stress against the same prompt row.

## What This Proves About The Current State Of The Repo

- HumanLoop now has honest end-to-end proof for the operator workflow at three layers:
- live localhost API and HTML seams
- smoke-script producer ingress against a real running server
- rendered browser/operator behavior for copy, keyboard shortcuts, complete, dismiss, requeue, and queue polling
- The repo no longer relies only on static template assertions for the keyboard/manual-handoff contract. The current browser proof now shows the page behaving like a real operator surface.
- The remaining gaps are no longer “does the inbox workflow work in practice?” gaps. They are packaging, external producer wiring, and higher-stress edge-case gaps.
