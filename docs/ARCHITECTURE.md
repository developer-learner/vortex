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
| public_id | str | user-facing model id (`vortex load <public_id>`) |
| runtime | str | engine family: `ds4`/`llama-server` |
| engine | str | e.g. `mtplx`, `llama.cpp` |
| launch_command | list[str] | script (and args) that start the runtime server |
| port | int | runtime's own listen port |
| ready_url | str | http health probe the daemon polls after launch |
| chat_endpoint | str | runtime's chat/completions URL that /v1 proxies to |
| upstream_alias | str | model id sent upstream for this entry |
| ram_estimate_gb | float | budget line for admission/eviction decisions |
| exclusive | bool | true = only one loaded at a time |

**Relationships:**
- has one `RuntimeState` while loaded (in-memory, not persisted)

### RuntimeState (in-memory, one per running entry)

| Field | Type | Notes |
|-------|------|-------|
| entry_id | str | the CatalogEntry public_id |
| proc | subprocess.Popen | sidecar owner of the runtime process |
| ready | bool | poll result of `ready_url` |
| ops | dict[str, str] | last operations context (e.g. `load`) |

---

## API Structure

```
# Universal surface (OpenAI Chat Completions — what clients use)
POST   /v1/chat/completions         proxy to loaded model (also streams SSE)
GET    /v1/models                   list loaded models

# Management surface (the daemon's own controls)
GET    /api/status                  daemon + RAM + loaded-set status
GET    /api/runtimes                catalog entries + load state
POST   /api/runtimes/{id}/load      start sidecar, poll ready_url to ready
POST   /api/runtimes/{id}/unload    graceful terminate, wait port free
POST   /api/runtimes/{id}/evict     force-kill under RAM pressure
GET    /api/runtimes/{id}           single-entry detail

# CLI (src/modelmux/cli.py) — same verbs: vortex models|load|unload|status
```

---

## Key Flows

> Describe the important user journeys as numbered steps.
> These prevent the LLM from misunderstanding how pieces connect.

### Load

1. `POST /api/runtimes/{id}/load` (or CLI)
2. Manager checks admission: eviction set computed off `ram_estimate_gb`,
   exclusive entries evict current first
3. Lifecycle spawns the launch script as the ONLY process owner (sidecar)
4. Daemon polls `ready_url` until 200 (10s-interval loop) then marks ready
5. Runtime becomes visible at `/v1/models` and in `/api/status`

### Chat proxy

1. Client calls `POST /v1/chat/completions` with a loaded public_id
2. App resolves the entry, forwards body (model id remapped to
   `upstream_alias`) to `chat_endpoint` via httpx
3. Non-stream: response relayed with usage passthrough intact
4. Stream: async generator relays SSE chunks verbatim (`reasoning_content`
   preserved)

### Unload

1. `POST /api/runtimes/{id}/unload` (or CLI)
2. Graceful TERM to the sidecar process, wait with timeout (CLI 60s) for
   port + process exit
3. RuntimeState cleared; `vortex models` reports unloaded
4. RAM is released back to the pool for admission

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
- **Ready ≠ loaded (finding #1, D-174)** — llama-server answers `/v1/models` 200 while weights still load; the first chat after ready can return `503 Loading model`. Milestone-1 target: a stronger probe (anneal/poke before first request)
- **Process ownership is strict** — a loaded model's sidecar is the single owner; the daemon never spawns clones via health re-polls (orphan adoptable only after restart, per CEO ruling)
- **No DB** — the catalog is the only persistent truth; runtime state dies with the daemon
- **RAM is a budget, not a lock** — admission/eviction uses `ram_estimate_gb`; eviction races are structured 409 errors, not silent kills

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
