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

## v36 scope (fail-safe admission under uncertain occupancy — T1)

Scope brief: the outcome is that Vortex never admits a load it cannot cover
because a catalog port is held by a process it cannot identify, or because a
port scan was incomplete. Such an entry's catalog RAM estimate is counted —
once — in admission, it is never offered for eviction, and a load that cannot
fit is refused even when nothing is evictable. Policy chosen: option 2 of the
T1 decision note (count the catalog estimate); host-available memory as an
extra bound (option 3) is deferred. One file changes: `src/vortex/manager.py`.
Expected time band: 10–25 minutes of pipeline time.

## Explicitly out of scope for v36

Using host-available memory (`psutil.virtual_memory().available`) as an
additional bound, evicting or killing unidentified processes, and any change
to how ports are scanned or processes identified.

## v36 acceptance criteria

- **AC-12:** WHEN another catalog entry's port scan is incomplete or its port
  holds a process Vortex cannot identify, THE SYSTEM SHALL count that entry's
  catalog RAM estimate in load admission, such that a load that only fits by
  ignoring it is refused with MemoryConflict and no load operation starts.
- **AC-13:** THE SYSTEM SHALL never offer such an uncertain entry as an
  eviction candidate, such that `eviction_required` lists only identified
  loaded entries.
- **AC-14:** WHEN another entry's runtime is identified (verified this session
  or not), THE SYSTEM SHALL keep counting its estimate and offering it for
  eviction as before, such that an over-subscribing load is still refused
  with that entry among the eviction candidates.
- **AC-15:** WHEN other catalog entries are simply unloaded (no process on
  their port), THE SYSTEM SHALL not count them, such that a load that fits the
  budget is admitted.
- **AC-16:** THE SYSTEM SHALL count an uncertain entry already held as ready
  only once, and SHALL never count the load target against itself, such that
  a load that fits under single counting is admitted.
- **AC-17:** WHEN a load is refused and nothing loaded can be evicted, THE
  SYSTEM SHALL say in the MemoryConflict message that the memory is held by a
  process Vortex cannot identify and name the uncertain entries, such that
  the refusal explains itself.

## v38 scope (operator restart control)

Scope brief: the outcome is a Restart Vortex control in the dashboard that
returns Vortex to a clean, live state in one click — every loaded model is
unloaded (RAM freed, ports closed), the daemon exits, and a fresh daemon is
started from the same command line, re-reading `config/catalog.json`. Today
picking up a catalog edit means Stop Vortex, then relaunching Vortex.app by
hand. This deliberately reverses v27's out-of-scope note ("a restart/relaunch
control (the launcher owns start)"): the CEO asked for it on 2026-09-29, with
models unloaded rather than carried across the restart.

Essential scope, three files:
- `src/vortex/restart.py` (NEW) owns the relaunch mechanism only: a detached
  helper that waits for a given process to exit, then runs a given command in a
  given directory. It knows nothing about FastAPI, models, or the catalog.
- `src/vortex/app.py` adds `POST /api/restart`: refuse while a load/unload is in
  flight; otherwise unload every loaded model, then invoke an injectable
  restart hook after the response is sent. The default hook starts the
  relauncher with this process's own interpreter + argv and cwd, then stops
  this process exactly as shutdown does.
- `src/vortex/ui.py` adds the header button, confirm gate, in-flight
  disabling, the wait-for-new-daemon poll, reload, and visible failure.

Deferred: carrying loaded models across a restart (sidecar re-adoption), a
restart from the CLI, restarting the model runtimes themselves, and any
server-side boot identifier for the poll. Expected time band: 20–45 minutes
of pipeline time.

## Explicitly out of scope for v38

Keeping models loaded across the restart, killing or restarting processes
Vortex cannot identify, relaunching through Vortex.app, a restart schedule or
watchdog, and any confirmation UI beyond the browser's native `confirm()`.

## v38 acceptance criteria

- **AC-18:** WHEN `POST /api/restart` is called and no load or unload
  operation is in flight, THE SYSTEM SHALL terminate every loaded model's
  process, return `{"restarting": true, "unloaded": [<public ids>]}` with
  status 200, and invoke the injectable restart hook exactly once after the
  response is sent, such that the model is no longer advertised on
  `/v1/models` and its port is closed.
- **AC-19:** THE SYSTEM SHALL keep restart and shutdown distinct, such that
  `POST /api/restart` never invokes the shutdown hook and
  `POST /api/shutdown` never invokes the restart hook.
- **AC-20:** IF a load or unload operation is in flight when
  `POST /api/restart` is called, THEN THE SYSTEM SHALL respond 409 with a
  `detail` carrying `"busy": true` and the in-flight operation id, and SHALL
  neither unload any model nor invoke the restart hook, such that the
  in-flight operation is still reported as in progress and the restart hook
  has not been called.
- **AC-21:** THE relauncher SHALL wait until the given process id has exited
  before running the given command, SHALL run it in the given working
  directory, and SHALL run detached in its own session, such that the new
  daemon survives the old daemon's exit.
- **AC-22:** the dashboard header SHALL provide a Restart Vortex control
  beside Stop Vortex such that clicking it first requires the operator to
  confirm a warning that every loaded model will be unloaded, and a cancelled
  confirmation sends no request and leaves Vortex running.
- **AC-23:** WHILE a restart is in flight, THE dashboard SHALL keep the
  Restart control disabled, SHALL poll `/api/status` until the new daemon
  answers, and SHALL then reload the page.
- **AC-24:** WHEN the restart request fails (including the 409 busy refusal)
  or the new daemon does not answer within the poll budget, THE dashboard
  SHALL show an error beginning "Restart failed" and SHALL re-enable the
  Restart control.

## v39 scope (add discovered models to Vortex)

Scope brief: the outcome is that a model the operator downloads in LM Studio
becomes loadable in Vortex with one click — no hand-written catalog entry.
Today discovery (v32) only lists library models; making one loadable means
editing `config/catalog.json` by hand. v39 adds an "Add to Vortex" control per
discovered model, an "Add all new" control, and a Remove control for entries
added this way. Config-first is preserved and restated: scanning still never
makes a model loadable — only the operator's click does, and every added entry
is an ordinary catalog entry with the same validation and safety invariants
(single-owner ports, identified-process termination).

The CEO fixed four policies on 2026-09-30:
1. Runtime rule: an MLX model is served by `mlx-serve --model <path>`; a GGUF
   model by `llama-server -m <path>`; anything else (embeddings, unknown
   formats) is refused with a stated reason.
2. Added entries persist in a separate, gitignored `config/catalog.local.json`
   merged at startup, so clicks never dirty the committed catalog.
3. Controls: one Add per discovered model plus "Add all new" (confirmed).
4. A Remove control for added entries.

Essential scope, five files: `src/vortex/discovery.py` (each discovered model
carries its on-disk path, read from LM Studio's `lms ls --json`; "in catalog"
also matches by path), `src/vortex/catalog_synth.py` (NEW — the pure
discovered-model → catalog-entry rule), `src/vortex/catalog.py` (entry origin
and source path, local-catalog merge, add, remove, save), `src/vortex/app.py`
(three routes and local-catalog persistence), `src/vortex/ui.py` (the
controls). Deferred: auto-add on download, per-model runtime override, tuning
flags (MTP, context size) on added entries, non-LM-Studio libraries, and
verifying an added model can actually load (the first load's readiness probe
is that check). Expected time band: 45–90 minutes of pipeline time.

## Explicitly out of scope for v39

Loading a model as part of adding it, editing an added entry, removing
entries that came from `config/catalog.json`, choosing among several runtimes
per format, downloading models, and any limit on how many models are loaded.

## v39 acceptance criteria

- **AC-25:** THE discovery layer SHALL report, for each discovered model, the
  absolute on-disk path LM Studio's `lms ls --json` gives for that model key
  (joined onto the LM Studio models root), or no path when the listing omits
  the key or cannot be read, such that a model whose files are known carries a
  path and an unreadable listing never raises.
- **AC-26:** THE discovery layer SHALL mark a discovered model as in the
  catalog WHEN its key equals an entry's upstream alias OR its path equals an
  entry's source path or appears in an entry's launch command, such that a
  model already served by a hand-written entry is not reported as newly found.
- **AC-27:** WHEN a discovered MLX model with a known path is synthesized, THE
  SYSTEM SHALL produce an entry whose launch command runs mlx-serve on that
  path on the lowest free port in 8200–8299, such that the entry passes catalog
  validation, records the path as its source path, and has origin "local".
- **AC-28:** WHEN a discovered GGUF model with a known path is synthesized, THE
  SYSTEM SHALL produce an entry whose launch command runs llama-server with
  `-m <path>` on the lowest free port in 8200–8299, such that it passes catalog
  validation with origin "local".
- **AC-29:** IF a discovered model has no known path, an unsupported format, no
  architecture, an id or path already in the catalog, or no free port remains,
  THEN synthesis SHALL raise SynthesisError naming the reason, such that no
  entry is produced.
- **AC-30:** THE synthesized entry SHALL estimate RAM as the model size plus
  10% (rounded to 0.1 GB) and SHALL be exclusive exactly when that estimate
  exceeds 40 GB, such that large models evict others on load as hand entries do.
- **AC-31:** WHEN `POST /api/discovered-models/{key}/add` names a discovered
  model that synthesizes, THE SYSTEM SHALL add the entry to the live catalog
  and persist it to the local catalog file, such that the response is 201 with
  the added entry, `/api/catalog` lists it with origin "local", and the model
  can be loaded without a restart.
- **AC-32:** IF the key is not a discovered model, THEN the add route SHALL
  respond 404; IF synthesis raises SynthesisError, THEN it SHALL respond 422
  with the reason, such that nothing is added and the local file is unchanged.
- **AC-33:** WHEN `POST /api/discovered-models/add-new` is called, THE SYSTEM
  SHALL rescan and add every discovered model not in the catalog that
  synthesizes, such that the response lists added ids and skipped keys with
  their reasons, and ports never collide between models added in one call.
- **AC-34:** WHEN `DELETE /api/catalog/{public_id}` names an entry with origin
  "local" that is not loaded and has no operation in flight, THE SYSTEM SHALL
  remove it from the live catalog and the local file, such that it is no
  longer listed or loadable; IF the entry is unknown THEN 404; IF it came from
  `config/catalog.json`, is loaded, or has an operation in flight THEN 409
  with the reason, such that nothing is removed.
- **AC-35:** WHEN the daemon starts, THE SYSTEM SHALL merge the entries of
  `config/catalog.local.json` (if present) into the catalog with origin
  "local", rejecting duplicate ids or ports exactly as config entries are,
  such that added models survive a restart.
- **AC-36:** THE dashboard SHALL offer an Add control on each discovered model
  not in the catalog and an "Add all new" control that first confirms, SHALL
  offer a Remove control that first confirms on each catalog entry whose
  origin is "local", and SHALL refresh the catalog and discovered lists after
  each succeeds, such that a cancelled confirm sends no request.
- **AC-37:** WHEN an add, add-all, or remove request fails, THE dashboard
  SHALL show an error beginning "Add failed" or "Remove failed" with the
  server's reason, and WHEN add-all skips models THE dashboard SHALL list the
  skipped keys and reasons, such that no failure or skip is silent.
