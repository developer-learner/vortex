"""Frozen suite v39: add / add-new / remove routes (AC-31..AC-34).

Observes only the locked surface: vortex.app:build_app with an injected
model_discovery and local_catalog_path, and the declared routes. Discovery is
a fake that honours catalog_entries (a model whose path an entry already
serves is in_catalog), mirroring the real rule in AC-26.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil
from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog, CatalogEntry
from vortex.discovery import DiscoveredModel

TESTS_DIR = Path(__file__).parent


def _model(key: str, path: str | None, fmt: str = "mlx", arch: str | None = "qwen3",
           size: int = 1_000_000_000) -> dict:
    return {"key": key, "display_name": key, "publisher": "pub", "architecture": arch,
            "quantization": "4bit", "size_bytes": size, "max_context": 32768,
            "fmt": fmt, "source": "lmstudio", "path": path}


LIBRARY = [
    _model("alpha-mlx", "/models/pub/Alpha-MLX-4bit"),
    _model("beta-gguf", "/models/pub/Beta/Beta-Q4_K_M.gguf", fmt="gguf"),
    _model("nomic-embed", "/models/nomic/embed.gguf", fmt="gguf", arch=None),
    _model("served-already", "/models/pub/Served"),
]


def fake_discovery(catalog_entries=None, fetch=None, probes=None):
    entries = list(catalog_entries or [])
    out = []
    for row in LIBRARY:
        served = any(
            row["path"] is not None
            and (e.source_path == row["path"] or row["path"] in e.launch_command)
            for e in entries
        )
        out.append(DiscoveredModel(**row, in_catalog=served))
    return out


def _entry(public_id: str, port: int, **overrides: object) -> CatalogEntry:
    base: dict[str, object] = {
        "public_id": public_id,
        "runtime": "omlx",
        "engine": "omlx",
        "launch_command": ["/bin/true"],
        "port": port,
        "ready_url": f"http://127.0.0.1:{port}/v1/models",
        "chat_endpoint": f"http://127.0.0.1:{port}/v1/chat/completions",
    }
    base.update(overrides)
    return CatalogEntry.model_validate(base)


def _config_entries() -> list[CatalogEntry]:
    return [_entry("hand", 8300, launch_command=["/x", "--model", "/models/pub/Served"])]


def _client(tmp_path: Path, entries: list[CatalogEntry] | None = None) -> tuple[TestClient, Path]:
    local = tmp_path / "catalog.local.json"
    app = build_app(
        catalog=Catalog(entries=entries if entries is not None else _config_entries()),
        sidecar_dir=tmp_path / "sidecars",
        model_discovery=fake_discovery,
        local_catalog_path=local,
        on_shutdown=lambda: None,
        on_restart=lambda: None,
    )
    return TestClient(app), local


def _catalog_rows(client: TestClient) -> dict[str, dict]:
    return {e["public_id"]: e for e in client.get("/api/catalog").json()["entries"]}


def test_add_puts_the_model_in_the_live_catalog_and_the_local_file(tmp_path: Path) -> None:
    """201 with the entry; /api/catalog lists it as local; the file holds it (AC-31)."""
    client, local = _client(tmp_path)
    resp = client.post("/api/discovered-models/alpha-mlx/add")
    assert resp.status_code == 201
    added = resp.json()["added"]
    assert added["public_id"] == "alpha-mlx"
    assert added["port"] == 8200
    assert added["runtime"] == "mlx-serve"
    rows = _catalog_rows(client)
    assert rows["alpha-mlx"]["origin"] == "local"
    assert rows["alpha-mlx"]["source_path"] == "/models/pub/Alpha-MLX-4bit"
    assert rows["hand"]["origin"] == "config"
    saved = json.loads(local.read_text(encoding="utf-8"))
    assert [e["public_id"] for e in saved["entries"]] == ["alpha-mlx"]


def test_added_model_is_no_longer_newly_found(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    client.post("/api/discovered-models/alpha-mlx/add")
    newly = client.post("/api/discovered-models/discover").json()["newly_found"]
    assert "alpha-mlx" not in newly


def test_add_unknown_key_is_404_and_changes_nothing(tmp_path: Path) -> None:
    client, local = _client(tmp_path)
    assert client.post("/api/discovered-models/no-such-model/add").status_code == 404
    assert not local.exists()
    assert set(_catalog_rows(client)) == {"hand"}


def test_add_unsynthesizable_is_422_with_the_reason(tmp_path: Path) -> None:
    """A model synthesis refuses answers 422 naming why; nothing is added (AC-32)."""
    client, local = _client(tmp_path)
    resp = client.post("/api/discovered-models/nomic-embed/add")
    assert resp.status_code == 422
    assert "architecture" in json.dumps(resp.json()["detail"])
    assert not local.exists()
    assert set(_catalog_rows(client)) == {"hand"}


def test_add_new_adds_every_synthesizable_new_model_on_distinct_ports(tmp_path: Path) -> None:
    """New models are added, refusals are reported, served ones are left alone (AC-33)."""
    client, local = _client(tmp_path)
    resp = client.post("/api/discovered-models/add-new")
    assert resp.status_code == 200
    body = resp.json()
    assert sorted(body["added"]) == ["alpha-mlx", "beta-gguf"]
    skipped = {s["key"]: s["reason"] for s in body["skipped"]}
    assert set(skipped) == {"nomic-embed"}
    assert "architecture" in skipped["nomic-embed"]
    rows = _catalog_rows(client)
    assert {rows["alpha-mlx"]["port"], rows["beta-gguf"]["port"]} == {8200, 8201}
    assert rows["beta-gguf"]["runtime"] == "llama-server"
    saved = json.loads(local.read_text(encoding="utf-8"))
    assert sorted(e["public_id"] for e in saved["entries"]) == ["alpha-mlx", "beta-gguf"]


def test_remove_deletes_a_local_entry_from_catalog_and_file(tmp_path: Path) -> None:
    client, local = _client(tmp_path)
    client.post("/api/discovered-models/alpha-mlx/add")
    resp = client.delete("/api/catalog/alpha-mlx")
    assert resp.status_code == 200
    assert resp.json() == {"removed": "alpha-mlx"}
    assert "alpha-mlx" not in _catalog_rows(client)
    assert json.loads(local.read_text(encoding="utf-8"))["entries"] == []


def test_remove_refuses_config_entries_and_unknown_ids(tmp_path: Path) -> None:
    """Config entries answer 409 and stay; unknown ids answer 404 (AC-34)."""
    client, _ = _client(tmp_path)
    resp = client.delete("/api/catalog/hand")
    assert resp.status_code == 409
    assert "hand" in _catalog_rows(client)
    assert client.delete("/api/catalog/nope").status_code == 404


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_remove_refuses_a_loaded_local_entry(tmp_path: Path) -> None:
    """A local entry that is loaded answers 409 and is not removed (AC-34)."""
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.fake_server", str(port)],
        cwd=TESTS_DIR.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=1).status_code == 200:
                    break
            except Exception:  # noqa: BLE001, S110 — readiness polling loop
                pass
            time.sleep(0.05)
        live = _entry("live", port, origin="local",
                      launch_command=[sys.executable, "-m", "tests.fake_server", str(port)])
        sidecars = tmp_path / "sidecars"
        sidecars.mkdir()
        (sidecars / "live.json").write_text(json.dumps({
            "pid": proc.pid, "start_time": psutil.Process(proc.pid).create_time(),
            "public_id": "live", "port": port,
        }), encoding="utf-8")
        client, _ = _client(tmp_path, entries=[live])
        op = client.post("/api/models/live/load").json()["operation"]
        deadline = time.monotonic() + 30
        while client.get(f"/api/operations/{op}").json()["state"] != "ready":
            assert time.monotonic() < deadline, "adoption never became ready"
            time.sleep(0.05)
        resp = client.delete("/api/catalog/live")
        assert resp.status_code == 409
        assert "live" in _catalog_rows(client)
    finally:
        proc.kill()
        proc.wait(timeout=5)
