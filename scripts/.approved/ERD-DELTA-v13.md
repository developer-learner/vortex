# ERD-DELTA v13 — vortex product debt: named memory source + bounded anneal retry

Two hardening fixes from the combined blueprint TODO (vortex product debt,
both CEO-ordered direct with refreeze pairing):

1. **Memory figure — one named source.** `estimate_ram_used_gb()` blended two
   unlabeled bases behind one function: the Activity Monitor figure (vm_stat:
   wired+compressor+active+inactive+speculative pages, what `top` PhysMem
   shows) and a silent psutil-used fallback (~15GB lower on macOS). When
   vm_stat failed, `/api/status` flipped basis with no explanation — the
   2026-08-17 anomaly class. The figure now always carries its source:
   `/api/status` gains `ram_source` (`"vm_stat" | "psutil"`), and psutil
   remains only as the explicitly-labeled degraded path for hosts without
   vm_stat (Linux). Display-only: eviction math stays model-estimate-based
   and independent of this figure (2026-08-17 ruling).

2. **`_anneal_probe` — bounded retry for transport blips.** The D-174 anneal
   shipped as a single 5s shot; one transient connection reset the instant a
   listener comes up failed an otherwise-loaded model's readiness cycle.
   Exceptions now retry up to `ANNEAL_ATTEMPTS = 3` with a 0.5s gap. A non-200
   answer (503 Loading model) is the upstream speaking about WEIGHTS, not
   noise: it stays single-shot False, so the spawn loop's poll cadence still
   governs load waits exactly as before.

## Changed acceptance criteria

None. No AC ids are defined for M1 (the frozen suite is the binding
definition, D-54). Both changes are corrective hardening of existing
"ready" / status-report scope.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/manager.py` — EDIT. `estimate_ram_used_gb()` delegates to a new
  `_ram_used() -> tuple[float, str]` returning the figure WITH its source;
  new `ram_used_source()` exposes the label. No arithmetic changes.
- `src/vortex/app.py` — EDIT. `/api/status` adds `"ram_source"` to its
  payload (additive field; the dashboard reads a subset today).
- `src/vortex/lifecycle.py` — EDIT. `_anneal_probe` wraps its single httpx
  post in a bounded attempt loop over exceptions only; module constants
  `ANNEAL_ATTEMPTS = 3`, `ANNEAL_RETRY_DELAY_SECONDS = 0.5`.

## Test-to-file mapping

New frozen files pin both fixes:

* `tests/test_memory_figure.py::test_activity_monitor_parse_matches_the_vm_stat_arithmetic`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_activity_monitor_missing_keys_report_zero`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_ram_used_prefers_vm_stat_and_names_it`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_psutil_fallback_is_labeled_never_silent`
    -> `src/vortex/manager.py`
* `tests/test_memory_figure.py::test_status_api_names_the_memory_source`
    -> `src/vortex/app.py`
* `tests/test_anneal_retry.py::test_anneal_retries_a_transport_blip_and_succeeds`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_gives_up_after_bounded_attempts`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_does_not_retry_a_loading_503`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_still_rejects_a_completion_without_choices`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_bounds_are_bounded`
    -> `src/vortex/lifecycle.py`

Carried unchanged: every other node-id in `tests/test_serve.py`
(including both D-174 anneal regression tests — their chat-call counts are
preserved because a 503 answer never retries inside the probe),
`tests/test_catalog.py`, `tests/test_ui_*.py`, `tests/test_cli.py`,
`tests/test_lifecycle_scan.py`.
