"""Wrapper discovery: locate installed model-serving binaries and report status."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from pydantic import BaseModel


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