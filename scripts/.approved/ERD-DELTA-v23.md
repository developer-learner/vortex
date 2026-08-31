# ERD-DELTA v23 — p0 complete: async 202 contract, bounded operation store, catalog construction invariants, streaming status, CLI/dashboard failure bounding

v23 is a behavioral re-freeze landing the p0-complete branch on top of v22:
the load/unload endpoints become genuinely asynchronous (202 + operation id,
work in the background), the operation store gains bounded retention and
atomic snapshots, the catalog rejects invalid entries on every construction
path, and the streaming proxy, CLI, and dashboard stop swallowing failures.
Each is pinned by new or adapted frozen tests.

1. **Async 202 load/unload contract** (`src/vortex/manager.py`,
   `src/vortex/app.py`): `POST /api/models/{id}/load` and `.../unload` return
   `202 + {operation, model}` promptly and never block on the spawn/terminate.
   Preflight stays synchronous — unknown model 404, memory conflict 409
   (`required_gb`/`eviction_candidates`), port conflict 409 (including
   `SCAN_UNKNOWN` fail-closed and unidentified occupants, mirroring
   `Lifecycle.spawn`) — so refusals are immediate, not a 202 that later fails.
   The spawn/terminate continues in a daemon thread; success lands
   `ready:done` / `unloaded:done`, failure lands `error:failed` /
   `error:refused` on the operation. A spawn failure is therefore observable
   only via the operation, never as a 500 at POST time (the dead
   `SpawnError -> 500` route handler is removed). The synchronous
   `Manager.load()`/`unload()` remain for direct callers.
2. **Bounded, atomic operation store** (`src/vortex/operations.py`):
   `MAX_OPS = 100` / `RETENTION_SECONDS = 3600` retention — completed ops
   older than the window are expired and the registry is capped at `MAX_OPS`
   (oldest completed first) on every create, so a long-lived daemon cannot
   grow the registry without bound; in-flight ops (`loading`/`unloading`) are
   never pruned. `update()` returns a bool (an update on an unknown id is an
   observable no-op, not a silent swallow). `snapshot()` copies the fields
   under the lock, so poll-path readers never see a half-updated operation or
   write through the returned dict. `__len__` exposes the cap to tests/UI.
3. **Catalog construction invariants** (`src/vortex/catalog.py`):
   `CatalogEntry` validates `ready_url`/`chat_endpoint` as `http(s)://` URLs
   with a host, `ram_estimate_gb`/`ctx_size` as positive when set. `Catalog`
   rejects duplicate `public_id` and duplicate `port` via a `model_validator`,
   so the invariant holds on EVERY construction path (direct construction,
   `model_validate`, `load_catalog`) — not only via the post-hoc
   `assert_unique_*()` helpers (which remain).
4. **Streaming proxy preserves upstream status** (`src/vortex/app.py`,
   `tests/fake_server.py`): a streaming request whose upstream answers
   non-200 (e.g. 404 unknown model, 503 not-ready) returns that status and
   body immediately instead of opening a 200 `text/event-stream`; only a
   successful upstream opens the SSE relay. The fake server gains the
   streaming-failure surface the test drives.
5. **CLI failure bounding** (`src/modelmux/cli.py`): request timeouts,
   upstream HTTP errors, and malformed load/unload responses produce
   controlled one-line messages and the established exit codes (1 = operation
   failed, 2 = conflict, 3 = daemon unreachable) instead of tracebacks; the
   poll loop has a 310s deadline; `--no-wait` returns the operation id without
   polling.
6. **Dashboard failure visibility** (`src/vortex/ui.py`): the poll and action
   handlers (`pollCatalog`, `pollWrappers`, load/unload, discover) no longer
   end in empty catches — every failure writes a concrete message to a
   visible `#uierror` banner (`setError`), an operation that ends in
   `state=error` shows its `op.message`, and successful polls clear the
   banner.

## Changed acceptance criteria

None. The PRD AC block stays immutable; no PRD AC is added, removed, or
reworded. These are correctness and contract fixes to the load/unload
endpoints, operation store, catalog validation, streaming proxy, CLI, and
dashboard, pinned by the frozen tests below.

## Superseded acceptance criteria

None. Superseded TEST ASSERTIONS (not ACs):

- `test_catalog_rejects_duplicate_public_ids` /
  `test_catalog_rejects_duplicate_ports` previously constructed a
  duplicate-carrying `Catalog` and asserted the post-hoc
  `assert_unique_public_ids()` / `assert_unique_ports()` raised. With fix 3
  the construction itself raises, so the assertions now expect the
  `ValidationError`/`ValueError` at construction time (direct and
  `model_validate` paths). The helper methods remain and are unchanged.
- `test_proxy_non_streaming`, `test_proxy_streaming_passthrough`,
  `test_unload_terminates_child`, and `test_load_conflict_reports_eviction`
  previously relied on `POST /load` blocking until ready (synchronous
  semantics) before using the model. With fix 1 the POST returns a 202
  immediately, so these tests now poll the returned operation to its
  terminal state (`_wait_state`) before exercising the model — the same
  pattern the alias-remap tests already use. `test_load_conflict_reports_eviction`
  additionally gives m2 its own port (the catalog now rejects duplicate
  ports at construction) and a launch command that binds that port, so a
  wrongly-granted admission fails the test fast instead of blocking on the
  ready timeout.
- `tests/test_ui_api_contract.py` fixture: the synthetic `CatalogEntry`
  now carries scheme-carrying `http://` URLs, required by fix 3 (the proxy
  needs a scheme to forward; the test's intent is the dashboard ⇄ API field
  contract, not URL format).

## Changed files

- `src/vortex/manager.py` — `load_async()` / `unload_async()` (synchronous
  preflight, then 202 + background worker); synchronous `load()`/`unload()`
  retained.
- `src/vortex/app.py` — load/unload routes call the async variants; dead
  `SpawnError -> 500` handler removed; streaming path opens the SSE relay
  only for a successful upstream and otherwise returns the upstream status
  and body.
- `src/vortex/operations.py` — `MAX_OPS`/`RETENTION_SECONDS`, `_prune()` on
  create, `update() -> bool`, atomic `snapshot()`, `__len__`.
- `src/vortex/catalog.py` — URL/ram/ctx field validators on
  `CatalogEntry`; duplicate id/port `model_validator` on `Catalog`.
- `src/modelmux/cli.py` — controlled timeout/HTTP/malformed handling, 310s
  poll deadline, `--no-wait`.
- `src/vortex/ui.py` — `#uierror` banner + `setError()`; every poll/action
  failure path writes an operator-visible message; success clears it.
- `tests/test_serve.py` — two new tests (`test_load_returns_before_ready`,
  `test_failed_load_reaches_error_operation`), one new streaming test
  (`test_streaming_preserves_upstream_error_status`), four tests adapted to
  the 202 contract (see superseded assertions).
- `tests/test_catalog.py` — three new validator tests; two duplicate tests
  adapted to construction-time rejection.
- `tests/test_operations.py` — NEW: six tests for the operation-store
  invariants (observable no-op, atomic snapshot, retention cap, retention
  expiry, in-flight never pruned).
- `tests/test_cli.py` — five new tests for bounded/normalized CLI failure
  behavior.
- `tests/test_ui_content.py` — one new test
  (`test_dashboard_surfaces_fetch_failures`).
- `tests/test_ui_api_contract.py` — fixture URLs gain a scheme (test
  functions unchanged).
- `tests/fake_server.py` — streaming-failure surface for the streaming
  status test.

## Test-to-file mapping

* `tests/test_serve.py::test_load_returns_before_ready`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_failed_load_reaches_error_operation`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_streaming_preserves_upstream_error_status`
    -> `src/vortex/app.py`
* `tests/test_serve.py::test_proxy_non_streaming`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_proxy_streaming_passthrough`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_unload_terminates_child`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_load_conflict_reports_eviction`
    -> `src/vortex/manager.py`
* `tests/test_catalog.py::test_catalog_rejects_non_http_url`
    -> `src/vortex/catalog.py`
* `tests/test_catalog.py::test_catalog_rejects_nonpositive_ram`
    -> `src/vortex/catalog.py`
* `tests/test_catalog.py::test_catalog_rejects_nonpositive_ctx`
    -> `src/vortex/catalog.py`
* `tests/test_catalog.py::test_catalog_rejects_duplicate_public_ids`
    -> `src/vortex/catalog.py`
* `tests/test_catalog.py::test_catalog_rejects_duplicate_ports`
    -> `src/vortex/catalog.py`
* `tests/test_operations.py::test_update_missing_op_returns_false`
    -> `src/vortex/operations.py`
* `tests/test_operations.py::test_update_present_op_returns_true`
    -> `src/vortex/operations.py`
* `tests/test_operations.py::test_snapshot_is_a_copy`
    -> `src/vortex/operations.py`
* `tests/test_operations.py::test_retention_caps_total_ops`
    -> `src/vortex/operations.py`
* `tests/test_operations.py::test_retention_expires_old_completed_ops`
    -> `src/vortex/operations.py`
* `tests/test_operations.py::test_retention_never_prunes_in_flight_ops`
    -> `src/vortex/operations.py`
* `tests/test_cli.py::test_request_timeout_is_controlled_not_traceback`
    -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_http_error_status_is_controlled`
    -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_malformed_load_response_is_controlled`
    -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_poll_has_a_deadline`
    -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_load_no_wait_skips_polling`
    -> `src/modelmux/cli.py`
* `tests/test_ui_content.py::test_dashboard_surfaces_fetch_failures`
    -> `src/vortex/ui.py`

Carried unchanged: every other frozen node-id keeps its standing pin — the
discovery/app/ui/cli/lifecycle/anneal/memory-figure ids per the v20/v21/v22
delta snapshots (`ERD-DELTA-v20.md`, `ERD-DELTA-v21.md`,
`ERD-DELTA-v22.md`) and the standing `contracts.json` test_mapping.
