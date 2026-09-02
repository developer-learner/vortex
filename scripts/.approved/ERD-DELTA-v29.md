# ERD-DELTA v29 — operator shutdown control (Stop Vortex), verbatim briefs

v29 re-issues the v28 shutdown milestone with verbatim coder briefs so the
plan is synthesized mechanically (no EM paraphrase). Behaviour and the frozen
tests are unchanged from v27/v28. The prior build stalled because the coder
reached for the low-level `_terminate_pid` helper instead of the
`lifecycle.terminate(entry)` instance method; the T1 brief below states the
exact call to make.

## Changed acceptance criteria

None. v29 re-issues the milestone unchanged.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/app.py` — adds the `POST /api/shutdown` route and an
  `on_shutdown` keyword parameter to `build_app`.
- `src/vortex/ui.py` — adds a Stop Vortex header button and its confirm-gated
  click handler.

## Test-to-file mapping

* `tests/test_shutdown_api.py::test_shutdown_signals_stop_and_reports_nothing_loaded`
    -> `src/vortex/app.py`
* `tests/test_shutdown_api.py::test_shutdown_unloads_loaded_model_and_reports_it`
    -> `src/vortex/app.py`
* `tests/test_ui_content.py::test_stop_vortex_button_in_header`
    -> `src/vortex/ui.py`
* `tests/test_ui_content.py::test_stop_vortex_confirms_then_posts_shutdown`
    -> `src/vortex/ui.py`

## Coder briefs (verbatim)

### T1 — src/vortex/app.py (shutdown route)

Add one POST route and one keyword parameter to `build_app`. Inside
`build_app`, two objects already exist in local scope: `manager` (a Manager)
and `lifecycle` (a Lifecycle). Use those existing objects — do not import or
construct new ones.

Add these imports at the top, next to the existing ones:
    import os
    import signal
    from collections.abc import Callable
    from starlette.background import BackgroundTask
Extend the existing `from fastapi.responses import StreamingResponse` line to:
    from fastapi.responses import JSONResponse, StreamingResponse

Add a keyword parameter to build_app's signature, after `wrapper_discovery=discover_wrappers,`:
    on_shutdown: Callable[[], None] | None = None

Immediately after `manager = Manager(...)` is created inside build_app, add:
    def _default_stop() -> None:
        os.kill(os.getpid(), signal.SIGTERM)
    stop_daemon = on_shutdown or _default_stop

Register this route inside build_app, next to the other `@app.post(...)` routes:
    @app.post("/api/shutdown")
    def shutdown() -> Response:
        unloaded: list[str] = []
        for entry in manager.all_ready():
            if lifecycle.terminate(entry):
                unloaded.append(entry.public_id)
        return JSONResponse(
            {"stopping": True, "unloaded": unloaded},
            background=BackgroundTask(stop_daemon),
        )

`manager.all_ready()` returns a list of CatalogEntry objects. `lifecycle.terminate(entry)`
is an instance method that takes one CatalogEntry and returns True when it
stopped that entry's process. That method call is the only termination call.

Self-verify before finishing: `ruff check src/vortex/app.py` is clean;
`mypy --explicit-package-bases src/vortex/app.py` is clean; the shutdown
handler calls `lifecycle.terminate(entry)`; and `build_app` still returns the
FastAPI `app`.

### T2 — src/vortex/ui.py (stop button)

Add a Stop Vortex control to the header and a click handler that confirms
first, then calls the shutdown route. `UI_PAGE` is one HTML string.

In the `<header>` element, after the existing `<span class="sub">model menu</span>`,
add:
    <button id="stopvortex" title="Stop Vortex" style="margin-left:auto">✕ Stop Vortex</button>

In the page's `<script>`, next to the other `addEventListener` handlers, add:
    document.getElementById("stopvortex").addEventListener("click", function () {
      if (!confirm("Stop Vortex? This unloads all loaded models, freeing their RAM, and shuts down the server.")) return;
      fetch("/api/shutdown", { method: "POST" })
        .then(function (r) {
          if (!r.ok) throw new Error("shutdown " + r.status);
          document.getElementById("down").style.display = "block";
        })
        .catch(function (e) { setError("Shutdown failed: " + e.message); });
    });

The button id is exactly `stopvortex`. The confirm() message contains the
words "unloads" and "models".

Self-verify before finishing: the string `id="stopvortex"` appears inside the
`<header>...</header>` block; the `confirm(` call and the `/api/shutdown` POST
are both present; and the page adds no `http`/`https` asset URL.

## Task DAG

T1 (`src/vortex/app.py`) and T2 (`src/vortex/ui.py`) are independent — neither
depends on the other; they may run in any order.
