# ERD-DELTA v14 — vortex: engine-wrapper inventory (operator visibility)

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

## Changed acceptance criteria

New criteria introduced by this milestone (PRD v14):

- **AC-1:** `GET /api/engine-wrappers` lists every installed wrapper from
  the vetted registry, each carrying name, kind, installed (always true), binary_path,
  version, port, port_open, and in_catalog.
- **AC-2:** detection consults only the vetted registry (omlx, mtplx,
  ollama, lmstudio, llama-server, llama-cli, vllm, mlx-lm); nothing outside
  the registry is ever reported, and the new module has no third-party
  dependencies.
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

None. M1 behavior is unchanged; AC-1..AC-6 append to it. `manager.py` is
not touched.

## Changed files

- `src/vortex/discovery.py` — NEW. Vetted registry + read-only detection.
  Stdlib-only (os, re, enum, subprocess, socket, shutil, pathlib, typing)
  plus pydantic. Entry surface (locked):

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

    | name | kind | bin_names | known_paths | version_flags | port |
    |---|---|---|---|---|---|
    | omlx | cli | omlx | ~/.omlx/bin/omlx | --version | 8000 |
    | mtplx | cli | mtplx | ~/.mtplx/bin/mtplx | --version | 8001 |
    | ollama | cli | ollama | /usr/local/bin/ollama, /opt/homebrew/bin/ollama | --version | 11434 |
    | lmstudio | ui | lmstudio | /Applications/LM Studio.app/Contents/MacOS/LM Studio | --version | 1234 |
    | llama-server | cli | llama-server, llama-server.exe | /opt/homebrew/bin/llama-server | --version | 8080 |
    | llama-cli | cli | llama-cli, llama-cli.exe | /opt/homebrew/bin/llama-cli | --version | — |
    | vllm | cli | vllm | — | --version | 8000 |
    | mlx-lm | cli | mlx_lm | — | --version | — |

    Resolution rules (AC-2/AC-4):
    * binary: `shutil.which(name, path=search_path)` when search_path given,
      else `shutil.which(name)`; if unresolved, any `known_paths` entry whose
      expanded absolute path `is_file()` and is executable. Unknown → return
      Wrapper with installed False, no probe, no port check.
    * version: when resolved and `probe_version`, run
      `subprocess.run([bin, *flags], capture_output=True, text=True,
      timeout=3.0)`; version = first non-empty stdout line when returncode
      == 0, else None. Never any other subprocess.
    * port_open: effective port = `ports.get(name)` override else
      `spec.port`; None → False; else
      `socket.create_connection(("127.0.0.1", p), timeout=0.5)` success.
    * in_catalog: any `catalog_entries` entry e with
      `name in (e.runtime, e.engine)` or `e.launch_command[0].split()[0] == name`.
    * result order == WRAPPER_SPECS order; every vetted wrapper appears
      (installed False when unresolved).

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

New frozen files pin the v14 behavior:

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

Carried unchanged: every other node-id in `tests/test_serve.py`,
`tests/test_catalog.py`, `tests/test_ui_api_contract.py`,
`tests/test_ui_content.py`, `tests/test_ui_down.py`, `tests/test_cli.py`,
`tests/test_memory_figure.py`, `tests/test_anneal_retry.py`,
`tests/test_lifecycle_scan.py`.