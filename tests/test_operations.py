"""OperationStore invariants: atomic snapshots, observable no-ops, bounded retention.

The 202 + poll contract (POST /load -> operation id -> GET /api/operations/{id})
depends on the store being safe to read from the poll path while the worker
thread mutates it, and on the registry staying bounded for a long-lived daemon.
"""

from __future__ import annotations

import time

from vortex.operations import MAX_OPS, RETENTION_SECONDS, OperationStore


def _completed(store: OperationStore, model: str = "m1") -> str:
    op_id = store.create("load", model)
    store.update(op_id, state="ready", phase="done")
    return op_id


def test_update_missing_op_returns_false() -> None:
    """A no-op update must be observable (bool), not silently swallowed."""
    store = OperationStore()
    assert store.update("nope", state="ready") is False
    assert store.get("nope") is None


def test_update_present_op_returns_true() -> None:
    store = OperationStore()
    op_id = store.create("load", "m1")
    assert store.update(op_id, state="loading", phase="spawning") is True
    assert store.get(op_id).state == "loading"
    assert store.get(op_id).phase == "spawning"


def test_snapshot_is_a_copy() -> None:
    """Mutating a returned snapshot must not corrupt the stored operation —
    the poll path hands dicts to clients; a torn or shared view would let a
    reader observe half-updated fields or write through the response."""
    store = OperationStore()
    op_id = store.create("load", "m1")
    store.update(op_id, state="loading", phase="spawning", message="work")
    snap = store.snapshot(op_id)
    snap["state"] = "ready"
    snap["message"] = "tampered"
    assert store.get(op_id).state == "loading"
    assert store.get(op_id).message == "work"
    assert store.snapshot(op_id)["message"] == "work"


def test_get_returns_a_copy() -> None:
    """Mutating a returned get() result must not corrupt the stored operation —
    get() hands out a copy, like snapshot(), so a reader cannot write through
    the live registry outside the lock."""
    store = OperationStore()
    op_id = store.create("load", "m1")
    store.update(op_id, state="loading", phase="spawning", message="work")
    got = store.get(op_id)
    got.state = "ready"
    got.message = "tampered"
    assert store.get(op_id).state == "loading"
    assert store.get(op_id).message == "work"


def test_retention_caps_total_ops() -> None:
    """A long-lived daemon must not grow the registry without bound: completed
    ops are pruned to MAX_OPS on create, oldest first."""
    store = OperationStore()
    last = None
    for i in range(MAX_OPS + 25):
        last = _completed(store, model=f"m{i}")
    assert len(store) <= MAX_OPS
    assert store.get(last) is not None, "the most recent op must survive the prune"


def test_retention_expires_old_completed_ops() -> None:
    """Completed ops older than RETENTION_SECONDS are expired on the next create."""
    store = OperationStore()
    old = _completed(store, model="old")
    real_time = time.time
    time.time = lambda: real_time() + RETENTION_SECONDS + 60
    try:
        new = _completed(store, model="new")  # prune runs on create
    finally:
        time.time = real_time
    assert store.get(old) is None, "completed op past the retention window must be pruned"
    assert store.get(new) is not None


def test_retention_never_prunes_in_flight_ops() -> None:
    """In-flight ops (loading/unloading) are never pruned, no matter how many
    completed ops pile up — a client mid-poll must not lose its operation."""
    store = OperationStore()
    in_flight = store.create("load", "busy")  # state stays "loading"
    for i in range(MAX_OPS + 25):
        _completed(store, model=f"m{i}")
    assert store.get(in_flight) is not None
    assert store.active_for("busy") == in_flight
