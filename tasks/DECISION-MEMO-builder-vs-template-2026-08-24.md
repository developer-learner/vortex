# Decision Memo — Builder vs Template (2026-08-24)

**RESOLVED 2026-08-24 — both: template at seed, builder for life.** The
fork below is preserved as the evidence base; the decision record is
D-170 in the Blueprint's `docs/DECISIONS.md`.

**Decision requested:** where future control-plane effort lives — commit to the
Blueprint as a **builder** (living product; projects are linked children that
track it) or **freeze as template v1.0** (snapshot; copy to seed new projects;
stop evolving centrally).

**Decider:** the CEO. The project-pipeline plan (how many projects come off
the Blueprint, how fast the control plane must evolve) is the deciding input.
This memo supplies the evidence and the cost of each path. It does not decide.

## Premise (corrected)

The control plane (41 scripts, 493-test selftest suite) is:

> **proven live · fixture-teeth by static read (not yet mutation-proven to
> bite) · unmeasured useful in the wild**

Not "bloat is dead." The dead-weight question is dead (0 orphans in the wiring
audit) — but that is a weaker claim than "the machinery is proven," and this
memo does not rest on it.

## Evidence, tiered

Each tier is a different claim with a different instrument. Merging tiers is
how "running = useful" — and its mirror error — both happen.

| Tier | Claim | Status | Instrument |
|------|-------|--------|------------|
| 1 | Wired and executed | **Proven** — 40/41 wired to live paths; suite runs on every push (green this session, on the audit commit itself) | wiring audit + release-gate execution |
| 2a | A fixture test builds a violation and asserts the gate detects it | **38 yes (per static read of test intent) · 3 partial · 2 none** | selftest suite — exists, runs green every push |
| 2b | The fixture test would actually *fail* if the gate were removed/broken (the teeth bite) | **Unproven across the gates** | mutation pass — exists but is tests-only, manual, one-shot; never run across the gates |
| 3 | Catches real-world variants (useful in the wild) | **Unmeasured for all 41** | catch ledger — unbuilt |

**2a detail.** The 3 partials: `check-ac-postconditions.py`,
`check-test-direction.py`, `flake-ledger.py` — wired and running, no dedicated
violating-fixture test found. The 2 nones: `tpm-lint.sh` (retire candidate —
refreeze preflights lint bundles inline) and `em-bench.sh` (manual research
tool, not a gate). The 38 labels are static-read inferences, not per-test
verifications.

**Why 2b is a real gap, not pedantry — the project's own correction log:**

- teardown DRY-RUN banner: asserted-present, so always true (vacuous test)
- S6: proven on synthetic fixtures only
- mutation-pass test: stale bytecode let a mutant survive green

Fixture-green has been *vacuous* here, repeatedly. That history is the single
best evidence that 2a-green ≠ 2b.

**Why 3 is open.** A gate can pass every fixture and still miss the real
variant; no execution history exists to say otherwise. The one real catch on
record (the flap-bug class, 2026-08-18) is genuine evidence the machinery
earns — labeled **n=1**.

## The fork

**Template (freeze as v1.0).** Pay once: close the 2a shortlist (3 fixture
tests), settle `tpm-lint.sh`, backfill the 6 provenance gaps in DECISIONS.md.
Then every new project costs ~nothing.

**Cost of freezing:** strands 2b and 3 *permanently*. You lock in machinery
that is proven to run, fixture-tested by static read, never proven to bite,
never measured in the wild — on a codebase with a documented vacuous-test
history. The unmeasured axes become **accepted risk**, inherited by every
project that copies the template, forever.

**Builder (commit).** Pay ongoing — once, applied to all children:

1. 2a shortlist close (3 fixture tests) — direction-independent, cheap
2. 2b: extend the mutation pass from tests to gates (one-shot sweep first, then standing)
3. 3: catch ledger (standing; real catches over time)
4. tiering + cost accounting (which gates earn their run cost)
5. `tpm-lint.sh` settlement

**Cost of building:** ongoing maintenance of the measurement instruments
themselves; the Blueprint stays a live dependency of every child (already
true — vortex's pre-push hook symlinks into it).

**The hybrid fact.** We are already running the builder: vortex is a linked
child (`link-template.sh` seeded it; pre-push hook symlinks into the
Blueprint; the caps-exhausted fix landed three weeks ago and propagated).
The call is not "start a builder" — it is **keep the thing we are already
running and fund its missing measurement**, or **cut the cord and freeze**.

## Lean

**Builder** — for the measurement reason, not the "machinery is sound" reason:

- 2b and 3 are both unbuilt, and both are builder deliverables. "Only the
  builder path funds the measurement" names **two** concrete instruments, not one.
- Freezing converts two open measurement questions into permanent accepted
  risk, on a codebase with a documented vacuous-test history.
- The n=1 real catch (flap-bug) supports "it earns" but is not the
  load-bearing argument; the load-bearing argument is that the proof is
  unfunded under freeze.

The lean is not the decision. If the pipeline plan is "one more project, then
the control plane is done," template is defensible — with the 2b/3 gaps
explicitly signed as accepted risk.

## Direction-independent (proceeds under either call)

- 2a shortlist: one violating-fixture test each for the 3 partials (the
  pattern already exists in selftest_gates.py)
- `tpm-lint.sh`: retire or wire into the refreeze preflight (operator call)
- 6 provenance backfills in DECISIONS.md (blueprint side)
- silent-halt live-fire (double coder-failure → does escalation get reached)
  — next milestone

## Sources

- `tasks/AUDIT-gates-2026-08-24.md` — pass 1 (wiring: 40 live / 1 doc-only /
  0 orphan) + pass 2 (teeth: 38 / 3 / 2); both committed, CI-green
- correction-log entries: teardown DRY-RUN banner, S6 synthetic-only,
  mutation-pass stale-bytecode
- session record 2026-08-24: flap-bug tri-state fix (`c9b4fb7`), refreeze v12
  (`85f0cbd`), 493-suite green on `65da200`