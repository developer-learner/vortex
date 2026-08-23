# ERD-DELTA v11 — regression pin for the tri-state port scan

This freeze adds no behavior. It pins the tri-state port-scan contract that
shipped in `71f8d9f`/`c9b4fb7` (the 2026-08-18 flap anomaly fix): `_scan_port`
must return a found pid, a CLEAN empty result (`None`), or `SCAN_UNKNOWN` when
the scan could not be completed — and must NOT count a permanent `AccessDenied`
on another user's process as incompleteness. Nothing guarded these branches
against regression; a future edit could silently reintroduce the false-`None`
that drove the sidecar-drop -> 409 cascade. No API shape, dependency, contract
entry, or src file is added or changed.

## Changed acceptance criteria

None. This freeze introduces regression tests only; the behavior they pin was
accepted in the M1 dashboard/lifecycle work already shipped on `main`.

## Superseded acceptance criteria

None.

## Changed files

None. No `src/` file changes in this freeze — the tests pin behavior already
present in `src/vortex/lifecycle.py` as of `c9b4fb7`. There is no coder task
and no task DAG: the staged tests pass against the current tree.

## Test-to-file mapping

* `tests/test_lifecycle_scan.py::test_scan_port_reports_unknown_on_transient_errors`
  -> `src/vortex/lifecycle.py`
* `tests/test_lifecycle_scan.py::test_scan_port_clean_empty_returns_none`
  -> `src/vortex/lifecycle.py`
* `tests/test_lifecycle_scan.py::test_scan_port_skips_access_denied_as_clean`
  -> `src/vortex/lifecycle.py`
