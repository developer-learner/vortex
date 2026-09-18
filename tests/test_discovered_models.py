"""Frozen tests for LM Studio library discovery (ERD-DELTA v32).

The discovery probe enumerates every model a running library wrapper (LM Studio
on :1234) has downloaded, via its `/api/v1/models` REST endpoint, and reports
each as DISCOVERED — never loadable — with an `in_catalog` flag. Config-first
is preserved: this surface only reports; it never mutates the catalog.
"""

from vortex.catalog import Catalog, CatalogEntry
from vortex.discovery import DiscoveredModel, discover_models

# One captured LM Studio /api/v1/models entry shape (the fields the probe reads).
_LMS_BODY = [
    {
        "type": "llm",
        "publisher": "lmstudio-community",
        "key": "qwen3-1.7b-mlx@bf16",
        "display_name": "Qwen3 1.7B",
        "architecture": "qwen3",
        "quantization": {"name": "bf16", "bits_per_weight": 16},
        "size_bytes": 3457091252,
        "params_string": "1.7B",
        "max_context_length": 40960,
        "format": "safetensors",
        "loaded_instances": [],
    },
    {
        "type": "llm",
        "publisher": "mlx-community",
        "key": "Qwen3.8-27B-MLX-8bit",
        "display_name": "Qwen3.8 27B",
        "architecture": "qwen3",
        "quantization": {"name": "8bit", "bits_per_weight": 8},
        "size_bytes": 30000000000,
        "params_string": "27B",
        "max_context_length": 262144,
        "format": "safetensors",
        "loaded_instances": [{"identifier": "qwen3.8-27b"}],
    },
]


def _fake_fetch(body):
    def fetch(base_url):
        return body

    return fetch


def _catalog_with_alias(alias):
    return Catalog(
        entries=[
            CatalogEntry(
                public_id="seat",
                runtime="omlx",
                engine="mlx",
                launch_command=["/bin/true"],
                port=8007,
                ready_url="http://127.0.0.1:8007/v1/models",
                chat_endpoint="http://127.0.0.1:8007/v1/chat/completions",
                upstream_alias=alias,
            )
        ]
    )


def test_probe_maps_every_library_entry_to_a_discovered_model():
    models = discover_models(catalog_entries=[], fetch=_fake_fetch(_LMS_BODY))
    assert [m.key for m in models] == ["qwen3-1.7b-mlx@bf16", "Qwen3.8-27B-MLX-8bit"]
    assert all(isinstance(m, DiscoveredModel) for m in models)


def test_discovered_model_carries_the_metadata_fields():
    models = discover_models(catalog_entries=[], fetch=_fake_fetch(_LMS_BODY))
    first = models[0]
    assert first.display_name == "Qwen3 1.7B"
    assert first.publisher == "lmstudio-community"
    assert first.architecture == "qwen3"
    assert first.quantization == "bf16"
    assert first.size_bytes == 3457091252
    assert first.params == "1.7B"
    assert first.max_context == 40960
    assert first.fmt == "safetensors"
    assert first.source == "lmstudio"


def test_loaded_flag_reflects_loaded_instances():
    models = discover_models(catalog_entries=[], fetch=_fake_fetch(_LMS_BODY))
    by_key = {m.key: m for m in models}
    assert by_key["qwen3-1.7b-mlx@bf16"].loaded is False
    assert by_key["Qwen3.8-27B-MLX-8bit"].loaded is True


def test_in_catalog_flag_matches_key_against_catalog_upstream_alias():
    catalog = _catalog_with_alias("Qwen3.8-27B-MLX-8bit")
    models = discover_models(
        catalog_entries=catalog.entries, fetch=_fake_fetch(_LMS_BODY)
    )
    by_key = {m.key: m for m in models}
    assert by_key["Qwen3.8-27B-MLX-8bit"].in_catalog is True
    assert by_key["qwen3-1.7b-mlx@bf16"].in_catalog is False


def test_library_unreachable_yields_no_models_never_an_error():
    models = discover_models(catalog_entries=[], fetch=_fake_fetch([]))
    assert models == []


def test_entries_without_a_key_are_skipped():
    body = [{"display_name": "no key here", "loaded_instances": []}]
    models = discover_models(catalog_entries=[], fetch=_fake_fetch(body))
    assert models == []
