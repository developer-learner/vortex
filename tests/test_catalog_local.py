"""Frozen suite v39: entry origin, the local catalog file, add/remove/save
(AC-31, AC-34, AC-35 — the catalog-level half; the routes are in
tests/test_catalog_add_api.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from vortex.catalog import Catalog, CatalogEntry, load_catalog, save_local_entries


def _raw(public_id: str, port: int, **overrides: object) -> dict:
    base: dict[str, object] = {
        "public_id": public_id,
        "runtime": "mlx-serve",
        "engine": "mlx-serve",
        "launch_command": ["/bin/true"],
        "port": port,
        "ready_url": f"http://127.0.0.1:{port}/v1/models",
        "chat_endpoint": f"http://127.0.0.1:{port}/v1/chat/completions",
    }
    base.update(overrides)
    return base


def _write(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def test_entries_default_to_config_origin_and_no_source_path() -> None:
    entry = CatalogEntry.model_validate(_raw("m1", 8300))
    assert entry.origin == "config"
    assert entry.source_path is None


def test_load_merges_the_local_file_as_local_origin(tmp_path: Path) -> None:
    """Local-file entries join the catalog with origin 'local' (AC-35)."""
    config = _write(tmp_path / "catalog.json", [_raw("cfg", 8300)])
    local = _write(tmp_path / "catalog.local.json",
                   [_raw("added", 8200, source_path="/models/x")])
    catalog = load_catalog(config, local_path=local)
    assert catalog.by_public_id("cfg").origin == "config"
    added = catalog.by_public_id("added")
    assert added is not None and added.origin == "local"
    assert added.source_path == "/models/x"


def test_load_without_a_local_file_is_just_the_config(tmp_path: Path) -> None:
    config = _write(tmp_path / "catalog.json", [_raw("cfg", 8300)])
    catalog = load_catalog(config, local_path=tmp_path / "missing.json")
    assert [e.public_id for e in catalog.entries] == ["cfg"]


def test_local_entries_colliding_with_config_are_rejected(tmp_path: Path) -> None:
    """Duplicate ids or ports across the two files fail like config duplicates (AC-35)."""
    config = _write(tmp_path / "catalog.json", [_raw("cfg", 8300)])
    same_port = _write(tmp_path / "a.json", [_raw("other", 8300)])
    with pytest.raises((ValueError, ValidationError), match="duplicate port"):
        load_catalog(config, local_path=same_port)
    same_id = _write(tmp_path / "b.json", [_raw("cfg", 8201)])
    with pytest.raises((ValueError, ValidationError), match="duplicate public id"):
        load_catalog(config, local_path=same_id)


def test_add_appends_and_rejects_duplicates() -> None:
    catalog = Catalog(entries=[CatalogEntry.model_validate(_raw("cfg", 8300))])
    catalog.add(CatalogEntry.model_validate(_raw("new", 8200, origin="local")))
    assert catalog.by_public_id("new") is not None
    with pytest.raises(ValueError, match="duplicate public id"):
        catalog.add(CatalogEntry.model_validate(_raw("new", 8201, origin="local")))
    with pytest.raises(ValueError, match="duplicate port"):
        catalog.add(CatalogEntry.model_validate(_raw("newer", 8300, origin="local")))
    assert [e.public_id for e in catalog.entries] == ["cfg", "new"]


def test_remove_only_removes_local_entries() -> None:
    """Config entries cannot be removed; unknown ids raise KeyError (AC-34)."""
    catalog = Catalog(entries=[
        CatalogEntry.model_validate(_raw("cfg", 8300)),
        CatalogEntry.model_validate(_raw("added", 8200, origin="local")),
    ])
    with pytest.raises(ValueError, match="config"):
        catalog.remove("cfg")
    with pytest.raises(KeyError):
        catalog.remove("nope")
    removed = catalog.remove("added")
    assert removed.public_id == "added"
    assert [e.public_id for e in catalog.entries] == ["cfg"]


def test_save_writes_only_local_entries_and_round_trips(tmp_path: Path) -> None:
    """The local file holds exactly the local entries and reloads identically."""
    config = _write(tmp_path / "catalog.json", [_raw("cfg", 8300)])
    catalog = load_catalog(config)
    catalog.add(CatalogEntry.model_validate(
        _raw("added", 8200, origin="local", source_path="/models/x")))
    local = tmp_path / "catalog.local.json"
    save_local_entries(catalog, local)
    saved = json.loads(local.read_text(encoding="utf-8"))
    assert [e["public_id"] for e in saved["entries"]] == ["added"]
    reloaded = load_catalog(config, local_path=local)
    assert reloaded.by_public_id("added").source_path == "/models/x"
    assert reloaded.by_public_id("added").origin == "local"
    assert json.loads(config.read_text(encoding="utf-8"))["entries"][0]["public_id"] == "cfg"
