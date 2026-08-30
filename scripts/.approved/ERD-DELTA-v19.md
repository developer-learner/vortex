# ERD-DELTA v19 — restate all 4 coder briefs so B3 always fires

v19 is a doc-only errata. Behavioral delta: none. Test bytes: none changed.
Source bytes: none staged. Contract IDs, routes, entry_points, smoke_checks:
all carried from v17/v18 unchanged. The one thing v19 changes is that all
four coder briefs are restated in this ERD-DELTA in full, so the mechanical
B3 synthesizer emits the whole plan without an EM call regardless of whether
prior task-state is present in `.pipeline-state/`.

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

- `contracts.json` — `erd_version` bumps to 19. No contract entries change.
- `src/vortex/discovery.py`, `src/vortex/app.py`, `src/vortex/ui.py` —
  carried in `changed_files` for the coder to reach; source bytes unchanged.
- `src/vortex/manager.py` — still `no_edit_files`, still carrying the v17
  write-free smoke_check.

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

Type parameters on discover_wrappers: leave catalog_entries and ports
untyped (Python-default), or annotate them as `Sequence` / `Mapping`
imports from `collections.abc` — do NOT tighten to `list` or `dict`; the
invariant collection types break mypy at the app.py call site where a
`list` of concrete CatalogEntry is passed as catalog_entries and is not a
subtype of `list` of object.

Acceptance: mapped discovery tests pass; stdlib-only + pydantic; 8 wrappers
in order; mlx-lm via console-script names only; kind ui never probed; only
the bounded probe subprocess. Re-open and re-verify after writing.

### T3 — src/vortex/app.py (edit)

EDIT the EXISTING `src/vortex/app.py` for the delta ONLY. Emit anchored
SEARCH/REPLACE blocks (D-59) that change exactly what is named here; do
not restate, reformat, or alter any carried route, handler, or startup
behavior.

Imports (add both; keep them on separate import lines; do NOT collapse
`Callable` into any `from .discovery import` line — `Callable` is a Python
standard-library abstract base class and lives in `collections.abc`, not in
this project's discovery module; and place both imports in isort-canonical
order within the existing import block so ruff I001 stays green):
* `from collections.abc import Callable`
* `from .discovery import Wrapper, discover_wrappers`

Delta:
* build_app gains a fourth parameter `wrapper_discovery=None`; the value
  used is `discover_wrappers` when None, else the injected callable is
  honored (tests inject a fake).
* A per-app scan cache storing (timestamp, findings); a cached read is
  served when the timestamp is at most 60 seconds old; on miss compute
  `wrapper_discovery(catalog_entries=catalog.entries)` and store it.
* GET /api/engine-wrappers responds with a body of the form
  `{"wrappers": ...}` where each item is `dict(w)` for installed w in
  the cached-else-fresh findings; wrappers with installed False are
  excluded. Wire schema is exactly Wrapper's fields: name, kind,
  installed, binary_path, version, port, port_open, in_catalog.
* POST /api/engine-wrappers/discover clears the cache, runs the provider
  now, and responds with a body of the form
  `{"wrappers": ..., "newly_found": ...}` where wrappers is the installed
  list and newly_found is the names of installed wrappers with
  in_catalog False.
* Keep sync/async style consistent with the rest of app.py. The existing
  2-second poll is unchanged; the cache exists so it does not rescan each
  tick.

Type-hint guidance (must satisfy ruff F401/F821 and mypy attr-defined):
* The simplest correct signature is `wrapper_discovery=None` with no type
  annotation on that parameter. That path removes the need for `Callable`
  entirely; if you take it, do NOT add the `from collections.abc import
  Callable` line above and do NOT reference `Callable` anywhere.
* If instead you keep a `Callable` annotation, the correct form is a
  `Callable` returning a list of Wrapper, with the argument spec left as
  `...` (ellipsis) — the callable is invoked with the keyword argument
  `catalog_entries`, not with a positional Catalog, so parameterizing the
  argument list will drift from the real call site.
* The scan cache should be typed as a dict mapping str keys to
  (float, list-of-Wrapper) tuples.
* Any import you add MUST be used somewhere in the file; any import you
  no longer need MUST be removed — ruff F401 fails the strike on unused
  imports.

Acceptance: GET lists only installed wrappers; POST forces a fresh scan
and reports newly_found; an injected fake provider is used when passed;
the default is the real discover_wrappers; every other endpoint responds
byte-identically to before; the mapped engine_wrappers_api tests pass;
ruff and mypy both clean on the file. Re-open the file after editing and
confirm no carried line changed and every import statement resolves.

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

Unchanged from v16/v17/v18. Every v14/v15/v16/v17/v18 frozen test node-id
keeps its owning task after the mechanical B3 synthesizer replans on v19.
