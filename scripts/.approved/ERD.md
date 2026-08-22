# ERD — vortex M1: operator dashboard (erd_version 1)

Stack: the existing FastAPI app (`src/vortex/app.py`, package `vortex`).
NO new dependencies, NO new files beyond the one below, NO external
assets (everything inline in one HTML document). Zero new endpoints.

The dashboard's design source is `examples/ui-demo/index.html` (committed,
CEO-approved look). Task 1 PORTS that document into Python; task 2 WIRES
the route. The JS logic is already proven — port it verbatim except for
the exact adjustments listed.

## File inventory (M1 build) — DAG order

### 1. src/vortex/ui.py — NEW

A single module-level constant:

    UI_PAGE: str = """<!doctype html> ... </html>"""

No imports. No functions. No f-strings (the page contains literal `{`
braces from JS/CSS — a plain string constant avoids all escaping bugs).
UTF-8 encoded source; the file starts with the module docstring:
"""Operator dashboard shell (router phase 2). Served at "/" by app.py;
JS polls /api/* client-side."""

Port examples/ui-demo/index.html with these EXACT adjustments:
- Wrap as the `UI_PAGE` string constant (triple-quoted, no interpolation).
- Keep the `<title>vortex · model menu</title>` tag verbatim.
- Keep these element ids verbatim (the frozen suite pins them):
  `ramlabel`, `ramfill`, `rows`, `conflict`, `conflictbody`, `down`.
- Keep the fetch URLs verbatim: `/api/status`, `/api/catalog`,
  `/api/operations/`, and action paths `/api/models/{id}/load|unload`.
- Keep button data attributes: `data-act="load"`, `data-act="unload"`,
  `data-id="${...}"`.
- Keep the RAM bar zones: width % with class `warn` above 70 and
  `danger` above 85.
- Keep the poll interval at 2000 ms and operation poll at 500 ms.
- Keep the daemon-down banner text mentioning `:9000` and the start
  command `.venv/bin/uvicorn vortex.app:build_app --factory --port 9000`.
- Keep the footer line noting this is served by the daemon (adjust the
  wording to "served at :9000/ by the daemon · polls /api/* every 2s").
- REMOVE nothing else; keep CSS, escaping helper, event delegation.

### 2. src/vortex/app.py — EDIT (existing file; anchored edits only)

Edit 1 — imports. After the existing line

    from .operations import OperationStore

add exactly:

    from .ui import UI_PAGE

Edit 2 — route. Immediately BEFORE the existing line

    @app.get("/v1/models")

insert exactly:

    @app.get("/")
    def dashboard() -> Response:
        """Operator dashboard shell; JS polls /api/* client-side."""
        return Response(content=UI_PAGE, media_type="text/html")

Nothing else in app.py changes.

## Constraints (both files)

Type hints on the new function signature. No new imports beyond
`UI_PAGE`. No global mutable state. No external asset references
(no `src="http…"` / `href="http…"` anywhere in the page). Each file
under 300 lines. No TODO comments. No print/logging in ui.py.
