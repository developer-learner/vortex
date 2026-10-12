"""Regression: a load that outlives the run's op cap must not leave the model
loaded.

The speed-run invariant is "every model ends in the load state it started in".
If a load is still in flight when the run's per-op cap expires, the run marks
the model failed and moves on — but if the load later succeeds, a background
reconciler must unload it again. Without the reconciler the model would sit
loaded while the speed page says "failed: load timed out".
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import psutil
import pytest

from vortex import speed_runner
from vortex.catalog import Catalog, CatalogEntry
from vortex.lifecycle import Lifecycle, SidecarStore, _find_listening_pid
from vortex.manager import Manager
from vortex.operations import OperationStore
from vortex.speed_runner import SpeedRun


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _cleanup(port: int) -> None:
    pid = _find_listening_pid(port)
    if isinstance(pid, int):
        try:
            psutil.Process(pid).kill()
        except psutil.Error:
            pass


def test_late_load_success_is_unloaded_by_reconciler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shorten the run's per-op cap so the test does not wait 45s; the fake
    # server starts serving after 3s, i.e. AFTER the cap has expired.
    monkeypatch.setattr(speed_runner, "_OP_WAIT_SECONDS", 1.5)
    port = _free_port()
    entry = CatalogEntry(
        public_id="slow",
        runtime="fake",
        engine="fake",
        launch_command=[sys.executable, "-m", "tests.fake_server", str(port), "0", "200", "3"],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
        ram_estimate_gb=1.0,
    )
    catalog = Catalog(entries=[entry])
    sidecars = SidecarStore(tmp_path / "sidecars")
    ops = OperationStore()
    manager = Manager(catalog, Lifecycle(catalog, sidecars), ops)
    run = SpeedRun(catalog, manager, ops, tmp_path / "speed-results.json")
    try:
        run.start(["slow"])
        deadline = time.monotonic() + 10
        while run.running and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not run.running, "the run did not finish at the op cap"
        row = run.rows()["slow"]
        assert row["status"] == "failed", row
        assert row["message"] == "load timed out", row

        # The load op is still in flight when the run gave up — the reconciler
        # is watching it. Grab its id now, while it is still "loading".
        op_id = ops.active_for("slow")
        assert op_id is not None, "the load op was already gone when the run gave up"

        # The late load succeeds (~3s): the op reaches "ready", proving the
        # model is now loaded despite the run having given up on it.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            snap = ops.snapshot(op_id)
            if snap is not None and snap["state"] == "ready":
                break
            time.sleep(0.05)
        snap = ops.snapshot(op_id)
        assert snap is not None and snap["state"] == "ready", (
            f"the late load never succeeded (op state: {snap and snap['state']!r})"
        )

        # Then the reconciler must unload it again, so the model ends in the
        # state the run found it in: not serving, no sidecar. The sidecar is
        # dropped only after terminate's kill-wait settles (up to the 5s grace
        # period, since the killed child is not reaped by this test process),
        # so wait for both conditions with one generous deadline.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if _find_listening_pid(port) is None and sidecars.read("slow") is None:
                break
            time.sleep(0.2)
        assert _find_listening_pid(port) is None, (
            "reconciler left the late-loaded model running"
        )
        assert sidecars.read("slow") is None, "reconciler left the sidecar behind"
    finally:
        _cleanup(port)
