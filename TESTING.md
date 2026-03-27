# Testing Guide

This file is the HumanLoop-specific testing adapter.

The shared testing process now lives in [TESTING.md](/c:/Users/gregs/.codex/process/TESTING.md).
The shared debugging process now lives in [DEBUGGING.md](/c:/Users/gregs/.codex/process/DEBUGGING.md).

Use the shared `.codex` docs for the workflow around regression matrices, executed regression runs, and task-scoped bug notes.

This local file only defines HumanLoop-specific testing details:

- shared manual regression matrix: [REGRESSION.md](/c:/Agent/HumanLoop/REGRESSION.md)
- executed regression-run results: `Tracking/task-<id>/Testing/REGRESSION-RUN-<N>.md`
- new task-scoped bug notes: `Tracking/task-<id>/bug<NN>.md`
- HumanLoop-specific debugging adapter: [DEBUGGING.md](/c:/Agent/HumanLoop/DEBUGGING.md)
- real localhost integration suite under `tests/integration/`

## Local Bootstrap

From the repo root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

Optional desktop shell support:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[desktop]
```

## Automated Coverage

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests\integration -q
```

Use the full suite for release confidence and the integration suite when you specifically need proof against a real running localhost process.

## Current Known Issue

The current copy-hang bug is tracked in [BUG1.md](/c:/Agent/HumanLoop/Tracking/task-0001/Testing/BUG1.md).
This note predates the current `Tracking/task-<id>/bug<NN>.md` convention.

## Artifact Placement

- Keep the shared QA-style integration checklist in [REGRESSION.md](/c:/Agent/HumanLoop/REGRESSION.md).
- Keep executed regression-run results as `Tracking/task-<id>/Testing/REGRESSION-RUN-<N>.md`.
- Keep new task-scoped bug notes at `Tracking/task-<id>/bug<NN>.md`.
- Treat older task-local regression notes such as [Tracking/task-0001/Testing/REGRESSION.md](/c:/Agent/HumanLoop/Tracking/task-0001/Testing/REGRESSION.md) as legacy context, not the canonical matrix location.
- Use [DEBUGGING.md](/c:/Agent/HumanLoop/DEBUGGING.md) for HumanLoop-specific debugging references layered on top of the shared `.codex` standard.
