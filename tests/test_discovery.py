"""Frozen tests for src.vortex.discovery (ERD-DELTA v15: engine-wrapper inventory)."""

import importlib
import re
import socket
from pathlib import Path

from vortex.discovery import WRAPPER_SPECS, discover_wrappers

from vortex.catalog import CatalogEntry

REGISTRY_ORDER = [
    "omlx",
    "mtplx",
    "ollama",
    "lmstudio",
    "llama-server",
    "llama-cli",
    "vllm",
    "mlx-lm",
]

# Third-party names the discovery module must never import (AC-2 stdlib-only).
FORBIDDEN_IMPORTS = [
    "requests",
    "httpx",
    "psutil",
    "fastapi",
    "uvicorn",
    "torch",
    "mlx",
    "fire",
    "rich",
    "yaml",
    "tomli",
]
ALLOWED_IMPORT_ROOTS = {
    "os",
    "re",
    "enum",
    "socket",
    "subprocess",
    "shutil",
    "pathlib",
    "typing",
    "collections",
    "datetime",
    "functools",
    "concurrent",
    "pydantic",
    "__future__",
}


def fake_bin(path: Path, name: str, version_line: str = "FAKE-VERSION") -> Path:
    """A tiny executable that logs its argv (via env) and prints one line."""
    bin_path = path / name
    bin_path.write_text(
        "#!/bin/sh\n"
        "if [ -n \"$VORTEX_TEST_LOG\" ]; then\n"
        "  printf '%s\\n' \"$0 $*\" >> \"$VORTEX_TEST_LOG\"\n"
        "fi\n"
        f"printf '%s\\n' '{version_line}'\n"
    )
    bin_path.chmod(0o755)
    return bin_path


def fake_bin_exit1(path: Path, name: str) -> Path:
    bin_path = path / name
    bin_path.write_text("#!/bin/sh\nexit 1\n")
    bin_path.chmod(0o755)
    return bin_path


def by_name(found, name):
    for w in found:
        if w.name == name:
            return w
    raise AssertionError(f"wrapper {name!r} not in result {[w.name for w in found]}")


def test_registry_covers_the_named_wrappers():
    names = {s.name for s in WRAPPER_SPECS}
    assert {"omlx", "mtplx", "ollama", "lmstudio", "llama-server"} <= names
    for spec in WRAPPER_SPECS:
        assert spec.name
        assert spec.bin_names
        assert spec.kind in {"cli", "ui", "runtime"}


def test_registry_entries_are_sane_and_ordered():
    assert [s.name for s in WRAPPER_SPECS] == REGISTRY_ORDER
    by = {s.name: s for s in WRAPPER_SPECS}
    assert by["omlx"].port == 8000
    assert by["ollama"].port == 11434
    assert by["llama-cli"].port is None
    assert by["lmstudio"].kind == "ui"
    assert by["mlx-lm"].kind == "cli"
    assert by["lmstudio"].probe_version is False
    for spec in WRAPPER_SPECS:
        if spec.kind == "ui":
            assert spec.probe_version is False
        else:
            assert spec.probe_version is True
    assert by["mlx-lm"].bin_names == ("mlx_lm.generate", "mlx_lm.server")
    assert "llama-server.exe" not in by["llama-server"].bin_names
    assert "llama-cli.exe" not in by["llama-cli"].bin_names


def test_finds_an_installed_binary_on_path(tmp_path):
    fake_bin(tmp_path, "ollama", "ollama version 0.5.7")
    results = discover_wrappers(search_path=str(tmp_path))
    w = by_name(results, "ollama")
    assert w.installed is True
    assert w.binary_path == str(tmp_path / "ollama")
    assert w.version == "ollama version 0.5.7"
    assert w.port == 11434
    assert w.kind == "cli"


def test_unresolved_wrappers_report_not_installed(tmp_path):
    results = discover_wrappers(search_path=str(tmp_path))
    assert [w.name for w in results] == REGISTRY_ORDER
    assert all(w.installed is False for w in results)
    assert all(w.binary_path is None for w in results)
    assert all(w.version is None for w in results)


def test_version_probe_records_first_stdout_line(tmp_path):
    fake_bin(tmp_path, "mtplx", "mtplx 3.8")
    w = by_name(discover_wrappers(search_path=str(tmp_path)), "mtplx")
    assert w.version == "mtplx 3.8"


def test_failed_version_probe_reports_empty(tmp_path):
    fake_bin_exit1(tmp_path, "llama-server")
    w = by_name(discover_wrappers(search_path=str(tmp_path)), "llama-server")
    assert w.version is None
    assert w.installed is True


def test_only_probe_subprocess_is_the_version_check(tmp_path, monkeypatch):
    log = tmp_path / "argv.log"
    monkeypatch.setenv("VORTEX_TEST_LOG", str(log))
    fake_bin(tmp_path, "ollama", "x")
    fake_bin(tmp_path, "llama-cli", "x")
    fake_bin(tmp_path, "lmstudio", "x")
    discover_wrappers(search_path=str(tmp_path))
    invocations = sorted(log.read_text().splitlines())
    assert invocations == [
        f"{tmp_path / 'llama-cli'} --version",
        f"{tmp_path / 'ollama'} --version",
    ]


def test_mlx_lm_resolves_only_its_console_script_names(tmp_path):
    fake_bin(tmp_path, "mlx_lm.generate", "mlx 14.0.2")
    results = discover_wrappers(search_path=str(tmp_path))
    w = by_name(results, "mlx-lm")
    assert w.installed is True
    assert w.version == "mlx 14.0.2"
    bare_only = tmp_path / "bare"
    bare_only.mkdir()
    fake_bin(bare_only, "mlx_lm", "mlx 14.0.2")
    results = discover_wrappers(search_path=str(bare_only))
    w = by_name(results, "mlx-lm")
    assert w.installed is False
    assert w.binary_path is None


def test_shared_default_ports_report_the_port_not_the_process(tmp_path):
    fake_bin(tmp_path, "omlx", "omlx 1.2")
    fake_bin(tmp_path, "vllm", "vllm 0.7")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        results = discover_wrappers(
            search_path=str(tmp_path), ports={"omlx": port, "vllm": port}
        )
        assert by_name(results, "omlx").port_open is True
        assert by_name(results, "vllm").port_open is True
    finally:
        sock.close()


def test_in_catalog_matches_absolute_launch_path_by_basename(tmp_path):
    fake_bin(tmp_path, "vllm", "vllm 0.7")
    fake_bin(tmp_path, "ollama", "ollama 0.5.7")
    catalog_entries = [
        CatalogEntry(
            public_id="V-ABS",
            runtime="custom-runtime",
            engine="custom-engine",
            launch_command=["/usr/local/share/bin/vllm", "--port", "8000"],
            port=8000,
            ready_url="http://127.0.0.1:8000/v1/models",
            chat_endpoint="http://127.0.0.1:8000/v1/chat/completions",
        ),
    ]
    results = discover_wrappers(
        search_path=str(tmp_path), catalog_entries=catalog_entries
    )
    assert by_name(results, "vllm").in_catalog is True
    assert by_name(results, "ollama").in_catalog is False


def test_port_check_reports_open_and_closed(tmp_path):
    fake_bin(tmp_path, "vllm", "vllm 0.7")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        w = by_name(
            discover_wrappers(search_path=str(tmp_path), ports={"vllm": port}),
            "vllm",
        )
        assert w.port_open is True
    finally:
        sock.close()
    w = by_name(
        discover_wrappers(search_path=str(tmp_path), ports={"vllm": port}),
        "vllm",
    )
    assert w.port_open is False


def test_in_catalog_reflects_catalog_entries(tmp_path):
    fake_bin(tmp_path, "ollama", "x")
    fake_bin(tmp_path, "llama-server", "x")
    catalog_entries = [
        CatalogEntry(
            public_id="O-CLI",
            runtime="ollama",
            engine="llama.cpp",
            launch_command=["ollama", "serve", "--port", "11434"],
            port=11434,
            ready_url="http://127.0.0.1:11434",
            chat_endpoint="http://127.0.0.1:11434/v1/chat/completions",
        ),
        CatalogEntry(
            public_id="LLS",
            runtime="llama-server",
            engine="llama.cpp",
            launch_command=["llama-server", "-m", "q4.gguf"],
            port=8080,
            ready_url="http://127.0.0.1:8080",
            chat_endpoint="http://127.0.0.1:8080/v1/chat/completions",
        ),
    ]
    results = discover_wrappers(
        search_path=str(tmp_path), catalog_entries=catalog_entries
    )
    assert by_name(results, "ollama").in_catalog is True
    assert by_name(results, "vllm").in_catalog is False


def test_discovery_module_is_stdlib_only():
    module = importlib.import_module("vortex.discovery")
    source = Path(module.__file__).read_text()
    for name in FORBIDDEN_IMPORTS:
        assert re.search(rf"^\s*(?:import|from)\s+{re.escape(name)}\b", source, re.MULTILINE) is None, (
            f"discovery.py must not import {name!r}"
        )
    for root in re.findall(
        r"^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import)", source, re.MULTILINE
    ):
        top = (root[0] or root[1]).split(".")[0]
        assert top in ALLOWED_IMPORT_ROOTS, (
            f"discovery.py imports unexpected module {top!r}"
        )