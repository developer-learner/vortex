# CURRENT.md — session notes

## State

- **2026-08-25 — Handoff before pi restart. Group A fully landed; sweep verified NOT run.**
  - **Done + pushed (through pre-push gates):** Group A — 3 fixture tests (2a
    shortlist closed), tpm-lint retired (D-171), 6 provenance backfills.
    Blueprint at `9a5ac32`, vortex at `e074bfa`, both at origin.
  - **2b mutation sweep — verified not running, no output.** Checked: no
    mutation-pass/pytest process on host, no `swbp-mutation.*` temp clone,
    no output file in either repo / /tmp / home, both repos clean, Lima
    `dev-vm` **Stopped** (not running in the VM either). The "other LLM"
    run died before its first incremental append. Only mutation artifact
    on disk: `2026-08-23-d161-vortex-mutation-report.md` (6 mutants:
    4 killed / 2 survived). **Next session: author the mutants file for
    the ambiguous gates and run `scripts/mutation-pass.sh` against
    Blueprint HEAD, incremental `--out` to
    `docs/research/2026-08-24-d161-gates-mutation-report.md`.**
  - **pi routing (host config, not repo):** `~/.pi/agent/models.json` now
    has a `vortex` provider → `http://localhost:9000/v1`, model
    `qwen3.8-27b-mtplxopt-dspark` (endpoint verified live, 200). Existing
    `local` :8002 provider untouched (A/B possible). Switch via `/model`.
  - **Throughput measured (same day):** dspark :9000 ≈ 24 tok/s agent /
    40.6 code / 30.3 prose; mtplx :8002 (the model running this session)
    ≈ 30 tok/s avg at ~50k ctx; lookup (drafter-free) strictly worse
    (≈16, tok/chunk ~1.05 — n-gram drafter never matches); dflash
    unavailable (no drafter registered; hybrid markov_rank=256 head
    unsupported by mlx-dspark). Verdict: dspark mode is the ceiling for
    this 27B-8bit locally; only levers left = smaller model or
    purpose-trained drafter.
  - **Minor flags still open:** (1) audit report header still reads
    "38 TEETH" — correction (35/3/2/1=41) is buried in the Post-report
    addendum; a casual reader meets the wrong number first. (2) 5 of the
    6 provenance backfills live in the audit report only, not
    `DECISIONS.md` (tpm-lint got D-171) — decide if acceptable.
  - **Optional, unconfirmed:** launchd agent so the :9000 daemon + model
    survive reboot (not set up).

- **2026-08-24 — Steady state. Flap-bug thread fully closed; direction settled (D-170).**
  Refreeze v11 (`8097f33`) pinned the tri-state regression; refreeze v12
  (`85f0cbd`) added the frozen CLI tests (`test_cli.py`, TPM seat: CEO);
  coverage 88.15% ≥ 80% floor; full product suite green; CI +
  check-drift green. Gate audit landed in two passes: `b3f040f`
  (wiring: 40/41 live, 1 doc-only, 0 orphan) + `65da200` (teeth by
  static read: 38 proven / 3 unproven / 2 settled) — report at
  `tasks/AUDIT-gates-2026-08-24.md`. Decision memo at
  `tasks/DECISION-MEMO-builder-vs-template-2026-08-24.md` (`6c07c49`).
  **Direction settled (D-170 in Blueprint `docs/DECISIONS.md`): both —
  template at seed (born-linked), builder for life.** Open work:
  combined TODO in Blueprint `tasks/TODO.md` (Group A foundation batch,
  2b mutation sweep, catch ledger, tiering, born-linked seed path;
  vortex product debt — memory-figure mismatch + `_anneal_probe`
  hardening — each pairs with a refreeze, D-139 named seat).

- **2026-08-23 — Flaky-probe fix landed (2026-08-18 anomaly class closed).**
  Port scan is now tri-state (`_scan_port` in `lifecycle.py`): pid /
  confirmed-empty `None` / `SCAN_UNKNOWN` after 2 retries. Only transient
  `psutil.Error` counts as incompleteness — `AccessDenied` (other users'
  processes, permanent on macOS) and `NoSuchProcess` are safe skips. All
  callers fail closed on unknown: `owner_status` holds last status (no
  state flip), `spawn` refuses (`PortConflictError`), `terminate` refuses
  and never drops the sidecar (the old false-`None` path that caused the
  `409 unidentified process` despite byte-exact match). `SidecarStore.read`
  now distinguishes absent from present-but-unreadable. `app.py` sanitizes
  `port_pid` via `as_pid()`. Tri-state regression tests were drafted but
  NOT committed here (INV-1: agents don't author frozen-suite tests) —
  SUPERSEDED 2026-08-24: pinned in refreeze v11 (`8097f33`) with a named
  TPM seat. Full product suite green (36 passed, all 6 test files);
  ruff clean.

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

- ~~HALT lifted — seat named.~~ Consumed: the first milestone ran
  end-to-end 2026-08-22 (freeze v1 → plan → tasks → `[success]`).
- ~~Orchestrate pre-flight requires: Lima `dev-vm` running, model
  reachable from inside the VM, working tree clean.~~ Met and consumed
  by the real M1 run (gateway + VM `models.env` wired and verified
  2026-08-21; run green 2026-08-22). These are standing pre-flight
  checks for FUTURE runs, not open work.

## Open questions

- ~~Refreeze-mode question (D-165): at the first freeze, are the 16
  legacy tests carried into the frozen suite or retired? (Milestone 1
  decides.)~~ ANSWERED by freeze v1 (`73eb737`): the legacy tests were
  CARRIED into the frozen suite (test-nodeids v1 = 27 = legacy catalog+serve
  plus the 9 new UI tests; v3 = 33 after ui_api_contract joined at v2).
  The `legacy-pin.json` snapshot remains as provenance only (NOT an
  oracle). Refreeze mode going forward is the standard delta machinery.
- OSS brownfield subject for adoption run #2 — candidate search parked
  (D-1 "do not suggest": only after vortex mechanics are proven).

## Next actions

1. ~~CEO names TPM seat → author first spec → freeze → orchestrate~~
   DONE 2026-08-22 (M1 complete, three freezes v1–v3 all `[success]`).
2. ~~Verify installed plane's selftests pass on this machine~~ — DONE
   2026-08-17 (456/456, 74s)
3. ~~Stand up Lima + models.env when the first milestone launches~~ —
   DONE 2026-08-21; exercised for real by the M1 run.
4. Exercise the vmlx catalog entry live once a model slot is free
   (BACKLOG Wave E item 17 — serialized runtime exercise, never a
   worktree job)

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

## Session 2026-08-23 — M1 close-out: browser eyeball + status-doc reconciliation

  **Browser eyeball DONE (conductor, real headless Chrome at
  1280×900, screenshot reviewed).** Daemon served the dashboard on
  :9000 from this tree (`uvicorn vortex.app:build_app --factory`);
  findings:
  - Title bar "vortex · model menu" renders; dark theme, layout clean.
  - RAM meter live and consistent with `/api/status` (50.4 / 128 GiB,
    39.4%; blue fill ~40% of track).
  - Model menu lists all five catalog entries (deepseek-v4-flash-0731,
    Flash_IQ3XXS, qwen3.8-27b-8bit, mtplx-qwen38-27b-optimized-quality,
    vmlx-dsv4-configi-mlx) with idle status dots, per-model size column,
    and a `load` action button each — matches catalog.json exactly.
  - Down-state banner correctly ABSENT (daemon up); conflict card
    correctly dormant (no conflict active). Footer poll note present.
  - Known residual (not M1 scope): the conflict card only ever shows via
    `s.conflict`, which `GET /api/status` never carries — BACKLOG item 5.
  Eyeball evidence: screenshot retained in session record; daemon shut
  down after verification, port freed.

  **Status-document reconciliation** (this commit):
  - Retired: "milestone launch memory-blocked" (M1 ran green
    2026-08-22), "Lima gateway wiring + VM models.env unmet" (met and
    consumed by the real run), D-165 refreeze-mode open question
    (answered below), UI route/slicing open decision (settled by plan).
  - Preserved verbatim: all v1/v2/v3 freeze/plan/task/success evidence.
  - CLAUDE.md tech-stack testing line updated (16-legacy-test snapshot
    → frozen suite); `.manifest-project` re-pinned.

## Results

  Delta-mapped frozen tests green against spec v1 — feature done (verdict scope: mapped tests only, D-112). Feature built and validated.

## Session 2026-08-22 (afternoon) — M1 run complete

  Milestone #1 (Router Phase 2 UI dashboard) executed end-to-end by the
  pipeline: freeze v1 -> plan -> T1+T2 attempt-1 green -> [success] a6f6ec6.
  Full frozen suite re-verified on host: 27/27. Dashboard live-serves 200.

  Incident trail (all resolved):
  - v1 freeze crashed twice post-apply (blueprint first-freeze old-contracts
    bug; VM git dubious-ownership). Manual completion missed ERD-DELTA-v1.md
    -> plan gate failed closed. Repaired 83918c0 (+correction row).
  - Blueprint bugs fixed upstream (6f37b21, 438d4c8, bd0231e, 8a247f8).
    The last fix closes the v1 ERD-delta contradiction by snapshotting the
    full initial ERD as ERD-DELTA-v1.md; all 467 control-plane selftests pass.
    Vortex's control-plane pin is aligned to 8a247f8.

  Open: CEO live acceptance of the served dashboard (Playwright-green and
  conductor visual QA are necessary, never sufficient under D-44). Conductor
  visual QA completed 2026-08-23; CEO acceptance remains pending.

## Results

  Delta-mapped frozen tests green against spec v2 — feature done (verdict scope: mapped tests only, D-112). Feature built and validated.

## Results

  Delta-mapped frozen tests green against spec v3 — feature done (verdict scope: mapped tests only, D-112). Feature built and validated.

## Session 2026-08-23 — conflict-card milestone and D-168 child live-fire

  **Product closure:** the dashboard conflict card now consumes the real
  model-load `409` detail, clears after a successful action, and no longer
  reads nonexistent `s.conflict` status data. The low-RAM VM also exposed and
  closed an idempotency defect: requesting an already-ready model no longer
  reports that same model as an eviction conflict. Spec v10 completed at
  `5f32f10` on plane `c66fa5779ab1`; 36/36 frozen tests and whole-source mypy
  were independently replayed green in the dev VM.

  **Control-plane closure:** Vortex live use exposed five child/composition
  defects after the original D-168 repair: real non-dry-run re-exec state,
  child working-directory preservation, child-repo sandbox mounting, stale
  one-file brief carry-forward, and future-DAG-file mypy coupling. Each was
  fixed upstream with a focused regression, the complete Blueprint suite was
  green before publication, and Vortex adopted the final published ref
  `c66fa57` in `526262d`. Blueprint reports 487/487 selftests at that ref.

  **Strict evidence still open:** Blueprint advanced from `6f8b6e8` to
  `9d431cd` during the real v4 run while the run remained pinned to its
  starting plane, proving the immutable/same-SHA behavior through that point.
  The run later halted on separate planning/product defects, so D-168 still
  needs one uninterrupted successful multi-task run that crosses a mid-run
  Blueprint advancement and records the unchanged starting SHA in both the
  success subject and metrics. Do not infer that proof from the later v10
  success, which began directly on `c66fa57`.

## Session 2026-08-23 — D-169 diagnosis taxonomy adoption

  Blueprint `5d4969c` adds the positive-evidence-only
  `transient_or_environmental` diagnosis and routes it to a preserved
  operator-review record plus a hard halt. The shell never automatically
  retries, re-probes, rewrites the plan, or sends the case to the TPM. Vortex
  adopted that exact published ref in `2a32945`; its inherited control-plane
  suite passed 490/490 in this child tree.

## Results

  Full frozen TPM suite green against spec v10 (on-demand regression check, D-112). Feature built and validated.
