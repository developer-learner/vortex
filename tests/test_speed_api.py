"""Frozen suite v45: the speed-test HTTP surface (AC-41, AC-42, AC-46, AC-48).

`register_speed_routes` is exercised on its own FastAPI app with the real
Manager / Lifecycle / OperationStore; `build_app` is exercised for its wiring
of the same routes and the results path.
"""

from __future__ import annotations

import socket
import sys
import time
import uuid
from pathlib import Path

import psutil
from fastapi import FastAPI
from fastapi.testclient import TestClient
from vortex.speed_routes import register_speed_routes
from vortex.speed_ui import SPEED_PAGE
from vortex.speedtest import save_result

from vortex.app import build_app
from vortex.catalog import Catalog, CatalogEntry
from vortex.lifecycle import Lifecycle, SidecarStore, _find_listening_pid
from vortex.manager import Manager
from vortex.operations import OperationStore

ROW_KEYS = {
    "public_id", "display_name", "quant", "runtime", "ram_estimate_gb",
    "state", "result", "run_status", "run_message",
}


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _entry(public_id: str, port: int, launch: list[str] | None = None) -> CatalogEntry:
    return CatalogEntry(
        public_id=public_id,
        runtime="fake",
        engine="fake",
        launch_command=launch or [sys.executable, "-m", "tests.fake_server", str(port)],
        port=port,
        ready_url=f"http://127.0.0.1:{port}/v1/models",
        chat_endpoint=f"http://127.0.0.1:{port}/v1/chat/completions",
        ram_estimate_gb=1.0,
        display_name=f"Model {public_id}",
        quant="8-bit",
    )


def _client(tmp_path: Path, entries: list[CatalogEntry]) -> TestClient:
    catalog = Catalog(entries=entries)
    ops = OperationStore()
    manager = Manager(catalog, Lifecycle(catalog, SidecarStore(tmp_path / "sidecars")), ops)
    app = FastAPI()
    register_speed_routes(app, catalog, manager, ops, tmp_path / "speed-results.json")
    return TestClient(app)


def _wait_idle(client: TestClient, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get("/api/speed").json()
        if not body["running"]:
            return body
        time.sleep(0.05)
    raise AssertionError("the speed-test run never finished")


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


def test_speed_list_has_every_catalog_model_in_order(tmp_path: Path) -> None:
    """GET /api/speed lists every catalog model in catalog order with its
    fields, null result and run status when untested, and max_models 3 (AC-41)."""
    entries = [_entry("zeta", _free_port()), _entry("alpha", _free_port())]
    body = _client(tmp_path, entries).get("/api/speed").json()
    assert body["running"] is False
    assert body["max_models"] == 3
    assert [r["public_id"] for r in body["models"]] == ["zeta", "alpha"]
    row = body["models"][0]
    assert ROW_KEYS <= set(row)
    assert row["display_name"] == "Model zeta"
    assert row["quant"] == "8-bit"
    assert row["runtime"] == "fake"
    assert row["ram_estimate_gb"] == 1.0
    assert row["state"] == "unloaded"
    assert row["result"] is None
    assert row["run_status"] is None


def test_speed_run_tests_a_model_and_reports_its_result(tmp_path: Path) -> None:
    """POST /api/speed/run answers 202 with the started ids; when the run ends
    the row shows status "done" and the latest result (AC-42, AC-41)."""
    port = _free_port()
    client = _client(tmp_path, [_entry("m1", port)])
    try:
        resp = client.post("/api/speed/run", json={"models": ["m1"]})
        assert resp.status_code == 202
        assert resp.json() == {"started": ["m1"]}
        row = _wait_idle(client)["models"][0]
        assert row["run_status"] == "done"
        result = row["result"]
        assert result is not None
        assert result["single_tps"] > 0 and result["multi_tps"] > 0 and result["first_token_s"] >= 0
        assert result["tested_at"]
    finally:
        pid = _find_listening_pid(port)
        if isinstance(pid, int):
            psutil.Process(pid).kill()


def test_speed_run_rejects_bad_selections(tmp_path: Path) -> None:
    """Empty, more than three, duplicate, unknown ids, or a body without a
    models list are rejected with 400 and start nothing (AC-42)."""
    entries = [_entry(f"m{i}", _free_port()) for i in range(4)]
    client = _client(tmp_path, entries)
    for body in ({"models": []}, {"models": ["m0", "m1", "m2", "m3"]},
                 {"models": ["m0", "m0"]}, {"models": ["nope"]}, {}):
        assert client.post("/api/speed/run", json=body).status_code == 400, body
    assert client.get("/api/speed").json()["running"] is False


def test_loads_unloads_and_new_runs_are_refused_while_a_run_is_in_progress(tmp_path: Path) -> None:
    """While a run is in progress, another run and any load or unload answer 409
    busy; once it ends the in-progress model is reported failed (AC-46, AC-42)."""
    marker = f"vortex-v45-slow-{uuid.uuid4().hex}"
    slow_port, other_port = _free_port(), _free_port()
    slow = _entry("slow", slow_port, [sys.executable, "-c", "import time; time.sleep(60)", marker])
    client = _client(tmp_path, [slow, _entry("other", other_port)])
    try:
        assert client.post("/api/speed/run", json={"models": ["slow"]}).status_code == 202
        assert client.get("/api/speed").json()["running"] is True
        again = client.post("/api/speed/run", json={"models": ["other"]})
        assert again.status_code == 409
        assert again.json()["detail"]["busy"] is True
        for path in ("/api/models/other/load", "/api/models/other/unload"):
            refused = client.post(path)
            assert refused.status_code == 409, path
            assert refused.json()["detail"]["busy"] is True
        assert _find_listening_pid(other_port) is None, "a refused load must start nothing"
    finally:
        _kill_marked(marker)
    body = _wait_idle(client)
    assert body["models"][0]["run_status"] == "failed"


def test_speed_page_is_served(tmp_path: Path) -> None:
    """GET /speed serves the speed page (AC-47)."""
    resp = _client(tmp_path, [_entry("m1", _free_port())]).get("/speed")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == SPEED_PAGE


def test_build_app_wires_the_speed_routes_and_results_path(tmp_path: Path) -> None:
    """build_app serves /speed and /api/speed, and reads results from the given
    speed_results_path (AC-48, AC-40)."""
    results = tmp_path / "speed.json"
    save_result(results, "m1", {"single_tps": 12.5, "multi_tps": 40.0, "first_token_s": 0.3})
    app = build_app(
        catalog=Catalog(entries=[_entry("m1", _free_port()), _entry("m2", _free_port())]),
        sidecar_dir=tmp_path / "sidecars",
        speed_results_path=results,
    )
    client = TestClient(app)
    assert client.get("/speed").status_code == 200
    rows = {r["public_id"]: r for r in client.get("/api/speed").json()["models"]}
    assert rows["m1"]["result"]["single_tps"] == 12.5
    assert rows["m2"]["result"] is None


def test_build_app_keeps_its_existing_routes(tmp_path: Path) -> None:
    """Adding the speed routes leaves the dashboard and catalog routes in place
    (AC-48)."""
    app = build_app(
        catalog=Catalog(entries=[_entry("m1", _free_port())]),
        sidecar_dir=tmp_path / "sidecars",
        speed_results_path=tmp_path / "speed.json",
    )
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert [e["public_id"] for e in client.get("/api/catalog").json()["entries"]] == ["m1"]
