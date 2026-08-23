# ERD-DELTA v3 — vortex M1: operation-completion terminal states

Follow-up to v2. The dashboard's action progress-poll
(`pollOperation` in `src/vortex/ui.py`) stops on `op.state === "done"`, but
the management API never emits that value: a finished operation's `state` is
`"ready"` (load), `"unloaded"` (unload), or `"error"` — `"done"` is the op's
*phase*, not its state (`src/vortex/operations.py`). So after a successful
load or unload the 500 ms poll never terminates and never fires its immediate
catalog/status refresh; the table only catches up on the regular 2 s poll.

This is a corrective (non-additive) delta: no new criteria, endpoints, files,
or dependencies. It aligns the completion check to the real terminal states
and adds one frozen assertion pinning it.

## Changed acceptance criteria

None. No AC ids are defined for M1 (the frozen suite is the binding
definition, D-54). This delta corrects the implementation so the existing M1
"Action feedback" scope is actually met.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/ui.py` — EDIT (existing file; anchored SEARCH/REPLACE edit,
  D-59). In `pollOperation`, the completion test must treat the real terminal
  states as done. Change the single condition

      if (op.state === "done" || op.state === "error") {

  to

      if (op.state === "ready" || op.state === "unloaded" || op.state === "error") {

  Change nothing else: the `op.operation` handle, the 500 ms interval, the
  `clearInterval` cleanup, and the follow-up `pollCatalog()` / `pollStatus()`
  refresh all stay exactly as they are.

## Test-to-file mapping

New assertion in the existing contract test pins the terminal-state fix to
`src/vortex/ui.py`:

* `tests/test_ui_api_contract.py::test_ui_operation_completion_uses_real_terminal_states`
    -> `src/vortex/ui.py`

Carried unchanged: every other node-id in `tests/test_ui_api_contract.py`,
`tests/test_ui_content.py` -> `src/vortex/ui.py`; `tests/test_ui_route.py`
-> `src/vortex/app.py`; `tests/test_catalog.py` and `tests/test_serve.py`.

## Out of scope (still filed)

The conflict card (`s.conflict` read from `/api/status`, which never carries
it — real refusals are a 409 on the load POST) remains a separate follow-up;
this delta does not touch it.
