# REFREEZE SCOPE — coverage floor + tri-state pin

**Status:** DRAFT — ready for a named TPM seat. D-139 inform-first: waits on CEO go.
**Prepared by:** coder seat (scope only — INV-1: the frozen tests themselves are
authored/installed by the TPM via `scripts/refreeze.sh`, never hand-edited).
**Date:** 2026-08-23 · **Base commit:** `91b86eb` (main, type-clean, 36 green)

## Why one pass closes two gaps

CI is red **only** on the coverage floor: **72.40% < 80%**. The drop is
legitimate: the tri-state scan fix (`c9b4fb7`) added ~130 lines of new
branches, and its 3 regression tests were correctly reverted for INV-1.
So the same refreeze pass that adds `cli.py` coverage (the 0% anchor)
should also pin the tri-state branches — one frozen-suite delta, one
manifest regeneration.

## Scope A — `src/modelmux/cli.py` (0% coverage, the floor anchor)

Thin argparse CLI over the daemon's HTTP API. All tests should
**monkeypatch `modelmux.cli.httpx.request`** (canned `httpx.Response`
objects / raised `httpx.ConnectError`) — no network, no live daemon.

Behaviors to pin (each ≈ one test):

1. **`main()` → rc 3** when the daemon is unreachable
   (`httpx.ConnectError` → `DaemonUnavailable` → stderr message, exit 3).
2. **`status`, no models** → prints `no models loaded`, rc 0.
3. **`status`, models loaded** → one line per model with
   id/runtime/engine/port/ram fields, rc 0.
4. **`models`** → table renders `●` for ready, `○` for
   loading/unloading, blank otherwise; sorted by `public_id`, rc 0.
5. **`load` 409** → prints `conflict: <detail>`, rc 2 (no polling).
6. **`load` success** → POST 202 → poll reaches `ready` → rc 0.
7. **`load` failure** → poll reaches non-ready terminal state → rc 1.
8. **`unload` success / failure** → rc 0 / rc 1.
9. **`_poll`** returns on first terminal state (loading/unloading loop
   exits; `time.sleep` monkeypatched to no-op).

## Scope B — tri-state scan branches, `src/vortex/lifecycle.py`

The 3 reverted draft tests are the starting point (valid as-is: the
module-level `SCAN_UNKNOWN` alias still exists after the `91b86eb`
enum conversion — `_ScanState.UNKNOWN`). Drafts appended below.

Optional hardening tests (TPM's call — they pin the fail-closed callers,
not just the scan):

10. **`owner_status` holds last status on `SCAN_UNKNOWN`** — no state flip,
    warning logged (the original flap class, asserted at the seam).
11. **`spawn` refuses on `SCAN_UNKNOWN`** — `PortConflictError` with
    `pid is None`, no process spawned, no sidecar written.
12. **`terminate` refuses on `SCAN_UNKNOWN`** — returns False, sidecar
    **not** dropped (the 409-cascade root cause).

## Draft input for the TPM (the 3 reverted tests, verbatim)

```python
def test_scan_port_reports_unknown_on_transient_errors(monkeypatch) -> None:
    """An incomplete scan (transient psutil errors) must report SCAN_UNKNOWN,
    never a false None — the 2026-08-18 flap class."""
    from vortex import lifecycle

    class _FlakyProc:
        def net_connections(self, kind=None):
            raise psutil.Error("transient syscall failure")

    monkeypatch.setattr(lifecycle.psutil, "process_iter", lambda attrs: iter([_FlakyProc()]))
    monkeypatch.setattr(lifecycle.time, "sleep", lambda s: None)
    assert lifecycle._scan_port(1) is lifecycle.SCAN_UNKNOWN


def test_scan_port_clean_empty_returns_none(monkeypatch) -> None:
    """A clean scan with no listener returns None (port truly free)."""
    from vortex import lifecycle

    class _QuietProc:
        def net_connections(self, kind=None):
            return []

    monkeypatch.setattr(lifecycle.psutil, "process_iter", lambda attrs: iter([_QuietProc()]))
    assert lifecycle._scan_port(1) is None


def test_scan_port_skips_access_denied_as_clean(monkeypatch) -> None:
    """AccessDenied on other users' processes is permanent on macOS and must
    not count as incompleteness (dozens of such processes on a dev box)."""
    from vortex import lifecycle

    class _ForeignProc:
        def net_connections(self, kind=None):
            raise psutil.AccessDenied(13, "operation not permitted")

    monkeypatch.setattr(lifecycle.psutil, "process_iter", lambda attrs: iter([_ForeignProc()]))
    assert lifecycle._scan_port(1) is None
```

(Tests 10–12 would follow the same monkeypatch pattern plus a
`Lifecycle`/`SidecarStore` fixture as in `tests/test_serve.py`.)

## Coverage math (estimate — TPM to confirm with `coverage report`)

- `cli.py`: ~90 executable lines at 0% → Scope A's 9 tests should take it
  to ~90%+ (every branch except the `__main__` guard).
- `lifecycle.py` new branches: the 3 scan tests cover the
  `_scan_port` retry/unknown/clean/AccessDenied paths; tests 10–12 cover
  the three caller guards. Existing 36 already cover the non-unknown
  spawn/terminate/owner_status paths.
- Target: project total **≥ 80%** (CI floor). If the estimate lands
  short, the cheapest additional yield is the `manager.py` eviction
  paths — out of scope here, note for a future freeze.

## Process / acceptance

1. CEO names the TPM seat (D-139 inform-first).
2. TPM authors the frozen tests from this scope + drafts.
3. Install via `scripts/refreeze.sh`; manifest re-pinned
   (`scripts/.approved/frozen-manifest`) — the phase-gate
   frozen-spec check must pass on the working tree.
4. Acceptance: full suite green (36 + new), `ruff check src/` clean,
   mypy clean, CI coverage ≥ 80% → CI fully green.