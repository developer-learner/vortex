"""Vortex — one place that owns every local LLM on this machine.

Two surfaces:
- Universal (OpenAI Chat Completions): /v1/models, /v1/chat/completions
- Management: /api/catalog, /api/status, /api/models/{id}/load, .../unload,
  /api/operations/{id}
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from collections.abc import Callable
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from .catalog import Catalog, load_catalog
from .discovery import Wrapper, discover_wrappers
from .lifecycle import (
    Lifecycle,
    PortConflictError,
    SidecarStore,
    as_pid,
    log_stale_sidecars,
    terminate,
)
from .manager import BusyError, Manager, MemoryConflict
from .memory import (
    estimate_ram_total_gb,
    estimate_ram_used_gb,
    ram_used_source,
)
from .operations import OperationStore
from .ui import UI_PAGE

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def build_app(
    catalog: Catalog | None = None,
    sidecar_dir: Path | None = None,
    wrapper_discovery=discover_wrappers,
    on_shutdown: Callable[[], None] | None = None,
) -> FastAPI:
    catalog = catalog or load_catalog(_REPO_ROOT / "config/catalog.json")
    sidecars = SidecarStore(sidecar_dir or _REPO_ROOT / "data/sidecars")
    ops = OperationStore()
    lifecycle = Lifecycle(catalog, sidecars)
    manager = Manager(catalog, lifecycle, ops)
    log_stale_sidecars(sidecars, catalog)
    wrapper_cache: dict[str, tuple[float, list[Wrapper]]] = {}

    app = FastAPI(title="Vortex", version="0.1.0")

    @app.get("/")
    def dashboard() -> Response:
        """Operator dashboard shell; JS polls /api/* client-side."""
        return Response(content=UI_PAGE, media_type="text/html")

    @app.get("/v1/models")
    def list_v1_models() -> dict:
        ready = manager.client_ready()
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
        # The client addresses the model by its public_id; the runtime knows it
        # by its own upstream_alias. Remap before forwarding (both paths).
        forwarded = {**body, "model": entry.upstream_alias or entry.public_id}

        if stream:
            # Open the upstream and inspect its status BEFORE returning a 200
            # event-stream: an upstream rejection (404/503) must reach the client
            # as that status, not as a successful-looking SSE body.
            client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
            try:
                upstream_request = client.build_request(
                    "POST", entry.chat_endpoint, json=forwarded
                )
                upstream = await client.send(upstream_request, stream=True)
            except httpx.RequestError as exc:
                await client.aclose()
                raise HTTPException(status_code=502, detail=f"upstream connection failed: {exc}") from exc
            if upstream.status_code != 200:
                await upstream.aread()
                content, status = upstream.content, upstream.status_code
                media = upstream.headers.get("content-type", "application/json")
                await upstream.aclose()
                await client.aclose()
                return Response(content=content, status_code=status, media_type=media)

            async def passthrough():
                try:
                    async for chunk in upstream.aiter_bytes():
                        yield chunk
                finally:
                    await upstream.aclose()
                    await client.aclose()

            return StreamingResponse(
                passthrough(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                upstream = await client.post(entry.chat_endpoint, json=forwarded, headers={"Content-Type": "application/json"})
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"upstream connection failed: {exc}") from exc
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
            "ram_source": ram_used_source(),
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
        except BusyError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "busy": True,
                    "operation": exc.operation,
                    "active_kind": exc.kind,
                    "active_model": exc.public_id,
                },
            ) from exc
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

    @app.post("/api/models/{public_id}/unload", status_code=202)
    def unload(public_id: str) -> dict:
        try:
            return manager.unload(public_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BusyError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "busy": True,
                    "operation": exc.operation,
                    "active_kind": exc.kind,
                    "active_model": exc.public_id,
                },
            ) from exc

    @app.get("/api/operations/{op_id}")
    def operation(op_id: str) -> dict:
        snapshot = ops.snapshot(op_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="unknown operation")
        return snapshot

    @app.post("/api/shutdown")
    def shutdown() -> Response:
        unloaded: list[str] = []
        for entry in manager.all_ready():
            terminate(entry)
            unloaded.append(entry.public_id)

        def _stop() -> None:
            if on_shutdown is not None:
                on_shutdown()
            else:
                os.kill(os.getpid(), signal.SIGTERM)

        return Response(
            content='{"stopping": true, "unloaded": ' + _json_list(unloaded) + "}",
            media_type="application/json",
            background=_Background(_stop),
        )

    def _get_wrappers() -> list[Wrapper]:
        now = time.time()
        cached = wrapper_cache.get("default")
        if cached is not None and now - cached[0] <= 60.0:
            return cached[1]
        findings = wrapper_discovery(catalog_entries=catalog.entries)
        wrapper_cache["default"] = (now, findings)
        return findings

    @app.get("/api/engine-wrappers")
    def engine_wrappers() -> dict:
        wrappers = [dict(w) for w in _get_wrappers() if w.installed]
        return {"wrappers": wrappers}

    @app.post("/api/engine-wrappers/discover")
    def engine_wrappers_discover() -> dict:
        wrapper_cache.clear()
        findings = wrapper_discovery(catalog_entries=catalog.entries)
        wrapper_cache["default"] = (time.time(), findings)
        wrappers = [dict(w) for w in findings if w.installed]
        newly_found = [w.name for w in findings if w.installed and not w.in_catalog]
        return {"wrappers": wrappers, "newly_found": newly_found}

    return app


def _json_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


class _Background:
    def __init__(self, func: Callable[[], None]) -> None:
        self._func = func

    async def __call__(self) -> None:
        self._func()
