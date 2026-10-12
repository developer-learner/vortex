# ERD delta — spec v46

Ratify freeze (D-63): the builder edits no source. The six Speed-page files
are frozen as no-edit files and re-accepted through their tests. The behavior
below was authored out of band by the TPM and committed with this freeze; the
frozen tests that pin it are staged here.

## Changed acceptance criteria

AC-49 — the Speed runner load-timeout reconciler. When a model load started
by a Speed run exceeds the runner's wait window but later reaches ready, a
background reconciler waits for the in-flight operation and unloads the model
again, and the model is marked failed with a timeout reason. This closes the
one hole the v45 runner left open: a load that finished after the timeout
would otherwise have left the model loaded. Pinned by
tests/test_speed_runner_reconcile.py, such that a timed-out load never leaves
a model loaded.

AC-50 — the reported memory figure. The RAM figure the dashboard and the
status report show is the macOS working set — active plus wired plus
compressor, the figure Activity Monitor labels as memory used — and when the
memory statistic prints no page size the system shows 0.0 rather than assume
one, such that the meter matches Activity Monitor and never derives a total
from a guessed page size.

AC-51 — plain-GiB synthesis estimate. A synthesized catalog entry estimates
RAM as the model file's plain size in GiB (size in bytes over 1024 cubed,
rounded to 0.1) and is exclusive exactly when that estimate exceeds 40 GiB,
such that the estimate carries the same unit as the catalog and the admission
budget.

AC-52 — flat admission ceiling. The load admission budget is a flat 107 GiB
minus the estimates counted against it, replacing the 80%-of-host-total
guess, such that a load is admitted only when its estimate fits the remaining
ceiling and the budget reads in the same unit as the catalog estimates.

## Superseded acceptance criteria

AC-30 is superseded by AC-51: the model-size-plus-10%-in-decimal-GB estimate
mixed decimal GB with the GiB catalog and admission units. The id is retained
here and in the PRD, marked superseded; the frozen oracle moved to the
plain-GiB values. No other criterion is superseded by this freeze.

## Changed files

This freeze's changed_files is empty: the builder edits nothing. The files
above were committed out of band with this freeze:
src/vortex/speed_runner.py (the reconciler), src/vortex/memory.py (the
working-set figure and the page-size guard), src/vortex/manager.py (the flat
ceiling), src/vortex/catalog_synth.py (the plain-GiB estimate), and
src/modelmux/cli.py (409 busy handling). Staged test updates:
tests/fake_server.py (optional startup delay for the reconciler test),
tests/test_speed_runner_reconcile.py (new), tests/test_catalog_synth.py, and
tests/test_admission_uncertain.py.

## Test-to-file mapping

* `tests/test_speed_runner_reconcile.py::test_late_load_success_is_unloaded_by_reconciler`
  -> `src/vortex/speed_runner.py`
* `tests/test_catalog_synth.py::test_ram_estimate_is_plain_gib_and_sets_exclusive`
  -> `src/vortex/catalog_synth.py`
* `tests/test_admission_uncertain.py::test_scan_unknown_neighbour_counts_and_refuses_the_load`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_unidentified_occupant_counts_and_refuses_the_load`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_uncertain_entry_is_not_an_eviction_candidate`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_scan_unknown_entry_held_ready_is_counted_once`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_refusal_without_candidates_names_the_unidentified_process`
  -> `src/vortex/manager.py`
