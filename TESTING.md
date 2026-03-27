# Testing Guide

This file is the HumanLoop-specific testing adapter.

The shared task lifecycle now lives in [ORCHESTRATION.md](/c:/Users/gregs/.codex/Orchestration/ORCHESTRATION.md).
The shared task-owned structure and glossary now live in [AGENTS.md](/c:/Users/gregs/.codex/AGENTS.md).
The shared testing process now lives in [TESTING.md](/c:/Users/gregs/.codex/Orchestration/Processes/TESTING.md).
The shared debugging process now lives in [DEBUGGING.md](/c:/Users/gregs/.codex/Orchestration/Processes/DEBUGGING.md).

Use the shared `.codex` docs for the workflow around regression matrices, executed regression runs, task-scoped bug notes, and shared test terminology.

This local file only defines HumanLoop-specific testing details:

- shared manual regression matrix: [REGRESSION.md](/c:/Agent/HumanLoop/REGRESSION.md)
- executed regression-run results: `Tracking/Task-<id>/Testing/REGRESSION-RUN-<NNNN>.md`
- new task-scoped bug notes: `Tracking/Task-<id>/BUG-<NNNN>.md`
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

The current copy-hang bug is tracked in [BUG-0001.md](/c:/Agent/HumanLoop/Tracking/Task-0001/BUG-0001.md).

## Artifact Placement

- Keep the shared QA-style integration checklist in [REGRESSION.md](/c:/Agent/HumanLoop/REGRESSION.md).
- Keep executed regression-run results as `Tracking/Task-<id>/Testing/REGRESSION-RUN-<NNNN>.md`.
- Keep new task-scoped bug notes at `Tracking/Task-<id>/BUG-<NNNN>.md`.
- Use [DEBUGGING.md](/c:/Agent/HumanLoop/DEBUGGING.md) for HumanLoop-specific debugging references layered on top of the shared `.codex` standard.
