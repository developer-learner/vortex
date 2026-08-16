# sw-dev-blueprint — Verification-Layer Review

> **HISTORICAL RECORD — 2026-07-01, kept verbatim.** This is a point-in-time
> adversarial review of the verification-layer thesis. Its claims that hooks
> did not exist / gates were prose-only predate the 2026-07-01 and later hook
> and gate hardening (see the correction log and DECISIONS.md for what
> shipped after this date) — treat findings here as stale until re-verified.

> Scope: adversarial review of the mechanical-verification thesis. Accuracy over valence —
> the goal is the true severity distribution, not a problem list.
> Method: read every governing artifact (BLUEPRINT.md, all four agent prompts, orchestrate.sh,
> phase-gate.sh, ci.yml, sandbox-run.sh/Containerfile, the control-plane manifest, DECISIONS.md,
> PM-ROLE.md) and empirically test the on-host gate, the manifest hashes, and the placeholder grep.
> Date: 2026-07-01

---

## Bottom line

The mechanical layer is **narrower than the thesis claims, and honest about it in the wrong places.**
Two of the gates (INV-2 write-boundary, INV-3 decision-traceability) genuinely work as advertised and
are well-built. But the headline promise — "the only trusted layer is mechanical verification" — is
contradicted by the system's own most candid documents, which state that the *actual* enforcement layer
is a frontier-LLM PM doing manual source review. Several things labeled "invariant" or "gate" are prose,
not mechanism.

Distribution: **2 sound mechanical gates · 4 high-severity gaps where the thesis leaks · 3 medium
implementation defects · 2 minor issues.** Not riddled with problems, but the central claim is oversold.

---

## The thesis, tested directly

The stated premise: agent self-report is unreliable, so the ONLY trusted safety layer is mechanical
gates — grep, CI, git hooks. Two of those three named layers do not hold up:

- **Git hooks: they do not exist.** `.git/hooks/` contains only stock samples; there is no
  `core.hooksPath`, no `.githooks/`, no pre-commit config anywhere. The only grep hit for "pre-commit"
  is an *aspirational* line in DECISIONS.md. Every boundary gate fires **only** when `orchestrate.sh`
  chooses to call `phase-gate.sh`. It is not a commit-time or push-time hook.
- **The docs admit the real enforcer is an agent.** D-20 and `docs/PM-ROLE.md` state plainly that
  Rules 2–7 are advisory and that *"The PM verify-at-source check is therefore the actual enforcement
  layer of this system"* — performed by a frontier LLM the same paragraph concedes *"too is an LLM,"*
  backstopped by the human CEO. That is exactly the "trust the agent to check its own class of work"
  the thesis claims to have eliminated, relocated one level up.

The trustworthy mechanical layer covers a narrow slice: the INV-2 write boundary, the INV-3 decision
grep, the PRD-approval string, and placeholder presence. Everything else is documentation wearing a
gate's vocabulary.

---

## Findings, ranked by severity

### HIGH-1 — Gates fire only on the `orchestrate.sh` path; any other entry bypasses them
`phase-gate.sh` is invoked from exactly one place: `orchestrate.sh:86`. With no git hook, it is trivially
bypassed.
**Failure scenario:** a human (or a confused `@pm`/`@architect` primary agent) opens `opencode`,
switches to `@build`, and edits `tests/` or `docs/` directly — or just runs `git commit` by hand. No gate
runs; INV-2 is never checked. The README actively invites direct sessions ("Start a session, then switch
agents with `@name`"). The write-boundary invariant holds only for the disciplined path — precisely the
"trust intent" the design rejects everywhere else.
**Minimal fix:** ship the gate as a real hook — commit `.githooks/pre-commit` that runs `phase-gate.sh`
against the current phase marker, and set `core.hooksPath=.githooks` in `bootstrap.sh`. Then the boundary
holds regardless of who drives.

### HIGH-2 — INV-1 ("tests derive from spec, not code") is not mechanically enforced at all
INV-1 is presented alongside INV-2/INV-3 as a mechanical invariant. It isn't. The test agent is blocked
only from **writing** `src/` (opencode `edit: {"src/**":"deny"}` + the phase-gate write-diff). Nothing
stops it from **reading** `src/`; `phase-gate.sh` only diffs *changed files*, so reads are invisible.
**Failure scenario:** the local test model — the same weak model the docs say has poor agentic
follow-through — reads `src/main.py`, writes tests asserting what the code already does, and a consistent
bug passes green. The "sole oracle is the frozen PRD" guarantee rests entirely on a prompt sentence
("Do not read src to decide correctness") aimed at the model least likely to obey it.
**Minimal fix:** run the test-authoring phase with `src/` genuinely unavailable — an overlay mount that
hides `src/` bodies, exposing only the frozen `scripts/.approved/ARCHITECTURE.approved.md` plus an
auto-extracted signatures-only stub. If the tester can't read implementations, INV-1 becomes structural.

### HIGH-3 — "All tests pass" is trusted though the tests are authored by the same untrusted model, with no quality/coverage/count check in the loop
The orchestrator's entire success condition (`orchestrate.sh:179–188`): JSON report exists, `total > 0`,
zero failures → write "All tests pass" to CURRENT.md and commit `[success]`.
**Failure scenario:** the test model writes one `assert True` for a 5-clause PRD; build writes a stub; the
run reports GREEN and the feature is declared built. Nothing checks (a) that test count matches EARS
clause count, (b) that tests contain real assertions, or (c) coverage — `--cov-fail-under=80` lives *only*
in CI (`ci.yml:50`), decoupled from the loop and skipped entirely when `requirements.txt` is absent. A
green orchestrator run is *self-consistency between two instances of the same local model*, not
correctness against the spec.
**Minimal fix (concrete new gate):** after tests pass, re-run them against a deliberately-emptied `src/`
(stub every public symbol to `raise NotImplementedError`); any test still passing does not constrain
behavior → fail. Add a clause-count check: count `SHALL` clauses in the frozen PRD, count collected test
node IDs, fail if tests < clauses. Move `--cov-fail-under` into the orchestrator, not just CI.

### HIGH-4 — Fleet drift is undetected and unreconciled by design
The honest answer to "how does it detect drift across 10+ projects": **it doesn't.** `gh repo create
--template` is a one-time copy with no upstream link. Once instantiated, a child is fully detached; a
security fix to `phase-gate.sh` or Rule 8 never propagates. The correction log documents this exact
failure — the Rule 8 fix "lived only in the derived project (spark) until ported back here" by hand. The
control-plane manifest guards *intra-repo* tampering only; it says nothing about template-vs-child
divergence. There is no version stamp, no drift report, no sync path.
**Minimal fix:** stamp each child at bootstrap with the template commit SHA it was born from (committed
`.template-version`), and ship a `check-drift` CI job that diffs the child's control-plane files against
that pinned template ref and reports divergence. Without a birth-SHA you can't even *compute* drift.

---

### MEDIUM-5 — Control-plane integrity check is non-portable (fails on stock macOS) and spoofable
`phase-gate.sh:32` uses `sha256sum`. Verified **not present** on this macOS host (only `shasum` is) — and
SANDBOX-VALIDATION.md names macOS/M5 as the primary platform. On a stock Mac the hash resolves empty,
every file "mismatches," and the gate hard-fails **closed** — safe, but it bricks the pipeline and invites
someone to "fix" it by loosening the check. Separately, the integrity model is self-referential: nothing
signs the manifest, the manifest doesn't list *itself*, `ci.yml`, `opencode.json`, or `Containerfile`, and
`phase-gate.sh` verifies *itself* against the manifest (a modified gate can simply skip the check). Anyone
who can write both a control-plane file and the manifest passes.
**Minimal fix:** use `shasum -a 256` (portable) or detect once; verify the manifest from an out-of-band
trusted copy (the pinned-ref hook in HIGH-1, or a CI recompute against a known-good ref) rather than
letting the file being checked also host the checker.

### MEDIUM-6 — The placeholder "completeness" gate has confirmed blind spots and false-positive pollution
Ran the exact Step 7 grep. It **does not match** the literal `[e.g. FastAPI / Django / Flask]` and
`[e.g. PostgreSQL / SQLite / MongoDB]` stack placeholders that ship unfilled in `CLAUDE.md` — the regex
requires an uppercase or bracketed-caps lead, so every lowercase-led `[e.g. …]` and `[relevant_service]`
slot survives the gate BLUEPRINT.md says *proves* you finished. Meanwhile, run from `.` as written, it
scans `.opencode/node_modules` (present, 104 MB): 20 of 53 hits are dependency-doc noise that would bury
the real signal at bootstrap.
**Minimal fix:** replace the ad-hoc regex with a single sentinel token (e.g. `«FILL»`) in every fill-in
slot and grep for that exact string — zero misses, zero false positives — and add
`--exclude-dir=node_modules`.

### MEDIUM-7 — The atomic-task discipline the handoff depends on is prose, not enforced
Rule 8 and the architect prompt correctly diagnose the local build model (drops half of multi-file tasks,
stalls on ambiguity) and instruct the architect to hand out atomic, one-file briefs. But the orchestrator
doesn't decompose anything — it sends one generic `"Implement src/ per the plan and PRD"`
(`orchestrate.sh:143`) and lets the weak model read the plan doc and self-scope, which is exactly the
agentic follow-through the docs say it lacks.
**Failure scenario:** the architect (or a re-plan) describes a two-file change in prose; build writes file
one, silently treats the task as done; the gate sees only `src/` writes and passes; the missing half
surfaces as a test failure two phases and several iterations later. Nothing enforces "one brief, one file."
**Minimal fix:** have the architect emit a machine-readable task list (one entry per file with signature +
acceptance), and have the orchestrator loop `build` once per task with the gate after each — turning
"atomic tasks" from a request into the loop structure.

---

### LOW-8 — The human-approval freeze is an honor-system string
`orchestrate.sh:55` gates on `grep -qE '^\*\*Status:\*\* *Approved *$' tasks/CURRENT.md`. The one step the
diagram calls "the only human-checked gate" is satisfied by the literal text "Approved" in a file the PM
*agent* can write. A PM agent that writes "Approved" (mistakenly or on instruction) launches the
autonomous loop on an unreviewed spec.
**Minimal fix:** record approval outside any agent's write lane (e.g. a human-signed marker in
`scripts/.approved/` the orchestrator checks), so the freeze is bound to something an agent can't forge.

### LOW-9 — Two enforcement standards for the same question
The orchestrator declares success with no coverage requirement; CI requires 80%. A feature "done" locally
can fail CI on push — and only if `requirements.txt` exists (CI's `if:` guard). Consolidate the standard
into the loop (folds into HIGH-3's fix).

---

## What is genuinely sound (stated plainly, not padding)

- **INV-2 write-boundary gate is correct and real.** The inverted-whitelist logic in `phase-gate.sh`
  checks committed + staged + working + untracked files, fails on anything outside the lane, and was
  validated with *both* a deterministic planted-file test and an agent-driven test (SANDBOX-VALIDATION
  3a/3c). On the orchestrate path, this one does exactly what it claims. Re-ran the manifest hashes: all
  13 entries currently match.
- **INV-3 decision-traceability grep** is simple and does what it says.
- **Freezing the API contract into `scripts/.approved/` (D-08)** is the right structural pattern — the
  tester's oracle sits outside every agent's write lane, so no re-plan architect can overwrite it.
- **Podman sandbox** (`--cap-drop=ALL`, `no-new-privileges`, non-root UID 1000, `slirp4netns`,
  memory/cpu caps) is a reasonable isolation posture, validated with 5 concrete escape proofs.
- **Moving loop control from an LLM prompt into deterministic shell (D-05)** — two-strike signature,
  re-plan cap, MAX_ITERS — is correctly done and is the strongest architectural decision here.
- **The candor in D-20 / PM-ROLE.md** about advisory-vs-mechanical is a real strength; it's why the
  thesis gap is a framing failure rather than a concealed lie.

---

## Map back to the six review questions

1. **Where it still trusts self-report:** HIGH-2 (INV-1 read-side), HIGH-3 (green ≠ correct), LOW-8
   (approval string), and the meta — HIGH-4/thesis: the real enforcer is a frontier agent's manual review.
2. **What grep+CI+hooks structurally can't catch:** test *meaningfulness* and clause coverage (HIGH-3);
   the tester reading `src/` (HIGH-2); anything off the orchestrate path since hooks don't exist (HIGH-1);
   template drift (HIGH-4). Grep catches string presence, never semantic faithfulness.
3. **Architect→executor handoff loss:** HIGH-3 and MEDIUM-7 — the orchestrator hands a single
   un-decomposed "implement the plan" to the model documented to drop multi-file work, with no mechanical
   atomicity check.
4. **Drift at scale:** HIGH-4 — not detected, not reconciled; no birth-SHA, no drift job. The design has
   no fleet story.
5. **Method vs. enforcement:** the thesis-level gap plus MEDIUM-5/6 (gates that don't run on the stated
   platform / miss the placeholders they exist to catch) and LOW-8. The docs are most honest exactly where
   they admit the gates don't reach.
6. **Fixes:** each finding above proposes a new gate or structural change, not more documentation.

---

## Highest-leverage single change

**HIGH-1.** Until the boundary gates run as committed git hooks (or equivalent) independent of
`orchestrate.sh`, every "mechanical" guarantee is conditional on taking the polite path — the one
assumption the whole system was built to stop making.
