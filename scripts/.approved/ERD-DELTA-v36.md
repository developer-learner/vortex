# ERD-DELTA v36 — fail-safe admission under uncertain occupancy (T1)

Freeze context: standing spec v35 (discovery frozen-test corrections).
`Manager.all_ready()` is the admission set and counts only ports owned by a
process Vortex identifies. A port held by an unidentified process, or whose
scan was incomplete (`SCAN_UNKNOWN`), was left out, so admission could
overcommit RAM. Policy: option 2 of `tasks/T1-admission-decision.md` — count
the catalog estimate of such entries.

## Design

- New `Manager.uncertain_entries(entry)`: other catalog entries (never the
  target, never one already in `all_ready()`) whose `occupying_pid` is
  `SCAN_UNKNOWN`, or is a pid whose `owner_status` is not `"ready"`. An entry
  with no process on its port (`occupying_pid` is None) is NOT uncertain — the
  decision note's sketch (`owner_status != "ready"`) would have counted every
  unloaded model; this design does not.
- New `Manager.admits(entry)`: the budget check that `eviction_required` used
  to do inline, now counting loaded plus uncertain estimates.
- `eviction_required` keeps its contract (identified loaded entries, or [])
  but delegates the fit decision to `admits`, so uncertain entries are never
  eviction candidates.
- `load()` refuses with `MemoryConflict` whenever `admits` is False — also
  when nothing is evictable, which previously slipped through as "no
  conflict". `MemoryConflict` gains an optional `uncertain` list and a
  message for the nothing-evictable case. The 409 detail shape in `app.py` is
  unchanged (`message`, `required_gb`, `eviction_candidates`).

## Changed acceptance criteria

- AC-12 (new): an uncertain neighbour's estimate is counted, such that a load
  that only fits by ignoring it is refused and no operation starts.
- AC-13 (new): uncertain entries are never eviction candidates, such that
  `eviction_required` lists only identified loaded entries.
- AC-14 (new): identified runtimes (verified or not) still count, such that
  an over-subscribing load is refused with them as candidates.
- AC-15 (new): unloaded entries are never counted, such that a fitting load
  is admitted.
- AC-16 (new): an uncertain entry held as ready counts once and the target
  never counts against itself, such that a load fitting under single counting
  is admitted.
- AC-17 (new): a refusal with nothing evictable names the unidentified
  holders, such that the refusal explains itself.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/manager.py` (UPDATED): `uncertain_entries`, `admits`,
  `eviction_required` delegation, `load()` refusal, `MemoryConflict`
  `uncertain` parameter and message.
- `tests/test_admission_uncertain.py` (new): nine deterministic oracles with a
  fake lifecycle and host RAM pinned to 100 GB (budget 80 GB).

## Coder briefs (verbatim)

### T1 — src/vortex/manager.py (fail-safe admission)

1. `MemoryConflict.__init__` gains a third parameter `uncertain: list[str] | None = None`; store `self.uncertain = uncertain or []`. When `candidates` is non-empty keep the existing message. When it is empty use: `f"loading needs {total_required}; not enough memory is free and nothing loaded can be evicted — held by a process Vortex cannot identify: {', '.join(self.uncertain)}"`.
2. After `eviction_required`, add a method `uncertain_entries(self, entry: CatalogEntry)` that returns a list of `CatalogEntry` (annotate it with the same `list` of `CatalogEntry` form the file uses elsewhere). Collect `loaded_ids = {e.public_id for e in self.all_ready()}`. For each `e` in `self.catalog.entries`, skip it when `e.public_id == entry.public_id` or `e.public_id in loaded_ids`; otherwise `pid = self.lifecycle.occupying_pid(e)` and include `e` when `pid is SCAN_UNKNOWN`, or when `pid is not None and self.lifecycle.owner_status(e, pid) != "ready"`. Return the list.
3. Add `def admits(self, entry: CatalogEntry) -> bool:`. Return True when `entry.ram_estimate_gb is None` or `not entry.exclusive`, or when `entry` is already in `self.all_ready()` (same `public_id`). Otherwise `used` = sum of `(e.ram_estimate_gb or 0)` over `self.all_ready()` plus the same sum over `self.uncertain_entries(entry)`; `available = max(0.0, psutil.virtual_memory().total / (1024**3) * 0.8 - used)`; return `entry.ram_estimate_gb <= available`.
4. Change the body of `eviction_required` after its first guard to: `loaded = self.all_ready()`; `if self.admits(entry): return []`; `return loaded`.
5. In `load()`, replace the block `conflicts = self.eviction_required(entry)` / `if conflicts: raise MemoryConflict(...)` with: `if not self.admits(entry): raise MemoryConflict(entry.ram_estimate_gb, [e.public_id for e in self.eviction_required(entry)], [e.public_id for e in self.uncertain_entries(entry)])`.

Self-verify: with one other entry on `SCAN_UNKNOWN` holding 50 GB of an 80 GB budget, `admits` on a 40 GB target is False and `load` raises `MemoryConflict` with `candidates == []`; with that entry simply unloaded, `admits` is True.

## Task DAG

Task order: T1 (manager)

`src/vortex/manager.py` is the single task.

## Test-to-file mapping

* `tests/test_admission_uncertain.py::test_scan_unknown_neighbour_counts_and_refuses_the_load`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_unidentified_occupant_counts_and_refuses_the_load`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_uncertain_entry_is_not_an_eviction_candidate`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_unloaded_entries_do_not_count`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_scan_unknown_entry_held_ready_is_counted_once`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_target_is_never_counted_against_itself`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_refusal_without_candidates_names_the_unidentified_process`
  -> `src/vortex/manager.py`
