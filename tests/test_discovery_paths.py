"""Frozen suite v39: discovered models carry their on-disk path (AC-25, AC-26).

The path comes from LM Studio's CLI listing (`lms ls --json`); the rows below
are copied from the frozen capture `captures/lms-ls.json`. Both the listing
runner and the library fetch are injected, so no LM Studio is needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from vortex.catalog import CatalogEntry
from vortex.discovery import discover_models, lmstudio_model_paths

# Verbatim rows from captures/lms-ls.json (the fields the path map reads).
_LMS_LS = [
    {
        "type": "llm",
        "modelKey": "qwen3.8-flash-next-uncensored-reap288-mtp-mlx",
        "format": "safetensors",
        "displayName": "Qwen3.8 Flash Next Uncensored REAP288 MTP",
        "publisher": "butterf1ying",
        "path": "butterf1ying/Qwen3.8-Flash-Next-Uncensored-REAP288-MTP-MLX-4bit",
        "sizeBytes": 76950364862,
        "architecture": "qwen4_exp",
    },
    {
        "type": "llm",
        "modelKey": "qwen3.8-27b-obliterated",
        "format": "gguf",
        "displayName": "Qwen3.8 27B OBLITERATED",
        "publisher": "OBLITERATUS",
        "path": "OBLITERATUS/Qwen3.8-27B-OBLITERATED/Qwen3.8-27B-OBLITERATED-Q4_K_M.gguf",
        "sizeBytes": 17741855528,
        "architecture": "qwen35",
    },
]

# Matching /api/v1/models rows (shape as captured in lmstudio-api-v1-models.json).
_API_BODY = [
    {
        "type": "llm",
        "publisher": "butterf1ying",
        "key": "qwen3.8-flash-next-uncensored-reap288-mtp-mlx",
        "display_name": "Qwen3.8 Flash Next Uncensored REAP288 MTP",
        "architecture": "qwen4_exp",
        "quantization": {"name": "4bit", "bits_per_weight": 4},
        "size_bytes": 76950364862,
        "params_string": None,
        "loaded_instances": [],
        "max_context_length": 262144,
        "format": "mlx",
    },
    {
        "type": "llm",
        "publisher": "lmstudio-community",
        "key": "not-in-the-cli-listing",
        "display_name": "Unlisted",
        "architecture": "qwen3",
        "quantization": {"name": "4bit", "bits_per_weight": 4},
        "size_bytes": 1000,
        "params_string": None,
        "loaded_instances": [],
        "max_context_length": 4096,
        "format": "mlx",
    },
]

ROOT = Path("/models-root")
REAP = str(ROOT / "butterf1ying/Qwen3.8-Flash-Next-Uncensored-REAP288-MTP-MLX-4bit")


def _fetch(base_url: str) -> list:
    return _API_BODY


def _paths() -> dict[str, str]:
    return {"qwen3.8-flash-next-uncensored-reap288-mtp-mlx": REAP}


def _entry(**overrides: object) -> CatalogEntry:
    base: dict[str, object] = {
        "public_id": "hand",
        "runtime": "mlx-serve",
        "engine": "mlx-serve",
        "launch_command": ["/bin/true"],
        "port": 8300,
        "ready_url": "http://127.0.0.1:8300/v1/models",
        "chat_endpoint": "http://127.0.0.1:8300/v1/chat/completions",
    }
    base.update(overrides)
    return CatalogEntry.model_validate(base)


def test_path_map_joins_cli_paths_onto_the_models_root() -> None:
    """Each `lms ls --json` row maps its modelKey to root/path (AC-25)."""
    paths = lmstudio_model_paths(run=lambda: json.dumps(_LMS_LS), models_root=ROOT)
    assert paths == {
        "qwen3.8-flash-next-uncensored-reap288-mtp-mlx": REAP,
        "qwen3.8-27b-obliterated": str(
            ROOT / "OBLITERATUS/Qwen3.8-27B-OBLITERATED/Qwen3.8-27B-OBLITERATED-Q4_K_M.gguf"
        ),
    }


def test_path_map_is_empty_when_the_listing_cannot_be_read() -> None:
    """A failing or garbled listing yields no paths, never an exception (AC-25)."""

    def boom() -> str:
        raise OSError("lms not installed")

    assert lmstudio_model_paths(run=boom, models_root=ROOT) == {}
    assert lmstudio_model_paths(run=lambda: "not json", models_root=ROOT) == {}


def test_path_map_skips_rows_without_key_or_path() -> None:
    rows = [{"modelKey": "k1"}, {"path": "p/only"}, {"modelKey": "k2", "path": "pub/m2"}]
    paths = lmstudio_model_paths(run=lambda: json.dumps(rows), models_root=ROOT)
    assert paths == {"k2": str(ROOT / "pub/m2")}


def test_discovered_models_carry_their_path_or_none() -> None:
    """A listed key gets its path; an unlisted key gets None (AC-25)."""
    models = discover_models(catalog_entries=[], fetch=_fetch, paths=_paths)
    by_key = {m.key: m for m in models}
    assert by_key["qwen3.8-flash-next-uncensored-reap288-mtp-mlx"].path == REAP
    assert by_key["not-in-the-cli-listing"].path is None


def test_in_catalog_matches_a_path_in_an_entry_launch_command() -> None:
    """A hand-written entry that launches the model's path counts as in the
    catalog even though its upstream alias differs from the key (AC-26)."""
    entry = _entry(launch_command=["/opt/homebrew/bin/mlx-serve", "--model", REAP])
    models = discover_models(catalog_entries=[entry], fetch=_fetch, paths=_paths)
    by_key = {m.key: m for m in models}
    assert by_key["qwen3.8-flash-next-uncensored-reap288-mtp-mlx"].in_catalog is True
    assert by_key["not-in-the-cli-listing"].in_catalog is False


def test_in_catalog_matches_an_entry_source_path() -> None:
    entry = _entry(source_path=REAP)
    models = discover_models(catalog_entries=[entry], fetch=_fetch, paths=_paths)
    by_key = {m.key: m for m in models}
    assert by_key["qwen3.8-flash-next-uncensored-reap288-mtp-mlx"].in_catalog is True


def test_unrelated_entry_does_not_mark_the_model_in_catalog() -> None:
    entry = _entry(launch_command=["/opt/homebrew/bin/mlx-serve", "--model", "/elsewhere"])
    models = discover_models(catalog_entries=[entry], fetch=_fetch, paths=_paths)
    assert all(m.in_catalog is False for m in models)
