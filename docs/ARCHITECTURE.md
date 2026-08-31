# ARCHITECTURE.md — System Design

> Living document. Update when structure changes.
> LLMs read this to understand how the system fits together.

---

## System Overview

Vortex is a local-only control plane for local LLMs. It owns every inference
runtime process on the machine: a catalog (`config/catalog.json`) declares the
known models — runtime, launch script, port, health URL, chat endpoint, RAM
estimate, exclusivity — and a FastAPI daemon (`src/vortex/app.py`) loads them
(sidecar-process lifecycle in `src/vortex/lifecycle.py`), manages and evicts
them under a RAM budget (`src/vortex/manager.py`), and exposes the loaded set
to every client through two surfaces: a universal OpenAI-shaped
`/v1/...` proxy (Chat Completions, streamable) plus a management
`/api/...` surface and the `vortex` CLI (`src/modelmux/cli.py`). There is no
database — configuration is the catalog, and runtime truth is the sidecar
process table. The daemon binds `127.0.0.1:9000` only.

---

## Data Models

> Define every entity, its fields, and relationships.
> Keep this updated — the LLM uses this to avoid inventing schema.

### CatalogEntry (config/catalog.json — the only persistent model)

| Field | Type | Notes |
|-------|------|-------|
| public_id | str | user-facing model id (`vortex load <public_id>`); pattern-validated |
| runtime | str | engine family: `ds4`/`llama-server` |
| engine | str | e.g. `mtplx`, `llama.cpp` |
| launch_command | list[str] | argv that starts the runtime server (non-empty, validated) |
| port | int | runtime's own listen port (1-65535; unique across the catalog) |
| ready_url | str | http(s) health probe the daemon polls after launch (validated) |
| chat_endpoint | str | http(s) runtime chat/completions URL that /v1 proxies to (validated) |
| upstream_alias | str \| None | model id sent upstream for this entry; `None` → public_id forwarded |
| ram_estimate_gb | float \| None | budget line for admission/eviction decisions (> 0 when set) |
| ctx_size | int \| None | context window (> 0 when set) |
| exclusive | bool | true = only one loaded at a time |
| pinned | bool | true = never an eviction candidate |

**Relationships:**
- has one sidecar owner while loaded (in-memory `Lifecycle.processes` + on-disk sidecar file, not persisted as state)

### In-memory runtime state (dies with the daemon)

| Field | Type | Notes |
|-------|------|-------|
| `Lifecycle.processes` | dict[str, Popen \| None] | public_id → sidecar owner of the runtime process (vortex-spawned only; adopted runtimes have no Popen) |
| `Lifecycle._last_status` | dict[str, str] | per-entry owner status; holds the last value on `SCAN_UNKNOWN` (fail-closed) |
| `Lifecycle._verified` | set[str] | public_ids verified harmonic **this session** (survives restart only by re-verification on adopt) |
| `OperationStore._ops` | dict[str, Operation] | 202+poll operations; atomic snapshots; retention `MAX_OPS 100` / `RETENTION 1h` |

Two derived sets (Manager):
- **consuming set** `all_ready()` — entries whose port is held by an identified
  process and `ready_url` answers 200. This is the admission/eviction
  accounting set: it must include a restart-surviving runtime that is running
  but not yet verified this session, or memory would be undercounted.
- **advertised set** `client_ready()` — consuming ∩ verified (harmonic this
  session). This is what `/v1/models` lists and what the chat proxy serves.

---

## API Structure

```
# Universal surface (OpenAI Chat Completions — what clients use)
POST   /v1/chat/completions         proxy to loaded model (model remapped to upstream_alias, streaming preserves upstream status, 502 on connection failure)
GET    /v1/models                   list advertised models (only harmonic-ready — verified this session)

# Management surface (the daemon's own controls)
GET    /api/status                  daemon + RAM (vm_stat/psutil labeled) + loaded-set = consuming set (identified + ready, incl. unverified adopted runtimes)
GET    /api/catalog                 catalog entries + per-entry state (ready|unloaded|loading|unloading|error) + port_pid (SCAN_UNKNOWN→null)
POST   /api/models/{id}/load        202 + {operation,model}; async via OperationStore (spawning→ready, 409 on memory/port conflict, spawn failure → operation error:failed)
POST   /api/models/{id}/unload      202 + {operation,model}; async (terminating→unloaded, 404 on unknown)
GET    /api/operations/{op}         poll operation snapshot (atomic copy, retention 100/1h)
GET    /api/engine-wrappers         installed wrappers (discover cache 60s)
POST   /api/engine-wrappers/discover  rescan, returns {wrappers,newly_found}

# CLI (src/modelmux/cli.py) — same verbs: vortex models|load|unload|status (load/unload --wait/--no-wait, poll deadline 310s, controlled exit codes 0/1/2/3)
```

---

## Key Flows

> Describe the important user journeys as numbered steps.
> These prevent the LLM from misunderstanding how pieces connect.

### Load

1. `POST /api/models/{id}/load` → `202 {operation}` promptly (or CLI `vortex load --wait/--no-wait`); the POST never blocks on the spawn
2. Manager checks admission synchronously: eviction set computed off `ram_estimate_gb` under `0.8*total` budget, never auto-evicts (409 with `required_gb`/`eviction_candidates`); port-conflict checks `SCAN_UNKNOWN` fail-closed, unidentified port never claimed
3. Operation moves `loading:spawning`; a background worker runs Lifecycle.spawn as ONLY owner (sidecar `pid+start_time`), polls `occupying_pid`==`ready` + `ready_url 200` + `anneal` (real 1-token completion, bounded retry) until deadline (`READY_TIMEOUT 300s`, `POLL_INTERVAL 0.25s`); adoption fast-path requires harmonic before `ready`
4. On success `ready:done`; on timeout/early exit the just-spawned process is terminated and sidecar dropped so retry cannot adopt a failed runtime; failures go `error:failed/refused`
5. The runtime enters the consuming set (`/api/status`, admission) when identified + ready; it is advertised at `/v1/models` and served by the chat proxy only when harmonic (verified); `GET /api/catalog` reflects `op.state` while `loading`/`unloading`

### Chat proxy

1. Client calls `POST /v1/chat/completions` with a loaded `public_id` (must be `harmonic-ready` — verified this session — else 404)
2. App remaps `body.model` to `upstream_alias or public_id` and forwards to `chat_endpoint` via httpx (300s timeout, `Content-Type: application/json`)
3. Non-stream: upstream `status_code`/`content`/`content-type` preserved, `502` on `RequestError`
4. Stream: single `client.stream` connection, status preserved (non-200 returns that status immediately, not 200 SSE); on success `text/event-stream` with `Cache-Control: no-cache`, SSE chunks relayed verbatim; `502` on connection failure; `reasoning_content` preserved

### Unload

1. `POST /api/models/{id}/unload` → `202 {operation}` promptly (async `unloading:terminating`)
2. A background worker runs `Lifecycle.terminate`: verifies `SCAN_UNKNOWN` fail-closed, `unidentified` never killed, otherwise `SIGINT`→`SIGKILL` process group + sidecar drop
3. Operation moves `unloaded:done` or `error:refused` (`unidentified process`); polling via `GET /api/operations/{id}` (atomic snapshot, `MAX_OPS 100`/`RETENTION 1h`)
4. `GET /api/catalog` and `/api/status` reflect unloaded; RAM released for admission; CLI `vortex unload` polls to `unloaded` with 310s deadline, `--no-wait` returns immediately

---

## External Services

| Service | Purpose | Notes |
|---------|---------|-------|
| mtplx/ds4 runtime | ds4 model server | 127.0.0.1:8005, launched by catalog script |
| llama-server (llama.cpp) | Flash quant models | 127.0.0.1:8101/8102, launched by catalog scripts |
| LM Studio | possible external runtime | NOT currently cataloged — never assumed present; halt on unreachable |

---

## Infrastructure

```
[localhost — Apple Silicon Mac]
├── Vortex daemon:  uvicorn "vortex.app:build_app" --factory :9000 (127.0.0.1 only)
├── Catalog:        config/catalog.json (config-first, no DB)
├── Sidecar models: ds4 :8005, llama-server :8101/8102 (per catalog)
├── Clients:        testchat, OpenCode, pi → http://127.0.0.1:9000/v1/...
└── Process model:  daemon = single FastAPI process; each loaded runtime = its own sidecar
```

---

## Known Constraints

> Things the LLM should know to avoid bad suggestions.

- **Local-only, no auth** — daemon binds 127.0.0.1; addresses and payloads are localhost-shaped
- **Ready = harmonic (ownership + /v1/models 200 + 1-token anneal, D-174)** — the *advertised* set (`/v1/models`, chat proxy) is never served without all three; adoption requires harmonic before `ready`. The *consuming* set (admission accounting, `/api/status`) counts identified + ready runtimes even when not yet verified this session — a restart-surviving runtime must count toward the RAM budget before it is re-verified (undercounting it is the failure this split exists to prevent)
- **Process ownership is strict** — sidecar `pid+start_time` identifies exactly one process; `SCAN_UNKNOWN` (incomplete psutil scan) fail-closed (hold last status, never claim or terminate), unidentified occupant never killed or evicted, only `409` refused
- **No DB** — catalog is the only persistent truth (validated `public_id` pattern, `http(s)://` URLs, `ram>0`/`ctx>0`/`port 1-65535`, unique ids/ports via any construction path); `OperationStore` is in-memory with atomic snapshots and bounded retention; runtime state dies with daemon
- **RAM is a budget, not a lock** — admission uses `ram_estimate_gb` under `0.8*total`; eviction set is `409` with `required_gb`/`eviction_candidates`, never silent kills; UI `poll*` failures are operator-visible via `#conflict`/`#wrapperstatus`, CLI timeouts/HTTP/malformed produce controlled `1/2/3` exits with 310s poll deadline and `--wait`/`--no-wait`

---

## Pipeline Decisions Index (template)

> **Not for child projects to edit.** This section indexes the template's own
> pipeline decisions — see `docs/DECISIONS.md` for the full entries with
> reasons, alternatives, and "do not suggest." INV-3 used to require every
> non-documentation-only D-entry here and mechanically enforce it via the
> `architect`-phase gate in `scripts/phase-gate.sh`; that phase was retired
> 2026-07-22 (see D-25 amendment) because post-D-53 nothing invokes it.
> Keeping this index maintained is now a PM-review discipline, not a gate.
>
> If your child project has never touched the pipeline, you can leave this
> section alone. The sections *above* this line are the template skeleton
> for describing YOUR project's architecture.

### Capability ladder & tiering

- **D-05**: Code-driven orchestration loop (the shell owns procedure)
- **D-07**: Four-role PRD→Plan→Build→Test pipeline
- **D-11**: Agent permission model, no catch-all deny
- **D-12**: Local model tier chosen for coder/test at that time
- **D-14**: Context-window ceiling measurement and fix
- **D-16**: Local coder model pinned as the default
- **D-18**: 32K context as pinned default for the local model
- **D-27**: Capability ladder — TPM (frontier chat) / EM (mid-tier) / coder (local); test-runner agent deleted
- **D-40**: OpenCode Build agent as conductor; em/coder become subagents
- **D-41**: Model identity leaves the repo — the blueprint is model-agnostic
- **D-43**: Flat hierarchy under the shell; `em`/`coder` denied the task tool
- **D-46**: Milestone sizing is TPM judgment against a fixed balance; no formula
- **D-48**: Conductor denied the task tool — no agent in this repo can spawn another
- **D-52**: em/coder back to primary mode; no silent agent/model substitution
- **D-53**: Retire the agent harness — EM/coder called over bare HTTP, shell writes every artifact
- **D-55**: Linux dev VM boundary; D-53 partial reversal for cross-boundary model access
- **D-60**: Task sizing governed by the coder's measured bare-completion capability
- **D-66**: The EM seat is precision-transcription work; dense models preferred
- **D-105**: Onboarding uses the exact `SWBP_<ROLE>_MODEL` runtime contract

### Sandbox & untrusted-code execution

- **D-08**: AC9 compliance — mandatory sandbox + freeze-trap closure
- **D-09**: Sandbox wiring in the orchestrator
- **D-10**: macOS compatibility fixes for sandbox scripts
- **D-13**: Pipeline robustness — container deps, PYTHONPATH, gate recovery
- **D-17**: Template deps baked into `Containerfile`
- **D-30**: Sandbox flip — read-only repo + per-lane rw mounts; pre-commit hook for the human path
- **D-50**: Stack drift killed mechanically — content-hashed sandbox image, podman preflight
- **D-62**: LM Studio drift probe in orchestrate.sh pre-flight
- **D-102**: Sandbox image copies only dependency manifests; project state and secrets never enter image layers
- **D-123**: Clean image builds run on packaging changes and weekly, then verify no project tree is present

### Frozen spec & TPM shuttle

- **D-06**: EARS format for acceptance criteria
- **D-26**: Schema-validated artifact handoffs; plan.json validation gate
- **D-31**: Versioned re-freeze — frozen spec changes only via delta (human approval removed by D-121)
- **D-32**: INV-4 — test-visible surface ⊆ ERD-locked surface
- **D-38**: TPM shuttle scripts (`tpm-pack.sh`/`tpm-unpack.sh`)
- **D-39**: Agent-mode TPM — scoped repo access via `tpm-agent.sh`
- **D-42**: Refreeze approval without a terminal — `--diff`/`--approve <hash>` (both superseded by D-121: no approval flag exists, `--diff` remains)
- **D-49**: `tpm-pack.sh` defaults to stdout; conductor relays the bundle verbatim
- **D-51**: Initial freeze collects node-ids statically
- **D-54**: Spec-drift policy — test surface is binding; ERD prose is advisory
- **D-56**: External interfaces enter the spec only as captured reality
- **D-58**: Browser oracle — locked surface extends to the DOM (`contracts.ui`)
- **D-61**: Template updates gain hash-bound approval
- **D-63**: Ratify milestones — catching up the spec after outside-band work
- **D-64**: Browser-test mapping enforced mechanically in `validate-plan.py`
- **D-67**: `refreeze` lints staged tests
- **D-75**: Red-before-green — a refreeze runs the delta's tests pre-implementation, warns on early passes
- **D-104**: One executable artifact-path policy governs TPM pack, unpack, agent mode, and refreeze
- **D-107**: Behavioral freezes require a fresh, coverage-checked `ERD-DELTA.md`
- **D-109**: Refreeze approval hashes use timestamp-free deletion labels

### Escalation ladder & failure paths

- **D-15**: INV-2 gate — halt, not cleanup
- **D-22**: INV-2 gate — halt, not auto-clean (reaffirmed)
- **D-24**: File-based pipeline state persistence
- **D-28**: Oracle projection — EM schedules frozen TPM tests, authors nothing
- **D-29**: Escalation ladder with batched, filesystem-only TPM round-trips
- **D-44**: The CEO gate is outcome acceptance, not diff review
- **D-57**: Carried-forward regression bucket computed by the shell
- **D-65**: `no_edit_files` — spec-declared no-op tasks never reach the coder
- **D-68**: Silent error swallows are a task failure; failure paths are spec surface
- **D-69**: Run wall-clock budget + phase-timing log
- **D-70**: The escalation ladder is armed — `MAX_TASK_STRIKES` defaults to 2
- **D-71**: EM diagnosis hardened — shrunken reply surface + one validator-fed retry
- **D-73**: Failure detail from the test report reaches retry briefs and consults
- **D-74**: Coder output linted per task, fail-closed, before acceptance
- **D-98**: Test verdicts require a freshly generated JSON report; stale reports are invalidated before every run
- **D-99**: Empty task state is allowed only after a covering success commit; mid-milestone loss still halts
- **D-100**: D-77 flake-green requires at least one isolated pass per failing carried node
- **D-103**: Frozen acceptance requires ordinary passed outcomes; skip/xfail/xpass remain red
- **D-110**: Report-parser compatibility is exercised against the real pytest-json-report producer
- **D-111**: Accepted flakes persist by spec; the recurring threshold routes directly to a TPM bundle
- **D-108**: Successful exact task/output matches persist in a bounded completion ledger
- **D-113**: Post-success spec continuity comes from the validated completion ledger, preserving delta invalidation

### Gates, lanes & governance

- **D-19**: `docs/.pm-last-review` — PM-owned ref marker
- **D-85**: A red CI stops the line — pre-flight consumes the external verdict, INCONCLUSIVE when it cannot, `SWBP_SKIP_CI_CHECK=1` to override
- **D-25**: INV-3 — decision-traceability gate (retired 2026-07-22, see D-25 amendment; keeping this section current is now a PM-review discipline)
- **D-33**: Fleet drift — birth-SHA identity, ownership-split manifests
- **D-34**: Template propagation — `update-template.sh` applies the refreeze pattern to the control plane
- **D-101**: Template removals contribute to the approval hash and apply atomically
- **D-36**: Gate-script self-tests (`scripts/selftest/`)
- **D-106**: The unconditional selftest CI job lints all template-owned Python under `scripts/`
- **D-37**: `build_extra`/`test_extra` exact-file lane exceptions in `.gate-paths` (retired 2026-07-22 with the `build`/`test` phase-gate phases that read them)
- **D-45**: Conductor bash allowlist — pipeline scripts + read-only git; everything else asks
- **D-47**: External TPM review of D-40..D-46 adjudicated
- **D-59**: The coder edits existing files through anchored blocks
- **D-76/D-84**: `project-trail/` running project record (né `postmortems/`) — unauthoritative, conductor- and human-authored, zero pipeline dependency, narrative never evidence
