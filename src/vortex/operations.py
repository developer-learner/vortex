"""Operation store: the 202 + poll contract for load/unload.

Model states: unloaded | loading | ready | unloading | error.
An operation carries phase, state, message, timestamps. Polling only for v1.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field, replace

from .catalog import MODEL_STATES


@dataclass
class Operation:
    id: str
    kind: str  # "load" | "unload"
    public_id: str
    state: MODEL_STATES = "loading"
    phase: str = "starting"
    message: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


MAX_OPS = 100
RETENTION_SECONDS = 3600


class OperationStore:
    """Thread-safe in-memory operation registry."""

    def __init__(self) -> None:
        self._ops: dict[str, Operation] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._ops)

    def _prune(self) -> None:
        """Bounded retention for a long-lived daemon: expire completed ops past
        RETENTION_SECONDS, then cap the registry at MAX_OPS (oldest completed
        first). In-flight ops (loading/unloading) are never pruned."""
        now = time.time()
        expired = [oid for oid, op in self._ops.items()
                   if op.state in ("ready", "unloaded", "error") and now - op.updated_at > RETENTION_SECONDS]
        for oid in expired:
            del self._ops[oid]
        if len(self._ops) > MAX_OPS:
            completed = sorted(
                [(oid, op) for oid, op in self._ops.items() if op.state in ("ready", "unloaded", "error")],
                key=lambda x: x[1].updated_at,
            )
            for oid, _ in completed[: len(self._ops) - MAX_OPS]:
                del self._ops[oid]

    def create(self, kind: str, public_id: str) -> str:
        op = Operation(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            public_id=public_id,
        )
        with self._lock:
            self._ops[op.id] = op
            self._prune()
        return op.id

    def get(self, op_id: str) -> Operation | None:
        with self._lock:
            return self._ops.get(op_id)

    def update(self, op_id: str, *, state: MODEL_STATES | None = None,
               phase: str | None = None, message: str | None = None) -> bool:
        """Apply fields to the operation. Returns False (no-op) when the id is
        unknown — observable, so a caller can tell its update landed."""
        with self._lock:
            op = self._ops.get(op_id)
            if op is None:
                return False
            if state is not None:
                op.state = state
            if phase is not None:
                op.phase = phase
            if message is not None:
                op.message = message
            op.updated_at = time.time()
            return True

    def snapshot(self, op_id: str) -> dict | None:
        with self._lock:
            op = self._ops.get(op_id)
            if op is None:
                return None
            # Atomic copy while holding the lock — poll-path readers never see
            # a half-updated operation or write through the returned dict.
            return {
                "id": op.id,
                "kind": op.kind,
                "model": op.public_id,
                "state": op.state,
                "phase": op.phase,
                "message": op.message,
                "created_at": op.created_at,
                "updated_at": op.updated_at,
            }

    def active_for(self, public_id: str) -> str | None:
        with self._lock:
            for op in self._ops.values():
                if op.public_id == public_id and op.state in ("loading", "unloading"):
                    return op.id
        return None

    def active(self) -> Operation | None:
        """Return an atomic copy of the one in-flight mutation, if any."""
        with self._lock:
            for op in self._ops.values():
                if op.state in ("loading", "unloading"):
                    return replace(op)
        return None
