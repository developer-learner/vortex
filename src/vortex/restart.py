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