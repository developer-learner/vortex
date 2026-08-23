"""Regression pin for the tri-state port scan (2026-08-18 flap anomaly class).

`_scan_port` must distinguish three outcomes — a found listener, a CLEAN empty
port (`None`), and an INCOMPLETE scan (`SCAN_UNKNOWN`) — so callers can fail
closed on uncertainty instead of mistaking "couldn't check" for "empty". The
old two-state scan returned `None` on an incomplete scan, which callers read
as "unloaded" and which drove the sidecar-drop -> 409 cascade.

See src/vortex/lifecycle.py and tasks/REFREEZE-SCOPE-coverage.md.
"""

from __future__ import annotations

import psutil
import pytest

from vortex import lifecycle


def test_scan_port_reports_unknown_on_transient_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A visible process raising a transient psutil.Error makes the scan
    incomplete — it must report SCAN_UNKNOWN, never a false None."""

    class _FlakyProc:
        def net_connections(self, kind: str | None = None) -> list:
            raise psutil.Error("transient syscall failure")

    monkeypatch.setattr(
        lifecycle.psutil, "process_iter", lambda attrs: iter([_FlakyProc()])
    )
    monkeypatch.setattr(lifecycle.time, "sleep", lambda s: None)
    assert lifecycle._scan_port(1) is lifecycle.SCAN_UNKNOWN


def test_scan_port_clean_empty_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean scan with no listener returns None (port truly free)."""

    class _QuietProc:
        def net_connections(self, kind: str | None = None) -> list:
            return []

    monkeypatch.setattr(
        lifecycle.psutil, "process_iter", lambda attrs: iter([_QuietProc()])
    )
    assert lifecycle._scan_port(1) is None


def test_scan_port_skips_access_denied_as_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AccessDenied on another user's process is permanent on macOS and must
    NOT count as incompleteness — a scan seeing only such processes is clean."""

    class _ForeignProc:
        def net_connections(self, kind: str | None = None) -> list:
            raise psutil.AccessDenied(13, "operation not permitted")

    monkeypatch.setattr(
        lifecycle.psutil, "process_iter", lambda attrs: iter([_ForeignProc()])
    )
    assert lifecycle._scan_port(1) is None
