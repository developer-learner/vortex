"""End-to-end tests: load/ready, adoption, proxy, unload, refusal, MemoryConflict."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest
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


def _entry(**overrides: object) -> CatalogEntry:
    base: dict[str, object] = {
        "public_id": "m1",
        "runtime": "fake",
        "engine": "fake",
        "launch_command": [sys.executable, "-m", "tests.fake_server", "0"],
        "port": 1,
        "ready_url": "http://127.0.0.1/v1/models",
        "chat_endpoint": "http://127.0.0.1/v1/chat/completions",
    }
    base.update(overrides)
    return CatalogEntry.model_validate(base)


def _entry_for(port: int, public_id: str = "m1", **overrides: object) -> CatalogEntry:
    overrides.setdefault("port", port)
    overrides.setdefault("ready_url", f"http://127.0.0.1:{port}/v1/models")
    overrides.setdefault("chat_endpoint", f"http://127.0.0.1:{port}/v1/chat/completions")
    overrides.setdefault("public_id", public_id)
    return _entry(**overrides)


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


def _client(tmp_path: Path, catalog: Catalog, *, sidecars: Path | None = None,
            adopt: list[tuple[str, int, int]] | None = None) -> TestClient:
    sidecar_dir = sidecars or (tmp_path / "sidecars")
    for public_id, pid, port in adopt or []:
        _adopt_sidecar(sidecar_dir, public_id, pid, port)
    app = build_app(catalog=catalog, sidecar_dir=sidecar_dir)
    return TestClient(app)


def _wait_state(client: TestClient, op_id: str, want: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        snap = client.get(f"/api/operations/{op_id}").json()
        if snap["state"] == want:
            return snap
        time.sleep(0.05)
    raise AssertionError(f"operation {op_id} never reached {want!r}")


@pytest.fixture()
def runtime():
    """A real child process serving the fake chat API on a fixed free port."""
    port = _free_port()
    proc = _spawn_runtime(port)
    yield port, proc
    proc.kill()
    proc.wait(timeout=5)


def test_unidentified_occupant_refused(runtime: tuple[int, subprocess.Popen], tmp_path: Path) -> None:
    """A process on a configured port with no sidecar must never be claimed."""
    port, _proc = runtime
    catalog = Catalog(entries=[_entry_for(port)])
    client = _client(tmp_path, catalog)
    assert client.get("/api/catalog").json()["entries"][0]["state"] == "unloaded"
    resp = client.post("/api/models/m1/load")
    assert resp.status_code == 409
    assert "unidentified" in resp.json()["detail"]
    assert client.get("/v1/models").json()["data"] == []


def test_adopt_surviving_runtime_and_load(runtime: tuple[int, subprocess.Popen], tmp_path: Path) -> None:
    """Sidecar-identified runtime = adoption on load; then it serves /v1."""
    port, _proc = runtime
    catalog = Catalog(entries=[_entry_for(port)])
    client = _client(tmp_path, catalog, adopt=[("m1", _proc.pid, port)])
    resp = client.post("/api/models/m1/load")
    assert resp.status_code == 202
    op = _wait_state(client, resp.json()["operation"], "ready")
    assert op["state"] == "ready"
    assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["m1"]


def _runtime_pid(port: int) -> int:
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if "tests.fake_server" in " ".join(proc.info["cmdline"] or []) and str(port) in proc.info["cmdline"]:
                return proc.pid
        except (psutil.ZombieProcess, psutil.AccessDenied):
            continue
    raise AssertionError(f"no fake runtime process found for port {port}")


def test_proxy_non_streaming(runtime: tuple[int, subprocess.Popen], tmp_path: Path) -> None:
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port)])
    client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, port)])
    client.post("/api/models/m1/load")
    resp = client.post("/v1/chat/completions", json={
        "model": "m1",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "hello from fake"
    assert resp.json()["usage"]["total_tokens"] == 8


def test_proxy_streaming_passthrough(runtime: tuple[int, subprocess.Popen], tmp_path: Path) -> None:
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port)])
    client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, port)])
    client.post("/api/models/m1/load")
    resp = client.post("/v1/chat/completions", json={
        "model": "m1",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.text.count("data:") >= 2
    assert "DONE" in resp.text


def test_proxy_unloaded_model_404(tmp_path: Path) -> None:
    """An entry with no occupant and no sidecar is 'unloaded' — proxy rejects."""
    catalog = Catalog(entries=[_entry_for(_free_port())])
    client = _client(tmp_path, catalog)
    assert client.get("/api/catalog").json()["entries"][0]["state"] == "unloaded"
    resp = client.post("/v1/chat/completions", json={
        "model": "m1",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 404
    assert "not loaded" in resp.json()["detail"]
    assert client.post("/v1/chat/completions", json={
        "model": "does-not-exist",
        "messages": [],
    }).status_code == 404


def test_unload_terminates_child(runtime: tuple[int, subprocess.Popen], tmp_path: Path) -> None:
    """Unload of an adopted runtime terminates the child and frees the port."""
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port)])
    client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, port)])
    client.post("/api/models/m1/load")
    resp = client.post("/api/models/m1/unload")
    assert resp.status_code == 202
    op = _wait_state(client, resp.json()["operation"], "unloaded")
    assert op["state"] == "unloaded"
    assert client.get("/v1/models").json()["data"] == []
    proc.wait(timeout=10)
    assert proc.poll() is not None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _find_listening_pid(port) is not None:
        time.sleep(0.05)
    assert _find_listening_pid(port) is None


def test_spawn_from_launch_command(tmp_path: Path) -> None:
    """True spawn path: launch_command boots a server; unload frees the port."""
    port = _free_port()
    catalog = Catalog(entries=[_entry(
        public_id="m1",
        launch_command=[sys.executable, "-m", "tests.fake_server", str(port)],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
    )])
    client = _client(tmp_path, catalog)
    resp = client.post("/api/models/m1/load")
    assert resp.status_code == 202
    op = _wait_state(client, resp.json()["operation"], "ready")
    assert op["state"] == "ready"
    assert client.get("/v1/models").json()["data"], "spawned runtime should be advertised"
    client.post("/api/models/m1/unload")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        r = client.get("/api/catalog").json()["entries"][0]
        if r["state"] == "unloaded" and r["port_pid"] is None:
            break
        time.sleep(0.1)
    assert client.get("/api/catalog").json()["entries"][0]["port_pid"] is None


def test_load_conflict_reports_eviction(tmp_path: Path) -> None:
    """Structured 409: required size + eviction candidates (never auto-evict)."""
    runtime = _free_port()
    proc = _spawn_runtime(runtime)
    try:
        catalog = Catalog(entries=[
            _entry_for(runtime, public_id="m1", ram_estimate_gb=5),
            _entry_for(runtime, public_id="m2", ram_estimate_gb=1e6),
        ])
        client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, runtime)])
        assert client.post("/api/models/m1/load").status_code == 202
        resp = client.post("/api/models/m2/load")
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["required_gb"] == 1e6
        assert "m1" in detail["eviction_candidates"]
        assert client.get("/v1/models").json()["data"]  # m1 still there
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_unknown_model_load_404(tmp_path: Path) -> None:
    client = _client(tmp_path, Catalog())
    assert client.post("/api/models/nope/load").status_code == 404
    assert client.get("/api/operations/nope").status_code == 404
    assert client.get("/api/status").json()["loaded"] == []