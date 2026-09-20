"""Frozen suite M1 (v2): dashboard ⇄ management-API field contract.

Guards the client/server contract the v1 static tests missed. The v1 suite
only string-matched vortex.ui:UI_PAGE and hit routes independently, so the
shipped dashboard could read field names and a response shape the real API
never returns while every test stayed green.

These tests exercise the page's field reads against the ACTUAL payloads of
vortex.app:build_app. They observe only the locked surface
(contracts.entry_points): build_app, UI_PAGE, and the catalog model
(as tests/test_ui_route.py already does).
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog, CatalogEntry
from vortex.discovery import DiscoveredModel
from vortex.ui import UI_PAGE


def _entry() -> CatalogEntry:
    return CatalogEntry(
        public_id="demo-model",
        runtime="mtplx",
        engine="mlx",
        launch_command=["serve", "demo"],
        port=8001,
        ready_url="http://127.0.0.1:8001/health",
        chat_endpoint="http://127.0.0.1:8001/v1/chat/completions",
        ram_estimate_gb=30.0,
    )


def _client(tmp_path: Path, entries: list[CatalogEntry], model_discovery=None) -> TestClient:
    kwargs = {"catalog": Catalog(entries=entries), "sidecar_dir": tmp_path / "s"}
    if model_discovery is not None:
        kwargs["model_discovery"] = model_discovery
    return TestClient(build_app(**kwargs))


def _one_discovered() -> list[DiscoveredModel]:
    return [
        DiscoveredModel(
            key="qwen3-1.7b-mlx@bf16",
            display_name="Qwen3 1.7B",
            publisher="lmstudio-community",
            architecture="qwen3",
            quantization="bf16",
            size_bytes=3457091252,
            params="1.7B",
            max_context=40960,
            fmt="safetensors",
            loaded=False,
            source="lmstudio",
            in_catalog=False,
        )
    ]


def _reads(prefix: str) -> set[str]:
    """Field names the dashboard JS reads off `prefix` (e.g. m.foo -> {foo})."""
    return set(re.findall(r"\b" + prefix + r"\.([A-Za-z_][A-Za-z0-9_]*)", UI_PAGE))


def test_catalog_response_is_enveloped(tmp_path: Path) -> None:
    body = _client(tmp_path, [_entry()]).get("/api/catalog").json()
    assert isinstance(body, dict), "catalog response is a JSON object"
    assert isinstance(body.get("entries"), list), "catalog rows live under 'entries'"
    # the dashboard must dig into the envelope, not iterate the object itself
    assert ".entries" in UI_PAGE, "UI must read catalog rows from data.entries"


def test_ui_only_reads_catalog_fields_the_api_returns(tmp_path: Path) -> None:
    # ERD-33: the dashboard reads m.* from TWO endpoints — /api/catalog (model
    # rows) and /api/discovered-models (library rows). The contract is that
    # every field the UI reads is returned by at least one of them.
    client = _client(tmp_path, [_entry()], model_discovery=lambda catalog_entries=None: _one_discovered())
    keys = set(client.get("/api/catalog").json()["entries"][0])
    keys |= set(client.get("/api/discovered-models").json()["models"][0])
    missing = _reads("m") - keys
    assert not missing, f"dashboard reads fields no API returns: {sorted(missing)}"


def test_ui_only_reads_status_fields_the_api_returns(tmp_path: Path) -> None:
    body = _client(tmp_path, []).get("/api/status").json()
    keys = set(body)
    assert {"ram_used_gb", "ram_total_gb"} <= keys
    # 'conflict' is a separate documented follow-up: real load refusals arrive
    # as a 409 on the load POST, never from /api/status. Every OTHER field the
    # RAM meter reads must be a real /api/status key.
    missing = (_reads("s") - {"conflict"}) - keys
    assert not missing, f"dashboard reads status fields the API never returns: {sorted(missing)}"


def test_ui_uses_the_api_loaded_state_token() -> None:
    # entry_state()/status report a serving model as "ready"; the demo checked
    # for "loaded", which the backend never emits.
    assert 'm.state === "ready"' in UI_PAGE
    assert 'm.state === "loaded"' not in UI_PAGE


def test_ui_uses_the_operation_field_the_api_returns() -> None:
    # load/unload return {"operation": <id>, "model": <id>}; the demo read op.id.
    assert "op.operation" in UI_PAGE
    assert "pollOperation(op.id)" not in UI_PAGE


def test_ui_operation_completion_uses_real_terminal_states() -> None:
    # A finished operation's state is "ready" (load), "unloaded" (unload), or
    # "error"; the backend never emits state "done" (that is the op's phase).
    # The progress poll must stop on the real terminal states so it does not
    # spin forever after a successful action.
    assert 'op.state === "done"' not in UI_PAGE
    assert 'op.state === "ready"' in UI_PAGE
    assert 'op.state === "unloaded"' in UI_PAGE
