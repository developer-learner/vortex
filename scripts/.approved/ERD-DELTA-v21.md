# ERD-DELTA v21 — extract the memory figure into src/vortex/memory.py

v21 is a module-cohesion refactor with no behavioral change. The five
memory-figure functions (`_activity_monitor_used_gb`, `_ram_used`,
`estimate_ram_used_gb`, `ram_used_source`, `estimate_ram_total_gb`) move
verbatim from `src/vortex/manager.py` into a new dedicated module
`src/vortex/memory.py`; `src/vortex/app.py` imports the three public
wrappers from the new module. The frozen `tests/test_memory_figure.py`
re-points its imports and monkeypatch targets from `vortex.manager` to
`vortex.memory` — same five node-ids, same assertions, same canned vm_stat
bytes (including the 16384 page-size header the arithmetic test pins). No
AC is added, removed, or reworded; no route, contract, or smoke check
changes. The manager keeps load/unload orchestration, eviction, and state
aggregation; the memory figure and its source label now live together in
one module.

## Changed acceptance criteria

None. This is a refactor freeze: no PRD AC is added, removed, or reworded.
The AC block carried forward from v15–v20 (AC-1..AC-6) stays immutable.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/memory.py` — NEW module owning the memory figure end to end:
  the vm_stat parse (page size read from vm_stat's own header), the
  named-source selection (vm_stat primary, psutil labeled fallback), the
  public wrappers the status API reports, and the psutil total.
- `src/vortex/manager.py` — the five memory-figure functions removed; the
  module keeps load/unload orchestration, eviction, and state aggregation.
- `src/vortex/app.py` — imports `estimate_ram_used_gb`,
  `estimate_ram_total_gb`, and `ram_used_source` from `vortex.memory`
  instead of `vortex.manager`.
- `tests/test_memory_figure.py` — imports and monkeypatch targets re-pointed
  to `vortex.memory`; node-ids, assertions, and canned input unchanged.

## Test-to-file mapping

The five memory-figure node-ids move their owning file from
`src/vortex/manager.py` to the new `src/vortex/memory.py`:

* `tests/test_memory_figure.py::test_activity_monitor_parse_matches_the_vm_stat_arithmetic`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_activity_monitor_missing_keys_report_zero`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_ram_used_prefers_vm_stat_and_names_it`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_psutil_fallback_is_labeled_never_silent`
    -> `src/vortex/memory.py`
* `tests/test_memory_figure.py::test_status_api_names_the_memory_source`
    -> `src/vortex/memory.py`

Carried unchanged: every other frozen node-id keeps its standing pin — the
two `tests/test_serve.py` ids via the standing `contracts.json`
test_mapping, and the discovery/app/ui/cli/lifecycle/anneal ids per the
v20 delta snapshot (`ERD-DELTA-v20.md`).
