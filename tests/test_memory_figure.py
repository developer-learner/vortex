"""Frozen suite: the displayed memory figure has ONE named source, and it is
at parity with testchat's memory surface (CEO 2026-09-15).

The 2026-08-17 anomaly (two unlabeled sources blended behind one function)
was fixed by naming the source. The 2026-09-15 parity change fixes the page
SET: the used figure is the working set (active + wired + compressor) only —
NOT inactive + speculative, which are reclaimable file cache that inflated the
number by tens of GB. That is the set testchat reports and the one macOS
Activity Monitor's "Memory Used" tracks; it supersedes the 2026-08-17 note
that summed inactive + speculative too. The per-model RSS and loadable figures
mirror testchat's status surface.
"""

from fastapi.testclient import TestClient

import vortex.memory as memory_module
from vortex.app import build_app
from vortex.catalog import Catalog
from vortex.memory import (
    _activity_monitor_used_gb,
    _ram_used,
    loadable_gb,
    model_rss_gb,
)


def _fake_run(stdout):
    return lambda *a, **k: type("R", (), {"stdout": stdout, "returncode": 0})()


def test_activity_monitor_parse_matches_the_vm_stat_arithmetic(
    monkeypatch,
) -> None:
    """vm_stat pages-to-GB arithmetic is pinned exactly: page size 16384,
    summing active + wired + compressor (the working set, testchat parity)."""
    canned = (
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
        "Pages free:                              53177.\n"
        "Pages active:                          2957161.\n"
        "Pages inactive:                        1828609.\n"
        "Pages speculative:                      465819.\n"
        "Pages wired down:                      1396963.\n"
        "Pages occupied by compressor:           702144."
    )
    monkeypatch.setattr(memory_module.subprocess, "run", _fake_run(canned))
    expected = (2957161 + 1396963 + 702144) * 16384 / 1024**3
    got = _activity_monitor_used_gb()
    assert abs(got - expected) < 1e-9, (got, expected)


def test_used_figure_excludes_reclaimable_cache(monkeypatch) -> None:
    """Parity pin (2026-09-15): inactive + speculative pages are reclaimable
    cache and MUST NOT be counted in the used figure — this is the whole
    ~114GB-vs-~65GB divergence from testchat. Large cache pages here must not
    move the result."""
    canned = (
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
        "Pages free:                              10000.\n"
        "Pages active:                            100000.\n"
        "Pages inactive:                         9000000.\n"
        "Pages speculative:                      8000000.\n"
        "Pages wired down:                        200000.\n"
        "Pages occupied by compressor:             50000."
    )
    monkeypatch.setattr(memory_module.subprocess, "run", _fake_run(canned))
    working_set = (100000 + 200000 + 50000) * 16384 / 1024**3
    assert abs(_activity_monitor_used_gb() - working_set) < 1e-9


def test_activity_monitor_missing_keys_report_zero(monkeypatch) -> None:
    """An unreadable vm_stat output must report 0.0 (degraded source), never
    a partial sum that silently understates usage."""
    monkeypatch.setattr(
        memory_module.subprocess, "run", _fake_run("Pages free: 1.\n")
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


def test_model_rss_gb_reads_ps_output(monkeypatch) -> None:
    """A loaded model's RSS (KB from `ps -o rss=`) is reported in GB."""
    monkeypatch.setattr(memory_module.subprocess, "run", _fake_run("  45088768\n"))
    assert abs(model_rss_gb(4321) - 45088768 / 1024**2) < 1e-9


def test_model_rss_gb_none_pid_is_zero() -> None:
    """A model with no known pid reports 0.0, never a stale or wrong figure."""
    assert model_rss_gb(None) == 0.0


def test_model_rss_gb_unreadable_is_zero(monkeypatch) -> None:
    """A dead/unknown process (empty ps output) reports 0.0, not a crash."""
    monkeypatch.setattr(memory_module.subprocess, "run", _fake_run(""))
    assert model_rss_gb(999999) == 0.0


def test_loadable_gb_bounds_reclaimable_by_wired_limit(monkeypatch) -> None:
    """loadable_gb mirrors testchat: reclaimable (free+speculative+purgeable+
    file-backed) bounded by the GPU wired-limit headroom, minus a 4GB buffer."""
    page = 16384
    vm_stat = (
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
        "Pages free:                             100000.\n"
        "Pages purgeable:                         20000.\n"
        "Pages speculative:                       50000.\n"
        "File-backed pages:                      200000.\n"
        "Pages wired down:                      1396963."
    )

    def run(cmd, *a, **k):
        joined = " ".join(cmd)
        if "hw.memsize" in joined:
            return _fake_run("137438953472\n")()
        if "iogpu.wired_limit_mb" in joined:
            return _fake_run("122880\n")()
        if joined == "vm_stat":
            return _fake_run(vm_stat)()
        raise AssertionError("unexpected command: " + joined)

    monkeypatch.setattr(memory_module.subprocess, "run", run)
    total_gb = 137438953472 / 1024**3
    reclaimable = (100000 + 50000 + 20000 + 200000) * page / 1024**3
    wired = 1396963 * page / 1024**3
    cap = 122880 / 1024
    expected = max(0.0, min(reclaimable, cap - wired) - 4.0)
    assert abs(loadable_gb() - expected) < 1e-9
    assert total_gb == 128.0  # sanity: the canned host is a 128 GiB machine


def test_loadable_gb_failure_reports_zero(monkeypatch) -> None:
    """Any failure computing the figure reports 0.0 — the operator sees no
    figure rather than a wrong one."""
    def boom(*a, **k):
        raise OSError("sysctl gone")

    monkeypatch.setattr(memory_module.subprocess, "run", boom)
    assert loadable_gb() == 0.0


def test_status_api_carries_memory_source_and_parity_figures(tmp_path) -> None:
    """The status surface names its memory source and carries the parity
    figures: a top-level loadable_gb and a loaded list (each entry gains
    rss_gb once a model is ready)."""
    client = TestClient(build_app(catalog=Catalog(entries=[]), sidecar_dir=tmp_path / "s"))
    body = client.get("/api/status").json()
    assert body["ram_source"] in {"vm_stat", "psutil"}
    assert isinstance(body["ram_used_gb"], (int, float))
    assert isinstance(body["loadable_gb"], (int, float))
    assert body["loaded"] == []


# The historical node-id the pin gate maps to app.py; kept as a stable alias so
# contracts.test_mapping continues to reference a frozen family (D-175 freeze).
def test_status_api_names_the_memory_source(tmp_path) -> None:
    client = TestClient(build_app(catalog=Catalog(entries=[]), sidecar_dir=tmp_path / "s"))
    body = client.get("/api/status").json()
    assert body["ram_source"] in {"vm_stat", "psutil"}
    assert isinstance(body["ram_used_gb"], (int, float))
    assert isinstance(body["loadable_gb"], (int, float))
