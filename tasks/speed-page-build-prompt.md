# Build prompt — Vortex Speed page

You are adding a feature to **Vortex**, a local FastAPI daemon (`~/dev/vortex`,
package `src/vortex/`, Python 3.12+) that owns every local LLM on this Mac: it
keeps a catalog of loadable models, loads/unloads them, and proxies them at
`:9000` as one OpenAI-compatible endpoint. The dashboard is a single HTML page
(`src/vortex/ui.py`, `UI_PAGE`) served at `/`.

## Goal

A **Speed page** where the operator sees how fast every loadable model is on
this machine and measures any of them on demand, so model choice rests on
numbers measured the same way.

## Behavior

1. List **every catalog model**, in catalog order. Untested values show "—".
2. The operator ticks **up to 3** models and presses **one "Test selected"**
   button. Vortex tests them **one after another** in the background.
3. A model **not loaded** is loaded, tested, then **unloaded again**. A model
   **already serving** is tested and **left loaded**. Every model ends in the
   load state it started in.
4. A model that **won't fit** in memory next to the loaded ones is **skipped**
   with the reason "won't fit (needs N GB)". Never unload another model to make
   room.
5. A model that fails to load or test is marked **failed** with the reason; the
   run continues with the next model. If the run loaded it, unload it anyway.
6. **While a run is in progress**, load and unload requests are refused (409).
7. Each test measures, with the same fixed prompt, temperature 0, no streaming:
   - **first_token_s** — wall time of a request with `max_tokens: 1` (round to 3 decimals);
   - **single_tps** — completion tokens ÷ wall seconds of one `max_tokens: 256` request;
   - **multi_tps** — 4 concurrent `max_tokens: 256` requests: summed completion
     tokens ÷ wall seconds from first start to last finish. Round tps to 1 decimal.
   Token counts come from `usage.completion_tokens`. A connection error, non-200
   reply, or reply without that count fails the test (reason mentions "token" for
   the missing count).
8. Keep each model's **latest result** (plus `tested_at`, local time,
   "YYYY-MM-DD HH:MM") in `data/speed-results.json` (gitignored), surviving restarts.
9. The page shows best picks (fastest single, fastest multi, quickest first
   word), a banner "loading and unloading are paused" while running, and the note
   "don't run a speed test during a pipeline milestone — both use the GPU".

## Files and interfaces (these names are pinned by tests)

- `src/vortex/speedtest.py` (NEW, stdlib + httpx): `PROMPT`, `MAX_TOKENS = 256`,
  `CONCURRENCY = 4`, `SpeedTestError(Exception)`,
  `measure(endpoint: str, model: str) -> dict[str, float]` (keys `single_tps`,
  `multi_tps`, `first_token_s`), `load_results(path) -> dict[str, dict]` (`{}` if
  missing / invalid JSON / not an object), `save_result(path, public_id, result)
  -> dict[str, float | str]` (adds `tested_at`, keeps other models, creates dirs).
- `src/vortex/speed_runner.py` (NEW): `SpeedRunBusy(Exception)`;
  `SpeedRun(catalog, manager, ops, results_path)` with `start(model_ids)`
  (ValueError unless 1–3 distinct catalog ids; SpeedRunBusy if running; sets
  `running` True before returning, runs on a thread), property `running`, and
  `rows() -> {id: {"status", "message"}}` for the latest run. Statuses: queued,
  loading, testing, unloading, done, skipped, failed; a model the run loaded ends
  "done" with message "unloaded again".
  Use: `manager.entry_state(entry, ops.active_for(id)) == "ready"` (serving),
  `manager.admits(entry)` (fits), `manager.load(id)` / `manager.unload(id)` (return
  `{"operation": op_id}`; poll `ops.snapshot(op_id)["state"]` until
  "ready"/"unloaded" or "error"), exceptions `MemoryConflict`, `BusyError`
  (`.manager`), `PortConflictError` (`.lifecycle`), `LookupError`. Test with
  `measure(entry.chat_endpoint, entry.upstream_alias or entry.public_id)`.
- `src/vortex/speed_routes.py` (NEW): `register_speed_routes(app, catalog, manager,
  ops, results_path)`:
  - `GET /speed` → `SPEED_PAGE` (text/html);
  - `GET /api/speed` → `{"running", "max_models": 3, "models": [...]}`, one row per
    catalog entry: `public_id, display_name, quant, runtime, ram_estimate_gb,
    state, result (or null), run_status (or null), run_message ("")`;
  - `POST /api/speed/run` `{"models": [ids]}` → 202 `{"started": ids}`; 400 for a
    bad selection or missing list; 409 `{"detail": {"message", "busy": true}}` if running;
  - an HTTP middleware that, while running, answers any POST to
    `/api/models/{id}/load|unload` with 409 `{"detail": {"message": "a speed test
    is running", "busy": true}}`.
- `src/vortex/speed_ui.py` (NEW): `SPEED_PAGE: str`, self-contained HTML (inline
  CSS/JS, no http/https URLs), dashboard look (dark theme, monospace). Header links
  `href="/"`. Polls `"/api/speed"` with `setInterval` every 2 s. In the script name a
  model row `row` and its result `res` and read only API fields. Checkboxes capped at
  `max_models`, disabled while running; "Test selected" appears exactly once and
  POSTs `{"models": ids}` with `method: "POST"`; failures show an error beginning
  "Speed test failed". Click a speed column to sort (untested last).
- `src/vortex/app.py` (EDIT): add `speed_results_path: Path | None = None` to
  `build_app`; after `register_catalog_routes(...)`, call
  `register_speed_routes(app, catalog, manager, ops, speed_results_path or
  _REPO_ROOT / "data/speed-results.json")`. Nothing else changes.
- `src/vortex/ui.py` (EDIT): add `<a href="/speed">Speed</a>` in the header before
  Stop Vortex. Nothing else changes (keep Stop Vortex's `confirm(` the first on the
  page; add no http/https URLs).

## Constraints

- `ruff check src/` must pass with the project config — ruff 0.16 defaults
  (~400 rules). Known traps: no naive `datetime.now()` (DTZ005), use `datetime.UTC`
  not `timezone.utc` (UP017), a blind `except Exception` needs `# noqa: BLE001`
  with a reason.
- `mypy --explicit-package-bases src/` must pass.
- Don't change existing behavior or tests; full suite stays green, coverage ≥ 80%.

## Acceptance

29 tests define done, staged at `scripts/.approved/incoming/tests/`:
`test_speedtest.py`, `test_speed_runner.py`, `test_speed_api.py`,
`test_speed_ui.py`. Run them with `.venv/bin/python -m pytest
scripts/.approved/incoming/tests -q` (they import `vortex.*` and
`tests.fake_server`), plus the existing suite: `.venv/bin/python -m pytest -q`.
Do not add or edit files under `tests/` — Vortex's commit gate only accepts test
changes through a freeze.

A look-and-feel mockup (dummy data, not normative) is at
`examples/speed-mockup/index.html`.
