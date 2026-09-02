# ERD-DELTA v27 — operator shutdown control (Stop Vortex)

v27 adds an operator-facing way to power Vortex down from the dashboard. It
introduces one management route, `POST /api/shutdown`, and one header control.
The route unloads every loaded model and then signals the daemon to stop; the
control confirms first, then calls the route. This milestone ADDS AC-7 and
AC-8 (see the PRD's v27 section); it changes no existing behaviour.

## Behaviour

1. `POST /api/shutdown` (`src/vortex/app.py`) iterates the loaded set
   (`manager.all_ready()`) and terminates each entry's process via
   `lifecycle.terminate(entry)`, collecting the public ids it actually
   stopped. It returns `{"stopping": true, "unloaded": [<ids>]}`. The unload
   runs synchronously in the handler BEFORE the stop is scheduled, so the RAM
   is reclaimed even though the model processes are session-leaders that would
   otherwise outlive the daemon.
2. The daemon-stop signal is a new `on_shutdown` keyword parameter on
   `build_app(...)`, invoked as a Starlette response background task so the
   response body flushes to the client before the server goes down. Its
   default sends `SIGTERM` to the daemon's own process (uvicorn's
   graceful-shutdown signal); the frozen tests inject a fake so the stop is
   observable without killing the test runner. The hook is called exactly
   once per shutdown request.
3. The dashboard header (`src/vortex/ui.py`) gains a Stop Vortex button
   (`id="stopvortex"`). Its click handler calls `confirm(...)` with a warning
   that every loaded model will be unloaded; on cancel it returns and sends
   nothing. On confirm it issues `fetch("/api/shutdown", { method: "POST" })`
   and, on success, shows the existing daemon-unreachable panel. No new
   endpoints, external assets, or dependencies are introduced on the page.

## Changed acceptance criteria

None. v27 ADDS AC-7 and AC-8; it changes no existing acceptance criterion.

## Superseded acceptance criteria

None. No prior acceptance criterion is superseded.

## Changed files

- `src/vortex/app.py` — adds the `POST /api/shutdown` route and an
  `on_shutdown` keyword parameter to `build_app`; the route unloads every
  loaded model, returns the stopped ids under `unloaded`, and schedules the
  daemon-stop hook as a response background task.
- `src/vortex/ui.py` — adds a Stop Vortex button to the header and a click
  handler that confirms (warning that loaded models will be unloaded), then
  POSTs `/api/shutdown`, then falls back to the daemon-unreachable state.

## Test-to-file mapping

* `tests/test_shutdown_api.py::test_shutdown_signals_stop_and_reports_nothing_loaded`
    -> `src/vortex/app.py`
* `tests/test_shutdown_api.py::test_shutdown_unloads_loaded_model_and_reports_it`
    -> `src/vortex/app.py`
* `tests/test_ui_content.py::test_stop_vortex_button_in_header`
    -> `src/vortex/ui.py`
* `tests/test_ui_content.py::test_stop_vortex_confirms_then_posts_shutdown`
    -> `src/vortex/ui.py`
