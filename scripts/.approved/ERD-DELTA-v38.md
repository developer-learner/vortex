# ERD-DELTA v38 — operator restart control (Restart Vortex), verbatim briefs

v38 adds a Restart Vortex control: `POST /api/restart` unloads every loaded
model, then a detached relauncher starts a fresh daemon from the same command
line once the old one has exited. The relaunch mechanism lives in its own
small module (`src/vortex/restart.py`) so it is testable against real
processes and knows nothing about the web app. Briefs are verbatim so the plan
is synthesized mechanically (no EM paraphrase), per the v27→v29 lesson.

## Changed acceptance criteria

New criteria introduced by this milestone (PRD v38): AC-18, AC-19, AC-20,
AC-21, AC-22, AC-23, AC-24. No existing criterion changes; AC-7/AC-8 (Stop
Vortex) are unchanged and their frozen tests stay as they are.

## Superseded acceptance criteria

None. (PRD v27's out-of-scope line "a restart/relaunch control" is lifted by
v38's scope section; no v27 criterion is superseded.)

## Changed files

- `src/vortex/restart.py` — NEW. `spawn_relauncher(pid, argv, cwd)` starts a
  detached `/bin/sh` helper that waits for `pid` to exit, then execs `argv` in
  `cwd`. Stdlib only.
- `src/vortex/app.py` — EDIT. Adds an `on_restart` keyword parameter to
  `build_app`, a default restart hook, and the `POST /api/restart` route.
- `src/vortex/ui.py` — EDIT. Adds the header button, its confirm-gated click
  handler, and the `waitForRestart` poll.

## Test-to-file mapping

* `tests/test_restart_relauncher.py::test_relauncher_waits_for_the_process_to_exit`
    -> `src/vortex/restart.py`
* `tests/test_restart_relauncher.py::test_relauncher_runs_the_command_in_the_given_directory`
    -> `src/vortex/restart.py`
* `tests/test_restart_relauncher.py::test_relauncher_is_detached_in_its_own_session`
    -> `src/vortex/restart.py`
* `tests/test_restart_api.py::test_restart_with_nothing_loaded_invokes_only_the_restart_hook`
    -> `src/vortex/app.py`
* `tests/test_restart_api.py::test_shutdown_never_invokes_the_restart_hook`
    -> `src/vortex/app.py`
* `tests/test_restart_api.py::test_restart_unloads_loaded_model_and_reports_it`
    -> `src/vortex/app.py`
* `tests/test_restart_api.py::test_restart_is_refused_while_an_operation_is_in_flight`
    -> `src/vortex/app.py`
* `tests/test_ui_restart.py::test_restart_vortex_button_in_header_beside_stop`
    -> `src/vortex/ui.py`
* `tests/test_ui_restart.py::test_restart_confirms_before_posting_restart`
    -> `src/vortex/ui.py`
* `tests/test_ui_restart.py::test_restart_disables_the_control_while_in_flight`
    -> `src/vortex/ui.py`
* `tests/test_ui_restart.py::test_restart_polls_status_then_reloads`
    -> `src/vortex/ui.py`
* `tests/test_ui_restart.py::test_restart_failure_is_visible`
    -> `src/vortex/ui.py`

## Coder briefs (verbatim)

### T1 — src/vortex/restart.py (relauncher)

Create the new file `src/vortex/restart.py` with exactly this content:

    """Relaunch helper: run a command once a given process has exited."""

    from __future__ import annotations

    import subprocess

    _WAIT_THEN_EXEC = 'while kill -0 "$1" 2>/dev/null; do sleep 0.2; done; shift; exec "$@"'


    def spawn_relauncher(pid: int, argv: list[str], cwd: str) -> subprocess.Popen:
        """Start a detached helper that waits for `pid` to exit, then execs `argv` in `cwd`."""
        return subprocess.Popen(
            ["/bin/sh", "-c", _WAIT_THEN_EXEC, "vortex-relaunch", str(pid), *argv],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

The module imports only `subprocess` from the standard library.

Self-verify before finishing: `ruff check src/vortex/restart.py` is clean;
`mypy --explicit-package-bases src/vortex/restart.py` is clean; the file
defines `spawn_relauncher` and passes `start_new_session=True`.

### T2 — src/vortex/app.py (restart route)

Add one POST route, one keyword parameter, and a default restart hook to
`build_app`. Inside `build_app` these objects already exist in local scope:
`manager`, `lifecycle`, `ops`, and `stop_daemon`. Use them as they are.

Add these imports next to the existing ones:
    import sys
    import psutil  # type: ignore[import-untyped]
    from .restart import spawn_relauncher

Add a keyword parameter to build_app's signature, right after the existing
`on_shutdown: Callable[[], None] | None = None,` line:
    on_restart: Callable[[], None] | None = None,

Right after the existing line `stop_daemon = on_shutdown or _default_stop`, add:
    def _default_restart() -> None:
        spawn_relauncher(os.getpid(), [sys.executable, *sys.argv], os.getcwd())
        os.kill(os.getpid(), signal.SIGTERM)

    restart_daemon = on_restart or _default_restart

Register this route directly after the existing `/api/shutdown` route:
    @app.post("/api/restart")
    def restart() -> Response:
        active = ops.active()
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"{active.kind} for {active.public_id!r} is in progress",
                    "busy": True,
                    "operation": active.id,
                },
            )
        unloaded: list[str] = []
        for entry in manager.all_ready():
            if lifecycle.terminate(entry):
                unloaded.append(entry.public_id)
        return JSONResponse(
            {"restarting": True, "unloaded": unloaded},
            background=BackgroundTask(restart_daemon),
        )

`ops.active()` returns the in-flight Operation or None; it has `.id`, `.kind`
and `.public_id`. The only termination call is `lifecycle.terminate(entry)`.

Self-verify before finishing: ruff and mypy are clean on the file; the
shutdown route is unchanged; the restart route uses `restart_daemon`, never
`stop_daemon`; `build_app` still returns `app`.

### T3 — src/vortex/ui.py (restart button)

`UI_PAGE` is one HTML string. In the `<header>`, directly after the existing
`<button id="stopvortex" ...>✕ Stop Vortex</button>`, add:
    <button id="restartvortex" title="Restart Vortex">↻ Restart Vortex</button>

In the page's `<script>`, directly after the existing `stopvortex` click
handler block, add:
    document.getElementById("restartvortex").addEventListener("click", function () {
      var btn = this;
      if (!confirm("Restart Vortex? This unloads all loaded models, freeing their RAM, then starts a clean server.")) return;
      btn.disabled = true;
      fetch("/api/restart", { method: "POST" })
        .then(function (r) {
          if (r.status === 409) throw new Error("a load or unload is in progress");
          if (!r.ok) throw new Error("restart " + r.status);
          waitForRestart(btn, 0, false);
        })
        .catch(function (e) { btn.disabled = false; setError("Restart failed: " + e.message); });
    });
    function waitForRestart(btn, tries, wentDown) {
      if (tries > 90) { btn.disabled = false; setError("Restart failed: Vortex did not come back; see ~/Library/Logs/Vortex.log"); return; }
      setTimeout(function () {
        fetch("/api/status")
          .then(function (r) {
            if (r.ok && (wentDown || tries >= 10)) { location.reload(); return; }
            waitForRestart(btn, tries + 1, wentDown);
          })
          .catch(function () { waitForRestart(btn, tries + 1, true); });
      }, 500);
    }

Self-verify before finishing: `id="restartvortex"` is inside the header; the
Stop Vortex button and handler are unchanged; the page adds no http/https URL.

## Task DAG

`src/vortex/app.py` depends on `src/vortex/restart.py`

Task order: T1 (restart.py) -> T2 (app.py). T3 (ui.py) is independent of both.
