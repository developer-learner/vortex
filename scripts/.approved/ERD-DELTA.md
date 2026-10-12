# ERD delta — spec v48

Test-only correction. No source file changes and no new acceptance criteria: the
frozen test `tests/test_serve.py::test_unverified_running_model_still_counts_for_admission`
sized both catalog estimates as half of the host's physical RAM, which was the
right way to over-subscribe the budget when the budget was a percentage of host
total (AC-30, superseded at v46). Under AC-52 the budget is a flat 107 GiB, so a
fraction-of-host-total fixture only over-subscribes it on a machine whose total
exceeds that ceiling: the test passed on the 128 GB deployment host and failed in
the 8 GiB sandbox, where the same two estimates sit far below the ceiling and the
load is correctly admitted. The estimates are now absolute GiB that straddle the
flat ceiling, so the refusal under test is about admission accounting rather than
about the size of the machine the suite happens to run on.

## Changed acceptance criteria

None. AC-52 (flat 107 GiB admission budget) is unchanged and is the criterion the
corrected fixture now exercises on every host, such that a load is admitted only
when its estimate fits the remaining ceiling.

## Superseded acceptance criteria

None. AC-30 was superseded by AC-51 at v46 and stays recorded there; this freeze
removes the last trace of its percentage-of-host-total arithmetic from the frozen
suite, which is a consequence of that supersession rather than a new one.

## Changed files

No source file changes: `src/vortex/manager.py` is a no-edit file and the coder is
never called. Only the frozen test file named above changes, and it changes to
match the acceptance criterion already frozen at v46.

## Test-to-file mapping

* `tests/test_serve.py::test_unverified_running_model_still_counts_for_admission`
    -> `src/vortex/manager.py`
