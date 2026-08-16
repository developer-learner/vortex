"""Vortex manager: load/unload orchestration, eviction, state aggregation."""

from __future__ import annotations

import threading

import psutil

from .catalog import Catalog, CatalogEntry
from .lifecycle import Lifecycle, PortConflictError, SpawnError
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
        out = []
        for e in self.catalog.entries:
            pid = self.lifecycle.occupying_pid(e)
            if self.lifecycle.owner_status(e, pid) == "ready":
                out.append(e)
        return out

    def entry_state(self, entry: CatalogEntry, active_op: str | None) -> str:
        pid = self.lifecycle.occupying_pid(entry)
        if active_op:
            op = self.ops.get(active_op)
            if op is not None:
                return op.state
        status = self.lifecycle.owner_status(entry, pid)
        return "ready" if status == "ready" else "unloaded"

    def eviction_required(self, entry: CatalogEntry) -> list[CatalogEntry]:
        """Loaded models that would need eviction for this entry, or []."""
        amount = entry.ram_estimate_gb
        if amount is None or not entry.exclusive:
            return []
        loaded = self.all_ready()
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


def estimate_ram_used_gb() -> float:
    return psutil.virtual_memory().used / (1024**3)


def estimate_ram_total_gb() -> float:
    return psutil.virtual_memory().total / (1024**3)