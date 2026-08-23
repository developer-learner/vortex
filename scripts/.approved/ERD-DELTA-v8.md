# ERD-DELTA v8 — conflict-card refusal detail execution

The v4 frozen behavior remains unchanged. A 409 refusal must render the
structured detail as readable text rather than passing the detail object to
the DOM. This execution freeze carries the already-approved one-file brief;
it adds no endpoint, dependency, file, test, or product behavior.

## Changed acceptance criteria

None. The v4 conflict explanation remains binding.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/ui.py` — edit only the load/unload response handler. Preserve
  all existing CSS, element ids, URLs, intervals, escaping, and unrelated
  client behavior.

## Test-to-file mapping

- `tests/test_ui_conflict_card.py::test_conflict_card_reads_the_409_detail`
  -> `src/vortex/ui.py`
- `tests/test_ui_conflict_card.py::test_conflict_no_longer_read_from_status`
  -> `src/vortex/ui.py`
- `tests/test_ui_conflict_card.py::test_conflict_clears_on_successful_action`
  -> `src/vortex/ui.py`

## Coder briefs (verbatim)

### T1 — src/vortex/ui.py (edit existing file)

File: `src/vortex/ui.py`. Use anchored SEARCH/REPLACE edits only. In the
load/unload click handler, parse the response body once. When the response
status is 409, read `body.detail.message`, `body.detail.required_gb`, and
`body.detail.eviction_candidates`; construct a readable string containing the
message, required RAM in GiB, and the candidate model ids (use `none` when the
array is empty), pass that string to `setConflict`, and return no operation.
For any other non-success status, keep throwing the existing action error. For
a successful response, return the parsed operation body; in the following
handler call `setConflict(null)` before `pollOperation(op.operation)`. Keep the
existing removal of the dead `s.conflict` status read. Do not change CSS,
element ids, fetch URLs, polling intervals, imports, or unrelated JS. Verify
the three `tests/test_ui_conflict_card.py` node-ids pass along with the carried
UI contract/content tests.

## Task DAG

Task order: T1 (`src/vortex/ui.py`).
