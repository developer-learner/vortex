"""Frozen suite v39: discovered model -> catalog entry synthesis (AC-27..AC-30).

`synthesize_entry` is pure: it reads a DiscoveredModel and the current catalog
and returns a validated CatalogEntry, or raises SynthesisError with a reason.
"""

from __future__ import annotations

import pytest
from vortex.catalog_synth import PORT_RANGE, RUNTIME_BINARIES, SynthesisError, synthesize_entry

from vortex.catalog import Catalog, CatalogEntry
from vortex.discovery import DiscoveredModel

MLX_PATH = "/models/butterf1ying/Qwen3.8-Flash-Next-Uncensored-REAP288-MTP-MLX-4bit"
GGUF_PATH = "/models/OBLITERATUS/Qwen3.8-27B-OBLITERATED/Qwen3.8-27B-OBLITERATED-Q4_K_M.gguf"


def _model(**overrides: object) -> DiscoveredModel:
    base: dict[str, object] = {
        "key": "qwen3.8-flash-next-uncensored-reap288-mtp-mlx",
        "display_name": "Qwen3.8 Flash Next Uncensored REAP288 MTP",
        "publisher": "butterf1ying",
        "architecture": "qwen4_exp",
        "quantization": "4bit",
        "size_bytes": 76_950_364_862,
        "max_context": 262144,
        "fmt": "mlx",
        "source": "lmstudio",
        "path": MLX_PATH,
    }
    base.update(overrides)
    return DiscoveredModel(**base)  # type: ignore[arg-type]


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


def test_port_range_and_binaries_are_the_ceo_policy() -> None:
    assert PORT_RANGE == range(8200, 8300)
    assert set(RUNTIME_BINARIES) == {"mlx", "gguf"}


def test_mlx_model_becomes_an_mlx_serve_entry() -> None:
    """MLX -> mlx-serve --model <path> on the lowest free port (AC-27)."""
    entry = synthesize_entry(_model(), Catalog(entries=[_entry("hand", 8007)]))
    assert entry.runtime == "mlx-serve"
    cmd = entry.launch_command
    assert cmd[0] == RUNTIME_BINARIES["mlx"]
    assert cmd[cmd.index("--model") + 1] == MLX_PATH
    assert "--serve" in cmd
    assert cmd[cmd.index("--port") + 1] == "8200"
    assert entry.port == 8200
    assert entry.ready_url == "http://127.0.0.1:8200/v1/models"
    assert entry.chat_endpoint == "http://127.0.0.1:8200/v1/chat/completions"
    assert entry.source_path == MLX_PATH
    assert entry.origin == "local"
    assert entry.public_id == "qwen3.8-flash-next-uncensored-reap288-mtp-mlx"
    CatalogEntry.model_validate(entry.model_dump())


def test_gguf_model_becomes_a_llama_server_entry() -> None:
    """GGUF -> llama-server -m <path> (AC-28)."""
    model = _model(key="qwen3.8-27b-obliterated", fmt="gguf", path=GGUF_PATH,
                   size_bytes=17_741_855_528)
    entry = synthesize_entry(model, Catalog())
    assert entry.runtime == "llama-server"
    cmd = entry.launch_command
    assert cmd[0] == RUNTIME_BINARIES["gguf"]
    assert cmd[cmd.index("-m") + 1] == GGUF_PATH
    assert cmd[cmd.index("--port") + 1] == str(entry.port)
    assert entry.origin == "local"


def test_lowest_free_port_skips_ports_the_catalog_uses() -> None:
    catalog = Catalog(entries=[_entry("a", 8200), _entry("b", 8201), _entry("c", 8203)])
    assert synthesize_entry(_model(), catalog).port == 8202


def test_public_id_is_sanitized_from_the_key() -> None:
    """Characters outside [a-z0-9._-] become '-' and letters are lowercased."""
    entry = synthesize_entry(_model(key="Qwen3.8-27B@8bit"), Catalog())
    assert entry.public_id == "qwen3.8-27b-8bit"


def test_ram_estimate_is_size_plus_ten_percent_and_sets_exclusive() -> None:
    """76.95 GB * 1.1 -> 84.6 GB, exclusive; 17.74 GB * 1.1 -> 19.5 GB, not (AC-30)."""
    big = synthesize_entry(_model(), Catalog())
    assert big.ram_estimate_gb == pytest.approx(84.6)
    assert big.exclusive is True
    small = synthesize_entry(_model(size_bytes=17_741_855_528), Catalog())
    assert small.ram_estimate_gb == pytest.approx(19.5)
    assert small.exclusive is False


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"path": None}, "path"),
        ({"fmt": "safetensors-unknown"}, "format"),
        ({"architecture": None}, "architecture"),
    ],
)
def test_unsynthesizable_models_raise_with_a_reason(overrides: dict, reason: str) -> None:
    """No path, unsupported format, or no architecture -> SynthesisError (AC-29)."""
    with pytest.raises(SynthesisError, match=reason):
        synthesize_entry(_model(**overrides), Catalog())


def test_a_model_already_in_the_catalog_is_refused() -> None:
    by_id = Catalog(entries=[_entry("qwen3.8-flash-next-uncensored-reap288-mtp-mlx", 8300)])
    with pytest.raises(SynthesisError, match="already"):
        synthesize_entry(_model(), by_id)
    by_path = Catalog(entries=[_entry("other", 8300, launch_command=["/x", "--model", MLX_PATH])])
    with pytest.raises(SynthesisError, match="already"):
        synthesize_entry(_model(), by_path)


def test_no_free_port_is_refused() -> None:
    full = Catalog(entries=[_entry(f"e{p}", p) for p in PORT_RANGE])
    with pytest.raises(SynthesisError, match="port"):
        synthesize_entry(_model(), full)
