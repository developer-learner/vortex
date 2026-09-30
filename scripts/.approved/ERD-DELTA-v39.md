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
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason`
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

`src/vortex/ui.py` depends on nothing in this delta.
