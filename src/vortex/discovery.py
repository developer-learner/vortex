"""Wrapper discovery: locate installed model-serving binaries and report status."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, TypeAdapter


class WrapperSpec(BaseModel):
    """Static description of a known wrapper binary."""

    model_config = {"frozen": True}

    name: str
    kind: Literal["cli", "ui", "runtime"]
    bin_names: tuple[str, ...]
    known_paths: tuple[str, ...] = ()
    version_flags: tuple[str, ...] = ("--version",)
    probe_version: bool = True
    port: int | None = None


class Wrapper(BaseModel):
    """Discovered status of a single wrapper."""

    model_config = {"frozen": True}

    name: str
    kind: str
    installed: bool
    binary_path: str | None = None
    version: str | None = None
    port: int | None = None
    port_open: bool = False
    in_catalog: bool = False


LMS_BIN = Path.home() / ".lmstudio/bin/lms"
LMSTUDIO_MODELS_ROOT = Path.home() / ".lmstudio/models"

WRAPPER_SPECS: tuple[WrapperSpec, ...] = (
    WrapperSpec(
        name="omlx",
        kind="cli",
        bin_names=("omlx",),
        known_paths=(os.path.expanduser("~/.omlx/bin/omlx"),),
        port=8000,
    ),
    WrapperSpec(
        name="mtplx",
        kind="cli",
        bin_names=("mtplx",),
        known_paths=(os.path.expanduser("~/.mtplx/bin/mtplx"),),
        port=8001,
    ),
    WrapperSpec(
        name="ollama",
        kind="cli",
        bin_names=("ollama",),
        known_paths=("/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"),
        port=11434,
    ),
    WrapperSpec(
        name="lmstudio",
        kind="ui",
        bin_names=("lmstudio",),
        known_paths=("/Applications/LM Studio.app/Contents/MacOS/LM Studio",),
        port=1234,
        probe_version=False,
    ),
    WrapperSpec(
        name="llama-server",
        kind="cli",
        bin_names=("llama-server",),
        known_paths=("/opt/homebrew/bin/llama-server",),
        port=8080,
    ),
    WrapperSpec(
        name="llama-cli",
        kind="cli",
        bin_names=("llama-cli",),
        known_paths=("/opt/homebrew/bin/llama-cli",),
    ),
    WrapperSpec(
        name="vllm",
        kind="cli",
        bin_names=("vllm",),
    ),
    WrapperSpec(
        name="mlx-lm",
        kind="cli",
        bin_names=("mlx_lm.generate",),
    ),
    WrapperSpec(
        name="mlx-serve",
        kind="cli",
        bin_names=("mlx-serve",),
        known_paths=("/opt/homebrew/bin/mlx-serve",),
    ),
    WrapperSpec(
        name="mlx-lm-server",
        kind="cli",
        bin_names=("mlx_lm.server",),
        port=8080,
        probe_version=False,
    ),
    WrapperSpec(
        name="ds4-server",
        kind="cli",
        bin_names=("ds4-server",),
        known_paths=(os.path.expanduser("~/dev/ds4/ds4-server"),),
        port=8005,
        probe_version=False,
    ),
    WrapperSpec(
        name="mlx-dspark",
        kind="cli",
        bin_names=("mlx-dspark",),
        known_paths=(os.path.expanduser("~/dev/mlx-dspark/run-server-8103.sh"),),
        port=8103,
        probe_version=False,
    ),
)


def _resolve_binary(spec: WrapperSpec, search_path: str | None) -> str | None:
    """Return the resolved binary path for a spec, or None if not found."""
    for bin_name in spec.bin_names:
        found = shutil.which(bin_name, path=search_path)
        if found is not None:
            return found
    for known in spec.known_paths:
        expanded = os.path.expanduser(known)
        if os.path.isabs(expanded) and os.path.exists(expanded) and os.access(expanded, os.X_OK):
            return expanded
    return None


def _probe_version(binary: str, version_flags: tuple[str, ...]) -> str | None:
    """Run the bounded version probe; return first non-empty stdout line on rc 0."""
    try:
        result = subprocess.run(
            [binary, *version_flags],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.strip():
            return line
    return None


def _check_port(port: int | None) -> bool:
    """Return True when a TCP connection to 127.0.0.1:port succeeds within 0.5s."""
    if port is None:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _default_lms_run() -> str:
    """Run lms ls --json and return stdout text."""
    result = subprocess.run(
        [str(LMS_BIN), "ls", "--json"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout


def lmstudio_model_paths(
    run: Callable[[], str] | None = None,
    models_root: Path | None = None,
) -> dict[str, str]:
    """Map modelKey -> absolute path from lms ls --json output."""
    if run is None:
        run = _default_lms_run
    if models_root is None:
        models_root = LMSTUDIO_MODELS_ROOT
    try:
        text = run()
        rows = TypeAdapter(list).validate_json(text)
        paths: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            model_key = row.get("modelKey")
            rel_path = row.get("path")
            if model_key and rel_path:
                paths[model_key] = str(models_root / rel_path)
        return paths
    except Exception:  # noqa: BLE001 — best-effort: an unreadable listing means no paths
        # Safe to ignore: discovery is best-effort; missing paths are handled downstream
        return {}


def _entry_matches(entry: Any, name: str) -> bool:
    """Return True when a catalog entry references the wrapper by name."""
    runtime = getattr(entry, "runtime", None)
    engine = getattr(entry, "engine", None)
    if name in (runtime, engine):
        return True
    launch = getattr(entry, "launch_command", None)
    if launch:
        try:
            first = launch[0]
        except (TypeError, IndexError):
            return False
        if os.path.basename(str(first)) == name:
            return True
    return False


def discover_wrappers(
    search_path: str | None = None,
    catalog_entries: list[Any] | None = None,
    ports: dict[str, int] | None = None,
) -> list[Wrapper]:
    """Discover all wrappers in WRAPPER_SPECS order and return their status."""
    resolved = [
        (spec, _resolve_binary(spec, search_path)) for spec in WRAPPER_SPECS
    ]

    probe_targets: list[tuple[WrapperSpec, str]] = [
        (spec, binary)
        for spec, binary in resolved
        if binary is not None and spec.probe_version and spec.kind != "ui"
    ]

    versions: dict[str, str | None] = {}
    if probe_targets:
        with ThreadPoolExecutor(max_workers=len(probe_targets)) as pool:
            results = pool.map(
                lambda item: (item[0].name, _probe_version(item[1], item[0].version_flags)),
                probe_targets,
            )
            versions = dict(results)

    wrappers: list[Wrapper] = []
    for spec, binary in resolved:
        installed = binary is not None
        version = versions.get(spec.name) if installed else None
        port = ports.get(spec.name) if ports is not None else spec.port
        port_open = _check_port(port) if installed else False
        in_catalog = False
        if catalog_entries:
            in_catalog = any(_entry_matches(entry, spec.name) for entry in catalog_entries)
        wrappers.append(
            Wrapper(
                name=spec.name,
                kind=spec.kind,
                installed=installed,
                binary_path=binary,
                version=version,
                port=port,
                port_open=port_open,
                in_catalog=in_catalog,
            )
        )
    return wrappers


class DiscoveredModel(BaseModel):
    model_config = {"frozen": True}
    key: str
    display_name: str
    publisher: str | None = None
    architecture: str | None = None
    quantization: str | None = None
    size_bytes: int | None = None
    params: str | None = None
    max_context: int | None = None
    fmt: str | None = None
    loaded: bool = False
    source: str
    in_catalog: bool = False
    path: str | None = None


LIBRARY_PROBES: tuple[tuple[str, int], ...] = (("lmstudio", 1234),)


def _get_json(url: str) -> Any:
    try:
        response = httpx.get(url, timeout=3.0)
    except (httpx.HTTPError, OSError):
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _resolve_unindexed_path(key: str, publisher: str | None, models_root: Path) -> str | None:
    """Locate a model folder on disk as models_root/<publisher>/<dir>.

    Picks the dir whose name starts with the key (case-insensitive), else the
    publisher's only dir; returns None when ambiguous or missing.
    """
    if not publisher:
        return None
    try:
        dirs = [d for d in (models_root / publisher).iterdir() if d.is_dir()]
    except OSError:
        return None
    matches = [d for d in dirs if d.name.lower().startswith(key.lower())]
    if len(matches) == 1:
        return str(matches[0])
    if not matches and len(dirs) == 1:
        return str(dirs[0])
    return None


def _dir_size(path: str) -> int | None:
    try:
        return sum(f.stat().st_size for f in Path(path).iterdir() if f.is_file())
    except OSError:
        return None


def _unindexed_rows(v0_body: Any, known: set[str], models_root: Path) -> list[dict]:
    """Convert /api/v0/models rows missing from the v1 library into v1-shaped rows.

    LM Studio's v1 library (and `lms ls`) is a cached index: a model downloaded
    after the index was built can be loaded yet absent there, while v0 still
    lists it.
    """
    data = v0_body.get("data") if isinstance(v0_body, dict) else None
    if not isinstance(data, list):
        return []
    rows: list[dict] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        key = raw.get("id")
        if not key or key in known:
            continue
        publisher = raw.get("publisher")
        path = _resolve_unindexed_path(key, publisher, models_root)
        rows.append(
            {
                "key": key,
                "display_name": key,
                "publisher": publisher,
                "architecture": raw.get("arch"),
                "quantization": raw.get("quantization"),
                "size_bytes": _dir_size(path) if path else None,
                "max_context_length": raw.get("max_context_length"),
                "format": raw.get("compatibility_type"),
                "loaded_instances": [key] if raw.get("state") == "loaded" else [],
                "path": path,
            }
        )
    return rows


def _fetch_library(base_url: str, models_root: Path | None = None) -> list[dict]:
    if models_root is None:
        models_root = LMSTUDIO_MODELS_ROOT
    body = _get_json(f"{base_url}/api/v1/models")
    if not isinstance(body, dict):
        return []
    models = body.get("models")
    if not isinstance(models, list):
        return []
    known = {str(m.get("key")) for m in models if isinstance(m, dict)}
    return (
        models
        + _unindexed_rows(_get_json(f"{base_url}/api/v0/models"), known, models_root)
        + _disk_rows(models_root)
    )


def _config_quant(config: dict) -> str | None:
    quant = config.get("quantization")
    if not isinstance(quant, dict):
        return None
    mode = quant.get("mode")
    if isinstance(mode, str) and mode != "affine":
        return mode.upper()
    bits = quant.get("bits")
    return f"{bits}bit" if bits else None


def _disk_row(model_dir: Path) -> dict | None:
    """Describe a model folder from its files, or None when it holds no weights."""
    try:
        files = [f for f in model_dir.iterdir() if f.is_file()]
    except OSError:
        return None
    names = [f.name for f in files]
    ggufs = sorted(n for n in names if n.endswith(".gguf"))
    weights_path = str(model_dir)
    if ggufs:
        fmt = "gguf"
        weights_path = str(model_dir / ggufs[0])
    elif "config.json" in names and any(n.endswith(".safetensors") for n in names):
        fmt = "mlx"
    else:
        return None
    config: dict = {}
    if "config.json" in names:
        try:
            loaded = TypeAdapter(dict).validate_json((model_dir / "config.json").read_bytes())
            config = loaded
        except Exception:  # noqa: BLE001 — best-effort: a bad config just means fewer labels
            config = {}
    text_config = config.get("text_config")
    ctx_source = text_config if isinstance(text_config, dict) else config
    return {
        "key": model_dir.name.lower(),
        "display_name": model_dir.name,
        "publisher": model_dir.parent.name,
        "architecture": config.get("model_type"),
        "quantization": _config_quant(config),
        "size_bytes": sum(f.stat().st_size for f in files),
        "max_context_length": ctx_source.get("max_position_embeddings"),
        "format": fmt,
        "loaded_instances": [],
        "path": weights_path,
        "on_disk_only": True,
    }


def _disk_rows(models_root: Path) -> list[dict]:
    """Scan models_root/<publisher>/<model> for folders LM Studio may not list.

    discover_models drops any of these whose folder LM Studio already reported.
    """
    rows: list[dict] = []
    try:
        publishers = sorted(d for d in models_root.iterdir() if d.is_dir())
    except OSError:
        return []
    for publisher in publishers:
        try:
            model_dirs = sorted(d for d in publisher.iterdir() if d.is_dir())
        except OSError:
            continue
        for model_dir in model_dirs:
            row = _disk_row(model_dir)
            if row is not None:
                rows.append(row)
    return rows


def _model_dir(path: str) -> str:
    return str(Path(path).parent) if path.endswith(".gguf") else path


def discover_models(
    catalog_entries: list[Any] | None = None,
    fetch: Callable[[str], list[dict]] = _fetch_library,
    probes: tuple[tuple[str, int], ...] = LIBRARY_PROBES,
    paths: Callable[[], dict[str, str]] | None = None,
) -> list[DiscoveredModel]:
    """Discover installed models and report status."""
    if paths is None:
        paths = lmstudio_model_paths
    paths_map = paths()
    aliases: set[str | None] = set()
    source_paths: set[str] = set()
    launch_cmds: set[str] = set()
    for entry in catalog_entries or []:
        aliases.add(getattr(entry, "upstream_alias", None))
        aliases.add(getattr(entry, "public_id", None))
        sp = getattr(entry, "source_path", None)
        if sp:
            source_paths.add(str(sp))
        lc = getattr(entry, "launch_command", None)
        if lc:
            for part in lc:
                launch_cmds.add(str(part))
    found: list[DiscoveredModel] = []
    seen_dirs = {_model_dir(p) for p in paths_map.values()}
    for source, port in probes:
        for raw in fetch(f"http://127.0.0.1:{port}"):
            key = raw.get("key")
            if not key:
                continue
            raw_path = paths_map.get(key) or raw.get("path")
            row_source = source
            if raw.get("on_disk_only"):
                if raw_path is None or _model_dir(raw_path) in seen_dirs:
                    continue
                row_source = "disk"
            if raw_path is not None:
                seen_dirs.add(_model_dir(raw_path))
            quant = raw.get("quantization")
            quant_name = quant.get("name") if isinstance(quant, dict) else quant
            model_path = raw_path
            in_catalog = key in aliases
            if not in_catalog and model_path is not None and (model_path in source_paths or model_path in launch_cmds):
                in_catalog = True
            found.append(
                DiscoveredModel(
                    key=key,
                    display_name=raw.get("display_name") or key,
                    publisher=raw.get("publisher"),
                    architecture=raw.get("architecture"),
                    quantization=quant_name,
                    size_bytes=raw.get("size_bytes"),
                    params=raw.get("params_string"),
                    max_context=raw.get("max_context_length"),
                    fmt=raw.get("format"),
                    loaded=bool(raw.get("loaded_instances")),
                    source=row_source,
                    in_catalog=in_catalog,
                    path=model_path,
                )
            )
    return found