"""Frozen tests for the engine-wrappers API routes (ERD-DELTA v14)."""

import inspect

from fastapi.testclient import TestClient
from vortex.discovery import Wrapper, discover_wrappers

from vortex.app import build_app
from vortex.catalog import Catalog


def fake_discovery(search_path=None, catalog_entries=None, ports=None):
    return [
        Wrapper(
            name="omlx",
            kind="cli",
            installed=True,
            binary_path="/opt/homebrew/bin/omlx",
            version="v0.7",
            port=8000,
            port_open=False,
            in_catalog=True,
        ),
        Wrapper(
            name="lmstudio",
            kind="ui",
            installed=True,
            binary_path="/Applications/LM Studio.app/Contents/MacOS/LM Studio",
            version="1.2",
            port=1234,
            port_open=False,
            in_catalog=False,
        ),
        Wrapper(
            name="ollama",
            kind="cli",
            installed=False,
            binary_path=None,
            version=None,
            port=11434,
            port_open=False,
            in_catalog=False,
        ),
    ]


def client_with(fake):
    app = build_app(catalog=Catalog(), wrapper_discovery=fake)
    return TestClient(app)


def test_get_lists_only_installed_wrappers():
    response = client_with(fake_discovery).get("/api/engine-wrappers")
    assert response.status_code == 200
    wrappers = response.json()["wrappers"]
    assert [w["name"] for w in wrappers] == ["omlx", "lmstudio"]
    assert all(w["installed"] is True for w in wrappers)


def test_wire_schema_carries_all_wrapper_fields():
    response = client_with(fake_discovery).get("/api/engine-wrappers")
    wrapper = response.json()["wrappers"][0]
    assert set(wrapper) == {
        "name",
        "kind",
        "installed",
        "binary_path",
        "version",
        "port",
        "port_open",
        "in_catalog",
    }
    assert wrapper["name"] == "omlx"
    assert wrapper["kind"] == "cli"
    assert wrapper["binary_path"] == "/opt/homebrew/bin/omlx"
    assert wrapper["version"] == "v0.7"
    assert wrapper["port"] == 8000
    assert wrapper["port_open"] is False
    assert wrapper["in_catalog"] is True


def test_discover_post_flags_newly_found():
    response = client_with(fake_discovery).post("/api/engine-wrappers/discover")
    assert response.status_code == 200
    payload = response.json()
    assert [w["name"] for w in payload["wrappers"]] == ["omlx", "lmstudio"]
    assert payload["newly_found"] == ["lmstudio"]


def test_build_app_defaults_to_real_discovery():
    signature = inspect.signature(build_app)
    parameter = signature.parameters["wrapper_discovery"]
    assert parameter.default is discover_wrappers