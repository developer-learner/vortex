"""Vortex manager: load/unload orchestration, eviction, state aggregation."""

from __future__ import annotations

import threading

import psutil  # type: ignore[import-untyped]

from .catalog import Catalog, CatalogEntry
from .lifecycle import Lifecycle, PortConflictError, SCAN_UNKNOWN, SpawnError
from .operations import OperationStore


class MemoryConflict(Exception):
    def __init__(self, required_gb: float | None, candidates: list[str]) -> None:
        self.required_gb = required_gb
        self.candidates = candidates
        total_required = (
            f"~{required_gb:.0f} GB" if required_gb is not None else "unknown size"
        )
        super().__init__(
            f"loading needs {total_required}; {len(candidates)} loaded model(s) "
            f"would need eviction: {', '.join(candidates)}"
        )


class Manager:
    """Serializes load/unload (one mutation at a time) and owns eviction."""

    def __init__(self, catalog: Catalog, lifecycle: Lifecycle, ops: OperationStore) -> None:
        self.catalog = catalog
        self.lifecycle = lifecycle
        self.ops = ops
        self._lock = threading.RLock()

    def occupied_entries(self) -> list[CatalogEntry]:
        return [e for e in self.catalog.entries if self.lifecycle.occupying_pid(e) is not None]

    def all_ready(self) -> list[CatalogEntry]:
        """Entries held by our identified process — i.e. consuming their estimated
        RAM. This is the admission/eviction accounting set: it must include a
        restart-surviving runtime that is running but not yet verified this
        session, or memory would be undercounted. NOT the client-facing set —
        see client_ready()."""
        out = []
        for e in self.catalog.entries:
            pid = self.lifecycle.occupying_pid(e)
            if self.lifecycle.owner_status(e, pid) == "ready":
                out.append(e)
        return out

    def client_ready(self) -> list[CatalogEntry]:
        """Entries a load/adopt verified to serve inference this session — the set
        advertised to clients (/v1/models). A subset of all_ready(): an identified
        process consuming RAM is not advertised until its inference path is
        confirmed (truthful readiness, finding #1)."""
        return [e for e in self.all_ready() if self.lifecycle.is_verified(e)]

    def entry_state(self, entry: CatalogEntry, active_op: str | None) -> str:
        pid = self.lifecycle.occupying_pid(entry)
        if active_op:
            op = self.ops.get(active_op)
            if op is not None:
                return op.state
        status = self.lifecycle.owner_status(entry, pid)
        verified = status == "ready" and self.lifecycle.is_verified(entry)
        return "ready" if verified else "unloaded"

    def eviction_required(self, entry: CatalogEntry) -> list[CatalogEntry]:
        """Loaded models that would need eviction for this entry, or []."""
        amount = entry.ram_estimate_gb
        if amount is None or not entry.exclusive:
            return []
        loaded = self.all_ready()
        if any(e.public_id == entry.public_id for e in loaded):
            return []
        used = sum((e.ram_estimate_gb or 0) for e in loaded)
        available = max(0.0, psutil.virtual_memory().total / (1024**3) * 0.8 - used)
        if amount <= available:
            return []
        return loaded

    def load(self, public_id: str) -> dict:
        entry = self.catalog.by_public_id(public_id)
        if entry is None:
            raise LookupError(f"no catalog entry for {public_id!r}")
        conflicts = self.eviction_required(entry)
        if conflicts:
            raise MemoryConflict(
                entry.ram_estimate_gb, [e.public_id for e in conflicts]
            )
        op_id = self.ops.create("load", public_id)
        try:
            with self._lock:
                self.ops.update(op_id, state="loading", phase="spawning")
                _process, ready = self.lifecycle.spawn(entry)
                if not ready:
                    self.ops.update(op_id, state="loading", phase="adopting")
                    raise SpawnError(f"{public_id} did not become ready", rc=None)
                self.ops.update(op_id, state="ready", phase="done", message="serving")
                return {"operation": op_id, "model": public_id}
        except PortConflictError as exc:
            self.ops.update(op_id, state="error", phase="refused", message=str(exc))
            raise
        except SpawnError as exc:
            self.ops.update(op_id, state="error", phase="failed", message=str(exc))
            raise
        except MemoryConflict:
            self.ops.update(op_id, state="error", phase="conflict", message="eviction required")
            raise

    def load_async(self, public_id: str) -> dict:
        """202 contract: preflight synchronously (404/409 are immediate), then
        return the operation id promptly while the spawn continues in the
        background. Clients poll GET /api/operations/{id} to the terminal
        state. The synchronous load() remains for callers that want to block."""
        entry = self.catalog.by_public_id(public_id)
        if entry is None:
            raise LookupError(f"no catalog entry for {public_id!r}")
        conflicts = self.eviction_required(entry)
        if conflicts:
            raise MemoryConflict(
                entry.ram_estimate_gb, [e.public_id for e in conflicts]
            )
        # Port preflight mirrors Lifecycle.spawn so a refusal is an immediate
        # 409, not a 202 that later surfaces as error:refused.
        occupant = self.lifecycle.occupying_pid(entry)
        if occupant is SCAN_UNKNOWN:
            raise PortConflictError(
                f"port {entry.port} scan incomplete — refusing to load "
                f"(cannot verify the port is free)",
                port=entry.port,
                pid=None,
            )
        if occupant is not None and not self.lifecycle.sidecars.identifies(entry.public_id, occupant):
            raise PortConflictError(
                f"port {entry.port} occupied by unidentified process {occupant}",
                port=entry.port,
                pid=occupant,
            )
        op_id = self.ops.create("load", public_id)
        self.ops.update(op_id, state="loading", phase="spawning")

        def _work() -> None:
            try:
                with self._lock:
                    _process, ready = self.lifecycle.spawn(entry)
                    if not ready:
                        self.ops.update(
                            op_id, state="error", phase="failed",
                            message=f"{public_id} did not become ready",
                        )
                    else:
                        self.ops.update(op_id, state="ready", phase="done", message="serving")
            except PortConflictError as exc:
                self.ops.update(op_id, state="error", phase="refused", message=str(exc))
            except SpawnError as exc:
                self.ops.update(op_id, state="error", phase="failed", message=str(exc))
            except Exception as exc:  # noqa: BLE001 — the operation must never die silently
                self.ops.update(op_id, state="error", phase="failed", message=str(exc))

        threading.Thread(target=_work, daemon=True).start()
        return {"operation": op_id, "model": public_id}

    def unload(self, public_id: str) -> dict:
        entry = self.catalog.by_public_id(public_id)
        if entry is None:
            raise LookupError(f"no catalog entry for {public_id!r}")
        op_id = self.ops.create("unload", public_id)
        try:
            with self._lock:
                self.ops.update(op_id, state="unloading", phase="terminating")
                stopped = self.lifecycle.terminate(entry)
                if stopped:
                    self.ops.update(op_id, state="unloaded", phase="done")
                else:
                    self.ops.update(op_id, state="error", phase="refused", message="unidentified process")
                return {"operation": op_id, "model": public_id, "stopped": stopped}
        except Exception as exc:
            self.ops.update(op_id, state="error", phase="failed", message=str(exc))
            raise

    def unload_async(self, public_id: str) -> dict:
        """202 contract: return the operation id promptly; the terminate
        continues in the background. Clients poll GET /api/operations/{id}."""
        entry = self.catalog.by_public_id(public_id)
        if entry is None:
            raise LookupError(f"no catalog entry for {public_id!r}")
        op_id = self.ops.create("unload", public_id)
        self.ops.update(op_id, state="unloading", phase="terminating")

        def _work() -> None:
            try:
                with self._lock:
                    stopped = self.lifecycle.terminate(entry)
                    if stopped:
                        self.ops.update(op_id, state="unloaded", phase="done")
                    else:
                        self.ops.update(
                            op_id, state="error", phase="refused",
                            message="unidentified process",
                        )
            except Exception as exc:  # noqa: BLE001 — the operation must never die silently
                self.ops.update(op_id, state="error", phase="failed", message=str(exc))

        threading.Thread(target=_work, daemon=True).start()
        return {"operation": op_id, "model": public_id}
