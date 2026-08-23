# ERD-DELTA v9 — close pre-existing whole-tree type debt

The corrected immutable sandbox now runs the final mypy gate against Vortex
instead of the Blueprint snapshot. It exposed three pre-existing findings:
two untyped `psutil` imports and a `spawn` return annotation that excludes its
documented adoption return `(None, True)`. This delta changes typing metadata
only; runtime behavior and dependencies remain unchanged.

## Changed acceptance criteria

None. The existing frozen suite plus the mandatory mypy gate remain binding.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/lifecycle.py` — acknowledge the untyped third-party import and
  make `spawn`'s return annotation match its existing adoption branch.
- `src/vortex/manager.py` — acknowledge the same untyped third-party import.

## Test-to-file mapping

- `tests/test_serve.py::test_unidentified_occupant_refused`
  -> `src/vortex/lifecycle.py`
- `tests/test_serve.py::test_adopt_surviving_runtime_and_load`
  -> `src/vortex/lifecycle.py`
- `tests/test_serve.py::test_unload_terminates_child`
  -> `src/vortex/lifecycle.py`
- `tests/test_serve.py::test_spawn_from_launch_command`
  -> `src/vortex/lifecycle.py`
- `tests/test_serve.py::test_spawn_waits_for_anneal_before_ready`
  -> `src/vortex/lifecycle.py`
- `tests/test_serve.py::test_spawn_fails_when_chat_never_succeeds`
  -> `src/vortex/lifecycle.py`
- `tests/test_serve.py::test_load_conflict_reports_eviction`
  -> `src/vortex/manager.py`
- `tests/test_serve.py::test_unknown_model_load_404`
  -> `src/vortex/manager.py`
- `tests/test_serve.py::test_proxy_non_streaming`
  -> `src/vortex/manager.py`
- `tests/test_serve.py::test_proxy_streaming_passthrough`
  -> `src/vortex/manager.py`
- `tests/test_serve.py::test_proxy_unloaded_model_404`
  -> `src/vortex/manager.py`

## Coder briefs (verbatim)

### T1 — src/vortex/lifecycle.py (typing-only edit)

File: `src/vortex/lifecycle.py`. Use anchored SEARCH/REPLACE edits only. Add
the targeted mypy suppression `# type: ignore[import-untyped]` to the existing
`import psutil` line. Change `Lifecycle.spawn`'s return annotation from
`tuple[subprocess.Popen, bool]` to `tuple[subprocess.Popen | None, bool]` so it
matches the existing `(None, True)` adoption return. Change no runtime logic,
imports, constants, or control flow. Verify the mapped lifecycle tests pass
and mypy reports no error for this file.

### T2 — src/vortex/manager.py (typing-only edit)

File: `src/vortex/manager.py`. Use one anchored SEARCH/REPLACE edit to add the
targeted mypy suppression `# type: ignore[import-untyped]` to the existing
`import psutil` line. Change no runtime logic, imports, annotations, or control
flow. Verify the mapped manager tests pass and mypy reports no error for this
file.

## Task DAG

`src/vortex/manager.py` depends on `src/vortex/lifecycle.py`.
Task order: T1 (`src/vortex/lifecycle.py`) -> T2 (`src/vortex/manager.py`).
