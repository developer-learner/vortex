# ERD-DELTA v22 — p0 redrive: truthful readiness, admission accounting, alias remap, spawn cleanup

v22 is a behavioral re-freeze landing the p0-redrive branch: four
correctness fixes to the runtime lifecycle, readiness accounting, and the
inference proxy, each pinned by a new or reconciled frozen test.

1. **Alias remap in the proxy** (`src/vortex/app.py`): the client addresses
   the model by its `public_id`; the runtime knows it by its own
   `upstream_alias`. The proxy now remaps the forwarded body's `model` to
   `upstream_alias or public_id` on both the streaming and non-streaming
   paths.
2. **Truthful readiness without probing on reads** (`src/vortex/lifecycle.py`,
   `src/vortex/manager.py`): structural port ownership is not readiness — an
   identified process can answer `/v1/models` while its inference path still
   503s (the phantom-ready class). The lifecycle now records a per-session
   `_verified` flag set only when an anneal completion actually succeeded
   (adoption probes the inference path before advertising); `manager.py`
   splits the readiness sets: `all_ready()` means identified/consuming, and
   the new `client_ready()` means verified. `/v1/models` advertises only
   `client_ready`; steady-state reads consult the flag and never re-probe.
3. **Admission accounting** (`src/vortex/manager.py`): `eviction_required()`
   counts the identified/consuming set (`all_ready()`), not only verified
   runtimes — a restart-surviving, not-yet-verified runtime still consumes
   RAM and must count toward admission and eviction.
4. **Failed-startup cleanup** (`src/vortex/lifecycle.py`): a spawn whose chat
   never succeeds within the ready timeout (or that exits early) is cleaned
   up — process group and pid terminated, the process entry cleared, the
   sidecar record dropped, the verified flag discarded — so a retry cannot
   adopt the corpse as ready. The process is one Vortex started this session
   (positively ours), so cleanup never touches an unidentified occupant.

## Changed acceptance criteria

None. The PRD AC block (AC-1..AC-6, engine-wrapper discovery and dashboard)
stays immutable; no PRD AC is added, removed, or reworded. These are
correctness fixes to runtime lifecycle, readiness, admission, and proxy
behavior, pinned by the frozen tests below.

## Superseded acceptance criteria

None. One superseded TEST ASSERTION (not an AC): the old
`test_spawn_fails_when_chat_never_succeeds` queried the failed process's
`/mock/received` surface after the load failed. With fix 4 the failed process
is cleaned up at spawn failure, so that query can no longer succeed; the
assertion is removed and the cleanup it would have observed is pinned by the
new `test_failed_spawn_leaves_no_owned_process_or_sidecar` (C1) instead.

## Changed files

- `src/vortex/lifecycle.py` — the `_verified` set and `is_verified()`;
  adoption probes the inference path (`_harmonic_ready`) before advertising
  readiness; `_cleanup_failed_spawn()` terminates the failed process group
  and pid, clears the process entry, drops the sidecar record, and discards
  the verified flag on both failure paths (early exit and anneal timeout).
- `src/vortex/manager.py` — readiness sets split: `all_ready()` is now the
  identified/consuming set; new `client_ready()` is the verified set that
  `/v1/models` advertises; `eviction_required()` accounts the consuming set
  so unverified-but-running runtimes count for admission.
- `src/vortex/app.py` — the proxy remaps the forwarded `model` from
  `public_id` to `upstream_alias or public_id` (streaming and non-streaming);
  `/v1/models` lists `client_ready()` models.
- `tests/test_serve.py` — seven new tests (three alias-remap, R1
  phantom-ready, C1 failed-spawn cleanup, NREG no-probe reads, admission
  accounting) and the reconciled
  `test_spawn_fails_when_chat_never_succeeds` (dead-process query removed).
- `tests/fake_server.py` — the `/mock/received` surface now also echoes
  `models` (the `model` field of every received request) so the alias tests
  can assert what the proxy actually forwarded.

## Test-to-file mapping

* `tests/test_serve.py::test_proxy_non_streaming_remaps_public_id_to_upstream_alias`
    -> `src/vortex/app.py`
* `tests/test_serve.py::test_proxy_streaming_remaps_public_id_to_upstream_alias`
    -> `src/vortex/app.py`
* `tests/test_serve.py::test_proxy_forwards_public_id_when_no_upstream_alias`
    -> `src/vortex/app.py`
* `tests/test_serve.py::test_unhealthy_adoption_never_advertised_ready`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_steady_state_reads_do_not_probe_runtime`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_unverified_running_model_still_counts_for_admission`
    -> `src/vortex/manager.py`
* `tests/test_serve.py::test_failed_spawn_leaves_no_owned_process_or_sidecar`
    -> `src/vortex/lifecycle.py`
* `tests/test_serve.py::test_spawn_fails_when_chat_never_succeeds`
    -> `src/vortex/lifecycle.py`

Carried unchanged: every other frozen node-id keeps its standing pin — the
discovery/app/ui/cli/lifecycle/anneal/memory-figure ids per the v20/v21 delta
snapshots (`ERD-DELTA-v20.md`, `ERD-DELTA-v21.md`) and the standing
`contracts.json` test_mapping.
