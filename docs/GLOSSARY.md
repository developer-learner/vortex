# Vortex Glossary

Settled terminology for this codebase and the surrounding project. The stack,
from the bottom up:

**weights** → **inference engine** → **inference runtime** → **router** → **clients**

## The stack

- **Weights** — the trained artifact (e.g. a GGUF quant like
  `DeepSeek-v4-flash-0731 Q2_K_XL`, ~97 GB).
- **Inference engine** — the compute core: llama.cpp, MLX, vLLM. What actually
  runs the weights on silicon.
- **Inference runtime** — the loader+server app built on an engine: mtplx,
  omlx, vmlx, llama-server, LM Studio, ds4. Market-confirmed term (LM Studio
  CLI itself says `lms runtime`). A runtime installs/configures/runs models
  on the machine and exposes an HTTP surface.
  - *Why not "loader"?* "Loader" already has an established meaning in the
    field: weight deserialization (the load-time step). Vortex neither wants
    nor redeems that word.
- **Router (Vortex)** — the layer that installs/owns runtimes, owns model
  lifecycles, and exposes loaded models as one universal surface. The process
  side of it is the daemon/CLI called **modelmux**; `vortex` is the app and
  repository name.
- **Clients** — everything else: testchat, OpenCode, the pi agent, scripts.

## Model identity

- **public model id** — what clients call a model; stable, hand-chosen
  (`deepseek-v4-flash-0731`, `Flash_Q2KXL`, `Flash_IQ3XXS`). Never equated
  with any upstream id.
- **upstream alias** — what the runtime itself calls the model
  (`deepseek-v4-flash-0731-ud`, …). Stored per catalog entry, used when the
  runtime needs a model name as it knows it.
- **runtime / engine (on a catalog entry)** — which runtime serves it and
  which engine that runtime uses. e.g. ds4/mtplx, llama-server/llama.cpp.

## The catalog

- **Catalog-first** — `config/catalog.json` is authoritative: only configured
  entries are loadable. Scanning never makes a model loadable; it can only
  report "discovered, not configured".
- **Catalog entry** — one loadable model: public id, runtime, engine, launch
  command, port, ready URL, chat endpoint, upstream alias, RAM estimate,
  context size, exclusivity, pinned flag.
- **Exclusive** — entry pins its port: Vortex owns it and single-owner applies.
  Nonexclusive entries make no port claims.
- **Pinned** — reserved for UI use later; no global pins in v1. The client
  menu shows *loaded ∪ the active thread's remembered model* (with a synthetic
  `○` row when that model is unloaded). Pinning, if it arrives, is opt-in.

## Lifecycle and ownership

- **Single-owner invariant** — every port a catalog entry declares is owned by
  exactly one process. Modelmux never spawns onto a port it doesn't own, and
  terminates nothing it can't identify.
- **Sidecar** — a per-entry record (PID + start time) written next to startup.
  It is the only proof of ownership. Survives modelmux restarts, so a
  surviving runtime can be *adopted* after a crash/restart instead of respawned
  over it.
- **Identification** — PID **and** start-time both must match the sidecar
  (1.0 s tolerance). Anything else on a configured port is
  **unidentified**: never claimed, never terminated, never evicted — the
  load/unload is refused with a clear error instead.
- **Continuous readiness probing** — loading is defined as "the ready URL
  answers 200"; there is no byte-progress reporting in v1. Poll phases, not
  bytes.

## Operations contract

- **202 + operation id** — loads/unloads return `202` immediately with an
  operation id; state is read by polling `GET /api/operations/{id}`.
- **Single mutation slot** — at most one load or unload is in flight. An exact
  duplicate returns the existing operation; a different concurrent mutation
  gets `409 busy` immediately and is never silently queued.
- **Model states** — `unloaded | loading | ready | unloading | error`.
- An operation carries `phase`, `state`, `message`, `created_at`,
  `updated_at`. v1 is poll-only (no webhook/push).

## Memory and eviction

- **RAM estimate** — declared per entry (`ram_estimate_gb`); used to decide
  whether loading is even plausible.
- **Eviction** — never automatic in v1. When loading would exceed budget,
  Vortex answers with a structured conflict: required size + the loaded
  candidates that would need eviction. The caller decides. (LRU eviction is a
  later, explicit, opt-in feature.)
- Loading uses `0.8 × physical RAM − (sum of loaded estimates)` as the working
  budget.

## The universal surface

- **Universal surface** — `GET /v1/models` and `POST /v1/chat/completions`
  (OpenAI Chat Completions surface only; near-verbatim pass-through). The
  whole point: every client points at one OpenAI endpoint and Vortex decides
  which runtime answers.
- **Near-verbatim pass-through** — tools, structured output, usage, finish
  reasons, vendor reasoning fields and streaming all survive the proxy. No
  opinionated rewriting in v1.

## The process

- **modelmux** — the daemon/CLI. `vortex` is the app. One `pyproject` script
  entry: `vortex = "modelmux.cli:main"`.
- **Process group termination** — namespaces/wrappers (e.g. `mtplx` scripts)
  may exec-and-orphan; termination SIGINTs the tracked process **and** its
  descendants, then SIGKILLs stragglers, so the port actually frees.
- **Duplicate detection at startup** — the catalog rejects duplicate public
  ids and duplicate ports.

## Machine learning terms kept despite the vocabulary ban

- **MTP / speculative decoding** — kept as-is; the ban was only on
  loader-as-product-word.

## Adjacent tooling (why Vortex exists)

- **llama-swap** — the closest neighbor: multi-backend, hot-swappable OpenAI
  surface. What it does *not* do: provision, tune, loader-family management,
  RAM-aware eviction, process ownership. That missing combination is Vortex.
- **`mtplx tune` / `vmlx bench`** — the planned v2 provisioning path: tune
  then benchmark, promote winning flags into the catalog.

## Blueprint vocabulary (D-165 onward)

- **Greenfield** — a repo born under the control plane.
- **Brownfield adoption (D-165)** — snapshot-plus-go-forward onto a repo built
  without the control plane. Theory, unvalidated until vortex is the first
  real subject.
- **Refreeze** — the open question of when (or whether) a brownfield snapshot
  is declared final relative to the control plane.
- **Control plane** — tasks/, project-trail/, conventions, review gates. Vortex
  explicitly does not ship one in v1; the quality bar is convention-enforced
  (in-repo tests + live walkthrough) until the adoption.
