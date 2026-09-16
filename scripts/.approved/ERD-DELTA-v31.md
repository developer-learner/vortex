# ERD-DELTA v31 — RAM display parity with testchat

The dashboard's memory figure is brought to exact parity with testchat's,
CEO-ordered (2026-09-15) direct with refreeze pairing (D-175 routing; the
v30 pairing precedent). Three corrections, all to the displayed memory
surface — no new routes, schemas, or ACs.

1. **Used figure = working set only.** `_activity_monitor_used_gb()` summed
   `active + inactive + speculative + wired + compressor`, which counted
   reclaimable file cache (inactive + speculative — tens of GB) as "used"
   and reported ~114 GB where testchat reported ~65 GB. It now sums
   `active + wired + compressor` only — the same page set testchat's
   `_ram_totals` uses and the figure macOS Activity Monitor's "Memory Used"
   actually tracks. **This supersedes the 2026-08-17 memory-figure ruling**,
   whose rationale ("match Activity Monitor") in fact picked the wrong page
   set: Activity Monitor does not count inactive/speculative cache.

2. **Per-model live RSS.** A new `memory.model_rss_gb(pid)` returns a loaded
   model process's resident set size in GB (via `ps -o rss=`), 0.0 when the
   pid is unknown. `/api/status` now carries `rss_gb` on each `loaded` entry,
   computed from `lifecycle.occupying_pid`. The dashboard shows it beside
   each model (testchat's "nemotron 43.1 GB").

3. **Loadable figure.** A new `memory.loadable_gb()` returns the memory still
   available for another model load — reclaimable pages bounded by the GPU
   wired limit (`iogpu.wired_limit_mb`, else 75% of total) minus a 4 GB
   buffer — mirroring testchat's `_loadable_gb`. `/api/status` now carries
   `loadable_gb`; the dashboard shows it (testchat's "~44.3 GB loadable").

## Changed acceptance criteria

None. No AC ids are defined (the frozen suite is the binding definition,
D-54). All three changes are corrective/additive to the existing memory
display scope.

## Superseded acceptance criteria

None. (The 2026-08-17 memory-figure ruling superseded here is an operating
decision recorded in `memory.py`, not an AC.)

## Changed files

- `src/vortex/memory.py` — EDIT. `_activity_monitor_used_gb()` drops
  `Pages inactive` + `Pages speculative` from the summed keys; adds
  `model_rss_gb(pid)` and `loadable_gb()`.
- `src/vortex/app.py` — EDIT. `/api/status` (`status_view`) adds top-level
  `loadable_gb` and per-`loaded`-entry `rss_gb`; imports `model_rss_gb`,
  `loadable_gb` from `.memory`.
- `src/vortex/ui.py` — EDIT. A `#ramdetail` span; `pollStatus` calls a new
  `setRamDetail(loadable, loaded)` that renders each loaded model's `rss_gb`
  and the `loadable_gb` figure.

## Test-to-file mapping

Two families (`test_activity_monitor_parse...`, `test_status_api_names...`)
are already frozen in `test-nodeids` and are pinned in `contracts.test_mapping`;
the remaining added/modified functions are pinned here (the freeze pin gate
accepts this section). All are unmapped for delta-orchestration — D-175 direct
route needs no coder task to gate.

* `tests/test_memory_figure.py::test_activity_monitor_parse_matches_the_vm_stat_arithmetic`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_used_figure_excludes_reclaimable_cache`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_activity_monitor_missing_keys_report_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_model_rss_gb_reads_ps_output`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_model_rss_gb_none_pid_is_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_model_rss_gb_unreadable_is_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_loadable_gb_bounds_reclaimable_by_wired_limit`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_loadable_gb_failure_reports_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_status_api_carries_memory_source_and_parity_figures`
    -> `src/vortex/app.py`
* `tests/test_memory_figure.py::test_status_api_names_the_memory_source`
    -> `src/vortex/app.py`
* `tests/test_ui_content.py::test_ram_detail_parity_elements_present`
    -> `src/vortex/ui.py`

## Coder briefs (verbatim)

None — direct route (D-175): the implementation is already landed in the
working tree; this freeze re-freezes the test suite to the parity behavior.
Pairs with the fix commit that follows.
