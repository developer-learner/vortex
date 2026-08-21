# BACKLOG.md — triaged work

## P1 — first milestone candidate

- **Ready-probe fix** (D-174): llama-server answers `/v1/models` 200 while
  weights still load → first inference returns `503 Loading model`. The
  spawn probe must not declare a runtime ready on a lying endpoint. First
  real work item under the plane: spec → freeze → EM → coder → gate.

## P2 — prototype hardening (post-milestone-1)

- (none — all retired; see below)

## P3 — roadmap phases (post-cutover)

- UI (router phase 2) — model menu w/ load/unload, RAM meter.
- testchat recut (phase 3) — swap `SCRIPT_MODELS` + per-model routing for
  the universal surface; oracle-heavy; refreeze mode question reopens.
- Cutover (phase 4) — `LLM_ENDPOINT` → `http://127.0.0.1:9000/v1/chat/completions`.
- Provisioning + tuning v2 (phase 5) — `mtplx tune` / `vmlx bench`, winners
  → catalog.
- Adoption run #2: mature OSS subject (CEO-approved profile; see D-1).

## Retired / superseded

- **Live-demo eviction** — done 2026-08-21: real 409 driven live
  (`required_gb: 30.4`, candidates `[Flash_IQ3XXS]`, pre-spawn refusal,
  port 8001 never bound). Evidence in `tasks/CURRENT.md` session notes.
- **Live-demo adoption across a daemon restart (sidecar reconcile)** —
  done 2026-08-21: mtplx runtime spawned by vortex survived a daemon
  restart; new daemon re-adopted via sidecar at first poll, model process
  unchanged, completions served post-restart. Evidence in session notes.
- **Exercise the ds4/mtplx catalog entry live (mtplx half)** — done
  2026-08-21: full lifecycle through vortex (spawn → ready → proxy →
  adoption across restart → unload). Evidence in session notes.
- **Exercise the ds4 catalog entry live** — done 2026-08-21: spawn →
  ready ~13s → real completion via :9000 → clean unload. Evidence in
  session notes.
- **CLI polish: daemon-less `vortex` UX when `:9000` is down** — done
  2026-08-17 (`2cf8484`).