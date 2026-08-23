"""Vortex — one place that owns every local LLM on this machine.

Two surfaces:
- Universal (OpenAI Chat Completions): /v1/models, /v1/chat/completions
- Management: /api/catalog, /api/status, /api/models/{id}/load, .../unload,
  /api/operations/{id}
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from .catalog import Catalog, load_catalog
from .lifecycle import (
    Lifecycle,
    PortConflictError,
    SidecarStore,
    SpawnError,
    as_pid,
    log_stale_sidecars,
)
from .manager import Manager, MemoryConflict, estimate_ram_total_gb, estimate_ram_used_gb
from .operations import OperationStore
from .ui import UI_PAGE

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def build_app(
    catalog: Catalog | None = None,
    sidecar_dir: Path | None = None,
) -> FastAPI:
    catalog = catalog or load_catalog(_REPO_ROOT / "config/catalog.json")
    sidecars = SidecarStore(sidecar_dir or _REPO_ROOT / "data/sidecars")
    ops = OperationStore()
    lifecycle = Lifecycle(catalog, sidecars)
    manager = Manager(catalog, lifecycle, ops)
    log_stale_sidecars(sidecars, catalog)

    app = FastAPI(title="Vortex", version="0.1.0")

    @app.get("/")
    def dashboard() -> Response:
        """Operator dashboard shell; JS polls /api/* client-side."""
        return Response(content=UI_PAGE, media_type="text/html")

    @app.get("/v1/models")
    def list_v1_models() -> dict:
        ready = manager.all_ready()
        return {
            "object": "list",
            "data": [
                {
                    "id": e.public_id,
                    "object": "model",
                    "owned_by": e.runtime,
                }
                for e in ready
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        body = await request.json()
        model = body.get("model")
        entry = catalog.by_public_id(model) if model else None
        if entry is None or manager.entry_state(entry, ops.active_for(entry.public_id)) != "ready":
            raise HTTPException(status_code=404, detail=f"model {model!r} is not loaded")
        stream = bool(body.get("stream", False))

        if stream:
            async def passthrough():
                async with (
                    httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client,
                    client.stream("POST", entry.chat_endpoint, json=body) as upstream,
                ):
                    async for chunk in upstream.aiter_bytes():
                        yield chunk

            return StreamingResponse(
                passthrough(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            upstream = await client.post(entry.chat_endpoint, json=body, headers={"Content-Type": "application/json"})
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    @app.get("/api/catalog")
    def catalog_view() -> dict:
        active_by_id = {e.public_id: ops.active_for(e.public_id) for e in catalog.entries}
        return {
            "entries": [
                {
                    **e.model_dump(),
                    "state": manager.entry_state(e, active_by_id.get(e.public_id)),
                    "port_pid": as_pid(lifecycle.occupying_pid(e)),
                }
                for e in catalog.entries
            ]
        }

    @app.get("/api/status")
    def status_view() -> dict:
        return {
            "ram_used_gb": round(estimate_ram_used_gb(), 1),
            "ram_total_gb": round(estimate_ram_total_gb(), 1),
            "loaded": [
                {
                    "id": e.public_id,
                    "runtime": e.runtime,
                    "engine": e.engine,
                    "port": e.port,
                    "ram_estimate_gb": e.ram_estimate_gb,
                }
                for e in manager.all_ready()
            ],
        }

    @app.post("/api/models/{public_id}/load", status_code=202)
    def load(public_id: str) -> dict:
        try:
            return manager.load(public_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MemoryConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "required_gb": exc.required_gb,
                    "eviction_candidates": exc.candidates,
                },
            ) from exc
        except PortConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except SpawnError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/models/{public_id}/unload", status_code=202)
    def unload(public_id: str) -> dict:
        try:
            return manager.unload(public_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/operations/{op_id}")
    def operation(op_id: str) -> dict:
        snapshot = ops.snapshot(op_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="unknown operation")
        return snapshot

    return app