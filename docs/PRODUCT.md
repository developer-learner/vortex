# PRODUCT.md — Product Context

> Evergreen. Describes what we're building and who it's for.
> Not a task list — that's in tasks/. This is the "why" layer.

---

## Problem Statement

Every local-LLM experiment on a Mac ends the same way: one model per runtime,
each runtime its own launcher, its own flags, its own port, its own RAM
budget. The moment a machine serves more than one model (ds4, llama-server,
LM Studio, mtplx…), "which model answers my request" becomes a manual art.
This owner-operator problem is real on this very machine: testchat spawns
run runts; LM Studio serves; scripts start llama-servers by hand. Vortex is
one place that owns every local LLM on the machine: installs and configures
runtimes, loads models, evicts them safely, and exposes the loaded set as one
universal OpenAI endpoint every client already speaks.

## Target Users

| User type | Description | Primary need |
|-----------|-------------|--------------|
| The owner-operator | one human Mac with GPU headroom and several runtimes (this machine, its pi agent, its scripts) | one endpoint, one CLI, one RAM policy for every local model |
| AI client apps | testchat, OpenCode, pi — anything OpenAI Chat Completions-shaped | a stable model id they can load/unload and stream against |
| Future: multi-runtime ML owners | dataset teams tuning 2–5 quantizations side by side | provisioning + tuning recipes that become catalog entries |

## Core Value Proposition

"We help the local-LLM owner run every runtime through one loader, one
catalog, and one OpenAI endpoint — so clients never care which runtime is
scarving which port."

## What We Are Not Building

- Not a chat front-end — that is testchat's job
- Not an inference engine or a runtime — Vortex owns *processes*, not math
- Not a cloud/labelled service — everything binds to 127.0.0.1
- Not a training/tuning platform in v1 — provisioning v2 (mtplx tune /
  vmlx bench) only tunes flags, never weights

## Success Metrics

| Metric | Target | How measured |
|--------|--------|--------------|
| Runtime habitat on one port | every catalog entry loads via one command | `vortex load <id>` live walkthrough |
| First-token correctness | 0 "phantom ready" (llama-server 503 class) | live walkthrough probe + milestone-1 fix |
| RAM safety | no silent eviction; conflicts structured (409) | live eviction demo + tests |
| Client cutover | testchat serves from `http://127.0.0.1:9000/v1/...` | phase-4 cutover oracle |

## Feature Flags / Rollout Notes

| Feature | Status | Notes |
|---------|--------|-------|
| Catalyst lifecycle (load/unload/operations) | live | prototype committed b76b5ea |
| Universal surface /v1 (Chat Completions) | live | non-stream + stream proxied |
| Provisioning + tuning (v2) | in-dev | roadmap phase 5 |
| Router UI | planned | roadmap phase 2 |
| testchat recut + cutover | planned | roadmaps 3–4; CEO-gated milestones