"""Discovered model -> catalog entry (the operator's Add click)."""
from __future__ import annotations

import os
import re

from .catalog import Catalog, CatalogEntry
from .discovery import DiscoveredModel

PORT_RANGE = range(8200, 8300)
RUNTIME_BINARIES = {"mlx": "/opt/homebrew/bin/mlx-serve",
                    "gguf": "/opt/homebrew/bin/llama-server"}


class SynthesisError(ValueError):
    """A discovered model that cannot become a catalog entry."""


def synthesize_entry(model: DiscoveredModel, catalog: Catalog,
                     binaries: dict[str, str] = RUNTIME_BINARIES) -> CatalogEntry:
    path, fmt = model.path, model.fmt
    if path is None:
        raise SynthesisError(f"no local path known for {model.key}")
    if fmt not in binaries:
        raise SynthesisError(f"unsupported format {fmt}")
    if model.architecture is None:
        raise SynthesisError("no architecture reported (not a chat model)")
    pid = re.sub(r"[^a-z0-9._-]", "-", model.key.lower())
    for e in catalog.entries:
        if e.public_id == pid or e.source_path == path or path in e.launch_command:
            raise SynthesisError(f"already in the catalog as {e.public_id}")
    free = [p for p in PORT_RANGE if p not in {e.port for e in catalog.entries}]
    if not free:
        raise SynthesisError("no free port in 8200-8299")
    port = free[0]
    net = ["--host", "127.0.0.1", "--port", str(port)]
    if fmt == "mlx":
        rt, eng, cmd = "mlx-serve", "mlx-serve", [binaries[fmt], "--model", path, "--serve"]
    else:
        rt, eng, cmd = "llama-server", "llama.cpp", [binaries[fmt], "-m", path]
    ram = round(model.size_bytes * 1.1 / 1e9, 1) if model.size_bytes else None
    base = f"http://127.0.0.1:{port}/v1"
    return CatalogEntry.model_validate({
        "public_id": pid, "runtime": rt, "engine": eng,
        "launch_command": cmd + net, "port": port,
        "ready_url": f"{base}/models", "chat_endpoint": f"{base}/chat/completions",
        "upstream_alias": os.path.basename(path.rstrip("/")),
        "ram_estimate_gb": ram, "exclusive": ram is not None and ram > 40,
        "source_path": path, "origin": "local"})