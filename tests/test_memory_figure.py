"""Frozen suite: the displayed memory figure has ONE named source.

The 2026-08-17 anomaly (daemon reported psutil-used ~111GB while Activity
Monitor / `top` PhysMem showed ~126GB) came from two unlabeled sources
blended behind one function. The CEO ruling (tasks/CURRENT.md 2026-08-17):
the Activity Monitor figure is the truth the UI reports; psutil-used may
exist only as an explicitly-labeled degraded source (Linux hosts), never as
a silent flip of the same number.
"""

from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog
from vortex.memory import _activity_monitor_used_gb, _ram_used

import vortex.memory as memory_module


def test_activity_monitor_parse_matches_the_vm_stat_arithmetic(
    monkeypatch,
) -> None:
    """vm_stat pages-to-GB arithmetic is pinned exactly: page size 16384,
    summing active+inactive+speculative+wired+compressor."""
    canned = "\n".join([
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)",
        "Pages free:                              53177.",
        "Pages active:                          2957161.",
        "Pages inactive:                        1828609.",
        "Pages speculative:                      465819.",
        "Pages wired down:                      1396963.",
        "Pages occupied by compressor:           702144.",
    ])
    monkeypatch.setattr(
        memory_module.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": canned, "returncode": 0})(),
    )
    expected = (
        (2957161 + 1828609 + 465819 + 1396963 + 702144) * 16384 / 1024**3
    )
    got = _activity_monitor_used_gb()
    assert abs(got - expected) < 1e-9, (got, expected)


def test_activity_monitor_missing_keys_report_zero(monkeypatch) -> None:
    """An unreadable vm_stat output must report 0.0 (degraded source), never
    a partial sum that silently understates usage."""
    monkeypatch.setattr(
        memory_module.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": "Pages free: 1.\n", "returncode": 0})(),
    )
    assert _activity_monitor_used_gb() == 0.0


def test_ram_used_prefers_vm_stat_and_names_it() -> None:
    saved = memory_module._activity_monitor_used_gb
    memory_module._activity_monitor_used_gb = lambda: 100.0  # type: ignore[assignment]
    try:
        value, source = _ram_used()
    finally:
        memory_module._activity_monitor_used_gb = saved  # type: ignore[assignment]
    assert value == 100.0
    assert source == "vm_stat"


def test_psutil_fallback_is_labeled_never_silent(monkeypatch) -> None:
    """When vm_stat is unavailable (non-macOS host), the figure still computes
    — but the caller can see it switched basis instead of being surprised by
    a ~15GB jump with no explanation."""
    monkeypatch.setattr(memory_module, "_activity_monitor_used_gb", lambda: 0.0)
    value, source = _ram_used()
    assert source == "psutil"
    assert value > 0.0


def test_status_api_names_the_memory_source(tmp_path) -> None:
    client = TestClient(build_app(catalog=Catalog(entries=[]), sidecar_dir=tmp_path / "s"))
    body = client.get("/api/status").json()
    assert body["ram_source"] in {"vm_stat", "psutil"}
    assert isinstance(body["ram_used_gb"], (int, float))
