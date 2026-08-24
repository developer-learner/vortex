# Gate audit — one-shot report, 2026-08-24

Scope: the 41 control-plane scripts in vortex (the Blueprint control plane as linked into this child).
Method: static reference sweep against live execution paths. A script is:

- **LIVE** — referenced by a live execution path: git hooks, CI workflow, orchestrate.sh, phase-gate.sh, refreeze.sh, or a control-plane selftest (the 493-test pre-push suite).
- **WIRED** — not directly live, but referenced by another script (indirectly reachable).
- **DOC-ONLY** — referenced only in prose docs (AGENTS/CLAUDE/BLUEPRINT/README/QUICKSTART/CONVENTIONS). Candidate for 'exists on paper, never runs'.
- **ORPHAN** — no references at all outside itself. Dead-weight candidate.

Flags: `selftest` = exercised by a control-plane selftest (strongest "it runs" evidence). `prov` = has a birth record in docs/DECISIONS.md (provenance-at-birth; treated as a hypothesis, not a record). `manual` = header says one-shot/operator-invoked (a human-run tool, not a per-run gate).

Honest limit: this proves *wiring*, not *execution history*. 'Last run' per script is not recoverable from static analysis in this pass.

---

## apply-edit-blocks.py — LIVE
- purpose: apply-edit-blocks.py <target-file> <raw-reply-file> — D-59 coder applier.
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/drive-coder.sh B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## bootstrap.sh — LIVE
- purpose: bootstrap.sh — Run once when starting a new project from this template
- live refs: B/.githooks/pre-commit B/.githooks/pre-push B/scripts/orchestrate.sh B/scripts/phase-gate.sh V/scripts/orchestrate.sh V/scripts/phase-gate.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (7 hits)

## check-ac-postconditions.py — LIVE
- purpose: S5 lint: state-changing ACs must carry post-condition clauses.
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## check-drift.sh — LIVE
- purpose: check-drift.sh <template-clone-dir> — fleet drift detection (D-33).
- live refs: B/scripts/phase-gate.sh V/scripts/phase-gate.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md 
- provenance (DECISIONS.md): yes (1 hits)

## check-prd-additive.py — LIVE
- purpose: check-prd-additive.py — PRD additive-only guard (D-136).
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## check-spec-delta.py — LIVE
- purpose: Validate the current-milestone ERD delta before a re-freeze."""
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (4 hits)

## check-swallowed-errors.py — LIVE
- purpose: check-swallowed-errors.py <file> [<file>...] — D-68 swallowed-error gate.
- live refs: B/scripts/orchestrate.sh B/scripts/refreeze.sh V/scripts/orchestrate.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/drive-coder.sh B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (2 hits)

## check-test-direction.py — LIVE
- purpose: check-test-direction.py — S6: reverse-direction test lint.
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## check-test-surface.py — LIVE
- purpose: check-test-surface.py — INV-4: test-visible surface ⊆ ERD-locked surface.
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (6 hits)

## completion-ledger.py — LIVE
- purpose: Persist and safely restore task completions across successful runs.
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_milestone_trim.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## context-budget.py — LIVE
- purpose: Byte budgets and no-expansion checks for model context (D-145).
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/selftest_b4a.py B/scripts/selftest/selftest_context_budgets.py B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_plane_snapshot.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## contracts-delta.py — LIVE
- purpose: contracts-delta.py — milestone-only contracts context (D-120) and the TPM
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/drive-plan-live.sh B/scripts/selftest/selftest_b4a.py B/scripts/selftest/selftest_context_budgets.py B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_milestone_trim.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (6 hits)

## contracts-merge.py — LIVE
- purpose: contracts-merge.py — staged-merge producer for contracts.json (D-136).
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## doc-consistency.sh — LIVE
- purpose: doc-consistency.sh — warning-only scan for retired-decision prose (2026-08-07).
- live refs: B/.githooks/pre-commit 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): NONE

## em-bench.sh — LIVE
- purpose: em-bench.sh — replay archived EM diagnosis calls with variant briefs.
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): NONE
- manual-tool hint: yes

## extract-test-functions.py — LIVE
- purpose: extract-test-functions.py — extract named test functions from a test file.
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/selftest_b6a.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): NONE

## feature-summary.py — LIVE
- purpose: n/a
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (2 hits)

## flake-ledger.py — LIVE
- purpose: Track accepted D-77 flake occurrences across successful spec versions."""
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/drive-drift.sh B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): NONE

## link-template.sh — LIVE
- purpose: link-template.sh — install/update the Blueprint control plane as one linked
- selftest: B/scripts/selftest/selftest_linked_template.py 
- wired via: B/scripts/update-template.sh V/scripts/update-template.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md B/README.md 
- provenance (DECISIONS.md): yes (2 hits)

## llm-call.sh — LIVE
- purpose: llm-call.sh — D-53: the pipeline speaks to models over bare HTTP.
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/drive-coder.sh B/scripts/selftest/drive-consult.sh B/scripts/selftest/drive-plan-live.sh B/scripts/selftest/drive-plan.sh B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (13 hits)

## manifest-drift-guard.sh — LIVE
- purpose: manifest-drift-guard.sh — warning-only drift advisory (2026-08-08).
- live refs: B/.githooks/pre-commit 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): NONE
- manual-tool hint: yes

## metrics-report.py — LIVE
- purpose: n/a
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## mutation-pass.sh — LIVE
- purpose: mutation-pass.sh — D-161 one-shot, report-only oracle-strength measurement.
- selftest: B/scripts/selftest/selftest_mutation_pass.py 
- provenance (DECISIONS.md): yes (1 hits)
- manual-tool hint: yes

## new-project.sh — LIVE
- purpose: new-project.sh is meant to run from INSIDE a fresh clone of this template
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md 
- provenance (DECISIONS.md): yes (9 hits)

## orchestrate.sh — LIVE
- purpose: orchestrate.sh v3 — walks the EM's task DAG from a frozen TPM spec.
- live refs: B/scripts/phase-gate.sh B/scripts/refreeze.sh V/.github/workflows/ci.yml V/scripts/phase-gate.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/drive-ci.sh B/scripts/selftest/drive-coder.sh B/scripts/selftest/drive-consult.sh B/scripts/selftest/drive-drift.sh B/scripts/selftest/drive-plan-live.sh B/scripts/selftest/drive-plan.sh B/scripts/selftest/drive-runtime.sh B/scripts/selftest/drive-verdict.sh B/scripts/selftest/selftest_b4a.py B/scripts/selftest/selftest_b6a.py B/scripts/selftest/selftest_context_budgets.py B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_mypy_cache.py B/scripts/selftest/selftest_plane_snapshot.py B/scripts/selftest/selftest_release_gate.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (48 hits)

## phase-gate.sh — LIVE
- purpose: phase-gate.sh <em|task|manifest> [phase-start-ref] [task-target]
- live refs: B/.githooks/pre-commit B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/drive-coder.sh B/scripts/selftest/drive-consult.sh B/scripts/selftest/drive-plan-live.sh B/scripts/selftest/drive-plan.sh B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_linked_template.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (15 hits)

## refreeze_delta.py — LIVE
- purpose: Compute and write a freeze's DELTA-v{n}.json (D-31 affected-subtree reset).
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_milestone_trim.py 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (2 hits)

## refreeze.sh — LIVE
- purpose: refreeze.sh — the ONLY path by which frozen TPM artifacts change (D-31).
- live refs: B/scripts/orchestrate.sh B/scripts/phase-gate.sh V/.github/workflows/ci.yml V/scripts/orchestrate.sh V/scripts/phase-gate.sh 
- selftest: B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (50 hits)

## regen-manifest.sh — LIVE
- purpose: regen-manifest.sh <manifest-file> — refresh every hash in a manifest,
- selftest: B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_linked_template.py 
- wired via: B/scripts/check-drift.sh B/scripts/link-template.sh B/scripts/manifest-drift-guard.sh B/scripts/update-template.sh V/scripts/check-drift.sh V/scripts/link-template.sh V/scripts/manifest-drift-guard.sh V/scripts/update-template.sh 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## sandbox-run.sh — LIVE
- purpose: sandbox-run.sh — run a command inside a disposable Podman container over the repo.
- live refs: B/scripts/orchestrate.sh B/scripts/refreeze.sh V/scripts/orchestrate.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/drive-runtime.sh B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_mypy_cache.py B/scripts/selftest/selftest_plane_snapshot.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md B/README.md 
- provenance (DECISIONS.md): yes (14 hits)

## spec_artifacts.py — LIVE
- purpose: Shared path policy for TPM shuttle and refreeze staging artifacts."""
- live refs: B/scripts/refreeze.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/selftest_b4a.py B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (2 hits)

## standing-summary.py — LIVE
- purpose: Generate standing rules plus a compact file-interface map (D-116).
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/drive-plan-live.sh B/scripts/selftest/selftest_b4a.py B/scripts/selftest/selftest_gates.py 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## status.sh — LIVE
- purpose: status.sh — read-only report on what pipeline resources are resident (D-97).
- selftest: B/scripts/selftest/selftest_gates.py 
- wired via: B/scripts/teardown.sh V/scripts/teardown.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (5 hits)

## teardown.sh — LIVE
- purpose: teardown.sh — explicit, operator-invoked reclamation of pipeline resources (D-97).
- selftest: B/scripts/selftest/selftest_gates.py 
- wired via: B/scripts/status.sh V/scripts/status.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (4 hits)
- manual-tool hint: yes

## tpm-agent.sh — LIVE
- purpose: tpm-agent.sh — launch the TPM as a scoped repo agent (D-39).
- selftest: B/scripts/selftest/selftest_gates.py 
- wired via: B/scripts/tpm-pack.sh B/scripts/tpm-view.sh V/scripts/tpm-pack.sh V/scripts/tpm-view.sh 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (7 hits)

## tpm-lint.sh — DOC-ONLY
- purpose: tpm-lint.sh — pre-ship mechanical lint for a staged TPM bundle (D-38).
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): NONE

## tpm-pack.sh — LIVE
- purpose: tpm-pack.sh — assemble the TPM chat bundle (D-38).
- selftest: B/scripts/selftest/selftest_b4a.py B/scripts/selftest/selftest_context_budgets.py B/scripts/selftest/selftest_gates.py 
- wired via: B/scripts/contracts-delta.py B/scripts/tpm-agent.sh V/scripts/contracts-delta.py V/scripts/tpm-agent.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (11 hits)

## tpm-unpack.sh — LIVE
- purpose: tpm-unpack.sh — split a TPM chat reply into refreeze staging (D-38).
- selftest: B/scripts/selftest/selftest_gates.py 
- wired via: B/scripts/tpm-agent.sh B/scripts/tpm-pack.sh V/scripts/tpm-agent.sh V/scripts/tpm-pack.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (5 hits)

## tpm-view.sh — LIVE
- purpose: tpm-view.sh — build the materialized TPM view (D-162).
- selftest: B/scripts/selftest/selftest_gates.py 
- wired via: B/scripts/tpm-agent.sh V/scripts/tpm-agent.sh 
- doc refs: B/AGENTS.md B/CLAUDE.md 
- provenance (DECISIONS.md): yes (1 hits)

## update-template.sh — LIVE
- purpose: update-template.sh — pull the template's control plane into this child (D-34).
- live refs: B/scripts/orchestrate.sh V/scripts/orchestrate.sh 
- selftest: B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_linked_template.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/QUICKSTART.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (13 hits)

## validate-plan.py — LIVE
- purpose: validate-plan.py — mechanical gate on the EM's task plan (D-26, D-28).
- live refs: B/scripts/orchestrate.sh B/scripts/phase-gate.sh B/scripts/refreeze.sh V/scripts/orchestrate.sh V/scripts/phase-gate.sh V/scripts/refreeze.sh 
- selftest: B/scripts/selftest/drive-consult.sh B/scripts/selftest/drive-plan-live.sh B/scripts/selftest/drive-plan.sh B/scripts/selftest/selftest_b6b.py B/scripts/selftest/selftest_gates.py B/scripts/selftest/selftest_milestone_trim.py 
- doc refs: B/AGENTS.md B/BLUEPRINT.md B/CLAUDE.md B/README.md V/CLAUDE.md 
- provenance (DECISIONS.md): yes (35 hits)

---

## Summary

- LIVE: 40
- WIRED: 0
- DOC-ONLY: 1
- ORPHAN: 0

### Actionable candidates (DOC-ONLY + ORPHAN)

## tpm-lint.sh — DOC-ONLY
- purpose: tpm-lint.sh — pre-ship mechanical lint for a staged TPM bundle (D-38).
- provenance (DECISIONS.md): NONE
