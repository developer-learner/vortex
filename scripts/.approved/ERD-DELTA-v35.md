# ERD-DELTA v35 — discovery frozen-test corrections (httpx allow, UI two-source contract)

No behavioral change and no new acceptance criteria. This re-freeze corrects two
internal inconsistencies in the v32/v33 discovery spec that made the frozen
tests unsatisfiable by any correct implementation of the already-frozen
`discover_models` feature (AC-9/10/11). Scope is tests only; `src/` behavior,
routes, and `contracts.json` are unchanged.

## Changed acceptance criteria

None new. Two clarifications to existing criteria, both test-only:

- **AC-2 (stdlib-only imports)** now carries one sanctioned exception: the
  discovery module may import `httpx`. AC-9's `discover_models` probes the LM
  Studio library over HTTP, so `src/vortex/discovery.py` must import an HTTP
  client; v33 froze the feature but left `httpx` forbidden, so the import-surface
  test rejected every working implementation. `httpx` moves from
  FORBIDDEN_IMPORTS to ALLOWED_IMPORT_ROOTS; every other third-party import
  (requests, psutil, fastapi, uvicorn, …) stays forbidden.
- **AC-11 (dashboard model fields)**: the UI reads `m.*` fields from TWO
  endpoints — `/api/catalog` and `/api/discovered-models`. The contract is now
  that every `m.*` field the UI reads is returned by at least one of the two,
  not by `/api/catalog` alone.

## Superseded acceptance criteria

None. No AC, route, or schema is removed or replaced.

## Changed files

- `tests/test_discovery.py` — EDIT (frozen test). Move `httpx` from
  FORBIDDEN_IMPORTS to ALLOWED_IMPORT_ROOTS. No new test node-ids.
- `tests/test_ui_api_contract.py` — EDIT (frozen test). The UI-field-coverage
  check now unions the keys of `/api/catalog` and `/api/discovered-models`; adds
  a `_one_discovered()` helper and a `model_discovery` injection into the test
  client. No new test node-ids.

Implementation (`src/vortex/discovery.py`, `app.py`, `ui.py`) satisfies the
already-frozen AC-9/10/11 and lands in a separate non-frozen commit; it is not
part of this freeze.

## Task DAG

None. This is a tests-only spec correction — no coder tasks; the implementation
already exists and is carried acceptance-only.

## Test-to-file mapping

No new test node-ids. The `test_discovery.py` change is module-level (the
import allow/forbid lists), so no test function body changes. One existing
frozen test function is modified in place and is pinned to its owner file here:

* `tests/test_ui_api_contract.py::test_ui_only_reads_catalog_fields_the_api_returns`
    -> `src/vortex/ui.py`
