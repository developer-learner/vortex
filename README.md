# Vortex

One place that owns every local LLM on this machine.

Vortex installs, configures, and runs inference runtimes (mtplx, omlx, vmlx,
llama-server, LM Studio, ds4), owns the lifecycles of the models they serve,
and exposes loaded models as a single OpenAI-compatible surface.

The command-line process is called **modelmux**: `vortex` is the app and
repository name; `modelmux` is the daemon + CLI underneath.

## Why

Local LLM tooling fragments per-runtime. Each manager knows only its own
model store, launching, and serving. Vortex is the layer above: one catalog,
one API, one eviction story, one place to point every client
(testchat, OpenCode, pi…).

Nobody owns the combination Vortex does. The closest neighbor, llama-swap,
hot-swaps between backends but does not provision, tune, manage loader
families, estimate RAM, evict, or own processes.

## Surfaces

- **Universal (OpenAI Chat Completions)**: `GET /v1/models`,
  `POST /v1/chat/completions` — near-verbatim pass-through to the loaded
  model's runtime (streaming included). Coming up on `:9000`.
- **Management (Vortex UI + API)**: `/api/catalog`, `/api/status`,
  `POST /api/models/{id}/load` (202 + operation), `POST /api/models/{id}/unload`,
  `GET /api/operations/{id}` (poll contract — see `docs/GLOSSARY.md`).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn vortex.app:build_app --factory --port 9000
vortex models          # or: vortex status, vortex load <id>, vortex unload <id>
```

## Config

`config/catalog.json` — config-first: only configured entries are loadable.
Scanning never makes a model loadable; it can only report "discovered, not
configured".

## Safety invariants

- Every configured port is owned by exactly one process (single-owner).
- modelmux terminates only processes its sidecars identify (PID + start-time).
  An unidentified occupant is never claimed or killed — the load is refused.
- Loads surface structured conflicts (eviction candidates) — never silent kills.

## Layout

```
config/catalog.json     the loadable models (config-first)
src/vortex/catalog.py   catalog model + validation
src/vortex/lifecycle.py spawn / ready-probe / sidecar identity / termination
src/vortex/operations.py202+poll contract for load and unload
src/vortex/manager.py   load/unload orchestration, eviction, state
src/vortex/app.py       universal + management FastAPI surface
src/modelmux/cli.py     the `modelmux` process CLI (`vortex` console script)
tests/                  catalog, lifecycle, proxy, eviction (real child processes)
```

## Vocabulary

Weights → **inference engine** (llama.cpp, MLX, vLLM) → **inference runtime**
(mtplx, omlx, vmlx, llama-server, LM Studio, ds4) → **router (Vortex)** →
**clients**. Full terms: `docs/GLOSSARY.md`.

## Roadmap

1. Orchestrate — this repo, v1 (in progress)
2. UI
3. testchat recut (swap its model handling for the universal surface)
4. Cutover (stop spawning from testchat, move to `LLM_ENDPOINT`)
5. Provisioning + tuning v2 (mtplx tune / vmlx bench → winning flags in catalog)

Blueprint control-plane adoption (D-165) is planned post-v1: the repo stays
app-only until then (quality bar: in-repo tests + live walkthrough, enforced
by convention).