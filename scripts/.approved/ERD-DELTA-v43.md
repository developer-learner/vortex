# ERD-DELTA v39 — add discovered models to Vortex (Add / Add all new / Remove)

v39 turns a discovered LM Studio model into a loadable catalog entry on the
operator's click. The discovered-model → entry rule is a pure new module
(`catalog_synth.py`); the catalog gains an entry origin, a source path, and a
separate local file for added entries; the app gains three routes; the
dashboard gains the controls. This delta deliberately carries NO verbatim
coder briefs: the EM decomposes it from the per-file detail below (the CEO
asked to exercise the EM seat). The DAG and ownership pins are authoritative.

## Changed acceptance criteria

New criteria introduced by this milestone (PRD v39):

- AC-25: discovered models carry their `lms ls --json` path (discovery.py).
- AC-26: in_catalog also matches by path (discovery.py).
- AC-27: MLX → mlx-serve entry on the lowest free 8200–8299 port (catalog_synth.py).
- AC-28: GGUF → llama-server entry (catalog_synth.py).
- AC-29: unsynthesizable models raise SynthesisError with a reason (catalog_synth.py).
- AC-30: RAM estimate = size + 10%, exclusive above 40 GB (catalog_synth.py).
- AC-31: add route adds live + persists; 201 (app.py, catalog.py).
- AC-32: add route 404 unknown key / 422 synthesis refusal (app.py).
- AC-33: add-new adds all new models on distinct ports, reports skips (app.py).
- AC-34: remove route for local entries; 404 / 409 refusals (app.py, catalog.py).
- AC-35: local catalog file merged at load with origin "local" (catalog.py).
- AC-36: dashboard Add / Add all new / Remove controls with confirms (ui.py).
- AC-37: dashboard shows Add failed / Remove failed and lists skips (ui.py).

## Superseded acceptance criteria

AC-10 is narrowed, not replaced: the discovered-model wire schema now also
carries `path` (AC-25). `tests/test_discovered_models_api.py::
test_wire_schema_carries_all_discovered_model_fields` is re-frozen with `path`
added to the expected field set; its other assertions are unchanged.

## Changed files

- `src/vortex/catalog.py` — EDIT.
- `src/vortex/discovery.py` — EDIT.
- `src/vortex/catalog_synth.py` — NEW.
- `src/vortex/app.py` — EDIT.
- `src/vortex/catalog_routes.py` — NEW (v43): the add / add-new / remove routes, registered by app.py.
- `src/vortex/ui.py` — EDIT.

## Per-file behavioral detail

### src/vortex/catalog.py

- `CatalogEntry` gains two optional fields, both carried through
  `model_dump()`/validation: `source_path: str | None = None` (the model files
  an added entry serves) and `origin: Literal["config", "local"] = "config"`.
- `load_catalog(path, local_path=None)`: loads `path` as today (origin
  "config"). When `local_path` is given AND the file exists, its
  `{"entries": [...]}` rows are loaded with origin forced to "local" and
  merged after the config rows; the merged catalog is validated by the same
  duplicate public id / duplicate port rules (same messages: "duplicate
  public id", "duplicate port"). A missing local file is not an error.
- `Catalog.add(entry)`: raises `ValueError` whose message contains "duplicate
  public id" or "duplicate port" when either collides with an existing entry;
  otherwise appends to `self.entries` IN PLACE (other components hold this
  same list).
- `Catalog.remove(public_id) -> CatalogEntry`: `KeyError` for an unknown id;
  `ValueError` with a message containing "config" for an entry whose origin is
  "config"; otherwise removes it from `self.entries` in place and returns it.
- `save_local_entries(catalog, local_path)`: writes
  `{"entries": [<every origin "local" entry as model_dump(mode="json")>]}`
  (indent 2) to a temp file beside `local_path`, then `os.replace` onto it.
  Only local entries are written; config entries never are.

### src/vortex/discovery.py

- `DiscoveredModel` gains `path: str | None = None` (field order: after
  `in_catalog`). It appears in the wire schema of `/api/discovered-models`.
- New `LMS_BIN = Path.home() / ".lmstudio/bin/lms"` and
  `LMSTUDIO_MODELS_ROOT = Path.home() / ".lmstudio/models"`.
- New `lmstudio_model_paths(run=None, models_root=None) -> dict[str, str]`:
  `run` is a zero-argument callable returning the stdout text of
  `lms ls --json`; the default runs `[str(LMS_BIN), "ls", "--json"]` with
  `subprocess.run(..., capture_output=True, text=True, timeout=10,
  check=False)` and returns its stdout. The text is a JSON array (see the frozen
  capture `captures/lms-ls.json`); each row with both a `modelKey` and a
  `path` maps `modelKey -> str(models_root / path)` (`models_root` defaults to
  `LMSTUDIO_MODELS_ROOT`). ANY exception or non-list JSON returns `{}` — log
  it at debug level, never raise.
- `discover_models(catalog_entries=None, fetch=None, probes=None, paths=None)`:
  `paths` is a zero-argument callable returning that map (default
  `lmstudio_model_paths`). Each DiscoveredModel's `path` is `paths_map.get(key)`.
  `in_catalog` is true when the key equals an entry's `upstream_alias` (as
  today) OR the model's path is not None and equals an entry's `source_path`
  or is one of the strings in an entry's `launch_command`.

### src/vortex/catalog_synth.py (NEW, stdlib + vortex imports only)

- **Imports (exact — v40 escalation response):** these three types live in
  existing modules of the `vortex` package and are imported RELATIVELY, the
  way every other module in the package imports its siblings. There is no
  `vortex.models` module.

      from .catalog import Catalog, CatalogEntry
      from .discovery import DiscoveredModel

  plus stdlib `os` and `re`. Annotate optional values as `X | None`.

- `PORT_RANGE = range(8200, 8300)`;
  `RUNTIME_BINARIES = {"mlx": "/opt/homebrew/bin/mlx-serve", "gguf": "/opt/homebrew/bin/llama-server"}`.
- `class SynthesisError(ValueError)`.
- `synthesize_entry(model: DiscoveredModel, catalog: Catalog, binaries=RUNTIME_BINARIES) -> CatalogEntry`,
  checks in this order, each raising SynthesisError whose message contains the
  quoted word: path is None → "no local path known for <key>" ("path");
  `model.fmt` not a key of `binaries` → "unsupported format <fmt>" ("format");
  architecture is None → "no architecture reported (not a chat model)"
  ("architecture"); public id (below) already used, or path equal to an
  entry's `source_path` or present in its `launch_command` → "already in the
  catalog as <id>" ("already"); no port of PORT_RANGE free of catalog ports →
  "no free port in 8200-8299" ("port").
- public id = `re.sub(r"[^a-z0-9._-]", "-", model.key.lower())`.
- port = lowest port in PORT_RANGE not used by any catalog entry.
- mlx: runtime and engine "mlx-serve", launch
  `[binaries["mlx"], "--model", path, "--serve", "--host", "127.0.0.1", "--port", str(port)]`.
- gguf: runtime "llama-server", engine "llama.cpp", launch
  `[binaries["gguf"], "-m", path, "--host", "127.0.0.1", "--port", str(port)]`.
- ready_url `http://127.0.0.1:<port>/v1/models`, chat_endpoint
  `http://127.0.0.1:<port>/v1/chat/completions`, upstream_alias =
  `os.path.basename(path.rstrip("/"))`, `ram_estimate_gb =
  round(size_bytes * 1.1 / 1e9, 1)` when size_bytes else None, `exclusive =
  ram_estimate_gb is not None and ram_estimate_gb > 40`, `source_path = path`,
  `origin = "local"`. Return `CatalogEntry.model_validate(...)` of that dict.

### src/vortex/app.py

- **Imports (exact — v40 escalation response):** extend the existing
  `from .catalog import ...` line so it also imports `save_local_entries`,
  and add `from .catalog_synth import SynthesisError, synthesize_entry` next
  to the other relative imports. There is no `vortex.models` module.

- `build_app` gains keyword `local_catalog_path: Path | None = None`. When
  `catalog` is None, the app loads
  `load_catalog(<repo>/config/catalog.json, local_path=<repo>/config/catalog.local.json)`
  and persists to that local path. When `catalog` is passed explicitly,
  persistence goes to `local_catalog_path` only if it was given (otherwise
  adds/removes stay in memory). `model_discovery` is still called with ONLY
  `catalog_entries=...` (frozen tests pass one-argument fakes).
- `/api/catalog` rows add `"origin"` and `"source_path"`.
- `POST /api/discovered-models/{key}/add`: find `key` in the discovered models
  (cached list; rescan once if absent) → 404 `{"detail": "..."}` if absent;
  `synthesize_entry(model, catalog)` → on SynthesisError 422
  `{"detail": {"message": str(exc), "key": key}}`; else `catalog.add`, persist,
  clear the discovered-model cache, and return 201
  `{"added": entry.model_dump(mode="json")}`.
- `POST /api/discovered-models/add-new`: clear the cache, rescan, and for each
  discovered model with `in_catalog` False try synthesize + add (the catalog
  grows as it goes, so ports never collide); SynthesisError rows go to
  `skipped` as `{"key", "reason"}`. Persist once, clear the cache, return 200
  `{"added": [<public ids>], "skipped": [...]}`.
- `DELETE /api/catalog/{public_id}`: 404 when unknown; 409
  `{"detail": {"message": ...}}` when origin is "config", when the entry is
  loaded (its port is occupied — `lifecycle.occupying_pid(entry)` is not None)
  or when an operation for it is active (`ops.active_for(public_id)`);
  otherwise `catalog.remove`, persist, clear the cache, return 200
  `{"removed": public_id}`.

### src/vortex/ui.py

- Beside the existing Scan control (`data-act="scan-models"`) add
  `<button id="addnewmodels">Add all new</button>` and an empty
  `<div id="addresult"></div>`.
- Its handler: `document.getElementById("addnewmodels").addEventListener("click", function () {`
  → `confirm("Add every discovered model not yet in Vortex to the loadable list?")`,
  `return` on cancel; else `fetch("/api/discovered-models/add-new", { method: "POST" })`;
  on success write "Added N" plus each skipped `s.key + " (" + s.reason + ")"`
  (reading `body.skipped` / `.reason`) into `#addresult`, then call
  `pollCatalog()` and `pollModels()`; on failure `setError("Add failed: " + message)`.
- In the discovered-model row renderer: when `!m.in_catalog`, render
  `<button data-act="add-model" data-key="...">Add</button>`; its click POSTs
  `"/api/discovered-models/" + encodeURIComponent(key) + "/add"` with
  `{ method: "POST" }`, then re-polls both lists; failure →
  `setError("Add failed: " + <server detail message>)`.
- In the catalog row renderer: when `m.origin === "local"`, render
  `<button data-act="remove-model" data-id="...">Remove</button>`; its click
  `confirm("Remove <id> from Vortex? The model files are not deleted.")`, then
  `fetch("/api/catalog/" + encodeURIComponent(id), { method: "DELETE" })`,
  re-polls both lists; failure → `setError("Remove failed: " + <detail message>)`.
- Every `m.*` field the page reads must be returned by `/api/catalog` or
  `/api/discovered-models` (frozen ERD-33 contract test).

## Test-to-file mapping

* `tests/test_catalog_local.py::test_entries_default_to_config_origin_and_no_source_path`
    -> `src/vortex/catalog.py`
* `tests/test_catalog_local.py::test_load_merges_the_local_file_as_local_origin`
    -> `src/vortex/catalog.py`
* `tests/test_catalog_local.py::test_load_without_a_local_file_is_just_the_config`
    -> `src/vortex/catalog.py`
* `tests/test_catalog_local.py::test_local_entries_colliding_with_config_are_rejected`
    -> `src/vortex/catalog.py`
* `tests/test_catalog_local.py::test_add_appends_and_rejects_duplicates`
    -> `src/vortex/catalog.py`
* `tests/test_catalog_local.py::test_remove_only_removes_local_entries`
    -> `src/vortex/catalog.py`
* `tests/test_catalog_local.py::test_save_writes_only_local_entries_and_round_trips`
    -> `src/vortex/catalog.py`
* `tests/test_discovery_paths.py::test_path_map_joins_cli_paths_onto_the_models_root`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_paths.py::test_path_map_is_empty_when_the_listing_cannot_be_read`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_paths.py::test_path_map_skips_rows_without_key_or_path`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_paths.py::test_discovered_models_carry_their_path_or_none`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_paths.py::test_in_catalog_matches_a_path_in_an_entry_launch_command`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_paths.py::test_in_catalog_matches_an_entry_source_path`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_paths.py::test_unrelated_entry_does_not_mark_the_model_in_catalog`
    -> `src/vortex/discovery.py`
* `tests/test_catalog_synth.py::test_port_range_and_binaries_are_the_ceo_policy`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_mlx_model_becomes_an_mlx_serve_entry`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_gguf_model_becomes_a_llama_server_entry`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_lowest_free_port_skips_ports_the_catalog_uses`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_public_id_is_sanitized_from_the_key`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_ram_estimate_is_size_plus_ten_percent_and_sets_exclusive`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason[overrides0-path]`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason[overrides1-format]`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason[overrides2-architecture]`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_a_model_already_in_the_catalog_is_refused`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_no_free_port_is_refused`
    -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_add_api.py::test_add_puts_the_model_in_the_live_catalog_and_the_local_file`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_added_model_is_no_longer_newly_found`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_add_unknown_key_is_404_and_changes_nothing`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_add_unsynthesizable_is_422_with_the_reason`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_add_new_adds_every_synthesizable_new_model_on_distinct_ports`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_remove_deletes_a_local_entry_from_catalog_and_file`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_remove_refuses_config_entries_and_unknown_ids`
    -> `src/vortex/app.py`
* `tests/test_catalog_add_api.py::test_remove_refuses_a_loaded_local_entry`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_wire_schema_carries_all_discovered_model_fields`
    -> `src/vortex/discovery.py`
* `tests/test_ui_catalog_add.py::test_add_all_new_control_sits_with_the_discovered_models_scan`
    -> `src/vortex/ui.py`
* `tests/test_ui_catalog_add.py::test_add_all_new_confirms_then_posts`
    -> `src/vortex/ui.py`
* `tests/test_ui_catalog_add.py::test_add_all_reports_skips_and_failures`
    -> `src/vortex/ui.py`
* `tests/test_ui_catalog_add.py::test_each_new_discovered_model_gets_an_add_control`
    -> `src/vortex/ui.py`
* `tests/test_ui_catalog_add.py::test_local_entries_get_a_confirmed_remove_control`
    -> `src/vortex/ui.py`
* `tests/test_ui_catalog_add.py::test_successful_changes_refresh_both_lists`
    -> `src/vortex/ui.py`

## Task DAG

`src/vortex/discovery.py` depends on `src/vortex/catalog.py`
`src/vortex/catalog_synth.py` depends on `src/vortex/catalog.py`
`src/vortex/catalog_synth.py` depends on `src/vortex/discovery.py`
`src/vortex/app.py` depends on `src/vortex/catalog_synth.py`
`src/vortex/catalog_routes.py` depends on `src/vortex/catalog_synth.py`
`src/vortex/app.py` depends on `src/vortex/catalog_routes.py`

`src/vortex/ui.py` depends on nothing in this delta.

## v40 escalation response (T3, caps-exhausted)

T3 failed twice because the coder imported `vortex.models`, which does not
exist: neither this delta nor the EM's brief named the modules the types come
from. The EM's consult verdict (decomposition_wrong, citing the DAG) was
incorrect — T3 already depended on T1 and T2. The fix is spec-side: exact
import lines are now stated for catalog_synth.py and app.py above. Behavior,
acceptance criteria and tests are unchanged. catalog.py, discovery.py and
ui.py passed in v39 and are no-edit for this resume.

## v41 escalation response (T3, caps-exhausted again)

With the imports fixed (v40), T3 still failed: the coder built the entry dict
with keys such as `id` instead of the CatalogEntry field names `public_id`
and `port`, and the EM's revised brief did not correct it. The per-file detail
above described values, not the exact field names — a spec gap. v41 adds
verbatim coder briefs for every inventory file so the plan is synthesized
mechanically (no EM paraphrase). catalog.py, discovery.py and ui.py passed in
v39 and stay no-edit; their briefs say so. Behavior, criteria and tests are
unchanged.

## Coder briefs (verbatim)

### T1 — src/vortex/catalog.py (no change)

No change. This file passed its tests and is a no-edit file for this delta.

### T2 — src/vortex/discovery.py (no change)

No change. This file passed its tests and is a no-edit file for this delta.

### T3 — src/vortex/catalog_synth.py (no change)

No change. This file passed its tests and is a no-edit file for this delta.

### T5 — src/vortex/ui.py (no change)

No change. This file passed its tests and is a no-edit file for this delta.

### T6 — src/vortex/catalog_routes.py (catalog routes)

Create the new file with exactly this content:

    """Catalog add / add-new / remove routes."""
    from __future__ import annotations

    from collections.abc import Callable

    from fastapi import FastAPI, HTTPException

    from .catalog import Catalog
    from .catalog_synth import SynthesisError, synthesize_entry
    from . import discovery
    from .lifecycle import Lifecycle
    from .operations import OperationStore


    def register_catalog_routes(
        app: FastAPI, catalog: Catalog, lifecycle: Lifecycle, ops: OperationStore,
        fresh_models: Callable[[], list[discovery.DiscoveredModel]], persist: Callable[[], None],
    ) -> None:
        @app.post("/api/discovered-models/{key}/add", status_code=201)
        def add_model(key: str) -> dict:
            model = next((m for m in fresh_models() if m.key == key), None)
            if model is None:
                raise HTTPException(404, detail="unknown")
            try:
                entry = synthesize_entry(model, catalog)
            except SynthesisError as exc:
                raise HTTPException(422, detail={"message": str(exc), "key": key}) from exc
            catalog.add(entry)
            persist()
            return {"added": entry.model_dump(mode="json")}

        @app.post("/api/discovered-models/add-new")
        def add_new() -> dict:
            added: list[str] = []
            skipped: list[dict[str, str]] = []
            for m in [m for m in fresh_models() if not m.in_catalog]:
                try:
                    entry = synthesize_entry(m, catalog)
                except SynthesisError as exc:
                    skipped.append({"key": m.key, "reason": str(exc)})
                    continue
                catalog.add(entry)
                added.append(entry.public_id)
            persist()
            return {"added": added, "skipped": skipped}

        @app.delete("/api/catalog/{public_id}")
        def remove_model(public_id: str) -> dict:
            entry = catalog.by_public_id(public_id)
            if entry is None:
                raise HTTPException(404, detail="unknown")
            busy = lifecycle.occupying_pid(entry) is not None or ops.active_for(public_id)
            if entry.origin != "local" or busy:
                raise HTTPException(409, detail={"message": "config entry, or loaded/busy"})
            catalog.remove(public_id)
            persist()
            return {"removed": public_id}

Self-verify: ruff and mypy clean.

### T4 — src/vortex/app.py (register the routes)

Two edits in `src/vortex/app.py`; change nothing else.

1. Replace the line
       from .catalog_synth import SynthesisError, synthesize_entry
   with
       from .catalog_routes import register_catalog_routes

2. Immediately before the final line of `build_app`, which is
       return app
   insert (4-space indent, inside build_app):
       def _fresh_models() -> list:
           model_cache.clear()
           return _get_models()

       register_catalog_routes(app, catalog, lifecycle, ops, _fresh_models, _persist)

`model_cache`, `_get_models`, `_persist`, `catalog`, `lifecycle` and `ops`
already exist in that scope. Self-verify: ruff and mypy clean.

## v42 plan-gate fix

The v41 plan halted at the plan gate: the mapping above named the
parametrized family `test_unsynthesizable_models_raise_with_a_reason`
without its parameter ids, and the gate requires exact frozen node-ids. The
three parametrized node-ids are now pinned individually. Briefs, behavior and
tests are unchanged.

## v43 escalation response (T4, operator-review)

T4 (app.py) failed four times after its first attempt applied the imports,
signature and `_persist` but not the routes: every later reply was a `Read`
tool call instead of edit blocks — the coder does not reliably emit a large
multi-part edit into a long existing file, while it does write whole new
files (T3 passed that way). The routes now live in a NEW module,
`src/vortex/catalog_routes.py` (T6, written whole; acceptance is its smoke
check, since its behavior is only reachable once app.py registers it), and
app.py's remaining change is two small anchored edits (T4, which carries all
the API tests). The three route contracts are re-pinned to the new file.
Behavior, criteria and tests are unchanged.
