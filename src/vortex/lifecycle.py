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
import psutil  # type: ignore[import-untyped]

from .catalog import Catalog, CatalogEntry

logger = logging.getLogger(__name__)

READY_TIMEOUT_SECONDS = 300
TERMINATE_GRACE_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.25
SIDECAR_TOLERANCE_SECONDS = 1.0


class _ScanUnknown:
    """Sentinel: the port scan could not be completed (unreadable processes)."""

    def __repr__(self) -> str:
        return "<port-scan-unknown>"


SCAN_UNKNOWN = _ScanUnknown()


def _scan_port(port: int, retries: int = 2) -> int | None | _ScanUnknown:
    """Scan for a listener on port.

    Returns the listener's pid, None when a CLEAN scan found no listener, or
    SCAN_UNKNOWN when some processes were unreadable and no listener was
    found. An incomplete scan must never be reported as "empty": transient
    per-process psutil failures under memory pressure are how a live model
    silently flapped to "unloaded" (2026-08-18 anomaly class).
    """
    for attempt in range(retries + 1):
        errored = 0
        found: int | None = None
        for proc in psutil.process_iter(["pid"]):
            try:
                for conn in proc.net_connections(kind="inet"):
                    if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                        found = proc.pid
                        break
                if found is not None:
                    break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                # AccessDenied: another user's process — cannot be the model
                # (modelmux spawns as the current user); permanent on macOS,
                # not incompleteness. NoSuchProcess: exited mid-scan; it is
                # gone, so it cannot hold the port. Both are safe to skip.
                continue
            except psutil.Error:
                # Transient syscall failure on a visible process: this scan
                # may have missed the model — count it as incompleteness.
                errored += 1
                continue
        if found is not None or errored == 0:
            return found
        if attempt < retries:
            logger.warning(
                "port %d scan incomplete (%d process(es) unreadable) — retry %d/%d",
                port, errored, attempt + 1, retries,
            )
            time.sleep(POLL_INTERVAL_SECONDS)
    logger.warning(
        "port %d scan still incomplete after %d attempt(s) — reporting unknown; "
        "callers must fail closed",
        port, retries + 1,
    )
    return SCAN_UNKNOWN


def _find_listening_pid(port: int) -> int | None:
    """Binary view of _scan_port (tests, diagnostics, port-free polling).

    An incomplete scan is reported as None here — safe only for "is the port
    free" polling, never for state decisions (use _scan_port / occupying_pid).
    """
    result = _scan_port(port)
    return None if result is SCAN_UNKNOWN else result


def as_pid(result: int | None | _ScanUnknown) -> int | None:
    """API-facing view of a scan result: an incomplete scan shows no occupant."""
    return None if result is SCAN_UNKNOWN else result


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


def _anneal_probe(chat_endpoint: str) -> bool:
    """A real inference anneal: the runtime must serve a 1-token completion.

    Endpoints that answer /v1/models across the load (llama-server returns
    200 while weights still load) must not count as ready until a completion
    actually succeeds — otherwise the first client chat receives the
    upstream's 503 Loading model (finding #1, D-174).
    """
    try:
        resp = httpx.post(
            chat_endpoint,
            json={
                "model": "__ready_probe__",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            return False
        body = resp.json()
        return bool(body.get("choices"))
    except Exception:  # noqa: BLE001 — probe must swallow any failure
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
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            # Present but unreadable: a transient I/O failure must not read as
            # "no sidecar record" (that path 409s a live, byte-exact model).
            # Callers fail closed either way; the log distinguishes the cases.
            logger.warning(
                "sidecar %s present but unreadable (transient I/O?) — "
                "treating as unidentified",
                public_id,
            )
            return None
        return record if isinstance(record, dict) else None

    def drop(self, public_id: str) -> None:
        try:
            self._path(public_id).unlink()
        except OSError:
            pass

    def identify_failure(self, public_id: str, pid: int) -> str | None:
        """Why the sidecar does NOT identify pid, or None if it does."""
        record = self.read(public_id)
        if not record:
            return "no sidecar record"
        if record.get("pid") != pid:
            return f"sidecar pid {record.get('pid')!r} != occupant {pid}"
        recorded = record.get("start_time")
        if not isinstance(recorded, (int, float)):
            return "sidecar start_time malformed"
        actual = _process_start_time(pid)
        if actual is None:
            return "occupant start-time unavailable (transient probe failure?)"
        if abs(actual - recorded) >= SIDECAR_TOLERANCE_SECONDS:
            return (
                f"start-time mismatch (recorded {recorded}, live {actual}, "
                f"delta {abs(actual - recorded):.3f}s)"
            )
        return None

    def identifies(self, public_id: str, pid: int) -> bool:
        return self.identify_failure(public_id, pid) is None


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
        self._last_status: dict[str, str] = {}

    def occupying_pid(self, entry: CatalogEntry) -> int | None | _ScanUnknown:
        return _scan_port(entry.port)

    def owner_status(self, entry: CatalogEntry, pid: int | None | _ScanUnknown) -> str:
        """'ready' | 'unidentified' | 'foreign' | 'unloaded' for a port."""
        if pid is SCAN_UNKNOWN:
            # Incomplete scan: never flip state on evidence we couldn't
            # gather — hold the last known status (2026-08-18 anomaly class).
            previous = self._last_status.get(entry.public_id)
            logger.warning(
                "%s: port %d scan incomplete — holding status %r",
                entry.public_id, entry.port, previous or "unknown",
            )
            return previous or "unloaded"
        if pid is None:
            status = "unloaded"
            reason = ""
        elif self.sidecars.identifies(entry.public_id, pid):
            status = "ready"
            reason = ""
        else:
            # We spawned it but never wrote a sidecar? Only case: crashed on write.
            proc = self.processes.get(entry.public_id)
            if proc is not None and proc.pid == pid:
                status = "ready"
                reason = ""
            else:
                status = "unidentified"
                reason = (
                    f" ({self.sidecars.identify_failure(entry.public_id, pid)})"
                )
        previous = self._last_status.get(entry.public_id)
        if previous != status:
            logger.info(
                "%s state flip: %s -> %s%s",
                entry.public_id,
                previous or "unknown",
                status,
                reason,
            )
            self._last_status[entry.public_id] = status
        return status

    def _harmonic_ready(self, entry: CatalogEntry) -> bool:
        """Port ownership PLUS a 200 on /v1/models PLUS a real completion."""
        return _responds_ready(entry.ready_url) and _anneal_probe(entry.chat_endpoint)

    def spawn(self, entry: CatalogEntry) -> tuple[subprocess.Popen | None, bool]:
        """Spawn the entry's launch command. Returns (process, became_ready).

        The single-owner invariant is enforced here: if the port is already
        held by a process we do NOT identify, spawning is refused.
        """
        occupant = self.occupying_pid(entry)
        if occupant is SCAN_UNKNOWN:
            raise PortConflictError(
                f"port {entry.port} scan incomplete — refusing to spawn "
                f"(cannot verify the port is free)",
                port=entry.port,
                pid=None,
            )
        if occupant is not None and not self.sidecars.identifies(entry.public_id, occupant):
            raise PortConflictError(
                f"port {entry.port} occupied by unidentified process {occupant} "
                f"— refusing ({self.sidecars.identify_failure(entry.public_id, occupant)})",
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
            if (
                self.owner_status(entry, self.occupying_pid(entry)) == "ready"
                and self._harmonic_ready(entry)
            ):
                return proc, True
            if proc.poll() is not None:
                raise SpawnError(f"{entry.public_id} exited early rc={proc.returncode}", rc=proc.returncode)
            time.sleep(POLL_INTERVAL_SECONDS)
        raise SpawnError(f"{entry.public_id} not ready within timeout", rc=None)

    def terminate(self, entry: CatalogEntry) -> bool:
        """Terminate the entry's process IF positively identified; else False."""
        occupant = self.occupying_pid(entry)
        if occupant is SCAN_UNKNOWN:
            # Incomplete scan: the port may still hold a live model — never
            # drop the sidecar or report "already unloaded" on unknown.
            logger.warning(
                "refusing to terminate %s: port %d scan incomplete",
                entry.public_id, entry.port,
            )
            return False
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
    def __init__(self, message: str, *, port: int, pid: int | None) -> None:
        super().__init__(message)
        self.port = port
        self.pid = pid


def log_stale_sidecars(sidecars: SidecarStore, catalog: Catalog) -> None:
    """Boot-time reconciliation: warn on sidecars whose process is gone or
    was replaced (e.g. after a machine reboot) — never delete, only report."""
    known = {e.public_id for e in catalog.entries}
    if not sidecars.dir.is_dir():
        return
    for path in sorted(sidecars.dir.glob("*.json")):
        public_id = path.stem
        record = sidecars.read(public_id)
        if record is None:
            logger.warning("stale sidecar %s: unreadable", path.name)
            continue
        pid = record.get("pid")
        if pid is None:
            logger.warning("stale sidecar %s: no pid recorded", path.name)
            continue
        if _process_start_time(pid) is None:
            logger.warning(
                "stale sidecar %s: pid %s no longer running (reboot or exit?)",
                path.name,
                pid,
            )
        elif public_id not in known:
            logger.warning("sidecar %s: unknown public_id, not in catalog", path.name)


class SpawnError(Exception):
    def __init__(self, message: str, *, rc: int | None) -> None:
        super().__init__(message)
        self.rc = rc