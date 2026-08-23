# ERD-DELTA v4 — vortex M1: conflict-card wiring (real 409 source)

The M1 dashboard's conflict card (`#conflict` / `#conflictbody`) is dormant:
`pollStatus` reads `s.conflict` from `GET /api/status`, which never carries it,
and the load/unload click handler swallows a `409` silently (its `.catch` drops
the error). Real load refusals arrive as a `409` on `POST /api/models/{id}/load`
with detail `{message, required_gb, eviction_candidates}` (see the load handler
in `src/vortex/app.py`). This is a corrective, non-additive delta: no new
endpoints, files, or dependencies; one file.

## Changed acceptance criteria

None. No AC ids are defined for M1 (the frozen suite is binding, D-54). This
delta makes the existing PRD "Conflict explanation" scope actually fire at
runtime.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/ui.py` — EDIT (existing file; anchored SEARCH/REPLACE, D-59).
  Two changes, nothing else touched (keep all CSS, ids, other fetch URLs, poll
  intervals, escaping, and wiring):

  1. Load/unload click handler. Read the response body, then branch on the
     status: on HTTP `409`, take the refusal detail (`body.detail` —
     `message`, `required_gb`, `eviction_candidates`) and drive the card via
     `setConflict(...)` with a readable message; on a successful response,
     call `setConflict(null)` to clear any standing card, then
     `pollOperation(op.operation)` as today. Eviction stays operator-driven —
     the card informs, it never auto-evicts (PRD M1 scope).
  2. `pollStatus`. Remove the `setConflict(s.conflict || null)` read — the card
     is driven by the 409 path, and `/api/status` never returns `conflict`.

## Test-to-file mapping

New — `tests/test_ui_conflict_card.py` gates the ui.py change; each function
pins to `src/vortex/ui.py`:

* `tests/test_ui_conflict_card.py::test_conflict_card_reads_the_409_detail`
    -> `src/vortex/ui.py`
* `tests/test_ui_conflict_card.py::test_conflict_no_longer_read_from_status`
    -> `src/vortex/ui.py`
* `tests/test_ui_conflict_card.py::test_conflict_clears_on_successful_action`
    -> `src/vortex/ui.py`

Carried unchanged: `tests/test_ui_api_contract.py`, `tests/test_ui_content.py`,
`tests/test_ui_route.py`, `tests/test_catalog.py`, `tests/test_serve.py`.
