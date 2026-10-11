"""Frozen suite v45: a speed-test run tests up to three models in turn (AC-42..AC-45).

Observes `vortex.speed_runner.SpeedRun` driving the real Manager, Lifecycle,
SidecarStore and OperationStore against real child processes running the fake
OpenAI server, so loading, testing and unloading are all real.
"""

from __future__ import annotations

import socket
import sys
import time
import uuid
from pathlib import Path

import httpx
import psutil
import pytest
from vortex.speed_runner import SpeedRun, SpeedRunBusy
from vortex.speedtest import load_results

from vortex.catalog import Catalog, CatalogEntry
from vortex.lifecycle import Lifecycle, SidecarStore, _find_listening_pid
from vortex.manager import Manager
from vortex.operations import OperationStore

TESTS_DIR = Path(__file__).parent


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _entry(public_id: str, port: int, launch: list[str], ram_gb: float | None = 1.0) -> CatalogEntry:
    return CatalogEntry(
        public_id=public_id,
        runtime="fake",
        engine="fake",
        launch_command=launch,
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
        ram_estimate_gb=ram_gb,
    )


def _fake(public_id: str, port: int, ram_gb: float | None = 1.0) -> CatalogEntry:
    return _entry(public_id, port, [sys.executable, "-m", "tests.fake_server", str(port)], ram_gb)


def _setup(tmp_path: Path, entries: list[CatalogEntry]) -> tuple[Catalog, Manager, OperationStore, SpeedRun, Path]:
    catalog = Catalog(entries=entries)
    ops = OperationStore()
    manager = Manager(catalog, Lifecycle(catalog, SidecarStore(tmp_path / "sidecars")), ops)
    results = tmp_path / "speed-results.json"
    return catalog, manager, ops, SpeedRun(catalog, manager, ops, results), results


def _finish(run: SpeedRun, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not run.running:
            return run.rows()
        time.sleep(0.05)
    raise AssertionError("the speed-test run never finished")


def _wait_op(ops: OperationStore, op_id: str, want: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        snap = ops.snapshot(op_id)
        if snap is not None and snap["state"] == want:
            return
        time.sleep(0.05)
    raise AssertionError(f"operation {op_id} never reached {want!r}")


def _cleanup(*ports: int) -> None:
    for port in ports:
        pid = _find_listening_pid(port)
        if isinstance(pid, int):
            try:
                psutil.Process(pid).kill()
            except psutil.Error:
                pass


def _kill_marked(marker: str, timeout: float = 15.0) -> None:
    """Kill the process carrying `marker` once it exists. The run launches it
    on a background thread, so killing before it starts would miss it and
    leave a 60 s sleeper the load waits on."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = False
        for p in psutil.process_iter(["cmdline"]):
            try:
                if marker in (p.info.get("cmdline") or []):
                    p.kill()
                    found = True
            except psutil.Error:
                continue
        if found:
            return
        time.sleep(0.05)


def test_unloaded_model_is_loaded_tested_and_unloaded_again(tmp_path: Path) -> None:
    """A model that is not serving is loaded, tested, recorded, then unloaded
    again; its row ends "done" with a message saying it was unloaded (AC-43)."""
    port = _free_port()
    _catalog, _manager, _ops, run, results = _setup(tmp_path, [_fake("m1", port)])
    try:
        run.start(["m1"])
        rows = _finish(run)
        assert rows["m1"]["status"] == "done", rows
        assert "unloaded again" in rows["m1"]["message"]
        saved = load_results(results)["m1"]
        assert saved["single_tps"] > 0 and saved["multi_tps"] > 0 and saved["first_token_s"] >= 0
        assert "tested_at" in saved
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _find_listening_pid(port) is not None:
            time.sleep(0.05)
        assert _find_listening_pid(port) is None, "the model must be unloaded after its test"
    finally:
        _cleanup(port)


def test_serving_model_is_tested_and_left_loaded(tmp_path: Path) -> None:
    """A model already serving is tested without being reloaded and is still
    serving afterwards (AC-43)."""
    port = _free_port()
    catalog, manager, ops, run, results = _setup(tmp_path, [_fake("m1", port)])
    try:
        _wait_op(ops, manager.load("m1")["operation"], "ready")
        run.start(["m1"])
        rows = _finish(run)
        assert rows["m1"]["status"] == "done", rows
        assert "unloaded" not in rows["m1"]["message"]
        assert "m1" in load_results(results)
        entry = catalog.by_public_id("m1")
        assert entry is not None
        assert manager.entry_state(entry, ops.active_for("m1")) == "ready", "a loaded model stays loaded"
        assert httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5).status_code == 200
    finally:
        _cleanup(port)


def test_model_that_will_not_fit_is_skipped_without_loading(tmp_path: Path) -> None:
    """A model whose memory estimate does not fit is skipped with a reason
    containing "won't fit", is never started, and gets no result (AC-44)."""
    port = _free_port()
    _catalog, _manager, _ops, run, results = _setup(tmp_path, [_fake("huge", port, ram_gb=100000.0)])
    run.start(["huge"])
    rows = _finish(run)
    assert rows["huge"]["status"] == "skipped", rows
    assert "won't fit" in rows["huge"]["message"]
    assert _find_listening_pid(port) is None, "a skipped model must never be started"
    assert "huge" not in load_results(results)


def test_a_failed_model_does_not_stop_the_run(tmp_path: Path) -> None:
    """A model that fails to load is marked "failed" with a reason, and the run
    still tests the next model (AC-45)."""
    bad_port, good_port = _free_port(), _free_port()
    marker = f"vortex-v45-exits-{uuid.uuid4().hex}"
    bad = _entry("bad", bad_port, [sys.executable, "-c", "raise SystemExit(3)", marker])
    _catalog, _manager, _ops, run, results = _setup(tmp_path, [bad, _fake("good", good_port)])
    try:
        run.start(["bad", "good"])
        rows = _finish(run)
        assert rows["bad"]["status"] == "failed", rows
        assert rows["bad"]["message"], "a failure must carry its reason"
        assert rows["good"]["status"] == "done", rows
        assert "bad" not in load_results(results)
        assert "good" in load_results(results)
    finally:
        _cleanup(bad_port, good_port)


# A runtime that serves completions (so it loads and passes Vortex's readiness
# probe) but never reports usage.completion_tokens, so its speed test fails.
NO_TOKEN_COUNT_SERVER = (
    "import json, sys\n"
    "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
    "class H(BaseHTTPRequestHandler):\n"
    "    def _send(self, body):\n"
    "        data = json.dumps(body).encode()\n"
    "        self.send_response(200)\n"
    "        self.send_header('Content-Type', 'application/json')\n"
    "        self.send_header('Content-Length', str(len(data)))\n"
    "        self.end_headers()\n"
    "        self.wfile.write(data)\n"
    "    def do_GET(self):\n"
    "        self._send({'object': 'list', 'data': [{'id': 'x', 'object': 'model'}]})\n"
    "    def do_POST(self):\n"
    "        self.rfile.read(int(self.headers.get('Content-Length', '0')))\n"
    "        self._send({'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'hi'}}]})\n"
    "    def log_message(self, *args):\n"
    "        pass\n"
    "HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()\n"
)


def test_a_loaded_model_whose_test_fails_is_unloaded_again(tmp_path: Path) -> None:
    """A model the run loads but whose speed test fails ends "failed" with the
    reason, gets no result, and is unloaded again — a failed test must never
    leave a model holding its memory (AC-45, AC-43)."""
    port = _free_port()
    entry = _entry("nocount", port, [sys.executable, "-c", NO_TOKEN_COUNT_SERVER, str(port)])
    _catalog, _manager, _ops, run, results = _setup(tmp_path, [entry])
    try:
        run.start(["nocount"])
        rows = _finish(run)
        assert rows["nocount"]["status"] == "failed", rows
        assert "token" in rows["nocount"]["message"].lower()
        assert "nocount" not in load_results(results)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _find_listening_pid(port) is not None:
            time.sleep(0.05)
        assert _find_listening_pid(port) is None, "a model the run loaded must be unloaded after a failed test"
    finally:
        _cleanup(port)


def test_start_rejects_bad_selections(tmp_path: Path) -> None:
    """start() accepts 1 to 3 distinct catalog ids; anything else raises
    ValueError and starts nothing (AC-42)."""
    ports = [_free_port() for _ in range(4)]
    entries = [_fake(f"m{i}", p) for i, p in enumerate(ports)]
    _catalog, _manager, _ops, run, _results = _setup(tmp_path, entries)
    for bad in ([], ["m0", "m1", "m2", "m3"], ["m0", "m0"], ["nope"]):
        with pytest.raises(ValueError):
            run.start(bad)
        assert not run.running
    assert run.rows() == {}


def test_a_second_start_while_running_is_refused(tmp_path: Path) -> None:
    """While a run is in progress start() raises SpeedRunBusy; rows report the
    in-progress run's models (AC-42)."""
    port = _free_port()
    marker = f"vortex-v45-slow-{uuid.uuid4().hex}"
    slow = _entry("slow", port, [sys.executable, "-c", "import time; time.sleep(60)", marker])
    _catalog, _manager, _ops, run, _results = _setup(tmp_path, [slow])
    try:
        run.start(["slow"])
        assert run.running
        assert set(run.rows()) == {"slow"}
        assert run.rows()["slow"]["status"] in ("queued", "loading")
        with pytest.raises(SpeedRunBusy):
            run.start(["slow"])
    finally:
        _kill_marked(marker)
    rows = _finish(run)
    assert rows["slow"]["status"] == "failed"
