# ERD-DELTA v34 — discovered-models re-freeze (brief-cap, DAG, no-op-brief fixes)

This re-freeze makes the v33 discovered-models feature buildable. The v33 ERD
declared four inventory files but carried briefs for only three, and two of those
briefs exceeded the 2500-char cap (Rule 8); the gate's brief-per-inventory-file rule
(D-54) and the cap together blocked `--synthesize-plan`, so the v33 run halted at the
plan phase. v34 fixes three mechanical defects with **no scope change** and **no
behavioral change**:

1. **Tighten the two over-cap briefs.** `discovery.py` (4010) and `ui.py` (4526) were
   over the 2500-char cap; both are rewritten under it — discovery as a field-mapping
   checklist, ui as a functional-structure description that embeds the exact tokens the
   frozen tests assert. `app.py` (2367) was already under cap and is unchanged.
2. **Add the missing no-op brief for `memory.py`.** The v33 ERD listed `memory.py` in
   the inventory (no_edit) but carried no brief, so synthesis could not complete. v34
   adds a no-op acceptance-only brief (the file is green from v31; no edit).
3. **Fix the Task DAG form.** The v33 DAG used `depends_on: T1` (task-id, underscore),
   which the gate's DAG parser does not recognize. v34 uses the recognized
   backtick-quoted file-path form.

The feature is unchanged from v32/v33: a read-only surface that enumerates the models a
library wrapper (LM Studio on :1234) has already downloaded, browsable on the dashboard.
**Browse only**: it reports discovered models, never mutates the catalog and never loads
a model. Config-first is preserved — a discovered model is "discovered, not configured".
It is a direct structural mirror of the v14 engine-wrappers inventory (discovery
function → injected into `build_app` → GET inventory + POST rescan routes → dashboard
section with a rescan button).

## Changed acceptance criteria

None new in v34. The discovered-models ACs (**AC-9** discover_models probe +
DiscoveredModel, **AC-10** the two `/api/discovered-models` routes, **AC-11** the
"Discovered models" dashboard section + Scan control) are carried unchanged from v32.

## Superseded acceptance criteria

None. No existing route, schema, or AC changes.

## Changed files

- `src/vortex/discovery.py` — EDIT. Add `DiscoveredModel`, `LIBRARY_PROBES`,
  `_fetch_library`, `discover_models`; add `import httpx` and
  `from collections.abc import Callable`. Existing wrapper discovery untouched.
- `src/vortex/app.py` — EDIT. Import `DiscoveredModel, discover_models`; add a
  `model_discovery=discover_models` parameter to `build_app`; add a
  `model_cache`; add `_get_models()` and the two routes.
- `src/vortex/ui.py` — EDIT. Add a `#discoveredmodels` section, `renderModels`,
  `pollModels`, a Scan click handler, and the poll-cadence wiring.
- `src/vortex/memory.py` — NO_EDIT (acceptance-only carry). Already implemented
  at v31; the coder is never invoked for it. Its frozen `test_memory_figure.py`
  tests run as acceptance and must stay green.

## Task DAG

`src/vortex/app.py` depends on `src/vortex/discovery.py`

- **T1** `src/vortex/discovery.py` — no dependencies.
- **T2** `src/vortex/app.py` — depends on T1 (imports the T1 symbols).
- **T3** `src/vortex/ui.py` — no dependencies (pure UI_PAGE string; no runtime dep).
- **T4** `src/vortex/memory.py` — no dependencies (no-op acceptance carry).

## Test-to-file mapping

The discovered-models test files are new this milestone, so their node-ids are not yet
in the frozen `test-nodeids` and cannot be pre-pinned in `contracts.test_mapping` (the
pin gate rejects unknown node-ids). Each is pinned to its owner file here instead; the
EM maps each to the task owning that file, per the DAG above. The `memory.py` tests are
a carried v31 acceptance set (no_edit) and are pinned here so the no-op brief has its
owning file.

* `tests/test_discovered_models.py::test_probe_maps_every_library_entry_to_a_discovered_model`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_discovered_model_carries_the_metadata_fields`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_loaded_flag_reflects_loaded_instances`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_in_catalog_flag_matches_key_against_catalog_upstream_alias`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_library_unreachable_yields_no_models_never_an_error`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_entries_without_a_key_are_skipped`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models_api.py::test_get_lists_discovered_models`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_wire_schema_carries_all_discovered_model_fields`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_discover_post_flags_models_not_in_catalog`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_build_app_defaults_to_real_model_discovery`
    -> `src/vortex/app.py`
* `tests/test_ui_discovered_models.py::test_ui_has_discovered_models_section`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_ui_fetches_the_discovered_models_endpoint`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_ui_renders_discovered_model_fields_from_the_api`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_scan_button_posts_to_the_rescan_route`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_poll_models_runs_on_the_existing_cadence`
    -> `src/vortex/ui.py`
* `tests/test_memory_figure.py::test_activity_monitor_parse_matches_the_vm_stat_arithmetic`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_used_figure_excludes_reclaimable_cache`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_activity_monitor_missing_keys_report_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_ram_used_prefers_vm_stat_and_names_it`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_psutil_fallback_is_labeled_never_silent`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_model_rss_gb_reads_ps_output`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_model_rss_gb_none_pid_is_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_model_rss_gb_unreadable_is_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_loadable_gb_bounds_reclaimable_by_wired_limit`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_loadable_gb_failure_reports_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_status_api_carries_memory_source_and_parity_figures`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_status_api_names_the_memory_source`
    -> `src/vortex/memory.py`

## Coder briefs (verbatim)

### T1 — src/vortex/discovery.py

This is an EDIT to `src/vortex/discovery.py`. Append the model-discovery surface after the existing `discover_wrappers`; change nothing else. Add `import httpx` and `from collections.abc import Callable` to the imports.

Add a frozen pydantic `DiscoveredModel` (`model_config = {"frozen": True}`) with fields: `key`, `display_name`, `publisher`, `architecture`, `quantization`, `size_bytes` (int), `params`, `max_context` (int), `fmt`, `loaded` (bool, default False), `source`, `in_catalog` (bool, default False).

Add `LIBRARY_PROBES = (("lmstudio", 1234),)`.

Add `_fetch_library(base_url) -> list[dict]`: GET `{base_url}/api/v1/models` with a 3s timeout; return the JSON `models` list, or `[]` on ANY failure (unreachable, non-200, bad JSON, missing/non-list key) — never raises.

Add `discover_models(catalog_entries=None, fetch=_fetch_library, probes=LIBRARY_PROBES)` returning a list of DiscoveredModel. For each `(source, port)` probe, for each fetched entry that has a `key`, build a `DiscoveredModel` with EXACTLY these mappings:
- `key` ← `key`
- `display_name` ← `display_name` (fall back to `key` if absent)
- `publisher` ← `publisher`
- `architecture` ← `architecture`
- `quantization` ← the `name` from the entry's `quantization` dict (or the raw value if it is a string)
- `size_bytes` ← `size_bytes`
- `params` ← `params_string`
- `max_context` ← `max_context_length`
- `fmt` ← `format`
- `loaded` ← `bool(loaded_instances)`
- `source` ← the probe's source name
- `in_catalog` ← True iff `key` equals some catalog entry's `upstream_alias` or `public_id`
Skip entries without a `key`. Never launches, loads, or alters anything.

Self-verify: the file parses; `DiscoveredModel` and `discover_models` import; the existing `discover_wrappers`/`Wrapper`/`WRAPPER_SPECS` are unchanged.

### T2 — src/vortex/app.py

This is an EDIT to an existing file. Make exactly four changes; change nothing
else.

**(a)** Change the discovery import line
`from .discovery import Wrapper, discover_wrappers`
to
`from .discovery import DiscoveredModel, Wrapper, discover_models, discover_wrappers`

**(b)** In the `build_app(...)` signature, add a new parameter
`model_discovery=discover_models` on its own line immediately after the
existing `wrapper_discovery=discover_wrappers,` line and before
`on_shutdown: Callable[[], None] | None = None,`.

**(c)** Immediately after the existing module-level line that declares
`wrapper_cache` (a dict initialized to an empty dict), add a new line
declaring `model_cache` with the SAME annotation shape as `wrapper_cache`
but substituting the element type Wrapper with DiscoveredModel — i.e. a dict
from str to a tuple of a float and a list of DiscoveredModel — initialized to
an empty dict. Indentation matches the `wrapper_cache` line.

**(d)** Immediately before the final `return app` line at the end of
`build_app`, insert these three definitions verbatim (keep the existing
`return app` after them). Annotate `_get_models`'s return as a list of
DiscoveredModel (shown as `-> list` below to keep this brief plain; use the
precise `list` of DiscoveredModel annotation in the code):

```python
    def _get_models() -> list:
        now = time.time()
        cached = model_cache.get("default")
        if cached is not None and now - cached[0] <= 60.0:
            return cached[1]
        findings = model_discovery(catalog_entries=catalog.entries)
        model_cache["default"] = (now, findings)
        return findings

    @app.get("/api/discovered-models")
    def discovered_models() -> dict:
        return {"models": [dict(m) for m in _get_models()]}

    @app.post("/api/discovered-models/discover")
    def discovered_models_discover() -> dict:
        model_cache.clear()
        findings = model_discovery(catalog_entries=catalog.entries)
        model_cache["default"] = (time.time(), findings)
        models = [dict(m) for m in findings]
        newly_found = [m.key for m in findings if not m.in_catalog]
        return {"models": models, "newly_found": newly_found}
```

Self-verify: the file parses; `build_app` has a `model_discovery` parameter
whose default is `discover_models`; the existing engine-wrappers routes are
unchanged.

### T3 — src/vortex/ui.py

This is an EDIT to the single `UI_PAGE` string in `src/vortex/ui.py`. Insert a `#discoveredmodels` section between the engine-wrappers `</section>` and `</main>`, plus the JS that drives it. `UI_PAGE` is a plain triple-quoted string — insert literal HTML/JS, no f-string interpolation.

HTML: a `<section id="discoveredmodels">` with an `<h2>Discovered models</h2>`, a `<table>` (thead: Model, Publisher, Quant, Size, Params, Context, Loaded, Catalog) whose `<tbody id="modelrows">` starts with a loading row, and a `<button data-act="scan-models">Scan</button>`.

JS (insert after the existing `pollWrappers` function):
- `renderModels(models)`: fill `#modelrows` with one row per model showing `m.key`, `m.publisher`, `m.quantization`, size, params, context, `m.loaded`, `m.in_catalog` (an empty-state row when the list is empty).
- `pollModels()`: `fetch("/api/discovered-models")` then `renderModels(data.models)`.
- A click handler on `#discoveredmodels`: for a `data-act="scan-models"` button, `fetch("/api/discovered-models/discover", { method: "POST" })` then `pollModels()`.

Bootstrap (the existing `pollStatus(); pollCatalog(); pollWrappers();` + `setInterval(..., POLL_MS)` block at the end): add `pollModels();` after `pollWrappers();` and `setInterval(pollModels, POLL_MS);` after `setInterval(pollWrappers, POLL_MS);`.

Self-verify: `UI_PAGE` contains `Discovered models`, `id="modelrows"`, `data-act="scan-models"`, `fetch("/api/discovered-models")`, `m.key`, `m.publisher`, `m.quantization`, `m.in_catalog`, `discovered-models/discover`, `method: "POST"`, and `setInterval(pollModels, POLL_MS)`.

### T4 — src/vortex/memory.py (no-op)

NO-OP — acceptance-only carry. Do not edit `src/vortex/memory.py`. It implements the v31 direct-route RAM parity (vm_stat working-set figure, psutil fallback, per-model RSS, loadable bound) and is green. Its frozen tests (`tests/test_memory_figure.py`) run as acceptance; make no changes.
