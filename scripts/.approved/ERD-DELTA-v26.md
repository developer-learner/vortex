# ERD-DELTA v26 — dashboard errors persist until acted on

v26 fixes a regression in the dashboard failure-visibility behaviour. The UI
surfaced an operation failure and then wiped it a beat later: a routine
catalog poll's success path called `setError(null)`, clearing an error the
operator still needed to see. The error banner is now cleared only by a user
action or a completed operation — never by a routine background poll.

1. `pollCatalog()`'s success path no longer calls `setError(null)`, so a
   routine poll can no longer clobber a surfaced error.
2. A completed operation clears the banner explicitly: `pollOperation()` sets
   the message when the operation ends in `error` and clears it when it ends
   in `ready`/`unloaded`.
3. User actions (load/unload, discover) continue to clear the banner on
   initiation, exactly as before.

## Changed acceptance criteria

None. This re-freeze corrects a regression in the existing dashboard
failure-visibility behaviour without adding or changing a PRD acceptance
criterion.

## Superseded acceptance criteria

None. No prior acceptance criterion changes; a routine poll simply no longer
clears the operator-visible error surface.

## Changed files

- `src/vortex/ui.py` — the catalog poll success path no longer clears the
  error banner; a completed operation clears it instead, so an operation
  failure stays visible until the operator acts on it.
- `tests/test_ui_content.py` — adds a static contract test pinning that the
  catalog/wrapper poll success bodies never call `setError(null)`.

## Test-to-file mapping

* `tests/test_ui_content.py::test_routine_polls_do_not_clear_error_banner` (UPDATED)
    -> `src/vortex/ui.py`
