# ERD-DELTA v30 — anneal probe addresses the runtime by its real model id

Two corrections to the D-174 anneal's model addressing, both CEO-ordered
direct with refreeze pairing (D-175 routing; the v13 pairing precedent):

1. **`_anneal_probe` sends the model the runtime actually serves.** The
   probe posted `"model": "__ready_probe__"` — a placeholder. Runtimes that
   validate the model field reject it, so an otherwise-loaded model failed
   its readiness cycle on the probe, not on inference. The probe now takes
   the model id, and `_harmonic_ready` hands it the same name the proxy
   forwards (`entry.upstream_alias or entry.public_id`, the `app.py`
   remap) — the anneal must succeed with exactly what the first real
   request will send.

2. **Catalog aliases are runtime model ids, not prose.** Two entries
   carried human-readable labels ("Qwen3.8-27B-4bit + DFlash2 draft
   (oMLX)") in `upstream_alias` — the field the proxy remaps to before
   forwarding. The proxy would have forwarded prose the runtime cannot
   resolve. Both now carry the served id.

Also: `READY_TIMEOUT_SECONDS` 300 → 600 — a 27B 4-bit/8-bit load plus
anneal exceeds five minutes on the current host; the old bound was
measured short, not derived.

## Changed acceptance criteria

None. No AC ids are defined (the frozen suite is the binding definition,
D-54). All three changes are corrective to the existing "ready" scope.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/lifecycle.py` — EDIT. `_anneal_probe(chat_endpoint, model_id)`
  posts the given model id instead of the `__ready_probe__` placeholder;
  `_harmonic_ready` passes `entry.upstream_alias or entry.public_id`;
  `READY_TIMEOUT_SECONDS` 300 → 600.
- `config/catalog.json` — EDIT. Two `upstream_alias` values corrected from
  prose labels to the served model ids.

## Test-to-file mapping

The four carried anneal tests are re-pinned to the new signature; two new
tests pin the corrected addressing:

* `tests/test_anneal_retry.py::test_anneal_retries_a_transport_blip_and_succeeds`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_gives_up_after_bounded_attempts`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_does_not_retry_a_loading_503`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_still_rejects_a_completion_without_choices`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_anneal_probe_sends_the_real_model_id`
    -> `src/vortex/lifecycle.py`
* `tests/test_anneal_retry.py::test_harmonic_ready_probes_with_alias_then_public_id`
    -> `src/vortex/lifecycle.py`

## Coder briefs (verbatim)

None — direct route (D-175): the implementation is already landed in the
working tree; this freeze re-freezes the test suite to the corrected
behavior. Pairs with the fix commit that follows.
