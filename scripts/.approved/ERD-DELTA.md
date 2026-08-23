# ERD-DELTA v2 — vortex M1: dashboard ⇄ API field-contract fix

The M1 dashboard (`src/vortex/ui.py`) was ported from
`examples/ui-demo/index.html` "verbatim" (v1 ERD), but that demo's client JS
reads field names and a response shape the real management API
(`src/vortex/app.py`) never emits. Every static v1 test passed because none
exercises the page against a real API payload, so the shipped dashboard shows
an empty table, a 0-GiB RAM meter, every running model as "idle", and dead
load/unload buttons.

This is a corrective (non-additive) delta: it changes NO acceptance criteria
and adds NO endpoints, files, or dependencies. It re-aligns the client to the
EXISTING API contract and adds one frozen test that pins the client⇄server
field contract the v1 suite missed.

## Changed acceptance criteria

None. No AC ids are defined for M1 — the frozen suite is the binding
definition (D-54). This delta corrects the implementation so the existing M1
scope (see PRD "M1 scope") is actually met at runtime.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/ui.py` — EDIT (existing file; anchored SEARCH/REPLACE edits,
  D-59). Correct the client JS to the real API contract below. Change ONLY the
  field / shape / state reads named here; leave all CSS, element ids, fetch
  URLs, poll intervals, the escaping helper, and event wiring untouched.

  The real API contract (authoritative — read from `src/vortex/app.py`):

  1. Catalog envelope. `GET /api/catalog` returns
     `{"entries": [ <entry>, ... ]}` — an object, not a bare array. The
     catalog poll renders rows from `data.entries`, not from the response
     object itself.
  2. Catalog entry fields. Each entry carries `public_id`, `runtime`,
     `engine`, `port`, `ram_estimate_gb`, `ctx_size`, and `state`. There is no
     `id`, `name`, or `size_gib`. In the row renderer: the model column shows
     `m.public_id` (was `m.name`); the size column shows `m.ram_estimate_gb`
     (was `m.size_gib`); the load/unload button `data-id` uses `m.public_id`
     (was `m.id`).
  3. Loaded-state token. A serving model's `state` is `"ready"`, never
     `"loaded"`. The row's loaded test becomes `m.state === "ready"`; the
     `"loading"` test is unchanged. Keep the existing `loaded` / `loading` CSS
     class names.
  4. Status fields. `GET /api/status` returns `ram_used_gb` and
     `ram_total_gb` (GB, not `_gib`) and no `ram_pct`. The RAM meter reads
     `s.ram_used_gb` / `s.ram_total_gb` and computes the percent itself
     (`total > 0 ? used / total * 100 : 0`); the warn (>70) / danger (>85)
     zones and the label format are unchanged.
  5. Operation handle. `POST /api/models/{id}/load|unload` returns
     `{"operation": <id>, "model": <id>}`. After a click, poll `op.operation`
     (was `op.id`).

## Test-to-file mapping

New — `tests/test_ui_api_contract.py` gates the ui.py fix. Each added
function pins to `src/vortex/ui.py`:

* `tests/test_ui_api_contract.py::test_catalog_response_is_enveloped`
    -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_only_reads_catalog_fields_the_api_returns`
    -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_only_reads_status_fields_the_api_returns`
    -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_uses_the_api_loaded_state_token`
    -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_uses_the_operation_field_the_api_returns`
    -> `src/vortex/ui.py`

Carried unchanged: `tests/test_ui_content.py` -> `src/vortex/ui.py`;
`tests/test_ui_route.py` -> `src/vortex/app.py`; `tests/test_catalog.py`
and `tests/test_serve.py` (domain/app coverage).

## Out of scope (separate follow-up)

The conflict card currently reads `s.conflict` from `/api/status`, which never
carries it — real load refusals arrive as a `409` on the load POST
(`{message, required_gb, eviction_candidates}`). Wiring the card to the 409
path is a separate small milestone; this delta leaves that card dormant and
does not touch it.
