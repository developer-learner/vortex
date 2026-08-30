# ERD-DELTA v16 — vortex: engine-wrapper inventory (operator visibility)

Behavioral delta adding a read-only report of the LLM inference engine
wrappers installed on the host (oMLX, mtplx, ollama, LM Studio,
llama-server, llama-cli, vLLM, mlx-lm). This is the M1 follow-up the CEO
ordered: "a list shows up showing omlx, mtplx, lm studio, ollama or any
other installed - UI or command line based inference engine wrappers, plus
a discover button to discover anything installed but not currently listed
in the app."

The dashboard gains a second table; the management API gains two routes;
a new, stdlib-only discovery module owns the vetted registry and the
probing. Model loading is untouched: `src/vortex/manager.py` is carried
byte-identical (`no_edit_files`). Detection is strictly read-only — it
never launches, loads, or alters any wrapper; the only subprocess ever
spawned is a bounded version probe (≤3s).

v16 is the mechanical-lane freeze (doc-level): it fixes no v15 drift and
changes no test or source bytes — it adds the B3 wiring this milestone
needs to stop depending on the 4-bit EM's planning ability, so the v15
errors (plan-gate brief overcap; a phantom duplicate task) cannot recur.

## Mechanical plan (B3)

Orchestrate B3 — `validate-plan.py --synthesize-plan` over the active
delta range — emits the whole plan without any EM call when this freeze
carries everything it reads: a verbatim coder brief per inventory file
(the `## Coder briefs` section below) plus a task-order DAG plus an
ownership pin for every milestone node-id (the `## Test-to-file mapping`
section). The full plan gate then judges that plan exactly as it judges
an EM's, with one flight of checks: one task per inventory file, brief
size ≤2500 (Rule 8), acceptance signal per task, D-133 delta-only
restatement, acyclic `depends_on`.

DAG statement (explicit `depends on` edges; no other edges):

`src/vortex/app.py` depends on `src/vortex/discovery.py`
`src/vortex/ui.py` depends on `src/vortex/app.py`

Discovery (`src/vortex/discovery.py`) is new with no predecessors; it
provides `discover_wrappers`, which app's `build_app` consumes, so app
depends on it. The UI speaks only to the API routes app adds, so ui
depends on app. The carried manager (`src/vortex/manager.py`) is a root
task with no dependents and is depended on by nothing.

## Changed acceptance criteria

New criteria introduced by this milestone (PRD v16):

- **AC-1:** `GET /api/engine-wrappers` lists every installed wrapper from
  the vetted registry, each carrying name, kind, installed (always true), binary_path,
  version, port, port_open, and in_catalog.
- **AC-2:** detection consults only the vetted registry (omlx, mtplx,
  ollama, lmstudio, llama-server, llama-cli, vllm, mlx-lm); nothing outside
  the registry is ever reported, and the new module adds no third-party
  dependency beyond the vortex baseline (pydantic); everything else it
  imports comes from the standard library.
- **AC-3:** `POST /api/engine-wrappers/discover` forces a fresh scan and
  returns `newly_found` = installed wrappers referenced by no catalog
  entry.
- **AC-4:** discovery never launches, loads, or alters any wrapper; the only
  subprocess spawned is a bounded version probe (≤3s timeout); repeated
  inventory reads are served from a short-lived cache (≤60s).
- **AC-5:** the dashboard renders an "Engine wrappers" section showing
  kind, binary path, version, port with a live/open indication, and
  catalog status, refreshed on the existing poll cadence.
- **AC-6:** a Discover control on the dashboard calls
  `POST /api/engine-wrappers/discover` and marks installed wrappers absent
  from the vortex catalog.

## Superseded acceptance criteria

AC-2 wording consolidated (v14, applied v15): "no third-party dependencies"
clarified to "no third-party dependency beyond the vortex baseline
(pydantic); everything else from the standard library" — the discovery
module's pydantic import was already allow-listed in the frozen v14 tests;
this is a wording correction, not a behavioral change, so the standing PRD
AC block stays immutable.

Nothing else is superseded. M1 behavior is unchanged; AC-1..AC-6 append to
it. `manager.py` is not touched.

## Changed files

- `src/vortex/discovery.py` — NEW. Vetted registry + read-only detection.
  Stdlib-only (os, re, enum, subprocess, socket, shutil, pathlib, typing,
  concurrent.futures) plus pydantic. Entry surface (locked):

    ```python
    class WrapperSpec(BaseModel):            # frozen
        name: str
        kind: Literal["cli", "ui", "runtime"]
        bin_names: tuple[str, ...]
        known_paths: tuple[str, ...] = ()
        version_flags: tuple[str, ...] = ("--version",)
        probe_version: bool = True
        port: int | None = None

    class Wrapper(BaseModel):                # frozen
        name: str
        kind: str
        installed: bool
        binary_path: str | None = None
        version: str | None = None
        port: int | None = None
        port_open: bool = False
        in_catalog: bool = False

    WRAPPER_SPECS = the vetted registry: a fixed-order tuple of WrapperSpec
    entries (annotated above).

    def discover_wrappers(
        search_path: str | None = None,
        catalog_entries: Sequence[object] | None = None,
        ports: Mapping[str, int] | None = None,
    )

    `discover_wrappers` returns one `Wrapper` per vetted spec (the model is
    named `Wrapper`, annotated above), in registry order.

    Registry order and fields (deterministic, matches PRD AC-2):

    | name | kind | bin_names | known_paths | version_flags | probe_version | port |
    |---|---|---|---|---|---|---|
    | omlx | cli | omlx | ~/.omlx/bin/omlx | --version | yes | 8000 |
    | mtplx | cli | mtplx | ~/.mtplx/bin/mtplx | --version | yes | 8001 |
    | ollama | cli | ollama | /usr/local/bin/ollama, /opt/homebrew/bin/ollama | --version | yes | 11434 |
    | lmstudio | ui | lmstudio | /Applications/LM Studio.app/Contents/MacOS/LM Studio | () | no | 1234 |
    | llama-server | cli | llama-server | /opt/homebrew/bin/llama-server | --version | yes | 8080 |
    | llama-cli | cli | llama-cli | /opt/homebrew/bin/llama-cli | --version | yes | — |
    | vllm | cli | vllm | — | --version | yes | 8000 |
    | mlx-lm | cli | mlx_lm.generate, mlx_lm.server | — | --version | yes | — |

    Resolution rules (AC-2/AC-4):
    * binary: `shutil.which(name, path=search_path)` when search_path given,
      else `shutil.which(name)`; if unresolved, any `known_paths` entry whose
      expanded absolute path `is_file()` and is executable. Unknown → return
      Wrapper with installed False, no probe, no port check. Note `mlx-lm`
      installs console scripts named `mlx_lm.generate`/`mlx_lm.server` (there
      is no `mlx_lm` executable); a bare file named `mlx_lm` does not count.
    * version: when resolved and `probe_version` (never for kind "ui"),
      run `subprocess.run([bin, *flags], capture_output=True, text=True,
      timeout=3.0)`; version = first non-empty stdout line when returncode
      == 0, else None. Never any other subprocess. Probes for all resolved
      wrappers run concurrently (stdlib `concurrent.futures`, one worker per
      wrapper), so the worst-case scan is ≈ one probe timeout, not
      N × 3s.
    * port_open: effective port = `ports.get(name)` override else
      `spec.port`; None → False; else
      `socket.create_connection(("127.0.0.1", p), timeout=0.5)` success.
      `port_open` names the *port*, not the daemon process: omlx and vllm
      share the same default (8000), so with both installed and no `ports`
      override they intentionally report the same answer for the same port.
      Operators running both engines concurrently pass
      `ports={"omlx": 8000, "vllm": 8005}` to disambiguate.
    * in_catalog: any `catalog_entries` entry e with
      `name in (e.runtime, e.engine)` or
      `os.path.basename(e.launch_command[0]) == name`. The basename check
      (not `split()[0]`) matches absolute launch commands such as
      `/Users/arc.elixir/.mtplx/bin/mtplx` → `mtplx`; shell-script launchers
      whose basename is not the wrapper name are considered not in catalog.
    * result order == WRAPPER_SPECS order; every vetted wrapper appears
      (installed False when unresolved).

    EM planning note (claim scope for this milestone): a task's `contracts`
    array is the minimal claim set. The app-route task claims exactly
    `route:GET /api/engine-wrappers` and
    `route:POST /api/engine-wrappers/discover`; the discovery-module task
    claims the five `src.vortex.discovery:*` entry points; the ui task
    claims an EMPTY contracts array. The ids `src.vortex.app`,
    `src.vortex.app:build_app`, `src.vortex.ui`, and `src.vortex.ui:UI_PAGE`
    are CARRIED inputs — never claim them on any task; the plan gate rejects
    self-owned unchanged contracts.

- `src/vortex/app.py` — EDIT. `build_app` gains a fourth optional param,
  `wrapper_discovery=discover_wrappers` (defaults to the real function;
  tests inject a fake). Calls
  `wrapper_discovery(catalog_entries=catalog.entries)`. Two new routes:
  * `GET /api/engine-wrappers` → `{"wrappers": [ ...dict(w) for w in
    found if w.installed ]}`. Persisted per-app scan cache (TTL ≤60s) so
    the 2s dashboard poll does not rescan each tick.
  * `POST /api/engine-wrappers/discover` → force rescan (clears the cache,
    runs the provider now) → `{"wrappers": [...installed...],
    "newly_found": [w.name for installed w not in_catalog]}`.
  The installed-wrappers wire schema is exactly `Wrapper`'s fields: name,
  kind, installed, binary_path, version, port, port_open, in_catalog.
  No other endpoints change; manager untouched.

- `src/vortex/ui.py` — EDIT. New "Engine wrappers" section on the same
  dashboard page (id `enginewrappers`), a table `<tbody id="wrapperrows">`,
  a status line `#wrapperstatus`, and a Discover button
  `<button data-act="discover">Discover</button>`. JS (literals pinned by
  the frozen UI tests):
  * `pollWrappers()` calls `fetch("/api/engine-wrappers")` and renders one
    row per wrapper from `w.name`, `w.kind`, `w.binary_path`, `w.version`,
    `w.port`, `w.port_open` (open dot when true), and `w.in_catalog`;
    `setInterval(pollWrappers, POLL_MS)` alongside the existing pollers.
  * Discover click → `fetch("/api/engine-wrappers/discover", { method:
    "POST" })` → re-render; wrappers whose name appears in the response's
    `newly_found` get a `newly-found` marker row state.
  * Existing element ids (`ramlabel`, `ramfill`, `rows`, `conflict`,
    `conflictbody`, `down`), the down-page overlay, and all existing
    pollers/actions stay byte-identical.

## Test-to-file mapping

New frozen files pin the v16 behavior:

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
* `tests/test_discovery.py::test_port_check_reports_open_and_closed`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_in_catalog_reflects_catalog_entries`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_in_catalog_matches_absolute_launch_path_by_basename`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_mlx_lm_resolves_only_its_console_script_names`
    -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_shared_default_ports_report_the_port_not_the_process`
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

Carried regression in the active range (deltas v11–v13), pinned to the
no-edit manager task, which owns no source change here and carries these
through acceptance untouched:

* `tests/test_cli.py::test_load_conflict_returns_2`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_load_failure_returns_1`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_load_success_polls_to_ready`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_main_returns_3_when_daemon_unreachable`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_models_table_marks_and_sort`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_status_no_models`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_status_with_loaded_models`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_unload_failure_returns_1`
    -> `src/vortex/manager.py`
* `tests/test_cli.py::test_unload_success`
    -> `src/vortex/manager.py`
* `tests/test_lifecycle_scan.py::test_scan_port_clean_empty_returns_none`
    -> `src/vortex/manager.py`
* `tests/test_lifecycle_scan.py::test_scan_port_reports_unknown_on_transient_errors`
    -> `src/vortex/manager.py`
* `tests/test_lifecycle_scan.py::test_scan_port_skips_access_denied_as_clean`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_bounds_are_bounded`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_does_not_retry_a_loading_503`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_gives_up_after_bounded_attempts`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_retries_a_transport_blip_and_succeeds`
    -> `src/vortex/manager.py`
* `tests/test_anneal_retry.py::test_anneal_still_rejects_a_completion_without_choices`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_activity_monitor_missing_keys_report_zero`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_activity_monitor_parse_matches_the_vm_stat_arithmetic`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_psutil_fallback_is_labeled_never_silent`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_ram_used_prefers_vm_stat_and_names_it`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_status_api_names_the_memory_source`
    -> `src/vortex/manager.py`

Carried unchanged: every other node-id in `tests/test_serve.py`,
`tests/test_catalog.py`, `tests/test_ui_api_contract.py`,
`tests/test_ui_content.py`, `tests/test_ui_down.py`, `tests/test_cli.py`,
`tests/test_memory_figure.py`, `tests/test_anneal_retry.py`,
`tests/test_lifecycle_scan.py`.

## Coder briefs (verbatim)

Verbatim one-file coder briefs for the mechanical lane (B3). Each is a
self-contained Rule 8 brief (exact path, signatures, inputs/outputs,
acceptance, constraints first) that the plan validator transcribes
unchanged into a task; the coder sees the file and this brief, nothing
else about the milestone.

### T1 — src/vortex/manager.py (carried)

CARRIED NO-EDIT declaration for `src/vortex/manager.py`, which
`contracts.no_edit_files` freezes byte-identical. The orchestrate runner
never invokes the coder for this task; write nothing here, do not
reformat or refactor. Acceptance is the declared smoke check (the module
must continue to compile) plus the carried regression coverage the runner
routes itself. If any of that were ever to fail with the file untouched,
the diagnosis belongs to the frozen spec, never to an edit of this file.

### T2 — src/vortex/discovery.py (new)

CREATE `src/vortex/discovery.py`, stdlib-only. Allowed imports:
os, re, enum, socket, subprocess, shutil, pathlib, typing, collections,
datetime, functools, concurrent, __future__, pydantic; banned: requests,
httpx, psutil, fastapi, uvicorn, torch, mlx, fire, rich, yaml, tomli.

Models (frozen):
class WrapperSpec(BaseModel): name: str; kind: Literal["cli","ui","runtime"]; bin_names: tuple[str,...]; known_paths: tuple[str,...]=(); version_flags: tuple[str,...]=("--version",); probe_version: bool=True; port: int|None=None
class Wrapper(BaseModel): name: str; kind: str; installed: bool; binary_path: str|None=None; version: str|None=None; port: int|None=None; port_open: bool=False; in_catalog: bool=False

WRAPPER_SPECS = fixed tuple of these 8 (row: bin_names; known_paths;
kind; port):
1 omlx (omlx) (~/.omlx/bin/omlx) cli 8000
2 mtplx (mtplx) (~/.mtplx/bin/mtplx) cli 8001
3 ollama (ollama) (/usr/local/bin/ollama, /opt/homebrew/bin/ollama) cli 11434
4 lmstudio (lmstudio) (/Applications/LM Studio.app/Contents/MacOS/LM Studio) ui 1234 probe_version False
5 llama-server (llama-server) (/opt/homebrew/bin/llama-server) cli 8080
6 llama-cli (llama-cli) (/opt/homebrew/bin/llama-cli) cli none
7 vllm (vllm) () cli 8000
8 mlx-lm (mlx_lm.generate, mlx_lm.server) () cli none

bin_names exactly as written, no .exe variants.

def discover_wrappers(search_path=None, catalog_entries=None, ports=None):
one Wrapper per spec, in WRAPPER_SPECS order.
binary: first shutil.which(bin, path=search_path) over bin_names (path only
when that param passed); else first known_paths entry where the expanded
absolute path exists and is executable. Unresolved -> installed False,
binary_path None, version None; probe/port/catalog skipped.
version: if installed and probe_version (never for kind ui):
subprocess.run([binary, *version_flags], capture_output=True, text=True,
timeout=3.0); version = first non-empty stdout line when rc==0 else None.
Only subprocess allowed; probes run concurrently.
port_open: port = ports.get(name) if ports given else spec.port; None ->
False; else socket.create_connection(("127.0.0.1", port), timeout=0.5).
in_catalog: True when some catalog entry e has name in (e.runtime, e.engine)
or os.path.basename(e.launch_command[0]) == name.

Acceptance: mapped discovery tests pass; stdlib-only + pydantic; 8 wrappers
in order; mlx-lm via console-script names only; kind ui never probed; only
the bounded probe subprocess. Re-open and re-verify after writing.

### T3 — src/vortex/app.py (edit)

EDIT the EXISTING `src/vortex/app.py` for the delta ONLY. Emit anchored
SEARCH/REPLACE blocks (D-59) that change exactly what is named here; do
not restate, reformat, or alter any carried route, handler, or startup
behavior.

Delta:
* Import `discover_wrappers` from `src.vortex.discovery` (module level,
  matching the existing package import style).
* build_app gains a fourth parameter `wrapper_discovery=None`; the value
  used is `discover_wrappers` when None, else the injected callable is
  honored (tests inject a fake).
* A per-app scan cache storing (timestamp, findings); a cached read is
  served when ≤60s old; on miss compute
  `wrapper_discovery(catalog_entries=catalog.entries)` and store it.
* GET /api/engine-wrappers responds {"wrappers": [...]} where each item
  is dict(w) for installed w in the cached-else-fresh findings; wrappers
  with installed False are excluded. Wire schema is exactly Wrapper's
  fields: name, kind, installed, binary_path, version, port, port_open,
  in_catalog.
* POST /api/engine-wrappers/discover clears the cache, runs the provider
  now, and responds {"wrappers": [installed...], "newly_found": [w.name
  for installed w not in_catalog]}.
* Keep sync/async style consistent with the rest of app.py. The existing
  2s poll is unchanged; the cache exists so it does not rescan each tick.

Acceptance: GET lists only installed wrappers; POST forces a fresh scan
and reports newly_found; an injected fake provider is used when passed;
the default is the real discover_wrappers; every other endpoint responds
byte-identically to before; the mapped engine_wrappers_api tests pass.
Re-open the file after editing and confirm no carried line changed.

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