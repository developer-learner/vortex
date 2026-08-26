# BACKLOG.md — triaged work

## Canonical pending-work register

> Reconciled by **Codex (GPT-5), 2026-08-23** against the current Blueprint,
> Vortex, and Testchat trees; refreshed after Testchat's final adoption proof.
> This is the deduplicated current list. All
> agent-authored entries below remain untouched as historical source notes;
> where a historical note conflicts with current repository state, this
> section controls status.

### P0 closure — release repaired; one strict live-fire proof remains

1. [x] **Blueprint — repair and prove the D-168 release.** The original 47
   failures and the child-only defects subsequently exposed by Vortex and
   Testchat are repaired. Blueprint's exact full suite is green at **490/490**
   on published ref `3d5a5e6`; the copied-child whole-entrypoint, child-cwd,
   child sandbox-mount, current one-file brief, and per-task mypy boundaries
   all have regressions.
2. [x] **Blueprint — prevent another unverified publication.** The pre-push
   release gate checks the exact commit being published in an isolated copy,
   fails closed for an unavailable SHA, and has dogfooded every corrected
   Blueprint publication.
3. [x] **Blueprint → Vortex — publish and adopt the corrected successor.**
   Vortex advanced through `2a32945`, then adopted the final published
   Blueprint `3d5a5e6` in `8f8984e`; both manifest checks are green. Its
   inherited **490/490** suite was green at `5d4969c`; the final adoption adds
   the copied-child regression that Testchat subsequently proved.
4. [ ] **Vortex — collect the remaining D-168 live-fire evidence.** The
   mechanism, non-dry-run, child-tree, and VM proofs are complete. Blueprint
   was advanced from `6f8b6e8` to `9d431cd` during the real v4 run and the run
   remained pinned to `6f8b6e8`, but that run later halted on unrelated
   planning/product defects. The strict proof still owed is one successful
   real multi-task run that crosses a mid-run Blueprint advancement and records
   the unchanged starting plane SHA in both its success commit and metrics.

### P1/P2 — product and control-plane hardening

5. [x] **Vortex — fix the dashboard conflict card.** Spec v10 success
   `5f32f10` includes the real model-load `409` detail path, clears the card on
   success, and removes the dead `GET /api/status` `s.conflict` read. The
   complete frozen suite is green at **36/36** and whole-source mypy is green.
6. [x] **Vortex — close M1 review and reconcile status docs.** Conductor
   browser QA and status-document reconciliation are complete. CEO live
   acceptance followed on 2026-08-23: dashboard load/unload was exercised and
   reported working, closing the D-44 human acceptance boundary.
7. [x] **Blueprint — execute D-161's report-only oracle-strength measurement.**
   Completed in `492b8f0`; report and raw mutant results are under
   `docs/research/` and the runner is regression-tested.
8. [x] **Blueprint — A/B the denser EM diagnosis brief** against archived
   diagnosis transcripts. Completed in `2eb2809`; the dense wording was not
   shipped because both variants exposed the same missing transient verdict.
   The follow-up taxonomy is also complete: D-169 shipped at Blueprint
   `5d4969c` with positive-evidence-only classification and a hard
   operator-review halt—no automatic retry, re-probe, plan change, or TPM
   escalation. Vortex adopted that exact ref in `2a32945`; its inherited
   control-plane suite is green at 490/490.
9. [ ] **Blueprint — validate the first organic two-strike ladder climb.** The
   Vortex repair run produced schema-valid `brief_wrong` diagnosis and a
   materially revised brief, and later produced a usable TPM batch. Keep this
   open until one uninterrupted organic run exercises the complete intended
   ladder and its outcome is explicitly accepted against D-70/D-69.
10. [x] **Blueprint — finish the pending D-44/Rule-5 acceptance wording.**
    Reconciled in `3225106`; D-44 remains a human acceptance gate, not a test
    claim.
11. [x] **Blueprint — live-probe D-47's OpenCode permission behavior** for
    glob-versus-compound-command matching. Completed in `f3a2ba1`; evidence is
    recorded in `docs/research/2026-08-22-d47-permission-probe.md`.
12. [x] **Blueprint docs — close stale Linux-VM acceptance bookkeeping.**
    Completed in `3380371` using the unattended Vortex milestone evidence.
13. [ ] **Blueprint → Vortex — decide model-specific Git provenance.** If
    approved, use a trusted commit broker, author/committer separation,
    provenance trailers, prompt/reply hashes, and pipeline attestation; an
    author label alone is not reliable attribution.

### P3 — roadmap and CEO-gated work

14. [x] **Testchat — adopt the current control plane first.** Testchat adopted
    published Blueprint `3d5a5e6` in `e831315`; both manifest checks and the
    complete inherited suite are green at **490/490**. Adoption evidence is
    recorded in `bb8f7cd`, published on Testchat `main`.
15. [ ] **Vortex/Testchat — roadmap phase 3:** recut Testchat onto Vortex's
    universal surface; settle the reopened oracle/refreeze-mode question.
16. [ ] **Vortex/Testchat — roadmap phase 4:** cut `LLM_ENDPOINT` over to
    `http://127.0.0.1:9000/v1/chat/completions`.
17. [ ] **Vortex — roadmap phase 5:** provisioning and tuning v2, including a
    real vmlx load → ready → proxy → unload exercise.
    Status 2026-08-26: the vmlx path is live-verified up to the memory gate —
    `POST /api/models/vmlx-dsv4-configi-mlx/load` → 409 `required_gb: 100.8`,
    `eviction_candidates: [mlx-community--Qwen3.8-27B-4bit]`, pre-spawn (port
    8104 never bound, no vmlx process). The full exercise is memory-blocked in
    a sharper sense than "a slot is free": the sole eviction candidate is the
    4-bit model serving the working session (unloading it kills the session),
    and physical RAM (≈62 GB baseline + 100.8 GB ≈ 163 GB > 128 GB) would swap
    even after eviction. Needs the CEO to free ~35 GB+ of app memory and drive
    the exercise from OUTSIDE the session (or switch the session's model first).
18. [ ] **Vortex — choose and run CEO-approved mature OSS adoption subject #2.**
19. [ ] **Vortex — decide whether to build `vortex ctx-tune <model>`.**

## Parallel worktree execution map

> Item numbers refer to the canonical register above. A bucket is the merge
> unit: work inside one bucket stays together because it shares files or one
> evidence chain. Buckets in the same wave may run concurrently in separate
> worktrees. The stated ownership boundaries prevent avoidable merge conflicts.

### Wave A — four independent buckets can start now

| Bucket | Suggested worktree branch | Items | Exclusive ownership / completion boundary |
|---|---|---:|---|
| **A1 — D-168 core repair** | Blueprint `fix/d168-suite` | 1 | `scripts/orchestrate.sh`, extracted harnesses, affected selftests, and the D-168 correction-log row. Complete only at **469/469 green** (or the current collected total if it legitimately changes). |
| **A2 — publication enforcement** | Blueprint `fix/release-verification-gate` | 2 | CI/release/pre-push enforcement plus its own focused tests. It may be developed while A1 is red, but cannot be enabled or called proven until rebased onto A1 and the exact full suite is green. |
| **A3 — evidence and doctrine** | Blueprint `chore/open-evidence` | 7, 8, 10, 11, 12 | D-161 report, EM-diagnosis A/B, D-44 wording, D-47 live probe, and stale Linux-VM bookkeeping. Own research outputs and doctrine/docs; do not edit D-168 runtime or harness files. |
| **A4 — Vortex M1 close-out** | Vortex `docs/m1-closeout` | 6 | CEO browser findings and status-document reconciliation. Do not edit `tasks/BACKLOG.md`; the canonical/history register stays integration-owned. |

Item 9 is not a worktree job: it remains an **observation trigger** until a
real run organically reaches the second-strike consult path.

### Wave B — one serialized Blueprint integration lane

1. Merge/rebase **A1** into a clean Blueprint integration worktree.
2. Rebase and merge **A2** onto it.
3. Run the exact full selftest suite from that combined tree.
4. Publish one corrected successor only after the combined tree is green.

**A3** may merge before or after this lane if its ownership boundary remained
clean; it does not gate publication. **A4** is entirely independent.

### Wave C — adoption fan-out after the corrected Blueprint is published

| Bucket | Suggested worktree branch | Items | Dependency |
|---|---|---:|---|
| **C1 — Vortex adoption** | Vortex `chore/adopt-d168-closure` | 3 | Corrected Blueprint ref from Wave B. Regenerate and verify both manifests. |
| **C2 — Testchat adoption** | Testchat `chore/adopt-current-plane` | 14 | Same corrected Blueprint ref. A separate worktree avoids Testchat's current dirty `main` file. |

C1 and C2 are independent and can run at the same time because they are in
different repositories. Neither should adopt the known-red `042a74e` as the
final closure ref.

### Wave D — two product milestones can run in parallel after adoption

| Bucket | Suggested worktree branch | Items | Dependency / evidence reuse |
|---|---|---:|---|
| **D1 — Vortex conflict milestone + live proof** | Vortex `milestone/conflict-card` | 4, 5 | C1. Use the conflict-card milestone as the real multi-task D-168 live-fire run; advance Blueprint mid-run and capture the plane SHA instead of scheduling a second proof run. |
| **D2 — Testchat universal-surface recut** | Testchat `milestone/vortex-recut` | 15 | C2. Keep endpoint cutover out of this worktree so the recut remains independently testable. |

### Wave E — intentionally serialized or decision-gated

- **Item 16 — Testchat endpoint cutover:** follows D2; it is not independent
  of the recut.
- **Item 17 — provisioning/tuning v2 plus vmlx live exercise:** run after D1
  and outside other live-model exercises. A Git worktree does not isolate
  RAM, the Lima VM, runtime processes, or ports.
- **Item 13 — model-specific Git provenance:** create a post-P0 Blueprint
  worktree only if the CEO approves the design direction.
- **Item 18 — OSS adoption #2:** waits for the CEO to choose the subject.
- **Item 19 — `ctx-tune`:** waits for the CEO build/no-build decision.

### Verified as not currently pending

- **Merge `experiment/symlink-control-plane` into `main`:** no such local
  branch currently exists; Vortex is already on `main` at `f7257c7` with the
  adoption history. Retained below only as a historical agent note.
- **UI awaiting initial sign-off:** superseded by the shipped M1 dashboard,
  completed browser/document reconciliation, and CEO live acceptance in item 6.

## P0 — control-plane release blocker

- **Close D-168 immutable-plane rollout before the next milestone** *(filed
  by Codex (GPT-5), 2026-08-22)*. Blueprint `042a74e` fixes the initial
  launch-order and dry-run fallthrough defects, and Vortex now pins that ref,
  but the exact CI command still reports **422 passed / 47 failed**. The
  extracted plan, consult, runtime, coder, B6a, completion, and mypy harnesses
  do not initialize the new `PLANE_DIR` dependency; a few source-shape tests
  still assert pre-D-168 helper paths. Closure requires: restore the complete
  blueprint selftest suite to green; add a whole-entrypoint dry-run test (not
  only an extracted guard test); record the incident and false-green claim in
  the correction log; publish the corrected blueprint ref; adopt that ref here
  through `update-template`; then run a Linux-VM Vortex acceptance proving pin
  authority, immutable helper execution across blueprint movement, same-SHA
  resume, and durable plane-SHA success/measurement evidence.

## P1 — first milestone candidate

- **UI (router phase 2)** — model menu w/ load/unload, RAM meter.
  Concept drafted (`docs/UI-CONCEPT.md`, form factor A recommended:
  server-rendered page on `:9000/`) — awaiting CEO sign-off.
- **D-168 live-fire integration proof** *(filed by ox-alpha, 2026-08-22)*.
  The plane-snapshot mechanism (authority pin, immutable materialization,
  mid-run drift telemetry, adoption stop) is pinned at mechanism level by
  `selftest_plane_snapshot.py` (15 checks) plus a VM dry-launch proof
  (snapshot SHA == declared ref). Still unproven: a real multi-task run
  under live LLMs that crosses a blueprint advancement mid-flight. Rides
  the next milestone automatically — its `[success] spec vN (plane <sha>)`
  subject self-documents the evidence. No separate work item unless the
  subject is missing or mismatched, which would be a defect.

## P2 — prototype hardening (post-milestone-1)

- **Dashboard conflict card — wire to the real 409 source** *(filed by
  Claude Code, 2026-08-22)*. The M1 dashboard's conflict card reads
  `s.conflict` from `GET /api/status`, which never carries it, so the card
  is permanently dormant. Real load refusals arrive as a `409` on
  `POST /api/models/{id}/load` with detail
  `{message, required_gb, eviction_candidates}` (see `src/vortex/app.py`
  load handler). Fix: the load click handler should catch the 409 and drive
  the existing `#conflict` / `#conflictbody` card from that detail; drop the
  dead `s.conflict` read. Small, one-file (`src/vortex/ui.py`) behavioral
  delta — same shape as the v2/v3 field-contract fixes. Eviction stays
  operator-driven (never automatic), per PRD M1 scope. Deferred out of the
  v2 dashboard fix to keep that cycle small; the display + action-feedback
  contract (v2/v3) is shipped and verified.
- **Model-specific Git commit provenance** *(filed by Codex (GPT-5),
  2026-08-22; CEO decision pending)*. Commits currently share the Arc Elixir
  Git/GitHub identity, so old changes can be correlated to sessions only by
  inference, not reliably attributed to the producing LLM. Implement upstream
  in the blueprint and adopt here: the trusted orchestrator—not the model—owns
  commits; model/role/session-specific author identity, Arc as committer, and
  trailers record provider, observed model, session/run/task ids, plane SHA,
  and prompt/reply hashes. A pipeline-owned signature or attestation is the
  strong-evidence layer; an author label alone remains spoofable. Do not use
  `Co-authored-by` as execution provenance.

## P3 — roadmap phases (post-cutover)

- **M1 close-out and status-document reconciliation** *(filed by Codex
  (GPT-5), 2026-08-22)*. Complete the CEO browser eyeball recorded in
  `tasks/CURRENT.md`, then retire stale statements that the UI awaits sign-off,
  milestone launch is memory-blocked, Lima/model wiring is pending, the v1
  legacy-test choice is unresolved, and the UI route/slicing decision remains
  open. Preserve the completed v1/v2/v3 evidence; this is documentation/status
  cleanup, not a new product milestone.
- testchat recut (phase 3) — swap `SCRIPT_MODELS` + per-model routing for
  the universal surface; oracle-heavy; refreeze mode question reopens.
- Cutover (phase 4) — `LLM_ENDPOINT` → `http://127.0.0.1:9000/v1/chat/completions`.
- Provisioning + tuning v2 (phase 5) — `mtplx tune` / `vmlx bench`, winners
  → catalog.
- Adoption run #2: mature OSS subject (CEO-approved profile; see D-1).
- **Merge `experiment/symlink-control-plane` → `main`** *(filed by
  ox-alpha, 2026-08-22; CEO sequencing call)*. The working branch carries
  the entire control-plane experiment history (adoption, freeze v1–v3,
  D-168 adoption, all session commits); `main` is far behind. Big diff,
  zero code risk beyond review bandwidth — the tree is gate-verified on
  every commit. Schedule after the next clean milestone for a tidy
  evidence trail.
- **vmlx runtime live exercise** *(filed by ox-alpha, 2026-08-22)*. The
  vmlx catalog entry has never been driven against real workloads (load
  → ready → proxy → unload), unlike mtplx/ds4 which have live evidence.
  Same shape as the ds4 exercise retired below. Pairs naturally with
  Provisioning + tuning v2 above.
- **testchat plane adoption** *(filed by ox-alpha, 2026-08-22)*. Cross-
  project note filed here for visibility; execution belongs to testchat's
  own repo/backlog. One-command flip (`update-template.sh --stamp` +
  manifest re-pin) brings D-167, the staging-exclusion gate, and D-168
  snapshot execution to testchat. CEO-gated per the vortex precedent.

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
- **Ready-probe fix (D-174)** — done 2026-08-16 (`859bfb2`): anneal-load
  readiness (port ownership + `/v1/models` 200 + real 1-token
  completion); verified live 2026-08-17, pinned by two regression tests.
