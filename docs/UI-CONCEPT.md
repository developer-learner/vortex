# UI-CONCEPT.md — Router Phase 2 UI (model menu + RAM meter)

> Concept, not commitment. CEO-gated scope: read-only dashboard, load/unload
> actions, RAM meter. Everything here must be implementable against the
> existing :9000 API surface with zero new runtime dependencies.
>
> **STATUS: SIGNED OFF by the CEO 2026-08-21** (form factor A; look-and-feel
> proven by the interactive preview in `examples/ui-demo/`, which adopts the
> original Aug-17 preview's visual design). First-milestone candidate.

## Problem

The universal surface works headlessly (`vortex status`, `vortex models`,
`vortex load/unload`). The owner-operator's recurring question is visual:
*"what is loaded, how much RAM is left, and why can't I load that one?"*
Today that answer is a CLI call; the UI exists so the machine's model state
is visible at a glance and acts are one click away.

## Scope (phase 2)

- Model menu: every catalog entry, live state, one-click load/unload
- RAM meter: used/total from `/api/status`, per-model estimate from the catalog
- Conflict explanation: when a load returns 409, show `required_gb` vs
  available headroom and the eviction candidates instead of a bare error

Out of scope (v3+): provisioning/tuning UI, multi-host fleet, auth (the
daemon is local-only), model chat surface (clients already have that).

## Data contract (already exists — no new endpoints)

| Need | Source |
|------|--------|
| RAM used/total, loaded models | `GET /api/status` |
| Catalog entries + state + port + ram_estimate | `GET /api/catalog` |
| Load/unload | `POST /api/models/{id}/load` / `unload` (409 = conflict) |
| Progress | `GET /api/operations/{id}` (loading/unloading → ready/failed) |

State model: `idle → loading → ready`, `ready → unloading → idle`, plus
`conflict` on 409. The UI renders exactly these; it never invents states.

## Form factor decision (pick one)

- **A — server-rendered page from the daemon** (FastAPI mounts a static
  HTML+HTMX page at `:9000/`). Zero new deps, same process, same port,
  poll `/api/status` every 2-3s. Best fit for a single human operator.
- **B — standalone tiny static page** (separate port, reads the same API).
  Decouples UI from daemon lifecycle; adds a process to manage.
- **C — TUI** (`vortex ui` curses panel). No browser needed; more work than
  the problem justifies at this stage.

Recommendation: **A** — one process, one port, the page is ~100 lines of
HTML+JS, and the daemon already owns the lifecycle.

## Screen layout (A)

```
┌─ vortex ────────────────────────────────────────── RAM 108.5/128.0 GB ─┐
│                                                                         │
│  ● deepseek-v4-flash-0731          ds4      :8005   ~90.0 GB   [load]  │
│  ● Flash_IQ3XXS                    llama    :8102   ~90.0 GB   [unload]│
│  ○ qwen3.8-27b-8bit                dspark   :8103   ~30.0 GB   [load]  │
│  ○ mtplx-qwen38-27b-optimized-…    mtplx    :8001   ~30.4 GB   [load]  │
│  ○ vmlx-dsv4-configi-mlx           vmlx     :8104   ~100.8 GB  [load]  │
│                                                                         │
│  ┌ load qwen3.8-27b-8bit ────────────────────────────────────────────┐ │
│  │ needs ~30.0 GB — headroom ~19.5 GB                                │ │
│  │ conflict: no slot. candidate evictions: Flash_IQ3XXS (~90 GB)     │ │
│  │                                                       [evict+load] │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

Rules baked into the design:
- Load button disabled while state is loading/unloading (poll the operation)
- Conflict view is *informative*, never destructive: eviction requires a
  click on a named candidate, mirroring the CLI's 409 behavior
- RAM meter animates from `/api/status` polls; per-model estimates come from
  the catalog (estimates are estimates — the meter is the truth)
- Daemon-down page state mirrors the CLI fix (`2cf8484`): friendly message +
  the start command, never a traceback

## Deliverables

1. ~~Concept sign-off (this doc) — CEO~~ SIGNED OFF 2026-08-21
   (form factor A, `984a0ee`); shipped by M1 (`[success] spec v1..v3`,
   2026-08-22).
2. Implementation: one HTML template + one static route + polling JS; the
   daemon's existing test surface covers the API side (no new TPM scope:
   UI is presentation over a frozen-ish surface, no new acceptance)

## Open questions

- ~~Serve at `:9000/` root, or `:9000/ui` (keep `/api` namespace clean)?~~
  SETTLED: served at `:9000/` root (frozen route tests pin it,
  `tests/test_ui_route.py`).
- ~~Do we want the RAM meter alone first (dashboard-only), with
  load/unload in a second slice?~~ SETTLED: shipped in one milestone
  (menu + RAM meter + conflict card together, specs v1–v3).