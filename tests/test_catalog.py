from __future__ import annotations

import json
from pathlib import Path

import pytest

from vortex.catalog import Catalog, CatalogEntry, load_catalog


def _entry(**overrides: object) -> dict:
    base: dict[str, object] = {
        "public_id": "m1",
        "runtime": "llama-server",
        "engine": "llama.cpp",
        "launch_command": ["/bin/true"],
        "port": 9001,
        "ready_url": "http://127.0.0.1:9001/v1/models",
        "chat_endpoint": "http://127.0.0.1:9001/v1/chat/completions",
    }
    base.update(overrides)
    return base


def test_catalog_entry_roundtrip() -> None:
    entry = CatalogEntry.model_validate(_entry())
    assert entry.public_id == "m1"
    assert entry.exclusive is True
    assert entry.ram_estimate_gb is None


def test_catalog_rejects_duplicate_public_ids() -> None:
    """Duplicates are rejected on ANY construction path (D: model_validator),
    not just by a post-hoc assert the caller must remember to run."""
    from pydantic import ValidationError

    with pytest.raises((ValueError, ValidationError), match="duplicate public id"):
        Catalog(entries=[CatalogEntry.model_validate(_entry()),
                         CatalogEntry.model_validate(_entry(public_id="m1"))])
    with pytest.raises(ValidationError, match="duplicate public id"):
        Catalog.model_validate({"entries": [_entry(), _entry(public_id="m1")]})


def test_catalog_rejects_duplicate_ports() -> None:
    from pydantic import ValidationError

    with pytest.raises((ValueError, ValidationError), match="duplicate port"):
        Catalog(entries=[CatalogEntry.model_validate(_entry()),
                         CatalogEntry.model_validate(_entry(public_id="m2"))])
    with pytest.raises(ValidationError, match="duplicate port"):
        Catalog.model_validate({"entries": [_entry(), _entry(public_id="m2")]})


def test_catalog_rejects_non_http_url() -> None:
    with pytest.raises(ValueError, match="http"):
        CatalogEntry.model_validate(_entry(ready_url="ftp://127.0.0.1:9001/v1/models"))
    with pytest.raises(ValueError, match="host"):
        CatalogEntry.model_validate(_entry(chat_endpoint="http:///v1/chat/completions"))


def test_catalog_rejects_nonpositive_ram() -> None:
    with pytest.raises(ValueError, match=r"> 0"):
        CatalogEntry.model_validate(_entry(ram_estimate_gb=0))
    with pytest.raises(ValueError, match=r"> 0"):
        CatalogEntry.model_validate(_entry(ram_estimate_gb=-1.5))


def test_catalog_rejects_nonpositive_ctx() -> None:
    with pytest.raises(ValueError, match=r"> 0"):
        CatalogEntry.model_validate(_entry(ctx_size=0))


def test_catalog_rejects_empty_launch_command() -> None:
    with pytest.raises(ValueError, match="non-empty argv"):
        CatalogEntry.model_validate(_entry(launch_command=[]))


def test_catalog_rejects_bad_public_id() -> None:
    with pytest.raises(ValueError):
        CatalogEntry.model_validate(_entry(public_id="has space"))


def test_load_catalog_from_json(tmp_path: Path) -> None:
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(json.dumps({"entries": [_entry()]}), encoding="utf-8")
    catalog = load_catalog(catalog_file)
    assert catalog.by_public_id("m1") is not None
    assert catalog.by_public_id("nope") is None


def test_load_catalog_invalid_json_raises(tmp_path: Path) -> None:
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(catalog_file)