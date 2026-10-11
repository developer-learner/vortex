"""HTTP surface for the Speed page: list, start a run, refuse mutations mid-run.

While a run is in progress, load and unload requests are refused with 409
busy, and a second run is refused the same way.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .catalog import Catalog
from .manager import Manager
from .operations import OperationStore
from .speed_runner import SpeedRun, SpeedRunBusy
from .speed_ui import SPEED_PAGE
from .speedtest import load_results

MAX_MODELS = 3
_MUTATION_RE = re.compile(r"/api/models/[^/]+/(load|unload)")


def register_speed_routes(
    app: FastAPI,
    catalog: Catalog,
    manager: Manager,
    ops: OperationStore,
    results_path: Path,
) -> None:
    run = SpeedRun(catalog, manager, ops, results_path)

    @app.middleware("http")
    async def refuse_mutations_while_running(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if (
            request.method == "POST"
            and run.running
            and _MUTATION_RE.fullmatch(request.url.path)
        ):
            return JSONResponse(
                status_code=409,
                content={"detail": {"message": "a speed test is running", "busy": True}},
            )
        return await call_next(request)

    @app.get("/speed")
    def speed_page() -> Response:
        return Response(content=SPEED_PAGE, media_type="text/html")

    @app.get("/api/speed")
    def speed_view() -> dict:
        # Read `running` BEFORE the rows: once it reads False the rows are
        # final. Read after (with port scans in between), a run finishing
        # mid-request reported "not running" next to a stale "loading".
        running = run.running
        rows = run.rows()
        results = load_results(results_path)
        models = []
        for entry in catalog.entries:
            row = rows.get(entry.public_id)
            models.append(
                {
                    "public_id": entry.public_id,
                    "display_name": entry.display_name,
                    "quant": entry.quant,
                    "runtime": entry.runtime,
                    "ram_estimate_gb": entry.ram_estimate_gb,
                    "state": manager.entry_state(entry, ops.active_for(entry.public_id)),
                    "result": results.get(entry.public_id),
                    "run_status": row["status"] if row is not None else None,
                    "run_message": row["message"] if row is not None else "",
                }
            )
        return {"running": running, "max_models": MAX_MODELS, "models": models}

    @app.post("/api/speed/run", status_code=202)
    def start_run(body: dict) -> dict:
        models = body.get("models")
        if not isinstance(models, list) or not all(isinstance(m, str) for m in models):
            raise HTTPException(status_code=400, detail="models must be a list of model ids")
        try:
            run.start(models)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SpeedRunBusy as exc:
            raise HTTPException(
                status_code=409, detail={"message": str(exc), "busy": True}
            ) from exc
        return {"started": models}