"""Frozen tests for the discovered-models API routes (ERD-DELTA v32).

Mirrors the engine-wrappers API contract: a GET inventory route and a POST
rescan route that flags models not yet in the catalog. Discovery is injected
into build_app exactly as wrapper discovery is, so the routes are testable
without a running LM Studio.
"""

import inspect

from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog
from vortex.discovery import DiscoveredModel, discover_models


def fake_discovery(catalog_entries=None, fetch=None, probes=None):
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
        ),
        DiscoveredModel(
            key="Qwen3.8-27B-MLX-8bit",
            display_name="Qwen3.8 27B",
            publisher="mlx-community",
            architecture="qwen3",
            quantization="8bit",
            size_bytes=30000000000,
            params="27B",
            max_context=262144,
            fmt="safetensors",
            loaded=True,
            source="lmstudio",
            in_catalog=True,
        ),
    ]


def client_with(fake):
    app = build_app(catalog=Catalog(), model_discovery=fake)
    return TestClient(app)


def test_get_lists_discovered_models():
    response = client_with(fake_discovery).get("/api/discovered-models")
    assert response.status_code == 200
    models = response.json()["models"]
    assert [m["key"] for m in models] == [
        "qwen3-1.7b-mlx@bf16",
        "Qwen3.8-27B-MLX-8bit",
    ]


def test_wire_schema_carries_all_discovered_model_fields():
    response = client_with(fake_discovery).get("/api/discovered-models")
    model = response.json()["models"][0]
    assert set(model) == {
        "key",
        "display_name",
        "publisher",
        "architecture",
        "quantization",
        "size_bytes",
        "params",
        "max_context",
        "fmt",
        "loaded",
        "source",
        "in_catalog",
    }
    assert model["key"] == "qwen3-1.7b-mlx@bf16"
    assert model["display_name"] == "Qwen3 1.7B"
    assert model["quantization"] == "bf16"
    assert model["loaded"] is False
    assert model["in_catalog"] is False


def test_discover_post_flags_models_not_in_catalog():
    response = client_with(fake_discovery).post("/api/discovered-models/discover")
    assert response.status_code == 200
    payload = response.json()
    assert [m["key"] for m in payload["models"]] == [
        "qwen3-1.7b-mlx@bf16",
        "Qwen3.8-27B-MLX-8bit",
    ]
    assert payload["newly_found"] == ["qwen3-1.7b-mlx@bf16"]


def test_build_app_defaults_to_real_model_discovery():
    signature = inspect.signature(build_app)
    parameter = signature.parameters["model_discovery"]
    assert parameter.default is discover_models
