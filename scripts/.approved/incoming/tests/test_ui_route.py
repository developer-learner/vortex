"""Frozen suite M1 (UI): route wiring contract.

Observes only the locked surface: vortex.app:build_app plus the routes
GET / and GET /api/status (contracts.routes). These tests gate the
app.py task; they fail until the dashboard route exists.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog


def _client(tmp_path: Path) -> TestClient:
    return TestClient(build_app(catalog=Catalog(entries=[]), sidecar_dir=tmp_path / "sidecars"))


def test_dashboard_served(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<title>vortex · model menu</title>" in resp.text


def test_status_route_unshadowed(tmp_path: Path) -> None:
    """The new "/" route must not interfere with the management API."""
    body = _client(tmp_path).get("/api/status").json()
    assert "loaded" in body
    assert "ram_used_gb" in body
