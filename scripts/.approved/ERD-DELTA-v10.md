# ERD-DELTA v10 — idempotent load skips self-eviction

On constrained-memory hosts, loading a model that is already serving can
return 409 because `eviction_required` includes that same model in both used
RAM and eviction candidates. An idempotent load consumes no additional RAM and
must continue through the existing lifecycle adoption path. Loading a
different oversized model must still report the serving model as an eviction
candidate. No API shape, dependency, or file is added.

## Changed acceptance criteria

- Loading an already-ready catalog entry succeeds instead of conflicting with
  itself, independent of host RAM size.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/manager.py` — exclude the requested entry from memory-conflict
  evaluation when it is already in the ready set.

## Test-to-file mapping

- `tests/test_serve.py::test_load_conflict_reports_eviction`
  -> `src/vortex/manager.py`
- `tests/test_serve.py::test_adopt_surviving_runtime_and_load`
  -> `src/vortex/manager.py`

## Coder briefs (verbatim)

### T1 — src/vortex/manager.py (idempotent-load correction)

File: `src/vortex/manager.py`. Use one anchored SEARCH/REPLACE edit in
`Manager.eviction_required`. After collecting `loaded = self.all_ready()`, if
the requested `entry` is already present in `loaded`, return an empty conflict
list immediately because an idempotent adoption consumes no additional RAM.
Keep the existing RAM calculation and eviction candidates unchanged for every
other requested model. Change no API shapes, operation states, imports,
logging, or unrelated methods. Verify
`tests/test_serve.py::test_load_conflict_reports_eviction` and
`tests/test_serve.py::test_adopt_surviving_runtime_and_load` pass in the VM.

## Task DAG

Task order: T1 (`src/vortex/manager.py`).
