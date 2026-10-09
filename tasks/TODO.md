# Vortex TODO — current actionable work

> Refreshed 2026-10-08 against Vortex `main` (`a0f30b1`), frozen spec **v43**
> (last `[success]` `d566092`, 2026-09-30), and the canonical register in
> `tasks/BACKLOG.md`. Since the 2026-09-23 refresh: **R1 and T1 are done**
> (v36 T1 admission policy + v37 under `swbp orchestrate`), v38 Restart
> Vortex, v39–v43 Add to Vortex (4 post-`[success]` hand-fixes, `d65e468`).
> No milestone spec is staged; the next milestone needs a feature choice. This is the short execution
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
| T9 | Cut `LLM_ENDPOINT` over to Vortex `:9000` | P2 | M | ad hoc (config + verification) | none |
| T10 | vmlx live exercise (+ provisioning/tuning v2) | P2 | M + operator | ad hoc (exercise); v2 = milestone | ~35 GB free RAM; drive from outside the session |
| T3 | Remove Starlette TestClient deprecation warning | P3 | S/M | milestone (dependency change) | CEO approval for httpx2 |
| T12 | Build `vortex ctx-tune <model>`? | P3 | L if built | decision → milestone | CEO call (recommendation: defer until after T1) |
| H1 | launchd agent so the `:9000` daemon survives reboot | P4 | XS | ad hoc | optional; confirm wanted |

## Details

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

### T12 — decision

- Note at `tasks/T12-ctx-tune-decision.md` (build / no-build / defer).

## Closed since the last refresh

- **R1** first real milestone under `swbp orchestrate` — v37 `[success]`
  `c1e8aba` (2026-09-23); v38 and v43 since.
- **T1** fail-safe admission under uncertain occupancy — v36 (AC-13..AC-16).
- **T7** model-specific Git provenance — Blueprint D-174 commit broker (M1).
- **T11** second OSS adoption subject — rich 15.0.0 (`~/dev/rich-adoption`, D-175).

- **T2** continuous readiness — no-code acceptance (2026-09-01).
- **T4** publish docs — pushed; CI green.
- **T5** D-168 plane live-fire — superseded by R1 (D-186, 2026-09-23).
- **T6** organic escalation-ladder climb — validated via Testchat v115 (2026-09-03).
- **T8** Testchat recut — done, v119 `aa3deea` (2026-09-02).

## Recommended order

1. T9 cutover (ad hoc).
2. T10 when host memory allows.
3. T3 / T12 as their decision gates open.
4. Next feature milestone: none queued — needs a CEO feature choice.
