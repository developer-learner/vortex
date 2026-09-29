"""Frozen suite v38: POST /api/restart — unload every model, then relaunch.

Observes only the locked surface (vortex.app:build_app and the declared
management routes). The restart and shutdown hooks are injected so the
behaviour is observable without killing or relaunching the test runner; the
unload path runs against a real adopted runtime, exactly as
tests/test_shutdown_api.py does.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
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


def _entry(port: int, launch_command: list[str], public_id: str = "m1") -> CatalogEntry:
    return CatalogEntry(
        public_id=public_id,
        runtime="fake",
        engine="fake",
        launch_command=launch_command,
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
    )


def _fake_entry(port: int) -> CatalogEntry:
    return _entry(port, [sys.executable, "-m", "tests.fake_server", str(port)])


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


def _kill_marked(marker: str) -> None:
    for p in psutil.process_iter(["cmdline"]):
        try:
            if marker in (p.info.get("cmdline") or []):
                p.kill()
        except psutil.Error:  # the process may already be gone
            continue


def test_restart_with_nothing_loaded_invokes_only_the_restart_hook(tmp_path: Path) -> None:
    """With nothing loaded, POST /api/restart returns restarting:true with an
    empty unloaded list, invokes the restart hook exactly once, and never the
    shutdown hook (AC-18, AC-19)."""
    restarts: list[int] = []
    stops: list[int] = []
    app = build_app(
        catalog=Catalog(entries=[_fake_entry(_free_port())]),
        sidecar_dir=tmp_path / "sidecars",
        on_shutdown=lambda: stops.append(1),
        on_restart=lambda: restarts.append(1),
    )
    resp = TestClient(app).post("/api/restart")
    assert resp.status_code == 200
    assert resp.json() == {"restarting": True, "unloaded": []}
    assert restarts == [1], "the restart hook must be invoked exactly once"
    assert stops == [], "restart must not invoke the shutdown hook"


def test_shutdown_never_invokes_the_restart_hook(tmp_path: Path) -> None:
    """POST /api/shutdown stays a plain stop: the restart hook is not called
    (AC-19)."""
    restarts: list[int] = []
    stops: list[int] = []
    app = build_app(
        catalog=Catalog(entries=[_fake_entry(_free_port())]),
        sidecar_dir=tmp_path / "sidecars",
        on_shutdown=lambda: stops.append(1),
        on_restart=lambda: restarts.append(1),
    )
    resp = TestClient(app).post("/api/shutdown")
    assert resp.status_code == 200
    assert stops == [1]
    assert restarts == [], "shutdown must not invoke the restart hook"


def test_restart_unloads_loaded_model_and_reports_it(tmp_path: Path) -> None:
    """A loaded (adopted) runtime is terminated by POST /api/restart: its id is
    returned under `unloaded`, it is no longer advertised, its port closes,
    and the restart hook fires once (AC-18)."""
    port = _free_port()
    proc = _spawn_runtime(port)
    restarts: list[int] = []
    try:
        sidecar_dir = tmp_path / "sidecars"
        _adopt_sidecar(sidecar_dir, "m1", proc.pid, port)
        app = build_app(
            catalog=Catalog(entries=[_fake_entry(port)]),
            sidecar_dir=sidecar_dir,
            on_shutdown=lambda: None,
            on_restart=lambda: restarts.append(1),
        )
        client = TestClient(app)
        op = client.post("/api/models/m1/load").json()["operation"]
        _wait_state(client, op, "ready")
        assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["m1"]

        resp = client.post("/api/restart")
        assert resp.status_code == 200
        assert resp.json() == {"restarting": True, "unloaded": ["m1"]}
        assert restarts == [1]
        assert client.get("/v1/models").json()["data"] == []

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _find_listening_pid(port) is not None:
            time.sleep(0.05)
        assert _find_listening_pid(port) is None, "restart left a model process running"
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_restart_is_refused_while_an_operation_is_in_flight(tmp_path: Path) -> None:
    """While a load is still in flight, POST /api/restart answers 409 busy with
    the operation id and neither restarts nor touches the load (AC-20)."""
    marker = f"vortex-v38-inflight-{uuid.uuid4().hex}"
    port = _free_port()
    never_ready = [sys.executable, "-c", "import time; time.sleep(60)", marker]
    restarts: list[int] = []
    try:
        app = build_app(
            catalog=Catalog(entries=[_entry(port, never_ready)]),
            sidecar_dir=tmp_path / "sidecars",
            on_shutdown=lambda: None,
            on_restart=lambda: restarts.append(1),
        )
        client = TestClient(app)
        load = client.post("/api/models/m1/load")
        assert load.status_code == 202
        op = load.json()["operation"]
        assert client.get(f"/api/operations/{op}").json()["state"] == "loading"

        resp = client.post("/api/restart")
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["busy"] is True
        assert detail["operation"] == op
        assert restarts == [], "a refused restart must not invoke the restart hook"
        assert client.get(f"/api/operations/{op}").json()["state"] == "loading"
    finally:
        _kill_marked(marker)
