# ERD-DELTA v25 — CLI malformed-type hardening and copy-safe operation reads

v25 hardens two read paths without changing the 202 + operation-id contract or
any route. The daemon's responses are trusted JSON, but a malformed body (wrong
type, not just a missing key) must fail the CLI cleanly instead of leaking a
traceback, and the operation store must not hand out live mutable records
through `get()`.

1. `modelmux.cli.main` now treats a mistyped daemon response (a body whose JSON
   type is wrong, e.g. a string where an object is expected) as the same
   controlled failure as a missing key or invalid JSON: it exits 1 with a
   message on stderr and never raises `TypeError`/`AttributeError`.
2. `OperationStore.get()` returns an atomic copy of the stored operation,
   matching `active()` and `snapshot()`. A reader can no longer mutate live
   operation state outside the store's lock. The API boundary already returned
   copies via `snapshot()`; this closes the last live-record seam.

## Changed acceptance criteria

None. This re-freeze hardens two read paths (CLI response handling and
operation-store reads) without adding or changing a PRD acceptance criterion.

## Superseded acceptance criteria

None. The 202 + operation-id contract and the retention / atomic-snapshot
behavior are unchanged. One carried retention test is re-authored to age an
operation by advancing the clock instead of mutating it through `get()`, which
no longer returns a live record.

## Changed files

- `src/modelmux/cli.py` — catches `TypeError`/`AttributeError` from a mistyped
  daemon response alongside `KeyError`/`ValueError`, so a wrong JSON type fails
  cleanly (exit 1 + stderr message) instead of a traceback.
- `src/vortex/operations.py` — `get()` returns an atomic copy of the stored
  operation, matching `active()`/`snapshot()`.
- `tests/test_cli.py` — adds a malformed-type response gate.
- `tests/test_operations.py` — adds a `get()`-returns-a-copy gate and re-authors
  the retention test to age the operation by advancing the clock.
- `docs/GLOSSARY.md` — records the harmonic/session readiness model (a separate
  docs commit; not a frozen artifact).

## Test-to-file mapping

* `tests/test_cli.py::test_malformed_type_response_is_controlled`
    -> `src/modelmux/cli.py`
* `tests/test_operations.py::test_get_returns_a_copy`
    -> `src/vortex/operations.py`
* `tests/test_operations.py::test_retention_expires_old_completed_ops`
    -> `src/vortex/operations.py`

Carried unchanged: every other frozen node-id retains its standing ownership
pin from v24 and earlier versioned ERD delta snapshots.
