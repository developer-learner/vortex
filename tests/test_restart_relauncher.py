"""Frozen suite v38: the detached relauncher behind POST /api/restart (AC-21).

Observes only the locked surface (vortex.restart:spawn_relauncher). A real
"holder" process stands in for the old daemon, so waiting-for-exit is
observed against an actual pid rather than a mock.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from vortex.restart import spawn_relauncher


def _writer(target: Path, expr: str) -> list[str]:
    """A command that writes `expr` (evaluated in the child) to `target`."""
    code = f"import os; open({str(target)!r}, 'w').write(str({expr}))"
    return [sys.executable, "-c", code]


def _wait_for_file(path: Path, seconds: float = 10.0) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text(encoding="utf-8"):
            return path.read_text(encoding="utf-8")
        time.sleep(0.05)
    raise AssertionError(f"relaunched command never wrote {path}")


def test_relauncher_waits_for_the_process_to_exit(tmp_path: Path) -> None:
    """The command does not run while the watched pid is alive, and runs once
    it has exited (AC-21)."""
    marker = tmp_path / "ran.txt"
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    helper = None
    try:
        helper = spawn_relauncher(holder.pid, _writer(marker, "'ran'"), str(tmp_path))
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            assert not marker.exists(), "the command ran before the watched process exited"
            time.sleep(0.05)
        holder.kill()
        holder.wait(timeout=5)
        assert _wait_for_file(marker) == "ran"
        assert helper.wait(timeout=10) == 0
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=5)
        if helper is not None and helper.poll() is None:
            helper.kill()
            helper.wait(timeout=5)


def test_relauncher_runs_the_command_in_the_given_directory(tmp_path: Path) -> None:
    """The relaunched command's working directory is the one passed in (AC-21)."""
    workdir = tmp_path / "work"
    workdir.mkdir()
    marker = tmp_path / "cwd.txt"
    holder = subprocess.Popen([sys.executable, "-c", "pass"])
    holder.wait(timeout=5)
    helper = spawn_relauncher(holder.pid, _writer(marker, "os.getcwd()"), str(workdir))
    try:
        got = _wait_for_file(marker)
        assert os.path.realpath(got) == os.path.realpath(workdir)
        assert helper.wait(timeout=10) == 0
    finally:
        if helper.poll() is None:
            helper.kill()
            helper.wait(timeout=5)


def test_relauncher_is_detached_in_its_own_session(tmp_path: Path) -> None:
    """The helper leads its own session, so the old daemon's exit cannot take
    it down (AC-21)."""
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    helper = spawn_relauncher(holder.pid, [sys.executable, "-c", "pass"], str(tmp_path))
    try:
        assert os.getsid(helper.pid) == helper.pid, "the relauncher must lead a new session"
        assert os.getsid(helper.pid) != os.getsid(0)
    finally:
        holder.kill()
        holder.wait(timeout=5)
        helper.wait(timeout=10)
