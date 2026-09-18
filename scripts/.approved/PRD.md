# PRD — vortex router phase 2 UI (M1: operator dashboard)

## Problem

Vortex's management surface is headless: knowing *what is loaded, how much
RAM is left, and why a load was refused* requires CLI calls. The owner-
operator's recurring question is visual, and the answer should be one
browser tab away.

## Product

A server-rendered dashboard served by the vortex daemon itself at
`http://127.0.0.1:9000/`. One page, no framework, no new dependencies,
no external assets. The page is a thin client over the EXISTING management
API (`/api/status`, `/api/catalog`, `/api/models/{id}/load|unload`,
`/api/operations/{id}`) — it introduces no new endpoints and never invents
states beyond what those return.

## M1 scope (this milestone)

- **Model menu**: every catalog entry with live state (idle/loading/ready/
  unloading), runtime, port, RAM estimate, and one-click load/unload.
- **RAM meter**: used/total from `/api/status`, animated bar with warn
  (>70%) and danger (>85%) zones.
- **Action feedback**: load/unload buttons poll `/api/operations/{id}` and
  render real transition states; buttons disable while busy.
- **Conflict explanation**: when a load returns 409, show the refusal
  message, `required_gb`, and eviction candidates. Eviction is NEVER
  automatic — the card informs, the operator acts.
- **Daemon-down state**: if the API is unreachable, a friendly message
  with the start command — never a blank page or traceback.

## Explicitly out of scope for M1

Chat/inference surface (clients already have that), auth (daemon is
local-only), provisioning/tuning UI, multi-host fleet view, HTMX or any JS
framework, external CSS/JS/font assets.

## Success criteria

The frozen test suite is the binding definition (D-54). Informally: the
CEO opens `http://127.0.0.1:9000/` in a browser and can see machine state
at a glance and load/unload models with one click; conflicts explain
themselves; a stopped daemon explains itself too.

## v14 scope (engine wrappers inventory)

The operator's machine holds inference engine wrappers beyond what
`config/catalog.json` happens to reference — oMLX, mtplx, ollama, LM
Studio, llama-server/llama-cli, vLLM, mlx-lm. The daemon should report,
read-only, which of those wrappers are installed on the host, and surface
any that are installed but not yet referenced by any catalog entry, so the
owner can tell at a glance what Vortex could be pointed at.

- **Discovery module**: a vetted registry of wrappers is probed
  read-only. A wrapper counts as installed when its binary/app resolves on
  PATH or at a known install path. Detection never launches, loads, or
  alters any wrapper; the only subprocess ever spawned is a bounded
  version probe.
- **Inventory route**: `GET /api/engine-wrappers` returns the installed
  wrappers with name, kind, binary path, version string, default service
  port, live-port flag, and whether a catalog entry already references it.
- **Rescan route**: `POST /api/engine-wrappers/discover` forces a fresh
  scan and reports which installed wrappers are NOT referenced by any
  catalog entry (`newly_found`).
- **Dashboard section**: a second table on the same dashboard page lists
  installed wrappers; a Discover control triggers a rescan and flags
  newly-found wrappers.

## v14 acceptance criteria

- **AC-1:** the daemon exposes an engine-wrapper inventory at
  `GET /api/engine-wrappers` such that the response lists every installed
  wrapper defined by the vetted registry, each carrying name, kind,
  installed (always true for listed wrappers), binary_path, version, port,
  port_open, and in_catalog.
- **AC-2:** wrapper detection consults only the vetted registry (omlx,
  mtplx, ollama, lmstudio, llama-server, llama-cli, vllm, mlx-lm) such
  that no process or binary outside the registry is ever reported and the
  new module has no third-party dependencies.
- **AC-3:** `POST /api/engine-wrappers/discover` forces a fresh scan such
  that the response includes newly_found, the names of installed wrappers
  referenced by no catalog entry.
- **AC-4:** discovery never launches, loads, or alters any wrapper such
  that the only subprocess ever spawned is a bounded version probe (≤3s
  timeout) and repeated inventory reads are served from a short-lived
  cache.
- **AC-5:** the dashboard renders an "Engine wrappers" section such that
  each installed wrapper shows kind, binary path, version, port (with a
  live/open indication), and catalog status, refreshed on the existing
  poll cadence.
- **AC-6:** the dashboard provides a Discover control such that clicking
  it calls `POST /api/engine-wrappers/discover` and marks installed
  wrappers that are absent from the vortex catalog.

## v27 scope (operator shutdown control)

Vortex is launched from an app, but the dashboard offers no way to power it
back down. The owner-operator's ask is a single control that stops Vortex
cleanly from the page itself: unload every loaded model — freeing its RAM and
closing its port — and then stop the daemon, returning the machine to a clean
state. Stopping is deliberate and destructive, so the control is gated behind
an explicit confirmation.

- **Shutdown route**: a new `POST /api/shutdown` endpoint that unloads every
  loaded model, then signals the daemon to stop. The unload runs first, so
  the RAM is actually reclaimed — the model processes are session-leaders
  that would otherwise outlive the daemon. The daemon-stop signal is an
  injectable hook, so the behaviour is testable without killing the caller.
- **Stop control**: a Stop Vortex button in the dashboard header. Clicking it
  first requires the operator to confirm a warning; only on confirmation does
  the page call the shutdown route and fall back to the existing
  daemon-unreachable state. A cancelled confirmation leaves Vortex running.

## Explicitly out of scope for v27

A restart/relaunch control (the launcher owns start), a graceful per-client
drain, scheduling or auto-shutdown, and any confirmation UI beyond the
browser's native `confirm()`.

## v27 acceptance criteria

- **AC-7:** the daemon exposes `POST /api/shutdown` such that the call
  unloads every currently-loaded model — each loaded entry's process is
  terminated and its public id returned in the response `unloaded` list — and
  then invokes an injectable daemon-stop hook after the response body is
  sent, such that the response is `{"stopping": true, "unloaded": [<ids>]}`
  and the hook is called exactly once.
- **AC-8:** the dashboard header provides a Stop Vortex control such that
  clicking it first requires the operator to confirm a warning that every
  loaded model will be unloaded, and only on confirmation issues
  `POST /api/shutdown` and falls back to the daemon-unreachable state, such
  that a cancelled confirmation leaves Vortex running and sends no request.

## v32 scope (LM Studio library discovery)

Every loadable model must be hand-added to `config/catalog.json` today. The
owner-operator wants to *browse the models a library wrapper has already
downloaded* — LM Studio first — directly on the dashboard, so the catalog can
be grown from what the machine already holds instead of from memory. This
milestone delivers the read-only browse surface only; it never mutates the
catalog and never loads a model. It preserves config-first: a discovered model
is reported as DISCOVERED, never made loadable, exactly as the discovery layer
already reserves ("discovered, not configured").

- **Model discovery**: a library wrapper that exposes an OpenAI-style library
  listing (LM Studio on :1234, via `GET /api/v1/models`) is probed read-only.
  Each downloaded model is reported with its key, display name, publisher,
  architecture, quantization, size, parameter string, max context, format,
  whether the wrapper currently has it loaded, its source wrapper, and whether
  a catalog entry already references it. An unreachable library yields no
  models, never an error.
- **Inventory route**: `GET /api/discovered-models` returns the discovered
  models. **Rescan route**: `POST /api/discovered-models/discover` forces a
  fresh probe and reports which discovered models are NOT referenced by any
  catalog entry (`newly_found`).
- **Dashboard section**: a "Discovered models" table on the same dashboard
  page lists the library's models; a Scan control triggers a rescan and flags
  models absent from the catalog.

## Explicitly out of scope for v32

Promotion of a discovered model into the catalog (a later milestone: entry
synthesis, port allocation, launch-command derivation), loading a discovered
model, LM Studio as the runtime loader (presets/chat templates/JIT), auto
download of models not yet downloaded, and non-LM-Studio libraries (a later
add on the same route shape).

## v32 acceptance criteria

- **AC-9:** the discovery layer exposes `discover_models` such that probing a
  library wrapper's `/api/v1/models` listing yields one DiscoveredModel per
  downloaded entry carrying key, display_name, publisher, architecture,
  quantization, size_bytes, params, max_context, fmt, loaded, source, and
  in_catalog, where in_catalog is true exactly when the model's key matches a
  catalog entry's upstream alias, an entry without a key is skipped, and an
  unreachable library yields an empty list rather than raising.
- **AC-10:** the daemon exposes `GET /api/discovered-models` returning the
  discovered models with all of the above fields, and
  `POST /api/discovered-models/discover` forcing a fresh probe such that the
  response includes newly_found, the keys of discovered models referenced by
  no catalog entry; discovery is injected into the app exactly as wrapper
  discovery is, so the routes are exercisable without a running library.
- **AC-11:** the dashboard renders a "Discovered models" section such that each
  discovered model shows its key, publisher, quantization, and catalog status
  on the existing poll cadence, and provides a Scan control such that clicking
  it calls `POST /api/discovered-models/discover` and marks discovered models
  absent from the catalog.