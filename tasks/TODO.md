# Vortex TODO — current actionable work

> Refreshed 2026-09-23 against Vortex `main` (`2f46a09`), frozen spec **v35**,
> and the canonical register in `tasks/BACKLOG.md`. This is the short execution
> list; `BACKLOG.md` keeps the detailed history and original item numbers.
>
> Baseline: product suite 144 tests (coverage ~91%); GitHub CI and swbp-guard
> green on `2f46a09`. Since 2026-09-23 Vortex is a **builder-targeted app**
> (D-186): no control-plane files; every pipeline step runs as
> `~/dev/sw-dev-blueprint/scripts/swbp <cmd> --app ~/dev/vortex`, pinned by
> `.swbp`. Refreezes and builds run in the Lima `dev-vm` (D-152).
>
> Shipped since the v26 list: v27–v29 Stop Vortex, v30 anneal-probe model id,
> v31 RAM display parity, dashboard endpoint column, `nemotron` catalog entry,
> Splash/mtplx catalog entries, v32–v35 discovered-models, D-186 migration.

## Legend

- **Criticality:** P0 blocks the pipeline/release path · P1 safety ·
  P2 roadmap value · P3 maintenance/optional · P4 housekeeping
- **Cost:** XS < 1h · S ≈ half day · M ≈ 1–2 days · L multi-day
- **Kind:** **milestone** = frozen spec → `swbp refreeze` → `swbp orchestrate`;
  **ad hoc** = direct change/operation, no refreeze;
  **decision** = CEO/TPM call first, then becomes one of the above

## Pending — ordered by criticality

| # | Item | Crit | Cost | Kind | Blocker |
|---|------|------|------|------|---------|
| R1 | First real milestone under `swbp orchestrate` | P0 | M | milestone | a spec to run (T1 is the natural candidate) |
| T1 | Fail-safe admission under uncertain occupancy | P1 | M/L | decision → milestone | CEO/TPM policy choice |
| T9 | Cut `LLM_ENDPOINT` over to Vortex `:9000` | P2 | M | ad hoc (config + verification) | none |
| T10 | vmlx live exercise (+ provisioning/tuning v2) | P2 | M + operator | ad hoc (exercise); v2 = milestone | ~35 GB free RAM; drive from outside the session |
| T3 | Remove Starlette TestClient deprecation warning | P3 | S/M | milestone (dependency change) | CEO approval for httpx2 |
| T12 | Build `vortex ctx-tune <model>`? | P3 | L if built | decision → milestone | CEO call (recommendation: defer until after T1) |
| T7 | Model-specific Git provenance | P3 | L if built | decision → Blueprint milestone | CEO build/no-build |
| T11 | Mature OSS adoption subject #2 | P3 | L | decision → Blueprint milestone | CEO picks subject |
| H1 | launchd agent so the `:9000` daemon survives reboot | P4 | XS | ad hoc | optional; confirm wanted |

## Details

### R1 — First real milestone under `swbp orchestrate` (D-186 live-fire)

- **Replaces:** T5 / backlog #4 (D-168 immutable-plane live-fire). D-186
  removed the in-app control plane, so the "unchanged plane SHA across a mid-run
  Blueprint advance" proof no longer applies; the builder pin (`.swbp ref=`)
  is its successor.
- **Why P0:** `swbp orchestrate` has never run end-to-end. Blueprint stage F
  (delete the sync layer) is gated on every app completing a green real
  milestone under swbp.
- **Done when:** one real multi-task milestone runs via
  `swbp orchestrate --app ~/dev/vortex` in the dev VM, ends `[success]`,
  CI + swbp-guard green on push.

### T1 — Fail-safe admission under uncertain occupancy

- **Status:** decision note at `tasks/T1-admission-decision.md`
  (recommendation: conservatively count the catalog RAM estimate for uncertain
  non-target entries). Awaiting the policy choice.
- **Risk:** a non-target entry with `SCAN_UNKNOWN` and no prior status, or an
  unidentified occupant (missing/invalid sidecar), is excluded from
  `Manager.all_ready()`, so admission can undercount RAM.
- **Done when:** policy recorded; blind tests discriminate the uncertain cases
  without regressing identified-unverified; lands via refreeze; gates green.
  Running it as R1 closes both.

### T9 — Cut `LLM_ENDPOINT` over to Vortex

- **State:** T8 (Testchat recut) done 2026-09-02 (v119). Testchat still points
  at LM Studio (`.env.example`: `localhost:1234`).
- **Done when:** clients use `http://127.0.0.1:9000/v1/chat/completions`, with
  rollback and end-to-end streaming/tool behavior verified.

### T10 — vmlx live exercise / provisioning v2

- **State:** load reaches the memory gate correctly (409, `required_gb: 100.8`)
  but the only eviction candidate is the model serving the working session.
- **Done when:** a real vmlx load → ready → proxy → unload cycle succeeds and
  the evidence is recorded.

### T3 — TestClient deprecation warning

- `StarletteDeprecationWarning` (httpx → httpx2) from `fastapi/testclient.py`.
  Fix is a dependency migration touching `requirements.txt`/`pyproject.toml`
  and tests → maintenance milestone.

### T12, T7, T11 — decisions

- **T12:** note at `tasks/T12-ctx-tune-decision.md` (build / no-build / defer).
- **T7:** if approved, a trusted commit broker with author/committer separation,
  provenance trailers, prompt/reply hashes, attestation. (Distinct from the
  D-184 supply-chain provenance already landed.)
- **T11:** choose the second mature OSS brownfield subject.

## Closed since the last refresh

- **T2** continuous readiness — no-code acceptance (2026-09-01).
- **T4** publish docs — pushed; CI green.
- **T5** D-168 plane live-fire — superseded by R1 (D-186, 2026-09-23).
- **T6** organic escalation-ladder climb — validated via Testchat v115 (2026-09-03).
- **T8** Testchat recut — done, v119 `aa3deea` (2026-09-02).

## Recommended order

1. CEO picks the T1 policy → author the T1 freeze → run it as **R1**.
2. T9 cutover (ad hoc) once R1 is green.
3. T10 when host memory allows.
4. T3 / T12 / T7 / T11 as their decision gates open.
