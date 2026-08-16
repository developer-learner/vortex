"""Catalog model definition.

The catalog is config-first: only configured entries are loadable. Scanning is
never used to make a model loadable — it can only report "discovered, not
configured".

Terms (see docs/GLOSSARY.md):
- public model id: what clients call it (stable, e.g. Flash_IQ3XXS)
- runtime: the loader app (mtplx, omlx, vmlx, llama-server, LM Studio, ds4)
- engine: the compute core the runtime uses (llama.cpp, MLX, ...)
- upstream alias: what the runtime itself calls the model
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

MODEL_STATES = Literal["unloaded", "loading", "ready", "unloading", "error"]


class CatalogEntry(BaseModel):
    """One loadable model."""

    public_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    runtime: str
    engine: str
    launch_command: list[str]
    port: int = Field(ge=1, le=65535)
    ready_url: str
    chat_endpoint: str
    upstream_alias: str | None = None
    ram_estimate_gb: float | None = None
    ctx_size: int | None = None
    exclusive: bool = True
    pinned: bool = False

    @field_validator("launch_command")
    @classmethod
    def _nonempty_command(cls, v: list[str]) -> list[str]:
        if not v or not v[0]:
            raise ValueError("launch_command must be a non-empty argv")
        return v


class Catalog(BaseModel):
    """The full set of loadable models (config-first)."""

    entries: list[CatalogEntry] = Field(default_factory=list)

    def by_public_id(self, public_id: str) -> CatalogEntry | None:
        for e in self.entries:
            if e.public_id == public_id:
                return e
        return None

    def assert_unique_public_ids(self) -> None:
        seen: dict[str, str] = {}
        for e in self.entries:
            if e.public_id in seen:
                raise ValueError(
                    f"duplicate public id {e.public_id!r} (seen in {seen[e.public_id]} and {e.runtime})"
                )
            seen[e.public_id] = e.runtime

    def assert_unique_ports(self) -> None:
        seen: dict[int, str] = {}
        for e in self.entries:
            if e.port in seen:
                raise ValueError(
                    f"duplicate port {e.port} ({seen[e.port]} and {e.public_id})"
                )
            seen[e.port] = e.public_id


def load_catalog(path: Path) -> Catalog:
    """Load and validate a catalog file. Raises ValueError on any problem."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    try:
        catalog = Catalog.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"catalog {path} invalid: {exc}") from exc
    catalog.assert_unique_public_ids()
    catalog.assert_unique_ports()
    return catalog