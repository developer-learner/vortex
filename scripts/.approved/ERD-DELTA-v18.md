## Mechanical plan (B3) — v18 T3 brief errata

v18 is a doc-only errata. Behavioral delta: none. Test bytes: none changed.
Source bytes: none staged. Contract IDs, routes, entry_points, smoke_checks:
all carried from v17 unchanged. The one thing v18 changes is the T3 coder
brief text below, so the B3 mechanical synthesizer re-emits T3's brief with
imports spelled out explicitly — the v16 brief left "where does Callable
come from?" implicit, and the 4-bit coder answered `from .discovery import
Callable` on both strikes of the original brief and both strikes of the EM's
revised brief, exhausting the escalation ladder at T3.

T1, T2, T4 briefs are carried from v16 unchanged and are not re-stated here;
the synthesizer picks up the latest brief per file across the active delta
range.

DAG (unchanged from v16): `src/vortex/app.py` depends on
`src/vortex/discovery.py`; `src/vortex/ui.py` depends on
`src/vortex/app.py`; `src/vortex/discovery.py` and `src/vortex/manager.py`
are roots.

## Changed acceptance criteria

None. v18 is doc-level errata: no PRD AC is added, removed, or reworded.
The AC block carried forward from v15/v16/v17 (AC-1..AC-6) stays immutable.

## Superseded acceptance criteria

None. The v16 T3 coder brief is superseded by the T3 brief below.

## Changed files

- `contracts.json` — `erd_version` bumps to 18. No contract entries change.
- `src/vortex/app.py`, `src/vortex/discovery.py`, `src/vortex/ui.py` — carried
  in `changed_files` for the coder to reach; source bytes unchanged from
  whatever the coder produced under v17 (T2 discovery.py is green; T3 app.py
  is red pending this brief update; T4 ui.py never started because T3
  blocked).
- `src/vortex/manager.py` — still `no_edit_files`, still carrying the v17
  write-free smoke_check.

### T3 — src/vortex/app.py (edit)

EDIT the EXISTING `src/vortex/app.py` for the delta ONLY. Emit anchored
SEARCH/REPLACE blocks (D-59) that change exactly what is named here; do
not restate, reformat, or alter any carried route, handler, or startup
behavior.

Imports (add both; keep them on separate import lines; do NOT collapse
`Callable` into any `from .discovery import` line — `Callable` is a Python
standard-library abstract base class and lives in `collections.abc`, not in
this project's discovery module):
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
  `{"wrappers": [...]}` where each item is `dict(w)` for installed w in
  the cached-else-fresh findings; wrappers with installed False are
  excluded. Wire schema is exactly Wrapper's fields: name, kind,
  installed, binary_path, version, port, port_open, in_catalog.
* POST /api/engine-wrappers/discover clears the cache, runs the provider
  now, and responds with a body of the form
  `{"wrappers": [installed...], "newly_found": [w.name for installed w not
  in_catalog]}`.
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

## Test-to-file mapping

Unchanged from v16/v17. Every v14/v15/v16/v17 frozen test node-id keeps
its owning task after the mechanical B3 synthesizer replans on v18.
