# CURRENT.md — session notes

## State

- **2026-08-15 — Brownfield adoption landed.** Control plane installed
  verbatim from blueprint @`8f9ce08` (66 template-owned files hash-verified,
  birth ref stamped, `.manifest-project` regenerated, gate hook armed).
  Legacy prototype pinned at `b76b5ea`; its 16 tests snapshotted
  (`scripts/.approved/legacy-pin.json`, NOT an oracle — D-1). Ledger D-172..D-174.
  Testchat ruled hands-off by the CEO (never an experimentation subject).
- **2026-08-16 — Adoption commit `015a4a2` landed.** 112 files, 454/454
  plane selftests, ruff clean. D-160 placeholder gate satisfied (PRODUCT /
  ARCHITECTURE / CLAUDE contacts filled; `.manifest-project` re-pinned after
  the AGENTS.md symlink hash trip).
- **2026-08-16 — TPM seat named (D-139 cleared): the conductor.** EM/coder =
  `qwen3.8-27b-8bit` served via mlx-dspark (`lmstudio-community`
  Qwen3.8-27B-MLX-8bit, 8-bit complete; mlx-community 8-bit is shard-incomplete
  — never use), loaded through vortex at :8103 behind the :9000 universal
  surface. Verified round-trip 0.3s, thinking off (`--no-thinking`), usage
  passthrough intact. Cache capped pre-import (8GB cache / 50GB memory).
- **Pre-spec tunnel** (D-173): plane is gate-clean until the first freeze
  creates `scripts/.approved/VERSION`.
- **2026-08-17 — Adoption check done.** Full control-plane selftest suite
  green on this machine: 456 passed / 74s (`pytest scripts/selftest/selftest_*.py`,
  CI-identical invocation). 454→456 = the two phantom-ready regression tests
  shipped with `859bfb2`.
- **2026-08-17 — Catalog maintenance.** `Flash_Q2KXL` entry removed
  (`fede767`; Q2_K_XL GGUF deleted from disk 2026-08-17, ~90GB reclaimed).
  `mtplx-qwen38-27b-optimized-quality` (:8001, 30.4GB) and
  `vmlx-dsv4-configi-mlx` (:8104, 100.8GB) registered — registration only;
  exercise-live (BACKLOG item) still pending: the 3-bit is resident
  (~107GB/128GB), so no further model may load until the CEO frees memory.
- **2026-08-17 — Ready-probe fix verified live.** `859bfb2` predicate
  (port ownership + /v1/models 200 + real 1-token chat completion) passes
  against the resident Flash_IQ3XXS; negative path pinned by the two
  regression tests in the 456.
- **2026-08-17 — Milestone + Lima deferred by CEO.** No orchestrate run, no
  `dev-vm` boot while the 3-bit is resident (memory headroom ~20GB).
  Direct ad-hoc work only (D-175 routing). Preflight prerequisites
  (VM gateway wiring, VM `models.env`) remain unmet until a run is
  authorized.
- **2026-08-17 — CEO rulings.** (1) `omlx` is NOT in the backlog/plan —
  install only on the day it is actually needed; never re-suggest as
  pending. (2) UI concept (router phase 2) un-gated: `docs/UI-CONCEPT.md`
  drafted, awaiting CEO sign-off (form factor A recommended: server-rendered
  page on `:9000/`). (3) check-drift verified IN_SYNC on
  `experiment/symlink-control-plane` (child == template @`1ce8a33f`, rc=0)
  — the symlink declutter does not register as drift.
- **2026-08-17 — Memory figure in UI = Activity Monitor's number.** The
  daemon reports psutil-used (~111GB) while Activity Monitor counts ~126GB
  (wired + compressor + active + inactive + cache). The UI shows the AM
  figure (top PhysMem), not psutil-used. The daemon's eviction math
  (`manager.py eviction_required`) is model-estimate-based
  (`0.8*total` vs sum of loaded estimates) and is independent of the
  displayed figure — changing the display cannot affect loadability.
  **No load-threshold rule**: high-occupancy loads (e.g. the 3-bit at
  ~126GB) are legitimate; the DSpark failure was GPU working-set, not RAM.

## Halt notes

- **HALT lifted — seat named.** First milestone (ready-probe fix, `503
  Loading model` class) may proceed: spec authored by the TPM seat
  (conductor), frozen via `refreeze.sh`, run via `orchestrate.sh`.
- Orchestrate pre-flight requires: Lima `dev-vm` running, **model reachable
  from inside the VM** (vortex daemon currently binds 127.0.0.1 only —
  VM/host-gateway wiring + VM `models.env` (`qwen3.8-27b-8bit`,
  `SANDBOX_LLM_HOST/PORT`) is orchestrate prep), working tree clean.

## Open questions

- Refreeze-mode question (D-165): at the first freeze, are the 16 legacy
  tests carried into the frozen suite or retired? (Milestone 1 decides.)
- OSS brownfield subject for adoption run #2 — candidate search parked
  (D-1 "do not suggest": only after vortex mechanics are proven).

## Next actions

1. CEO names TPM seat → author first spec (ready-probe fix) → freeze →
   orchestrate — **blocked: milestone runs deferred until memory freed**
2. ~~Verify installed plane's selftests pass on this machine~~ — DONE
   2026-08-17 (456/456, 74s)
3. Stand up Lima + models.env when the first milestone launches — blocked
   with item 1
4. Exercise mtplx/vmlx catalog entries live once a model slot is free
   (BACKLOG)