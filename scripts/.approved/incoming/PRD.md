# PRD — vortex router phase 2 UI (M1: operator dashboard)

## Problem

Vortex's management surface is headless: knowing *what is loaded, how much
RAM is left, and why a load was refused* requires CLI calls. The owner-
operator's recurring question is visual, and the answer should be one
browser tab away.

## Product

A server-rendered dashboard served by the vortex daemon itself at
`http://127.0.0.1:9000/`. One page, no framework, no new dependencies,
no external assets. The page is a thin client over the EXISTING management
API (`/api/status`, `/api/catalog`, `/api/models/{id}/load|unload`,
`/api/operations/{id}`) — it introduces no new endpoints and never invents
states beyond what those return.

## M1 scope (this milestone)

- **Model menu**: every catalog entry with live state (idle/loading/ready/
  unloading), runtime, port, RAM estimate, and one-click load/unload.
- **RAM meter**: used/total from `/api/status`, animated bar with warn
  (>70%) and danger (>85%) zones.
- **Action feedback**: load/unload buttons poll `/api/operations/{id}` and
  render real transition states; buttons disable while busy.
- **Conflict explanation**: when a load returns 409, show the refusal
  message, `required_gb`, and eviction candidates. Eviction is NEVER
  automatic — the card informs, the operator acts.
- **Daemon-down state**: if the API is unreachable, a friendly message
  with the start command — never a blank page or traceback.

## Explicitly out of scope for M1

Chat/inference surface (clients already have that), auth (daemon is
local-only), provisioning/tuning UI, multi-host fleet view, HTMX or any JS
framework, external CSS/JS/font assets.

## Success criteria

The frozen test suite is the binding definition (D-54). Informally: the
CEO opens `http://127.0.0.1:9000/` in a browser and can see machine state
at a glance and load/unload models with one click; conflicts explain
themselves; a stopped daemon explains itself too.
