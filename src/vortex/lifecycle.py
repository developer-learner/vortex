"""Process lifecycle: spawn, ready-probe, terminate, sidecar identity.

All the lessons are re-homed here (see docs/GLOSSARY.md); the single-owner
invariant is the spine:

- Every port a catalog entry declares is owned by exactly one process.
- modelmux terminates only processes ITS sidecars identify (PID + start-time).
- A process occupying a configured port that modelmux cannot identify is
  NEVER claimed, terminated, or evicted-on-load — it refuses instead.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import psutil

from .catalog import Catalog, CatalogEntry

logger = logging.getLogger(__name__)

READY_TIMEOUT_SECONDS = 300
TERMINATE_GRACE_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.25
SIDECAR_TOLERANCE_SECONDS = 1.0


def _find_listening_pid(port: int) -> int | None:
    for proc in psutil.process_iter(["pid"]):
        try:
            for conn in proc.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                    return proc.pid
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.Error):
            continue
    return None


def _process_start_time(pid: int) -> float | None:
    try:
        return psutil.Process(pid).create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _responds_ready(ready_url: str) -> bool:
    try:
        return httpx.get(ready_url, timeout=2).status_code == 200
    except Exception:  # noqa: BLE001 — probe must swallow any connection failure
        return False


class SidecarStore:
    """PID + start-time record per entry; survives modelmux restarts."""

    def __init__(self, dir_: Path) -> None:
        self.dir = dir_

    def _path(self, public_id: str) -> Path:
        return self.dir / f"{public_id}.json"

    def write(self, entry: CatalogEntry, process: subprocess.Popen) -> None:
        start_time = _process_start_time(process.pid)
        if start_time is None:
            logger.warning("no start-time for pid %s — sidecar skipped", process.pid)
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        record = {
            "pid": process.pid,
            "start_time": start_time,
            "public_id": entry.public_id,
            "port": entry.port,
        }
        tmp = f"{self._path(entry.public_id)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f)
        os.replace(tmp, self._path(entry.public_id))

    def read(self, public_id: str) -> dict | None:
        try:
            with open(self._path(public_id), encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, ValueError):
            return None
        return record if isinstance(record, dict) else None

    def drop(self, public_id: str) -> None:
        try:
            self._path(public_id).unlink()
        except OSError:
            pass

    def identifies(self, public_id: str, pid: int) -> bool:
        record = self.read(public_id)
        if not record or record.get("pid") != pid:
            return False
        recorded = record.get("start_time")
        if not isinstance(recorded, (int, float)):
            return False
        actual = _process_start_time(pid)
        if actual is None:
            return False
        return abs(actual - recorded) < SIDECAR_TOLERANCE_SECONDS


def _terminate_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + TERMINATE_GRACE_SECONDS
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _children_of(pid: int) -> list[int]:
    try:
        parent = psutil.Process(pid)
        return [c.pid for c in parent.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []


def _terminate_process_group(pid: int) -> None:
    """SIGINT the tracked process AND its descendants, then SIGKILL stragglers.

    The wrapper scripts exec into the real server, so the tracked pid may be
    long gone while its orphaned child still holds the port — killing only the
    recorded pid leaves the port bound.
    """
    for child in _children_of(pid):
        _terminate_pid(child)
    _terminate_pid(pid)


class Lifecycle:
    """Owns spawn/terminate for the catalog, driven by an operation store."""

    def __init__(self, catalog: Catalog, sidecars: SidecarStore,
                 ready_timeout: Callable[[], float] = lambda: READY_TIMEOUT_SECONDS) -> None:
        self.catalog = catalog
        self.sidecars = sidecars
        self.ready_timeout = ready_timeout
        self.processes: dict[str, subprocess.Popen | None] = {}

    def occupying_pid(self, entry: CatalogEntry) -> int | None:
        return _find_listening_pid(entry.port)

    def owner_status(self, entry: CatalogEntry, pid: int | None) -> str:
        """'ready' | 'unidentified' | 'foreign' | 'unloaded' for a port."""
        if pid is None:
            return "unloaded"
        if self.sidecars.identifies(entry.public_id, pid):
            return "ready"
        # We spawned it but never wrote a sidecar? Only case: crashed on write.
        proc = self.processes.get(entry.public_id)
        if proc is not None and proc.pid == pid:
            return "ready"
        return "unidentified"

    def spawn(self, entry: CatalogEntry) -> tuple[subprocess.Popen, bool]:
        """Spawn the entry's launch command. Returns (process, became_ready).

        The single-owner invariant is enforced here: if the port is already
        held by a process we do NOT identify, spawning is refused.
        """
        occupant = self.occupying_pid(entry)
        if occupant is not None and not self.sidecars.identifies(entry.public_id, occupant):
            raise PortConflictError(
                f"port {entry.port} occupied by unidentified process {occupant} — refusing",
                port=entry.port,
                pid=occupant,
            )
        if occupant is not None:
            logger.info("%s already serving on :%d — adopting", entry.public_id, entry.port)
            return None, True

        proc = subprocess.Popen(
            entry.launch_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.processes[entry.public_id] = proc
        self.sidecars.write(entry, proc)
        deadline = time.monotonic() + self.ready_timeout()
        while time.monotonic() < deadline:
            if self.owner_status(entry, self.occupying_pid(entry)) == "ready":
                return proc, True
            if proc.poll() is not None:
                raise SpawnError(f"{entry.public_id} exited early rc={proc.returncode}", rc=proc.returncode)
            time.sleep(POLL_INTERVAL_SECONDS)
        raise SpawnError(f"{entry.public_id} not ready within timeout", rc=None)

    def terminate(self, entry: CatalogEntry) -> bool:
        """Terminate the entry's process IF positively identified; else False."""
        occupant = self.occupying_pid(entry)
        if occupant is None:
            self.processes[entry.public_id] = None
            self.sidecars.drop(entry.public_id)
            return False
        if not self.sidecars.identifies(entry.public_id, occupant):
            logger.warning("refusing to terminate unidentified pid %s on :%d", occupant, entry.port)
            return False
        _terminate_process_group(occupant)
        _terminate_pid(occupant)
        self.processes[entry.public_id] = None
        self.sidecars.drop(entry.public_id)
        return True


class PortConflictError(Exception):
    def __init__(self, message: str, *, port: int, pid: int) -> None:
        super().__init__(message)
        self.port = port
        self.pid = pid


class SpawnError(Exception):
    def __init__(self, message: str, *, rc: int | None) -> None:
        super().__init__(message)
        self.rc = rc