"""Operation store: the 202 + poll contract for load/unload.

Model states: unloaded | loading | ready | unloading | error.
An operation carries phase, state, message, timestamps. Polling only for v1.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

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


class OperationStore:
    """Thread-safe in-memory operation registry."""

    def __init__(self) -> None:
        self._ops: dict[str, Operation] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, public_id: str) -> str:
        op = Operation(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            public_id=public_id,
        )
        with self._lock:
            self._ops[op.id] = op
        return op.id

    def get(self, op_id: str) -> Operation | None:
        with self._lock:
            return self._ops.get(op_id)

    def update(self, op_id: str, *, state: MODEL_STATES | None = None,
               phase: str | None = None, message: str | None = None) -> None:
        with self._lock:
            op = self._ops.get(op_id)
            if op is None:
                return
            if state is not None:
                op.state = state
            if phase is not None:
                op.phase = phase
            if message is not None:
                op.message = message
            op.updated_at = time.time()

    def snapshot(self, op_id: str) -> dict | None:
        op = self.get(op_id)
        if op is None:
            return None
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