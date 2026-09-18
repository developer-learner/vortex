# ERD-DELTA v32 — LM Studio library discovery (browse tier)

Adds a read-only surface that enumerates the models a library wrapper (LM
Studio on :1234) has already downloaded, so the operator can browse them on the
dashboard instead of hand-editing `config/catalog.json`. This milestone is
**browse only**: it reports discovered models, never mutates the catalog and
never loads a model. Config-first is preserved — a discovered model is
"discovered, not configured" (the exact status `catalog.py` already reserves);
promotion into the catalog is a later milestone.

The feature is a direct structural mirror of the v14 engine-wrappers inventory
(discovery function → injected into `build_app` → GET inventory + POST rescan
routes → dashboard section with a rescan button). Follow that precedent.

## Changed acceptance criteria

New: **AC-9** (discover_models probe + DiscoveredModel), **AC-10** (the two
`/api/discovered-models` routes, discovery injected into build_app), **AC-11**
(the "Discovered models" dashboard section + Scan control). Full text in
`PRD.md` under "v32 acceptance criteria".

## Superseded acceptance criteria

None. All three ACs are additive; no existing route, schema, or AC changes.

## Changed files

- `src/vortex/discovery.py` — EDIT. Add `DiscoveredModel`, `LIBRARY_PROBES`,
  `_fetch_library`, `discover_models`; add `import httpx` and
  `from collections.abc import Callable`. Existing wrapper discovery untouched.
- `src/vortex/app.py` — EDIT. Import `DiscoveredModel, discover_models`; add a
  `model_discovery=discover_models` parameter to `build_app`; add a
  `model_cache`; add `_get_models()` and the two routes.
- `src/vortex/ui.py` — EDIT. Add a `#discoveredmodels` section, `renderModels`,
  `pollModels`, a Scan click handler, and the poll-cadence wiring.

## Task DAG

- **T1** `src/vortex/discovery.py` — depends_on: none
- **T2** `src/vortex/app.py` — depends_on: T1  (imports the T1 symbols)
- **T3** `src/vortex/ui.py` — depends_on: none  (pure UI_PAGE string; no runtime dep)

## Test-to-file mapping

These test files are new this freeze, so their node-ids are not yet in the
frozen `test-nodeids` and cannot be pre-pinned in `contracts.test_mapping`
(the pin gate rejects unknown node-ids). Each is pinned to its owner file here
instead; the EM maps each to the task owning that file, per the DAG above.

* `tests/test_discovered_models.py::test_probe_maps_every_library_entry_to_a_discovered_model`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_discovered_model_carries_the_metadata_fields`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_loaded_flag_reflects_loaded_instances`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_in_catalog_flag_matches_key_against_catalog_upstream_alias`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_library_unreachable_yields_no_models_never_an_error`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models.py::test_entries_without_a_key_are_skipped`
    -> `src/vortex/discovery.py`
* `tests/test_discovered_models_api.py::test_get_lists_discovered_models`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_wire_schema_carries_all_discovered_model_fields`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_discover_post_flags_models_not_in_catalog`
    -> `src/vortex/app.py`
* `tests/test_discovered_models_api.py::test_build_app_defaults_to_real_model_discovery`
    -> `src/vortex/app.py`
* `tests/test_ui_discovered_models.py::test_ui_has_discovered_models_section`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_ui_fetches_the_discovered_models_endpoint`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_ui_renders_discovered_model_fields_from_the_api`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_scan_button_posts_to_the_rescan_route`
    -> `src/vortex/ui.py`
* `tests/test_ui_discovered_models.py::test_poll_models_runs_on_the_existing_cadence`
    -> `src/vortex/ui.py`

## Coder briefs (verbatim)

### T1 — src/vortex/discovery.py

This is an EDIT to an existing file. Make exactly two changes; change nothing
else in the file.

**(a)** In the import block at the top, add `import httpx` alongside the other
imports, and add `from collections.abc import Callable`. The block already has
`import os`, `import shutil`, `import socket`, `import subprocess`,
`from concurrent.futures import ThreadPoolExecutor`, `from typing import Any,
Literal`, and `from pydantic import BaseModel`. After the change the block also
contains `from collections.abc import Callable` and `import httpx`.

**(b)** APPEND the following to the END of the file, after the existing
`discover_wrappers` function. Insert it verbatim:

```python


class DiscoveredModel(BaseModel):
    """A model a library wrapper has downloaded — discovered, never loadable.

    Config-first is preserved: this is a report, not a catalog entry.
    `in_catalog` is true when the model's key already matches a catalog entry's
    upstream alias (or public id).
    """

    model_config = {"frozen": True}

    key: str
    display_name: str
    publisher: str | None = None
    architecture: str | None = None
    quantization: str | None = None
    size_bytes: int | None = None
    params: str | None = None
    max_context: int | None = None
    fmt: str | None = None
    loaded: bool = False
    source: str
    in_catalog: bool = False


LIBRARY_PROBES: tuple[tuple[str, int], ...] = (("lmstudio", 1234),)


def _fetch_library(base_url: str) -> list[dict]:
    """GET <base_url>/api/v1/models; its models list, [] on any failure.

    Read-only: an unreachable or non-200 library is reported as no models,
    never an exception (mirrors _check_port's tolerance for absent wrappers).
    """
    try:
        response = httpx.get(f"{base_url}/api/v1/models", timeout=3.0)
    except (httpx.HTTPError, OSError):
        return []
    if response.status_code != 200:
        return []
    try:
        body = response.json()
    except ValueError:
        return []
    models = body.get("models")
    return models if isinstance(models, list) else []


def discover_models(
    catalog_entries: list | None = None,
    fetch: Callable[[str], list[dict]] = _fetch_library,
    probes: tuple[tuple[str, int], ...] = LIBRARY_PROBES,
) -> list:
    """Enumerate every model each library wrapper has downloaded.

    Never launches, loads, or alters anything — it reads the wrapper's own
    library listing. `fetch` is injectable so the routes are testable without a
    running library. Returns a list of DiscoveredModel.
    """
    aliases: set[str | None] = set()
    for entry in catalog_entries or []:
        aliases.add(getattr(entry, "upstream_alias", None))
        aliases.add(getattr(entry, "public_id", None))
    found: list = []
    for source, port in probes:
        for raw in fetch(f"http://127.0.0.1:{port}"):
            key = raw.get("key")
            if not key:
                continue
            quant = raw.get("quantization")
            quant_name = quant.get("name") if isinstance(quant, dict) else quant
            found.append(
                DiscoveredModel(
                    key=key,
                    display_name=raw.get("display_name") or key,
                    publisher=raw.get("publisher"),
                    architecture=raw.get("architecture"),
                    quantization=quant_name,
                    size_bytes=raw.get("size_bytes"),
                    params=raw.get("params_string"),
                    max_context=raw.get("max_context_length"),
                    fmt=raw.get("format"),
                    loaded=bool(raw.get("loaded_instances")),
                    source=source,
                    in_catalog=key in aliases,
                )
            )
    return found
```

Self-verify: `python -c "import ast; ast.parse(open('src/vortex/discovery.py').read())"`
parses, `DiscoveredModel` and `discover_models` are importable, and the
existing `discover_wrappers`/`Wrapper`/`WRAPPER_SPECS` are unchanged.

### T2 — src/vortex/app.py

This is an EDIT to an existing file. Make exactly four changes; change nothing
else.

**(a)** Change the discovery import line
`from .discovery import Wrapper, discover_wrappers`
to
`from .discovery import DiscoveredModel, Wrapper, discover_models, discover_wrappers`

**(b)** In the `build_app(...)` signature, add a new parameter
`model_discovery=discover_models` on its own line immediately after the
existing `wrapper_discovery=discover_wrappers,` line and before
`on_shutdown: Callable[[], None] | None = None,`.

**(c)** Immediately after the existing module-level line that declares
`wrapper_cache` (a dict initialized to an empty dict), add a new line
declaring `model_cache` with the SAME annotation shape as `wrapper_cache`
but substituting the element type Wrapper with DiscoveredModel — i.e. a dict
from str to a tuple of a float and a list of DiscoveredModel — initialized to
an empty dict. Indentation matches the `wrapper_cache` line.

**(d)** Immediately before the final `return app` line at the end of
`build_app`, insert these three definitions verbatim (keep the existing
`return app` after them). Annotate `_get_models`'s return as a list of
DiscoveredModel (shown as `-> list` below to keep this brief plain; use the
precise `list` of DiscoveredModel annotation in the code):

```python
    def _get_models() -> list:
        now = time.time()
        cached = model_cache.get("default")
        if cached is not None and now - cached[0] <= 60.0:
            return cached[1]
        findings = model_discovery(catalog_entries=catalog.entries)
        model_cache["default"] = (now, findings)
        return findings

    @app.get("/api/discovered-models")
    def discovered_models() -> dict:
        return {"models": [dict(m) for m in _get_models()]}

    @app.post("/api/discovered-models/discover")
    def discovered_models_discover() -> dict:
        model_cache.clear()
        findings = model_discovery(catalog_entries=catalog.entries)
        model_cache["default"] = (time.time(), findings)
        models = [dict(m) for m in findings]
        newly_found = [m.key for m in findings if not m.in_catalog]
        return {"models": models, "newly_found": newly_found}
```

Self-verify: the file parses; `build_app` has a `model_discovery` parameter
whose default is `discover_models`; the existing engine-wrappers routes are
unchanged.

### T3 — src/vortex/ui.py

This is an EDIT to the single `UI_PAGE` string constant. Make exactly four
insertions; change nothing else. `UI_PAGE` is a plain triple-quoted string —
insert literal HTML/JS text, no f-string interpolation.

**(a)** Find the end of the engine-wrappers section — the lines
`      <button data-act="discover">Discover</button>` / `    </div>` /
`  </section>` immediately followed by `</main>`. Between that `</section>` and
`</main>`, insert this markup block:

```html
  <section id="discoveredmodels">
    <h2>Discovered models</h2>
    <table>
      <thead>
        <tr>
          <th>Model</th>
          <th>Publisher</th>
          <th>Quant</th>
          <th>Size</th>
          <th>Params</th>
          <th>Context</th>
          <th>Loaded</th>
          <th>Catalog</th>
        </tr>
      </thead>
      <tbody id="modelrows">
        <tr class="empty"><td colspan="8">loading…</td></tr>
      </tbody>
    </table>
    <div style="margin-top: 10px; display: flex; align-items: center; gap: 10px;">
      <span id="modelstatus"></span>
      <button data-act="scan-models">Scan</button>
    </div>
  </section>
```

**(b)** Immediately after the existing `pollWrappers()` function (it ends with
its `.catch(...)` on "Could not refresh engine wrappers" and a closing `}`),
insert these functions:

```javascript
  function fmtSize(bytes) {
    if (!bytes) return "";
    return (bytes / 1e9).toFixed(1) + " GB";
  }

  function renderModels(models) {
    var rows = document.getElementById("modelrows");
    if (!models || !models.length) {
      rows.innerHTML = '<tr class="empty"><td colspan="8">no discovered models</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < models.length; i++) {
      var m = models[i];
      html += "<tr>";
      html += "<td>" + esc(m.key) + "</td>";
      html += "<td>" + esc(m.publisher) + "</td>";
      html += "<td>" + esc(m.quantization) + "</td>";
      html += "<td>" + esc(fmtSize(m.size_bytes)) + "</td>";
      html += "<td>" + esc(m.params) + "</td>";
      html += "<td>" + esc(m.max_context) + "</td>";
      html += "<td>" + (m.loaded ? "yes" : "no") + "</td>";
      html += "<td>" + (m.in_catalog ? "yes" : "no") + "</td>";
      html += "</tr>";
    }
    rows.innerHTML = html;
  }

  function pollModels() {
    fetch("/api/discovered-models")
      .then(function (r) {
        if (!r.ok) throw new Error("models " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderModels(data.models);
      })
      .catch(function (e) {
        setError("Could not refresh discovered models: " + e.message);
      });
  }
```

**(c)** Immediately after the existing engine-wrappers click handler (the
`document.getElementById("enginewrappers").addEventListener(...)` block that
ends with `.catch(...)` on "Engine-wrapper discovery failed" then `});`) and
before the `document.getElementById("stopvortex")` handler, insert:

```javascript
  document.getElementById("discoveredmodels").addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-act]");
    if (!btn) return;
    if (btn.getAttribute("data-act") !== "scan-models") return;
    fetch("/api/discovered-models/discover", { method: "POST" })
      .then(function (r) {
        if (!r.ok) throw new Error("scan " + r.status);
        return r.json();
      })
      .then(function (res) {
        setError(null);
        pollModels();
        var newly = res.newly_found || [];
        if (newly.length) {
          var rows = document.getElementById("modelrows").querySelectorAll("tr");
          for (var i = 0; i < rows.length; i++) {
            var keyCell = rows[i].cells[0];
            if (keyCell && newly.indexOf(keyCell.textContent) !== -1) {
              rows[i].classList.add("newly-found");
            }
          }
        }
      })
      .catch(function (e) {
        setError("Model discovery failed: " + e.message);
      });
  });
```

**(d)** In the bootstrap block at the very end (the run of `pollStatus();`
`pollCatalog();` `pollWrappers();` then three `setInterval(..., POLL_MS)`
calls), add `pollModels();` after `pollWrappers();` and
`setInterval(pollModels, POLL_MS);` after `setInterval(pollWrappers, POLL_MS);`.

Self-verify: the file parses; `UI_PAGE` contains `Discovered models`,
`id="modelrows"`, `data-act="scan-models"`, `fetch("/api/discovered-models")`,
`discovered-models/discover`, `m.key`, `m.publisher`, `m.quantization`,
`m.in_catalog`, and `setInterval(pollModels, POLL_MS)`.
