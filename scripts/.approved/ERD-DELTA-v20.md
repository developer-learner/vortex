# ERD-DELTA v20 — restore B3 parsing (brief header + full pin map)

v20 is a doc-only errata. Behavioral delta: none. Test bytes: none changed.
Source bytes: none staged. Contract IDs, routes, entry_points, smoke_checks:
all carried from v19 unchanged. The one thing v20 fixes is the v19 errata's
own defect: v19 restored the four briefs but dropped the `## Coder briefs
(verbatim)` section header and the Test-to-file mapping pin table. Without
them, on a clean rebuild B3 refused synthesis ("no verbatim coder brief for
4 inventory file(s)") and the EM fallback failed the plan gate. v20 restores
both, so the mechanical B3 synthesizer emits the whole plan with no EM call.

The v18 errata restated only the T3 brief. That worked while task-state from
earlier runs stayed on disk, but on a clean rebuild
(`SWBP_REBUILD_FROM_SCRATCH=1`) the B3 aggregator can only see the latest
ERD-DELTA and refused synthesis with "no verbatim coder brief for 4
inventory file(s)". The EM full-emission fallback then failed the plan gate
with invalid JSON. B3 must not depend on transient state; v19 makes that
structural by carrying every brief here.

T1 and T2 briefs are carried byte-identical from v16. T3 brief is the v18
version (imports guidance kept). T4 brief is carried byte-identical from v16.

DAG (unchanged from v16): `src/vortex/app.py` depends on
`src/vortex/discovery.py`; `src/vortex/ui.py` depends on
`src/vortex/app.py`; `src/vortex/discovery.py` and `src/vortex/manager.py`
are roots.

## Changed acceptance criteria

None. v19 is doc-level errata: no PRD AC is added, removed, or reworded.
The AC block carried forward from v15/v16/v17/v18 (AC-1..AC-6) stays
immutable.

## Superseded acceptance criteria

None. The v18 T3 coder brief is carried; T1/T2/T4 v16 briefs are carried.

## Changed files

- `contracts.json` — `erd_version` bumps to 20. No contract entries change.
- `src/vortex/discovery.py`, `src/vortex/app.py`, `src/vortex/ui.py` —
  carried in `changed_files` for the coder to reach; source bytes unchanged.
- `src/vortex/manager.py` — still `no_edit_files`, still carrying the v17
  write-free smoke_check.

## Coder briefs (verbatim)

### T1 — src/vortex/manager.py (carried)

CARRIED NO-EDIT declaration for `src/vortex/manager.py`, which
`contracts.no_edit_files` freezes byte-identical. The orchestrate runner
never invokes the coder for this task; write nothing here, do not
reformat or refactor. Acceptance is the declared smoke check (the module
must continue to compile) plus the carried regression coverage the runner
routes itself. If any of that were ever to fail with the file untouched,
the diagnosis belongs to the frozen spec, never to an edit of this file.

### T2 — src/vortex/discovery.py (new)

CREATE `src/vortex/discovery.py`, stdlib-only plus pydantic. No third-party
import beyond pydantic (requests/httpx/psutil/mlx/torch/yaml forbidden by the
frozen suite).

Models (frozen):
class WrapperSpec(BaseModel): name: str; kind: Literal["cli","ui","runtime"]; bin_names: tuple[str,...]; known_paths: tuple[str,...]=(); version_flags: tuple[str,...]=("--version",); probe_version: bool=True; port: int|None=None
class Wrapper(BaseModel): name: str; kind: str; installed: bool; binary_path: str|None=None; version: str|None=None; port: int|None=None; port_open: bool=False; in_catalog: bool=False

WRAPPER_SPECS = fixed tuple of these 8 (row: bin_names; known_paths; kind; port):
1 omlx (omlx) (~/.omlx/bin/omlx) cli 8000
2 mtplx (mtplx) (~/.mtplx/bin/mtplx) cli 8001
3 ollama (ollama) (/usr/local/bin/ollama, /opt/homebrew/bin/ollama) cli 11434
4 lmstudio (lmstudio) (/Applications/LM Studio.app/Contents/MacOS/LM Studio) ui 1234 probe_version False
5 llama-server (llama-server) (/opt/homebrew/bin/llama-server) cli 8080
6 llama-cli (llama-cli) (/opt/homebrew/bin/llama-cli) cli none
7 vllm (vllm) () cli 8000
8 mlx-lm (mlx_lm.generate, mlx_lm.server) () cli none

bin_names exact, no .exe variants.
def discover_wrappers(search_path=None, catalog_entries=None, ports=None) -> one Wrapper per spec, in WRAPPER_SPECS order.
binary: first shutil.which(bin, path=search_path) over bin_names (path only when passed); else first known_paths entry where the expanded absolute path exists and is executable. Unresolved -> installed False, binary_path None, version None; probe/port/catalog skipped.
version: if installed and probe_version (never ui): subprocess.run([binary, *version_flags], capture_output=True, text=True, timeout=3.0); version = first non-empty stdout line when rc==0 else None. Only subprocess; probes concurrent.
port_open: port = ports.get(name) if ports given else spec.port; None -> False; else socket.create_connection(("127.0.0.1", port), timeout=0.5).
in_catalog: True when some catalog entry e has name in (e.runtime, e.engine) or os.path.basename(e.launch_command[0]) == name.
Type params: leave catalog_entries/ports untyped (or Sequence/Mapping);
never list/dict — mypy fails at the app.py call site.
Acceptance: mapped discovery tests pass; stdlib-only + pydantic; 8 wrappers in order; mlx-lm only via console-script names; ui never probed; only the bounded probe subprocess. Re-open and re-verify.

### T3 — src/vortex/app.py (edit)

EDIT the EXISTING `src/vortex/app.py` for the delta ONLY. Anchored
SEARCH/REPLACE blocks (D-59); change exactly what is named; do not alter any
carried route, handler, or startup behavior.

Imports (separate lines, isort order, ruff I001 green):
* `from collections.abc import Callable`
* `from .discovery import Wrapper, discover_wrappers`

Delta:
* build_app gains a 4th parameter `wrapper_discovery=None`; used is
  `discover_wrappers` when None, else the injected callable (tests inject a
  fake).
* Per-app scan cache of (timestamp, findings); serve cached when <=60s old;
  on miss compute `wrapper_discovery(catalog_entries=catalog.entries)` and
  store it.
* GET /api/engine-wrappers -> `{"wrappers": [...]}`; each item `dict(w)` for
  installed w; wrappers with installed False excluded. Fields = Wrapper's:
  name, kind, installed, binary_path, version, port, port_open, in_catalog.
* POST /api/engine-wrappers/discover clears the cache, runs the provider
  now, returns `{"wrappers": [...], "newly_found": the names of installed
  wrappers whose in_catalog is False}`.
* Keep sync/async style consistent; existing 2s poll unchanged (cache avoids
  rescan each tick).

Type-hint guidance (ruff F401/F821, mypy attr-defined):
* Simplest correct: `wrapper_discovery=None` with NO annotation — then drop
  the `Callable` import entirely and never reference `Callable`.
* If you annotate: a `Callable` returning a list of Wrapper; argument spec
  left as `...` (ellipsis) — called with keyword `catalog_entries`, not a
  positional Catalog, so parameterizing the arg list drifts from the call
  site.
* Cache typed as a dict mapping str to (float, list-of-Wrapper) tuples.
* Every added import must be used; every unused import removed.

Acceptance: GET lists only installed wrappers; POST forces fresh scan and
reports newly_found; injected fake honored; default is real discover_wrappers;
other endpoints byte-identical; mapped engine_wrappers_api tests pass; ruff
and mypy clean on the file. Re-open and confirm no carried line changed.

### T4 — src/vortex/ui.py (edit)

EDIT the EXISTING `src/vortex/ui.py` for the delta ONLY. Anchored
SEARCH/REPLACE blocks (D-59). Every existing element id, the down-page
overlay, and all existing pollers and click handlers stay byte-identical;
do not restate carried markup or JS.

Delta:
* HTML: add a section with id enginewrappers containing a heading with
  text Engine wrappers, a table with tbody id wrapperrows, a status span
  id wrapperstatus, and a button with attribute data-act equal to
  discover and text Discover.
* JS: function pollWrappers() fetches "/api/engine-wrappers"; on ok it
  renders one row per wrapper into wrapperrows with cells for w.name,
  w.kind, w.binary_path, w.version, w.port, a live/open indicator when
  w.port_open (such as a filled dot with a state class), and w.in_catalog
  text. Register setInterval(pollWrappers, POLL_MS) next to the existing
  pollers, reusing the existing POLL_MS value unchanged.
* Discover click: fetch("/api/engine-wrappers/discover", {"method":
  "POST"}); on ok re-render via pollWrappers and give rows whose name
  appears in the response's newly_found array the newly-found row-state
  class.
* Add the open-dot and newly-found styles where the existing inline
  styles live.

Acceptance: the new section, wrapperrows tbody, wrapperstatus span, and
Discover button exist; pollWrappers fetches the inventory endpoint; the
Discover control posts to the rescan endpoint; every existing id and
handler is byte-identical; the mapped UI tests pass. Re-open ui.py after
editing and confirm no carried element changed.

## Test-to-file mapping

Every frozen test node-id in the active range (the v11–v15 carried
regression plus the v14/v15 discovery/app/ui inventory tests) keeps its owning
task, so B3's synthesizer sees a pin for all 44 scope ids and never falls back
to the EM:

* `tests/test_discovery.py::test_registry_covers_the_named_wrappers`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_registry_entries_are_sane_and_ordered`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_finds_an_installed_binary_on_path`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_unresolved_wrappers_report_not_installed`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_version_probe_records_first_stdout_line`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_failed_version_probe_reports_empty`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_only_probe_subprocess_is_the_version_check`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_mlx_lm_resolves_only_its_console_script_names`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_shared_default_ports_report_the_port_not_the_process`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_in_catalog_matches_absolute_launch_path_by_basename`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_port_check_reports_open_and_closed`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_in_catalog_reflects_catalog_entries`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_discovery_module_is_stdlib_only`
    -> `src/vortex/discovery.py`

* `tests/test_engine_wrappers_api.py::test_get_lists_only_installed_wrappers`
    -> `src/vortex/app.py`
* `tests/test_engine_wrappers_api.py::test_wire_schema_carries_all_wrapper_fields`
    -> `src/vortex/app.py`
* `tests/test_engine_wrappers_api.py::test_discover_post_flags_newly_found`
    -> `src/vortex/app.py`
* `tests/test_engine_wrappers_api.py::test_build_app_defaults_to_real_discovery`
    -> `src/vortex/app.py`

* `tests/test_ui_engine_wrappers.py::test_ui_has_engine_wrappers_section`
    -> `src/vortex/ui.py`
* `tests/test_ui_engine_wrappers.py::test_ui_fetches_the_inventory_endpoint`
    -> `src/vortex/ui.py`
* `tests/test_ui_engine_wrappers.py::test_ui_renders_wrapper_fields_from_the_api`
    -> `src/vortex/ui.py`
* `tests/test_ui_engine_wrappers.py::test_discover_button_posts_to_rescan`
    -> `src/vortex/ui.py`
* `tests/test_ui_engine_wrappers.py::test_poll_wrappers_runs_on_the_existing_cadence`
    -> `src/vortex/ui.py`

* `tests/test_cli.py::test_main_returns_3_when_daemon_unreachable`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_status_no_models`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_status_with_loaded_models`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_models_table_marks_and_sort`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_load_conflict_returns_2`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_load_success_polls_to_ready`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_load_failure_returns_1`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_unload_success`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_unload_failure_returns_1`
    -> `src/vortex/manager.py`

* `tests/test_lifecycle_scan.py::test_scan_port_reports_unknown_on_transient_errors`
    -> `src/vortex/manager.py`
* `tests/test_lifecycle_scan.py::test_scan_port_clean_empty_returns_none`
    -> `src/vortex/manager.py`
* `tests/test_lifecycle_scan.py::test_scan_port_skips_access_denied_as_clean`
    -> `src/vortex/manager.py`

* `tests/test_anneal_retry.py::test_anneal_retries_a_transport_blip_and_succeeds`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_gives_up_after_bounded_attempts`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_does_not_retry_a_loading_503`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_still_rejects_a_completion_without_choices`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_bounds_are_bounded`
    -> `src/vortex/manager.py`

* `tests/test_memory_figure.py::test_activity_monitor_parse_matches_the_vm_stat_arithmetic`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_activity_monitor_missing_keys_report_zero`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_ram_used_prefers_vm_stat_and_names_it`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_psutil_fallback_is_labeled_never_silent`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_status_api_names_the_memory_source`
    -> `src/vortex/manager.py`

Carried unchanged: the two `tests/test_serve.py` regression node-ids stay
pinned to `src/vortex/manager.py` via the standing `contracts.json` test_mapping.
