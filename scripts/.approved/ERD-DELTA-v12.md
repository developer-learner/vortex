# ERD-DELTA v12 — coverage + behavior pin for the modelmux CLI

This freeze adds no behavior. It pins the observable contract of the `modelmux`
CLI (`src/modelmux/cli.py`), which shipped with the prototype but carried no
frozen tests (0% coverage — the anchor keeping project coverage under the CI
floor). The tests exercise every command against a monkeypatched
`httpx.request`, so no network or live daemon is required. No API shape,
dependency, contract entry, or src file is added or changed.

## Changed acceptance criteria

None. This freeze introduces regression/coverage tests only; the CLI behavior
they pin is already shipped on `main`.

## Superseded acceptance criteria

None.

## Changed files

None. No `src/` file changes — the tests pin behavior already present in
`src/modelmux/cli.py`. There is no coder task and no task DAG: the staged
tests pass against the current tree.

## Test-to-file mapping

* `tests/test_cli.py::test_main_returns_3_when_daemon_unreachable`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_status_no_models`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_status_with_loaded_models`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_models_table_marks_and_sort`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_load_conflict_returns_2`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_load_success_polls_to_ready`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_load_failure_returns_1`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_unload_success`
  -> `src/modelmux/cli.py`
* `tests/test_cli.py::test_unload_failure_returns_1`
  -> `src/modelmux/cli.py`
