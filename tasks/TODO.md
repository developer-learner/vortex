# Vortex TODO — current actionable work

> Consolidated 2026-09-01 against Vortex `main`, frozen spec v26, and the
> canonical status register in `tasks/BACKLOG.md`. This is the short execution
> list; `BACKLOG.md` retains the detailed history and original item numbers.
>
> Baseline: the v22–v26 SOLID/async remediation is shipped on `origin/main`.
> The product suite is 115/115 green; manifest, Ruff, Mypy, release-gate, and
> GitHub CI are green. Completed audit items are intentionally not repeated
> below.

## Next product decisions

### T1 — Fail-safe admission under uncertain occupancy

- **Priority:** P1 safety hardening
- **Cost:** M/L
- **Blocker:** CEO/TPM must choose the conservative admission policy
- **Risk:** Vortex serializes its own load/unload admission correctly, and an
  identified-but-unverified runtime counts toward estimated RAM. However, a
  non-target catalog entry whose scan is `SCAN_UNKNOWN` with no prior status,
  or whose occupant cannot be identified because its sidecar is missing or
  invalid, is excluded from `Manager.all_ready()`. Admission can therefore
  undercount catalog-associated RAM while host state is uncertain.
- **Decision required:** choose one explicit rule for uncertain entries:
  refuse new loads; conservatively count the catalog RAM estimate; incorporate
  actual host-available memory as an additional bound; or a documented
  combination. This is fail-safe accounting, not a missing Manager slot lock.
- **Done when:** the policy is recorded, blind tests discriminate
  `SCAN_UNKNOWN`/unidentified non-target occupancy without regressing the
  identified-unverified case, implementation lands through refreeze, and the
  full product/static/manifest gates pass.

### T2 — Continuous readiness after post-load degradation

- **Priority:** P2 product-policy decision
- **Cost:** M if implemented; XS if the current limitation is explicitly accepted
- **Blocker:** CEO chooses whether session-latched readiness is sufficient
- **Current behavior:** harmonic readiness is verified on load/adopt and then
  represented by an in-memory session flag. A verified runtime that later
  degrades while remaining alive stays advertised. Steady-state reads perform
  zero inference probes by design.
- **Decision required:** accept the documented session-latched contract, or
  define a bounded re-probe policy (for example background/TTL/manual health
  refresh) that does not put a completion probe on every read.
- **Done when:** either the limitation is explicitly accepted and this item is
  closed without code, or the new policy is frozen, implemented, and verified
  against both degradation detection and the no-per-read-probe invariant.

## Maintenance

### T3 — Remove the Starlette TestClient deprecation warning

- **Priority:** P3 maintenance
- **Cost:** S/M
- **Blocker:** dependency/API migration choice; no new dependency without CEO approval
- **Done when:** the full suite emits no TestClient/httpx compatibility warning,
  behavior and coverage remain green, and dependency/config changes are pinned
  through the normal stack-sync path.

### T4 — Publish the current documentation updates

- **Priority:** operational
- **Cost:** XS
- **Blocker:** explicit push authorization
- **Current state:** local `main` contains the consolidated backlog/TODO updates;
  product v26 is already on `origin/main`.
- **Done when:** the documentation commits are pushed and remote CI is green.

## Pipeline evidence and governance

### T5 — Complete the D-168 immutable-plane live-fire proof

- **Backlog item:** 4
- **Priority:** evidence obligation
- **Cost:** M; coordination-heavy
- **Done when:** one successful real multi-task run crosses a mid-run Blueprint
  advancement and records the unchanged starting plane SHA in both the success
  commit and durable metrics.

### T6 — Observe one organic two-strike escalation-ladder climb

- **Backlog item:** 9
- **Priority:** observation trigger, not a standalone worktree job
- **Cost:** event-driven
- **Done when:** one uninterrupted organic run exercises the complete intended
  retry → diagnosis → revised brief/TPM path and its outcome is accepted against
  D-70/D-69.

### T7 — Decide model-specific Git provenance

- **Backlog item:** 13
- **Priority:** governance decision
- **Cost:** L if approved
- **Blocker:** CEO build/no-build decision
- **Done when:** either explicitly declined, or a trusted commit-broker design
  lands with author/committer separation, provenance trailers, prompt/reply
  hashes, pipeline attestation, tests, and Blueprint adoption.

## Product roadmap

### T8 — Recut Testchat onto Vortex's universal surface

- **Backlog item:** 15
- **Priority:** roadmap phase 3
- **Cost:** L
- **Blocker:** settle the reopened oracle/refreeze-mode question
- **Done when:** Testchat uses the Vortex-compatible universal surface under a
  frozen, accepted migration contract.

### T9 — Cut `LLM_ENDPOINT` over to Vortex

- **Backlog item:** 16
- **Priority:** roadmap phase 4
- **Cost:** M
- **Depends on:** T8
- **Done when:** clients use `http://127.0.0.1:9000/v1/chat/completions`, with
  rollback and end-to-end streaming/tool behavior verified.

### T10 — Complete provisioning/tuning v2 and the vmlx live exercise

- **Backlog item:** 17
- **Priority:** roadmap phase 5
- **Cost:** M plus operator time
- **Blocker:** host memory and session placement; the exercise must be driven
  outside the model session being evicted, with roughly 35 GB+ additional RAM
  headroom freed
- **Done when:** a real vmlx load → ready → proxy → unload cycle succeeds and
  its operational evidence is recorded.

### T11 — Choose mature OSS adoption subject #2

- **Backlog item:** 18
- **Priority:** roadmap/validation
- **Cost:** L
- **Blocker:** CEO selects and approves the subject
- **Done when:** a suitable mature OSS project is chosen and the second
  brownfield adoption is completed with its findings recorded.

### T12 — Decide whether to build `vortex ctx-tune <model>`

- **Backlog item:** 19
- **Priority:** roadmap decision
- **Cost:** L if approved
- **Blocker:** CEO build/no-build decision
- **Done when:** explicitly declined, or specified as a milestone covering
  workload profiling, model context probes, recommendation/application, and
  a bounded re-tuning policy.

## Recommended order

1. Decide T1; it is the only remaining audit-related safety question.
2. Decide T2; accepting the current limitation is a valid closure.
3. Publish the documentation (T4).
4. Execute T8 → T9; use a suitable real multi-task milestone to collect T5
   and, if it occurs organically, T6.
5. Schedule T10 when host memory/session constraints are satisfied.
6. Handle T3, T7, T11, and T12 independently when their decision gates open.
