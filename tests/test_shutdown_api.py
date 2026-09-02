"""Frozen suite v27: POST /api/shutdown — unload every model, then stop.

Observes only the locked surface (vortex.app:build_app and the declared
management routes). The daemon-stop hook is injected so the stop is observable
without killing the test runner; the unload-all path is exercised against a
real adopted runtime, exactly as tests/test_serve.py does.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog, CatalogEntry
from vortex.lifecycle import _find_listening_pid

TESTS_DIR = Path(__file__).parent


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _entry_for(port: int, public_id: str = "m1") -> CatalogEntry:
    return CatalogEntry(
        public_id=public_id,
        runtime="fake",
        engine="fake",
        launch_command=[sys.executable, "-m", "tests.fake_server", str(port)],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
    )


def _spawn_runtime(port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.fake_server", str(port)],
        cwd=TESTS_DIR.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            import httpx

            if httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=1).status_code == 200:
                return proc
        except Exception:  # noqa: BLE001, S110 — readiness polling loop
            pass
        time.sleep(0.05)
    proc.kill()
    raise RuntimeError("fake runtime did not become ready")


def _adopt_sidecar(path: Path, public_id: str, pid: int, port: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = {
        "pid": pid,
        "start_time": psutil.Process(pid).create_time(),
        "public_id": public_id,
        "port": port,
    }
    (path / f"{public_id}.json").write_text(json.dumps(record), encoding="utf-8")


def _wait_state(client: TestClient, op_id: str, want: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        snap = client.get(f"/api/operations/{op_id}").json()
        if snap["state"] == want:
            return snap
        time.sleep(0.05)
    raise AssertionError(f"operation {op_id} never reached {want!r}")


def test_shutdown_signals_stop_and_reports_nothing_loaded(tmp_path: Path) -> None:
    """With nothing loaded, POST /api/shutdown returns stopping:true with an
    empty unloaded list and invokes the injected daemon-stop hook exactly once.
    """
    stops: list[int] = []
    app = build_app(
        catalog=Catalog(entries=[_entry_for(_free_port())]),
        sidecar_dir=tmp_path / "sidecars",
        on_shutdown=lambda: stops.append(1),
    )
    resp = TestClient(app).post("/api/shutdown")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stopping"] is True
    assert body["unloaded"] == []
    assert stops == [1], "the daemon-stop hook must be invoked exactly once"


def test_shutdown_unloads_loaded_model_and_reports_it(tmp_path: Path) -> None:
    """A loaded (adopted) runtime is terminated by POST /api/shutdown: its
    process is gone, its id is returned under `unloaded`, and it is no longer
    advertised — while the injected daemon-stop hook fires. The real process
    makes the unload observable, exactly as test_serve.py does.
    """
    port = _free_port()
    proc = _spawn_runtime(port)
    stops: list[int] = []
    try:
        sidecar_dir = tmp_path / "sidecars"
        _adopt_sidecar(sidecar_dir, "m1", proc.pid, port)
        app = build_app(
            catalog=Catalog(entries=[_entry_for(port)]),
            sidecar_dir=sidecar_dir,
            on_shutdown=lambda: stops.append(1),
        )
        client = TestClient(app)
        op = client.post("/api/models/m1/load").json()["operation"]
        _wait_state(client, op, "ready")
        assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["m1"]

        resp = client.post("/api/shutdown")
        assert resp.status_code == 200
        assert resp.json()["unloaded"] == ["m1"]
        assert stops == [1]
        assert client.get("/v1/models").json()["data"] == []

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _find_listening_pid(port) is not None:
            time.sleep(0.05)
        assert _find_listening_pid(port) is None, "shutdown left a model process running"
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
