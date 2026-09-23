"""T1 — fail-safe admission under uncertain occupancy (AC-12..AC-17).

A catalog port held by a process Vortex cannot identify, or whose scan was
incomplete, may be using that model's memory. Admission counts such an
entry's catalog RAM estimate — once — without offering it for eviction, and
refuses a load it cannot cover even when nothing is evictable. Unloaded
entries and the load target itself are never counted.

Deterministic: the lifecycle is a small fake and host RAM is pinned to
100 GB, so the admission budget is 80 GB.
"""

from __future__ import annotations

import sys

import pytest

import vortex.manager as manager_mod
from vortex.catalog import Catalog, CatalogEntry
from vortex.lifecycle import SCAN_UNKNOWN
from vortex.manager import Manager, MemoryConflict
from vortex.operations import OperationStore


class _FakeLifecycle:
    """pid per public_id (int / None / SCAN_UNKNOWN) and status per pid; a
    SCAN_UNKNOWN entry holds the status in `held` (default 'unloaded')."""

    def __init__(self, pids: dict, statuses: dict, held: dict | None = None,
                 verified: set | None = None) -> None:
        self.pids = pids
        self.statuses = statuses
        self.held = held or {}
        self.verified = verified or set()

    def occupying_pid(self, entry: CatalogEntry):
        return self.pids.get(entry.public_id)

    def owner_status(self, entry: CatalogEntry, pid) -> str:
        if pid is SCAN_UNKNOWN:
            return self.held.get(entry.public_id, "unloaded")
        if pid is None:
            return "unloaded"
        return self.statuses[pid]

    def is_verified(self, entry: CatalogEntry) -> bool:
        return entry.public_id in self.verified


class _Mem:
    total = 100 * 1024**3


@pytest.fixture(autouse=True)
def _pin_host_ram(monkeypatch):
    monkeypatch.setattr(manager_mod.psutil, "virtual_memory", lambda: _Mem())


def _entry(public_id: str, port: int, ram_gb: float) -> CatalogEntry:
    return CatalogEntry.model_validate({
        "public_id": public_id,
        "runtime": "fake",
        "engine": "fake",
        "launch_command": [sys.executable, "-m", "tests.fake_server", str(port)],
        "port": port,
        "ready_url": f"http://127.0.0.1:{port}/v1/models",
        "chat_endpoint": f"http://127.0.0.1:{port}/v1/chat/completions",
        "ram_estimate_gb": ram_gb,
    })


def _manager(entries: list[CatalogEntry], lifecycle: _FakeLifecycle) -> Manager:
    return Manager(Catalog(entries=entries), lifecycle, OperationStore())


# AC-12 — an incomplete scan on another model's port counts its estimate.
def test_scan_unknown_neighbour_counts_and_refuses_the_load() -> None:
    target = _entry("target", 41001, 40)
    other = _entry("other", 41002, 50)
    mgr = _manager([target, other], _FakeLifecycle({"other": SCAN_UNKNOWN}, {}))
    assert mgr.admits(target) is False
    with pytest.raises(MemoryConflict) as exc:
        mgr.load("target")
    assert exc.value.required_gb == 40
    assert exc.value.candidates == []
    assert mgr.ops.active() is None


# AC-12 — an unidentified occupant counts its estimate the same way.
def test_unidentified_occupant_counts_and_refuses_the_load() -> None:
    target = _entry("target", 41011, 40)
    other = _entry("other", 41012, 50)
    mgr = _manager([target, other], _FakeLifecycle({"other": 777}, {777: "unidentified"}))
    assert mgr.admits(target) is False
    with pytest.raises(MemoryConflict):
        mgr.load("target")


# AC-13 — an uncertain entry is never offered for eviction.
def test_uncertain_entry_is_not_an_eviction_candidate() -> None:
    target = _entry("target", 41021, 40)
    loaded = _entry("loaded", 41022, 30)
    uncertain = _entry("uncertain", 41023, 30)
    life = _FakeLifecycle({"loaded": 501, "uncertain": 777},
                          {501: "ready", 777: "unidentified"}, verified={"loaded"})
    mgr = _manager([target, loaded, uncertain], life)
    assert mgr.admits(target) is False
    assert [e.public_id for e in mgr.eviction_required(target)] == ["loaded"]


# AC-14 — identified-but-unverified and identified-verified still count.
@pytest.mark.parametrize("verified", [set(), {"running"}])
def test_identified_runtime_still_counts(verified: set) -> None:
    target = _entry("target", 41031, 40)
    running = _entry("running", 41032, 50)
    life = _FakeLifecycle({"running": 601}, {601: "ready"}, verified=verified)
    mgr = _manager([target, running], life)
    assert mgr.admits(target) is False
    assert [e.public_id for e in mgr.eviction_required(target)] == ["running"]


# AC-15 — unloaded catalog entries are never counted.
def test_unloaded_entries_do_not_count() -> None:
    target = _entry("target", 41041, 40)
    idle_a = _entry("idle_a", 41042, 50)
    idle_b = _entry("idle_b", 41043, 50)
    mgr = _manager([target, idle_a, idle_b], _FakeLifecycle({}, {}))
    assert mgr.admits(target) is True
    assert mgr.eviction_required(target) == []


# AC-16 — an uncertain entry already held as ready is counted once, not twice.
def test_scan_unknown_entry_held_ready_is_counted_once() -> None:
    target = _entry("target", 41051, 45)
    held = _entry("held", 41052, 30)
    life = _FakeLifecycle({"held": SCAN_UNKNOWN}, {}, held={"held": "ready"})
    mgr = _manager([target, held], life)
    assert mgr.admits(target) is True


# AC-16 — the load target's own port is never counted against itself.
def test_target_is_never_counted_against_itself() -> None:
    target = _entry("target", 41061, 60)
    mgr = _manager([target], _FakeLifecycle({"target": 888}, {888: "unidentified"}))
    assert mgr.admits(target) is True


# AC-17 — a refusal with nothing evictable says why.
def test_refusal_without_candidates_names_the_unidentified_process() -> None:
    target = _entry("target", 41071, 40)
    other = _entry("other", 41072, 50)
    mgr = _manager([target, other], _FakeLifecycle({"other": SCAN_UNKNOWN}, {}))
    with pytest.raises(MemoryConflict) as exc:
        mgr.load("target")
    message = str(exc.value)
    assert "cannot identify" in message
    assert "other" in message
