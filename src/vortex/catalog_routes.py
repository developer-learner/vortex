"""Catalog add / add-new / remove routes."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException

from .catalog import Catalog
from .catalog_synth import SynthesisError, synthesize_entry
from . import discovery
from .lifecycle import Lifecycle
from .operations import OperationStore


def register_catalog_routes(
    app: FastAPI, catalog: Catalog, lifecycle: Lifecycle, ops: OperationStore,
    fresh_models: Callable[[], list[discovery.DiscoveredModel]], persist: Callable[[], None],
) -> None:
    @app.post("/api/discovered-models/{key}/add", status_code=201)
    def add_model(key: str) -> dict:
        model = next((m for m in fresh_models() if m.key == key), None)
        if model is None:
            raise HTTPException(404, detail="unknown")
        try:
            entry = synthesize_entry(model, catalog)
        except SynthesisError as exc:
            raise HTTPException(422, detail={"message": str(exc), "key": key}) from exc
        catalog.add(entry)
        persist()
        return {"added": entry.model_dump(mode="json")}

    @app.post("/api/discovered-models/add-new")
    def add_new() -> dict:
        added: list[str] = []
        skipped: list[dict[str, str]] = []
        for m in [m for m in fresh_models() if not m.in_catalog]:
            try:
                entry = synthesize_entry(m, catalog)
            except SynthesisError as exc:
                skipped.append({"key": m.key, "reason": str(exc)})
                continue
            catalog.add(entry)
            added.append(entry.public_id)
        persist()
        return {"added": added, "skipped": skipped}

    @app.delete("/api/catalog/{public_id}")
    def remove_model(public_id: str) -> dict:
        entry = catalog.by_public_id(public_id)
        if entry is None:
            raise HTTPException(404, detail="unknown")
        busy = lifecycle.occupying_pid(entry) is not None or ops.active_for(public_id)
        if entry.origin != "local" or busy:
            raise HTTPException(409, detail={"message": "config entry, or loaded/busy"})
        catalog.remove(public_id)
        persist()
        return {"removed": public_id}