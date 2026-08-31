# ERD-DELTA v24 — one fail-fast asynchronous lifecycle mutation slot

v24 supersedes v23's split synchronous/asynchronous Manager API. The daemon
now exposes one truthful mutation path: synchronous admission followed by a
prompt operation response and a background worker. The operation store's
in-flight state is the one daemon-wide lifecycle slot.

1. `Manager.load()` and `Manager.unload()` are the only mutation entry points;
   `load_async()` and `unload_async()` are removed.
2. Admission is serialized under a short lock. The long-running
   `Lifecycle.spawn()`/`terminate()` worker never holds that lock.
3. At most one `loading` or `unloading` operation exists. An exact duplicate
   (same operation kind and model id) returns the existing operation id. Any
   different concurrent mutation raises `BusyError` and the HTTP layer returns
   a structured `409 busy` response immediately; requests are never silently
   queued behind a readiness timeout.
4. Every worker exception closes the operation as terminal `error`, so a
   failed worker cannot leave the slot permanently occupied.
5. The dashboard renders the structured busy conflict as an operator-visible
   message. The catalog URL `startswith` tuple rewrite is a behavior-neutral
   Ruff cleanup.

## Changed acceptance criteria

None. This re-freeze corrects and strengthens the existing 202 + operation-id
contract without adding or changing a PRD acceptance criterion.

## Superseded acceptance criteria

None. Two pre-v24 test assertions that expected direct callers to receive a
synchronous `SpawnError` now poll the returned operation to `error:failed`,
matching the unified asynchronous contract. The behavioral expectation—failed
startup is observable and leaves no owned process or sidecar—does not change.

## Changed files

- `src/vortex/operations.py` — adds the atomic-copy `active()` lookup used as
  the single in-flight lifecycle slot.
- `src/vortex/manager.py` — unifies load/unload as prompt asynchronous
  operations, reserves the slot during admission, deduplicates exact retries,
  raises `BusyError` for conflicts, and terminates every worker path.
- `src/vortex/app.py` — routes use the unified Manager API and translate
  `BusyError` to structured HTTP 409 detail.
- `src/vortex/ui.py` — renders the structured busy detail without treating it
  as an eviction-size conflict.
- `src/vortex/catalog.py` — behavior-neutral Ruff cleanup for URL prefix
  validation.
- `tests/test_serve.py` — blind-authored concurrency contract plus reconciliation
  of the two superseded synchronous exception assertions.
- `docs/ARCHITECTURE.md`, `docs/GLOSSARY.md`, `docs/DECISIONS.md` — record the
  single-slot contract and D-181 rationale.

## Test-to-file mapping

* `tests/test_serve.py::test_async_load_returns_while_worker_blocked`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_async_unload_returns_while_worker_blocked`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_single_slot_load_in_flight_rejects_second_load`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_single_slot_load_in_flight_rejects_unload`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_exact_duplicate_load_returns_existing_operation`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_background_spawn_exception_drives_op_to_error`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_success_paths_reach_terminal_states`
    -> `src/vortex/manager.py`

Carried unchanged: every other frozen node-id retains its standing ownership
pin from v23 and earlier versioned ERD delta snapshots.
