# ERD-DELTA v45 — Speed page: measure every catalog model on demand

v45 adds a Speed page and its API. Four new modules keep each concern small
(measurement, the run, the HTTP surface, the page); `app.py` only wires them
and `ui.py` only gains a header link. The behavior is fixed here and by the
frozen tests; how each module is written is the coder's choice. A
look-and-feel mockup lives at `examples/speed-mockup/index.html` (dummy data,
not normative; where it differs from this ERD, this ERD wins).

## Changed acceptance criteria

New criteria introduced by this milestone (PRD v45): AC-38, AC-39, AC-40,
AC-41, AC-42, AC-43, AC-44, AC-45, AC-46, AC-47, AC-48. No existing criterion
changes.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/speedtest.py` — NEW. Measurement and the results file.
- `src/vortex/speed_runner.py` — NEW. `SpeedRun`: one run of up to 3 models.
- `src/vortex/speed_routes.py` — NEW. `register_speed_routes`: the HTTP surface.
- `src/vortex/speed_ui.py` — NEW. `SPEED_PAGE`: the page.
- `src/vortex/app.py` — EDIT. One keyword parameter and one registration call.
- `src/vortex/ui.py` — EDIT. One header link.

## Per-file behavioral detail

### src/vortex/speedtest.py (NEW; stdlib + httpx only)

Public names: `PROMPT` (a fixed one-sentence coding request), `MAX_TOKENS = 256`,
`CONCURRENCY = 4`, `SpeedTestError(Exception)`,
`measure(endpoint: str, model: str) -> dict[str, float]`,
`load_results(path: Path) -> dict[str, dict]`,
`save_result(path: Path, public_id: str, result: dict[str, float]) -> dict[str, float | str]`
(the stored record is the result's floats plus the `tested_at` string, so
type it `dict[str, float | str]` — a copy of `result` typed `dict[str, float]`
fails mypy when `tested_at` is added).

`measure` POSTs OpenAI chat-completion bodies to `endpoint`:
`{"model": model, "messages": [{"role": "user", "content": PROMPT}],
"max_tokens": N, "temperature": 0, "stream": false}` — first N=1 (its wall
time is `first_token_s`), then N=MAX_TOKENS (`single_tps` = its
`usage.completion_tokens` / its wall seconds), then CONCURRENCY requests of
N=MAX_TOKENS at the same time (threads; `multi_tps` = their summed
completion tokens / wall seconds from first start to last finish). Round
tps to 1 decimal, `first_token_s` to 3. Use a long per-request timeout
(600 s). Connection errors, non-200 replies, and replies without an integer
`usage.completion_tokens` raise `SpeedTestError` with a short reason (the
missing-count reason mentions "token").

`load_results` returns `{}` when the file is missing, not JSON, or not a JSON
object. `save_result` adds `tested_at` (local time from a timezone-aware
clock, "%Y-%m-%d %H:%M" — the project lint rejects a naive
`datetime.now()`, DTZ005) to the result, stores it under `public_id` keeping every other model's entry,
creates parent directories, writes JSON, and returns the stored record.

### src/vortex/speed_runner.py (NEW)

`SpeedRunBusy(Exception)`; `SpeedRun(catalog, manager, ops, results_path)`
with `start(model_ids: list[str]) -> None`, property `running: bool`, and
`rows() -> dict[str, dict]`: latest run's id → `{"status", "message"}`
(`{}` before any run).

`start`: `ValueError` unless 1–3 distinct ids all in
`catalog.by_public_id`; `SpeedRunBusy` if running. Else marks each
"queued", sets `running` True before returning, and tests the models in
order on a thread; `running` goes False after the last, whatever happened.

Per model (statuses queued, loading, testing, unloading, done, skipped,
failed). Serving (`manager.entry_state(entry, ops.active_for(id)) ==
"ready"`): test, leave loaded. Else `not manager.admits(entry)` → skipped
"won't fit (needs <ram_estimate_gb> GB)", never loaded. Else
`manager.load(id)` → `{"operation": op_id}`, then poll
`ops.snapshot(op_id)["state"]` until "ready" or "error" (error → failed
with its "message"); `MemoryConflict` → skipped "won't fit…";
`BusyError`, `PortConflictError`, `LookupError` → failed. Test:
`speedtest.measure(entry.chat_endpoint, entry.upstream_alias or
entry.public_id)`, then `save_result`; `SpeedTestError` → failed. A model
this run loaded is unloaded afterwards (`manager.unload(id)`, poll to
"unloaded"/"error"), also after a failed test; success then ends "done",
message "unloaded again". Any other exception: failed, run continues (the
catch-all needs `# noqa: BLE001` with a reason). Imports:
`MemoryConflict`, `BusyError` from `.manager`; `PortConflictError` from
`.lifecycle`.

### src/vortex/speed_routes.py (NEW)

`register_speed_routes(app: FastAPI, catalog: Catalog, manager: Manager,
ops: OperationStore, results_path: Path) -> None` creates one `SpeedRun`
and registers:

- `GET /speed` → `SPEED_PAGE` as `text/html`.
- `GET /api/speed` → `{"running": bool, "max_models": 3, "models": [...]}`,
  one row per catalog entry in catalog order:
  `public_id, display_name, quant, runtime, ram_estimate_gb`, `state`
  (`manager.entry_state(e, ops.active_for(e.public_id))`), `result` (the
  model's `load_results` record or null), `run_status` / `run_message` (from
  `SpeedRun.rows()`; null / "" when the model is not in the latest run).
- `POST /api/speed/run` with JSON `{"models": [ids]}` → 202
  `{"started": ids}`; a missing or non-list `models`, or a `ValueError` from
  `start` → 400 with the reason; `SpeedRunBusy` → 409 with
  `detail = {"message": ..., "busy": true}`.

It also adds an HTTP middleware to `app`: while the run is in progress, any
POST whose path matches `/api/models/{id}/load` or `/api/models/{id}/unload`
is answered 409 with `{"detail": {"message": "a speed test is running",
"busy": true}}` before reaching a route; everything else passes through. The
run itself calls the manager directly, so it is not blocked.

### src/vortex/speed_ui.py (NEW)

`SPEED_PAGE: str` — one self-contained HTML page (inline CSS/JS, no
http/https URLs), styled like the dashboard (`ui.py` colors, monospace).
`<header>`: "vortex", a link `href="/"` (Models), the Speed title.

The script polls `"/api/speed"` with `setInterval` (2 s). Reply:
`{running, max_models, models}`; each model row has exactly
`public_id`, `display_name` (nullable), `quant`, `runtime`,
`ram_estimate_gb` (nullable), `state`, `result` (null if untested),
`run_status` (null if not in the latest run), `run_message`; a result has
`single_tps`, `multi_tps`, `first_token_s`, `tested_at`. Name a row `row`
and its result `res` (`var res = row.result`); use those names for nothing
else (not fetch responses) and read no other fields from them.

Table, one row per model in API order: checkbox · `display_name` (else
`public_id`) with `public_id` · `quant` · `runtime` · `ram_estimate_gb` GB
· `res.single_tps` · `res.multi_tps` · `res.first_token_s` s ·
`res.tested_at` · `run_status` and `run_message`. Missing values show "—".

At most `max_models` boxes ticked (others disabled at the limit; all
disabled while `running`). One control labelled "Test selected" (the only
occurrence) POSTs `{"models": ids}` (`ids`: ticked `public_id` values) to
`/api/speed/run` with `method: "POST"`; disabled when none ticked or
`running`; a failed request shows an error beginning "Speed test failed".
While `running`, a banner: "loading and unloading are paused". Above the
table, best picks: fastest `single_tps`, fastest `multi_tps`, lowest
`first_token_s`. Clicking a speed column header sorts by it (untested
last); Model restores API order. Below: "don't run a speed test during a
pipeline milestone — both use the GPU".

### src/vortex/app.py (EDIT)

Add keyword parameter `speed_results_path: Path | None = None` to
`build_app` (after `local_catalog_path`). After the existing
`register_catalog_routes(...)` call, call `register_speed_routes(app,
catalog, manager, ops, speed_results_path or _REPO_ROOT /
"data/speed-results.json")` (`data/` is gitignored), importing it from
`.speed_routes`. Nothing else in the file changes.

### src/vortex/ui.py (EDIT)

In `UI_PAGE`'s `<header>`, add a link `<a href="/speed">Speed</a>` (styled
like the header's text, before the Stop Vortex button). Nothing else
changes. Standing invariants this file carries (frozen tests): Stop Vortex's
`confirm(` stays the page's first `confirm(`; every `m.<field>` / `s.<field>`
the script reads must be a field `/api/catalog` / `/api/discovered-models` /
`/api/status` returns; the page adds no http/https URL.

## Test-to-file mapping

* `tests/test_speedtest.py::test_measure_returns_the_three_speeds_from_real_replies`
    -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_sends_one_first_word_one_full_then_concurrent_requests`
    -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_fails_when_the_model_answers_an_error`
    -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_fails_when_nothing_is_listening`
    -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_fails_when_the_reply_has_no_token_count`
    -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_save_result_stamps_and_keeps_the_latest_per_model`
    -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_load_results_is_empty_for_a_missing_or_unreadable_file`
    -> `src/vortex/speedtest.py`
* `tests/test_speed_runner.py::test_unloaded_model_is_loaded_tested_and_unloaded_again`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_serving_model_is_tested_and_left_loaded`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_model_that_will_not_fit_is_skipped_without_loading`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_a_failed_model_does_not_stop_the_run`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_a_loaded_model_whose_test_fails_is_unloaded_again`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_start_rejects_bad_selections`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_a_second_start_while_running_is_refused`
    -> `src/vortex/speed_runner.py`
* `tests/test_speed_api.py::test_speed_list_has_every_catalog_model_in_order`
    -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_run_tests_a_model_and_reports_its_result`
    -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_run_rejects_bad_selections`
    -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_loads_unloads_and_new_runs_are_refused_while_a_run_is_in_progress`
    -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_page_is_served`
    -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_build_app_wires_the_speed_routes_and_results_path`
    -> `src/vortex/app.py`
* `tests/test_speed_api.py::test_build_app_keeps_its_existing_routes`
    -> `src/vortex/app.py`
* `tests/test_speed_ui.py::test_page_reads_only_fields_the_api_returns`
    -> `src/vortex/app.py`
* `tests/test_speed_ui.py::test_page_polls_and_starts_runs_through_the_api`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_has_one_test_button_and_a_capped_checklist`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_untested_values_show_a_dash`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_shows_status_banner_picks_and_warning`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_failures_are_visible`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_adds_no_external_urls`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_speed_page_links_back_to_the_dashboard`
    -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_dashboard_header_links_to_the_speed_page`
    -> `src/vortex/ui.py`

## Task DAG

`src/vortex/speed_runner.py` depends on `src/vortex/speedtest.py`
`src/vortex/speed_routes.py` depends on `src/vortex/speed_runner.py`
`src/vortex/speed_routes.py` depends on `src/vortex/speed_ui.py`
`src/vortex/app.py` depends on `src/vortex/speed_routes.py`

`src/vortex/ui.py` depends on nothing in this delta.
