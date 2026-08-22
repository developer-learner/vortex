# CURRENT.md — session notes

## State

- **2026-08-21 — Milestone #1 preflight WIRED AND SMOKED (all green).**
  dev-vm started; gateway verified from guest (`host.lima.internal` →
  vortex :9000 ✅ mtplx :8001 ✅). VM-side config written
  (`~/.config/sw-dev-blueprint/models.env`: EM/coder =
  `mtplx-qwen38-27b-optimized-quality`, SANDBOX_LLM_HOST/PORT set;
  `model-profiles.toml`: 32k context em/coder). **Key finding: mtplx
  honors `chat_template_kwargs.enable_thinking=false`** — reasoning_content
  empty, content clean (without it, --reasoning-mode auto separates
  reasoning into its own field; safe but burns budget). Smoke tests
  through real `llm-call.sh` FROM INSIDE THE VM: (a) plumbing round-trip
  → "SMOKE-OK", finish=stop, rc=0; (b) coder sentinel micro-task →
  byte-exact `=== FILE: … END FILE ===` block. mtplx left loaded (~30GB)
  for the run. Remaining to launch: TPM spec authoring → refreeze →
  orchestrate (blueprint-driven).
- **2026-08-21 — Milestone #1 seats named (D-139 cleared).** TPM =
  conductor LLM (this seat); EM/coder = `qwen3.8-27b-8bit` served by
  **mtplx** (`mtplx-qwen38-27b-optimized-quality`, :8001) — CEO corrected
  the earlier dspark mapping; mtplx is the runtime for the run. Conductor
  = same chat agent. Run driven by sw-dev-blueprint acting on vortex.
  Open preflight item: verify clean content-only completions through
  `llm-call.sh` — mtplx serves qwen3 with `--reasoning-mode auto`, and a
  live probe showed tokens consumed as `reasoning_content` with empty
  `content` (thinking-model parsing hazard).
- **2026-08-21 — CEO architecture ruling: blueprint-driven milestones.**
  Vortex stays **app-only**. `sw-dev-blueprint` is maturing into a
  framework that does the codework itself; the symlink control plane
  (`3ad9098`, branch `experiment/symlink-control-plane`) IS the intended
  wiring, not a stopgap. The next milestone (UI) must be RUN BY the actual
  sw-dev-blueprint acting on this repo — never a vortex-independent copy.
  Consequence: milestone preflights live on the blueprint side; vortex's
  `update-template.sh` path stays dormant while symlinks are in place.
- **2026-08-21 — UI concept SIGNED OFF (CEO).** Form factor A confirmed via
  the live interactive preview (`examples/ui-demo/`, look-and-feel adopted
  from the original Aug-17 preview at `~/dev/ui-demo/`, now deleted — its
  `top`-hack RAM figure was obsoleted by `a27fcf9`). UI is the
  first-milestone candidate. Implementation = one HTML template + static
  route + polling JS mounted in the daemon; no new API surface, so no new
  TPM acceptance scope per the concept doc. Milestone preflights still
  unmet: Lima gateway wiring + VM `models.env`.
- **2026-08-21 — ds4 runtime live PASSED (last P2 item closed).** Full
  lifecycle through vortex for `deepseek-v4-flash-0731` (:8005, ds4
  server / mtplx engine): spawn → ready in ~13s (op `4caa91b18e17`,
  sidecar pid 46748) → real completion via the :9000 universal surface
  (usage + cache_write passthrough) → unload `d1627e168fbd` stopped
  clean, port freed, sidecar dropped. Peak AM figure ~126.7/128 GB.
  Every catalog runtime family except vmlx has now run live through
  vortex (llama-server, dspark, mtplx, ds4; vmlx entry is the 100.8GB
  model — headroom-bound).
- **2026-08-21 — mtplx runtime live + adoption-across-restart PASSED
  (backlog P2 items closed).** Out-of-band mtplx app server on :8001
  (pid 44845, launched 14:47 via the desktop app — the exact
  out-of-band-spawner pattern predicted by the anomaly investigation)
  stopped by the CEO; vortex then spawned its own runtime on :8001
  (ready in ~7.5s, op `4dd0bc140545`, sidecar pid 46201). Proxy
  round-trip served real completions through :9000 (usage +
  `mtplx_stats` passthrough intact). Daemon restarted mid-loaded
  (46242): model process unchanged (46201), new daemon reported it
  `loaded` immediately via sidecar reconcile, completion served
  post-restart ("POST-RESTART-OK"). Unload `b5c4edaf5f15` → stopped,
  port free, sidecar dropped. NOTE: qwen3.8 reasoning-mode auto ate the
  first probe's tokens as `reasoning_content` (empty `content`) — the
  known thinking-model caveat; budget max_tokens accordingly.
  Second runtime family now proven live through vortex (llama-server
  was the only one before). ds4 catalog entry remains unexercised.
- **2026-08-21 — Daemon-drift anomaly investigation (findings; fix pending
  CEO go).** Reconstructed from artifacts (`kern.boottime`, boot2/boot3
  logs, sidecar dir mtimes, today's eviction-demo timings):
  (1) The machine **rebooted Aug 20 15:36**; boot3 daemon started 16:38.
  Boot3's log shows its FIRST `Flash_IQ3XXS/load` also got **409**, before
  today's successful run — the refusal reproduced across daemons.
  (2) Post-reboot, any `:8102` occupant must have been spawned by something
  other than vortex — prime suspect **testchat's SCRIPT_MODELS spawner**
  (`testchat/src/services/models.py` launches the very same
  `run-server-0731-ud.sh` on `:8102`). Vortex refusing it is the
  single-owner invariant working as designed, not drift.
  (3) Today's load took ~20s (fresh spawn, not instant adoption) and the
  port was free at preflight — the out-of-band server died between
  Aug 20 and Aug 21.
  (4) Remaining true anomaly is the **Aug 18 mid-session drop** from
  `loaded`. Leading theory: transient probe failure at ~126/128 GB memory
  pressure — `_find_listening_pid` swallows per-process `psutil.Error`
  and returns None (→ silently reports "unloaded"), and `identifies()`
  likewise swallows sidecar-read OSError / start-time-fetch failure
  (→ false "unidentified" 409). Both self-healed on later polls, matching
  the observed flapping; a fresh out-of-process check succeeded minutes
  later. Unprovable retroactively: lifecycle logs NOTHING on these paths.
  (5) **Root defect = observability**: state flips are silent, and the 409
  body does not distinguish no-record / pid-mismatch /
  start-time-unavailable.
  Proposed fixes (coder lane, D-175 direct): F1 log every owner_status
  transition + reason; F2 structured diagnostics in the PortConflictError
  409 body; F3 anchor sidecar/catalog paths to repo root (CWD-proof;
  current daemon verified cwd=repo root); F4 boot-time stale-sidecar
  reconciliation log.
- **2026-08-21 — F1–F4 LANDED (same day).** 18/18 tests green, ruff clean
  (E4,E7,E9,F; pre-existing SIM102 in `spawn()` untouched), daemon
  restarted on new code (`/tmp/vortex-boot4.log`). Live verification:
  warn-once-per-port scan warning fires; refusal diagnostics live-fire
  `409 ... refusing (no sidecar record)` via a fake `:8102` occupant.
  **New finding:** every scan skips ~310 unreadable processes (macOS
  denies connection enumeration on privileged processes) — the concrete
  silent-flap mechanism; if a model's own process is transiently
  unreadable it vanishes from `loaded`. Now visible in logs forever.
  Regression tests pinning F2's diagnostic shape = future freeze item.
- **2026-08-21 — Live-demo eviction PASSED (backlog P2 item closed).**
  Drove the real structured conflict on this machine: loaded
  `Flash_IQ3XXS` via `POST /api/models/{id}/load` (ready in ~20s,
  op `431abc7de1c8`; AM figure peaked ~126GB), then attempted
  `mtplx-qwen38-27b-optimized-quality` → **HTTP 409** with
  `required_gb: 30.4`, `eviction_candidates: ["Flash_IQ3XXS"]`
  (budget math: 102.4 − 90 = 12.4 < 30.4). Refusal was pre-spawn:
  port 8001 stayed free, no mtplx process ever existed. Unload
  (`34caea6dd630`) returned `stopped: true` in ~10s; `/api/status`
  back to `loaded: []`. First live (non-CI) evidence for the
  never-silent-kills invariant.
- **2026-08-18 — Daemon adoption anomaly + resolution.** A long-running
  daemon dropped Flash_IQ3XXS from `loaded` mid-session and then refused
  adoption (`409 unidentified process`) despite a byte-exact sidecar match
  (verified: live `create_time` == recorded `start_time`, delta 0.0; fresh
  in-process `SidecarStore.identifies()` returned True). Clean daemon restart
  re-adopted at boot (sidecar path works; `v1/models` + proxy round-trip
  verified `OK`). Root cause of the mid-session drop uninvestigated —
  candidate backlog item: daemon state drift across long uptimes.
  Daemon now pid 19743 (`/tmp/vortex.pid`), log `/tmp/vortex-boot2.log`.
  Also: `/api/status` reports the Activity-Monitor figure (wired+active+
  inactive+spec+compressor via vm_stat, `a27fcf9`) — display-only; AM's
  exact "Memory Used" decimal (~123.7) is not reproducible from public
  stats (app-attributed inactive pages); top-style figure (~126) and AM
  track together within the cache delta.
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

## Backlog

- **FEATURE (proposed, un-speced): `vortex ctx-tune <model>`** — automated
  context-length selection. Three parts: (1) workload profiler (largest
  artifact + tool-output budget + real session token usage from opencode
  session store), (2) model probe (needle test at 32k/64k/128k/256k +
  TTFT/TPS curve), (3) decision + application (recommend
  `max(workload_peak×2, artifact+budget)` clamped to the needle-validated
  ceiling, write into catalog `ctx_size` + opencode `limit.context`) with a
  compaction-frequency/TTFT watchdog that re-tunes only on >30% signal
  shift. CEO decision to build pending; raised 2026-08-18. Context choice
  should be a program's decision, not a human's.

## Results

  Delta-mapped frozen tests green against spec v1 — feature done (verdict scope: mapped tests only, D-112). Feature built and validated.
