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
from vortex.lifecycle import Lifecycle, SidecarStore, SpawnError, _find_listening_pid
from vortex.manager import Manager
from vortex.operations import OperationStore

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


def _spawn_unhealthy_runtime(port: int) -> subprocess.Popen:
    """Start a fake runtime that 200s GET /v1/models but 503s every chat call.

    Mirrors `_spawn_runtime` but passes anneal_failures=-1 (chat never
    succeeds — the llama-server phantom-ready class, D-174). Waits for
    GET /v1/models to answer 200 before returning, so the runtime is genuinely
    adoptable: a healthy models endpoint over a dead inference path.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.fake_server", str(port), "-1"],
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
    raise RuntimeError("unhealthy fake runtime did not answer /v1/models")


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


def _received_models(port: int) -> list[str]:
    import httpx

    return httpx.get(f"http://127.0.0.1:{port}/mock/received", timeout=2).json()["models"]


def test_proxy_non_streaming_remaps_public_id_to_upstream_alias(
    runtime: tuple[int, subprocess.Popen], tmp_path: Path
) -> None:
    """A client calls the public_id; the runtime must be addressed by upstream_alias.

    public_id and upstream_alias deliberately differ — the audit's regression shape.
    """
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port, public_id="pub-x", upstream_alias="up-x")])
    client = _client(tmp_path, catalog, adopt=[("pub-x", proc.pid, port)])
    op = client.post("/api/models/pub-x/load").json()["operation"]
    _wait_state(client, op, "ready")

    before = len(_received_models(port))
    resp = client.post("/v1/chat/completions", json={
        "model": "pub-x",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200
    forwarded = _received_models(port)[before:]
    assert "up-x" in forwarded, "runtime must receive the upstream_alias"
    assert "pub-x" not in forwarded, "the public_id must never reach the runtime"


def test_proxy_streaming_remaps_public_id_to_upstream_alias(
    runtime: tuple[int, subprocess.Popen], tmp_path: Path
) -> None:
    """Remapping must hold for the streaming path too, not only non-streaming."""
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port, public_id="pub-x", upstream_alias="up-x")])
    client = _client(tmp_path, catalog, adopt=[("pub-x", proc.pid, port)])
    op = client.post("/api/models/pub-x/load").json()["operation"]
    _wait_state(client, op, "ready")

    before = len(_received_models(port))
    resp = client.post("/v1/chat/completions", json={
        "model": "pub-x",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    forwarded = _received_models(port)[before:]
    assert "up-x" in forwarded, "runtime must receive the upstream_alias on the streaming path"
    assert "pub-x" not in forwarded, "the public_id must never reach the runtime"


def test_proxy_forwards_public_id_when_no_upstream_alias(
    runtime: tuple[int, subprocess.Popen], tmp_path: Path
) -> None:
    """With no upstream_alias configured, the forwarded model is the public_id."""
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port, public_id="solo")])  # upstream_alias defaults to None
    client = _client(tmp_path, catalog, adopt=[("solo", proc.pid, port)])
    op = client.post("/api/models/solo/load").json()["operation"]
    _wait_state(client, op, "ready")

    before = len(_received_models(port))
    resp = client.post("/v1/chat/completions", json={
        "model": "solo",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200
    assert _received_models(port)[before:] == ["solo"]


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


def _ops_wait(ops: OperationStore, op_id: str, want: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        snap = ops.snapshot(op_id)
        if snap is not None and snap["state"] == want:
            return snap
        time.sleep(0.05)
    raise AssertionError(f"operation {op_id} never reached {want!r}")


def test_spawn_waits_for_anneal_before_ready(tmp_path: Path) -> None:
    """Phantom-ready class (D-174): /v1/models 200s immediately while chat
    answers 503 — load must NOT complete until a real completion succeeds."""
    port = _free_port()
    catalog = Catalog(entries=[_entry(
        public_id="m1",
        launch_command=[sys.executable, "-m", "tests.fake_server", str(port), "2"],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
    )])
    ops = OperationStore()
    mgr = Manager(catalog, Lifecycle(catalog, SidecarStore(tmp_path / "sidecars"), ready_timeout=lambda: 30.0), ops)
    op_id = mgr.load("m1")["operation"]
    assert _ops_wait(ops, op_id, "ready")["state"] == "ready"
    import httpx

    received = httpx.get(f"http://127.0.0.1:{port}/mock/received", timeout=2).json()
    assert received["chat_calls"] == 3, "2 anneal probes must 503, then one must succeed"


def test_spawn_fails_when_chat_never_succeeds(tmp_path: Path) -> None:
    """A runtime whose chat never leaves 503 must fail the load, not go ready.

    v22 reconciliation: the lifecycle now cleans up the failed process at
    spawn failure, so the mock server is no longer reachable after the load
    fails — this test no longer queries it. The post-failure cleanup itself
    is pinned by test_failed_spawn_leaves_no_owned_process_or_sidecar (C1).
    """
    port = _free_port()
    catalog = Catalog(entries=[_entry(
        public_id="m1",
        launch_command=[sys.executable, "-m", "tests.fake_server", str(port), "-1"],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
    )])
    ops = OperationStore()
    mgr = Manager(catalog, Lifecycle(catalog, SidecarStore(tmp_path / "sidecars"), ready_timeout=lambda: 2.0), ops)
    with pytest.raises(SpawnError):
        mgr.load("m1")
    assert ops.active_for("m1") is None, "no lingering loading op"


def test_unhealthy_adoption_never_advertised_ready(tmp_path: Path) -> None:
    """R1: a sidecar-identified runtime that answers GET /v1/models with 200 but
    503s every chat completion must NEVER be advertised ready.

    - GET /v1/models never lists the model, and
    - GET /api/catalog never shows the entry state as 'ready' (it settles to a
      non-ready state such as 'unloaded'/'error').

    Robustness: no assertion on the load POST status, and no assumption that
    load is synchronous — readiness is judged only by polling the observable
    /v1/models and /api/catalog surfaces on a bounded deadline.
    """
    port = _free_port()
    proc = _spawn_unhealthy_runtime(port)
    try:
        import httpx

        # Confirm the phantom-ready shape before adopting: models 200s, chat 503s.
        assert httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=2).status_code == 200
        assert httpx.post(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            json={"model": "x", "messages": [{"role": "user", "content": "hi"}]},
            timeout=2,
        ).status_code == 503

        catalog = Catalog(entries=[_entry_for(port)])
        client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, port)])

        # Fire the load; do not depend on its status or on synchronous completion.
        # A failed load returns an HTTP error RESPONSE (not a raised exception),
        # so no catch is needed — an actual exception should fail the test.
        client.post("/api/models/m1/load")

        deadline = time.monotonic() + 10
        final_state = None
        while time.monotonic() < deadline:
            ids = [m["id"] for m in client.get("/v1/models").json()["data"]]
            final_state = client.get("/api/catalog").json()["entries"][0]["state"]
            assert "m1" not in ids, (
                f"unhealthy runtime was advertised in /v1/models "
                f"(catalog state={final_state!r})"
            )
            assert final_state != "ready", "unhealthy runtime shown 'ready' in /api/catalog"
            time.sleep(0.2)
        assert final_state != "ready", "unhealthy runtime settled to 'ready'"
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_failed_spawn_leaves_no_owned_process_or_sidecar(tmp_path: Path) -> None:
    """C1: a spawned runtime (launch_command path, not adoption) whose chat never
    succeeds within the ready timeout must FAIL the load and leave strict cleanup:

    - no process is listening on the port, and
    - the entry's sidecar record is gone.

    Mirrors `test_spawn_fails_when_chat_never_succeeds` (which pins SpawnError)
    but additionally pins the post-failure cleanup. New test; the original is
    left untouched.
    """
    port = _free_port()
    sidecar_dir = tmp_path / "sidecars"
    catalog = Catalog(entries=[_entry(
        public_id="m1",
        launch_command=[sys.executable, "-m", "tests.fake_server", str(port), "-1"],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
    )])
    ops = OperationStore()
    mgr = Manager(
        catalog,
        Lifecycle(catalog, SidecarStore(sidecar_dir), ready_timeout=lambda: 2.0),
        ops,
    )
    try:
        with pytest.raises(SpawnError):
            mgr.load("m1")
        # Allow for asynchronous teardown: poll the port free on a bounded deadline.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _find_listening_pid(port) is not None:
            time.sleep(0.05)
        assert _find_listening_pid(port) is None, "failed spawn left a process on the port"
        assert SidecarStore(sidecar_dir).read("m1") is None, "failed spawn left a sidecar record"
    finally:
        pid = _find_listening_pid(port)
        if pid is not None:
            try:
                psutil.Process(pid).terminate()
            except psutil.Error:
                pass


def test_steady_state_reads_do_not_probe_runtime(
    runtime: tuple[int, subprocess.Popen], tmp_path: Path
) -> None:
    """NREG: once a healthy adopted model is ready, repeatedly polling
    GET /api/catalog and GET /v1/models must NOT cause additional chat
    completions to the runtime. Guards against a fix that wires an inference
    probe into the per-request/per-poll read paths.
    """
    port, proc = runtime
    catalog = Catalog(entries=[_entry_for(port)])
    client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, port)])
    op = client.post("/api/models/m1/load").json()["operation"]
    _wait_state(client, op, "ready")
    assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["m1"]

    import httpx

    def _chat_calls() -> int:
        return httpx.get(f"http://127.0.0.1:{port}/mock/received", timeout=2).json()["chat_calls"]

    before = _chat_calls()
    for _ in range(5):
        client.get("/api/catalog")
        client.get("/v1/models")
    after = _chat_calls()
    assert after == before, (
        f"steady-state readiness reads probed the runtime "
        f"({before} -> {after} chat calls)"
    )


def test_unverified_running_model_still_counts_for_admission(tmp_path: Path) -> None:
    """Restart/RAM distinction: a model that is identified and consuming RAM but
    NOT yet verified this session must still participate in admission/eviction
    accounting — even though it is not advertised client-ready. Otherwise Vortex
    undercounts memory and admits a second model the machine cannot hold.

    m1 is adopted (identified, running) but never loaded, so it is unverified:
    absent from /v1/models, yet its RAM must still block an over-subscribing m2.
    """
    total = psutil.virtual_memory().total / (1024 ** 3)
    port = _free_port()
    m2_port = _free_port()
    proc = _spawn_runtime(port)
    try:
        catalog = Catalog(entries=[
            _entry_for(port, public_id="m1", ram_estimate_gb=total * 0.5),
            # m2's launch_command must bind m2_port (not the default ephemeral
            # port), so that if the admission bug wrongly lets m2 load, the spawn
            # becomes ready quickly and the test fails fast instead of blocking on
            # the ready-timeout.
            _entry_for(m2_port, public_id="m2", ram_estimate_gb=total * 0.5,
                       launch_command=[sys.executable, "-m", "tests.fake_server", str(m2_port)]),
        ])
        client = _client(tmp_path, catalog, adopt=[("m1", proc.pid, port)])
        # m1 running but unverified: not client-ready...
        assert client.get("/v1/models").json()["data"] == [], "unverified m1 must not be advertised"
        # ...yet it consumes RAM, so m2 (which only fits if m1 is ignored) is refused.
        resp = client.post("/api/models/m2/load")
        assert resp.status_code == 409, "running-but-unverified m1 must count against admission"
        assert "m1" in resp.json()["detail"]["eviction_candidates"]
    finally:
        for p in (port, m2_port):
            pid = _find_listening_pid(p)
            if pid is not None:
                try:
                    psutil.Process(pid).terminate()
                except psutil.Error:
                    pass
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)