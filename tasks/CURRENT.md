# CURRENT.md — session notes

## State

- **2026-08-15 — Brownfield adoption landed.** Control plane installed
  verbatim from blueprint @`8f9ce08` (66 template-owned files hash-verified,
  birth ref stamped, `.manifest-project` regenerated, gate hook armed).
  Legacy prototype pinned at `b76b5ea`; its 16 tests snapshotted
  (`scripts/.approved/legacy-pin.json`, NOT an oracle — D-1). Ledger D-172..D-174.
  Testchat ruled hands-off by the CEO (never an experimentation subject).
- **Pre-spec tunnel** (D-173): plane is gate-clean until the first freeze
  creates `scripts/.approved/VERSION`.

## Halt notes

- **HALT — first milestone launch is CEO-gated (D-139).** The ready-probe
  fix (`503 Loading model` class) is the first milestone candidate. Before
  any TPM round-trip or `orchestrate.sh` run: name the TPM seat for this
  session. Never assume the seat is "someone else."
- Orchestrate pre-flight requires: Lima `dev-vm` running, LM Studio reachable
  with mapped non-thinking models (`~/.config/sw-dev-blueprint/models.env`),
  working tree clean.

## Open questions

- Refreeze-mode question (D-165): at the first freeze, are the 16 legacy
  tests carried into the frozen suite or retired? (Milestone 1 decides.)
- OSS brownfield subject for adoption run #2 — candidate search parked
  (D-1 "do not suggest": only after vortex mechanics are proven).

## Next actions

1. CEO names TPM seat → author first spec (ready-probe fix) → freeze →
   orchestrate
2. Verify installed plane's selftests pass on this machine (adoption check)
3. Stand up Lima + models.env when the first milestone launches