# ERD-DELTA v37 — close out the v30–v35 discovery range as acceptance-only (T1 continues)

Freeze context: v36 (T1, fail-safe admission) was frozen as a one-file
milestone, but vortex's last recorded `[success]` is v29. The v30–v35 work
(memory figure, LM Studio discovery, discovered-models UI) landed directly at
`0da729b` and is green, yet it was never closed by an orchestrate run, so the
active milestone range spans v30–v36. The first `swbp orchestrate` run of v36
therefore asked the EM to plan all of it; four EM emissions failed the plan
gate (duplicate `discovery.py` tasks, a `lifecycle.py` task outside the
inventory, unchanged contracts claimed).

This freeze makes that range explicit: the four v30–v35 files are declared
acceptance-only (`no_edit_files` — the coder is never invoked for them, their
mapped tests still run), `src/vortex/manager.py` remains T1's one changed
file, and every in-scope test gets an owning-file pin so the plan is
synthesized mechanically with no EM call. No test, acceptance criterion or
contract entry changes.

## Changed acceptance criteria

None. AC-12 … AC-17 (v36) and the v30–v35 criteria stand unchanged.

## Superseded acceptance criteria

None.

## Changed files

- `src/vortex/manager.py` (UPDATED — T1, v36 brief stands unchanged).
- `src/vortex/memory.py`, `src/vortex/discovery.py`, `src/vortex/app.py`,
  `src/vortex/ui.py` (no edit — acceptance-only): the v30–v35 behavior is in
  place at `0da729b`; their mapped tests run to close the range.

## Coder briefs (verbatim)

No new briefs. The v36 brief for `src/vortex/manager.py` stands. The four
acceptance-only files keep their v34 briefs, which the coder never receives
(`no_edit_files`).

## Task DAG

`src/vortex/app.py` depends on `src/vortex/memory.py`
`src/vortex/app.py` depends on `src/vortex/discovery.py`
`src/vortex/ui.py` depends on `src/vortex/app.py`

`src/vortex/manager.py` is independent.

## Test-to-file mapping

The `tests/test_anneal_retry.py` pins below replace their earlier
`src/vortex/lifecycle.py` pins: `lifecycle.py` is not in this milestone's
inventory, and those tests run with the full app.

* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts[verified0]`
  -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts[verified1]`
  -> `src/vortex/manager.py`
* `tests/test_discovery.py::test_discovery_module_is_stdlib_only`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_failed_version_probe_reports_empty`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_finds_an_installed_binary_on_path`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_in_catalog_matches_absolute_launch_path_by_basename`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_in_catalog_reflects_catalog_entries`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_mlx_lm_resolves_only_its_console_script_names`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_only_probe_subprocess_is_the_version_check`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_port_check_reports_open_and_closed`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_registry_covers_the_named_wrappers`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_registry_entries_are_sane_and_ordered`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_shared_default_ports_report_the_port_not_the_process`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_unresolved_wrappers_report_not_installed`
  -> `src/vortex/discovery.py`
* `tests/test_discovery.py::test_version_probe_records_first_stdout_line`
  -> `src/vortex/discovery.py`
* `tests/test_ui_api_contract.py::test_catalog_response_is_enveloped`
  -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_only_reads_status_fields_the_api_returns`
  -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_operation_completion_uses_real_terminal_states`
  -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_uses_the_api_loaded_state_token`
  -> `src/vortex/ui.py`
* `tests/test_ui_api_contract.py::test_ui_uses_the_operation_field_the_api_returns`
  -> `src/vortex/ui.py`
* `tests/test_anneal_retry.py::test_anneal_does_not_retry_a_loading_503`
  -> `src/vortex/app.py`
* `tests/test_anneal_retry.py::test_anneal_gives_up_after_bounded_attempts`
  -> `src/vortex/app.py`
* `tests/test_anneal_retry.py::test_anneal_probe_sends_the_real_model_id`
  -> `src/vortex/app.py`
* `tests/test_anneal_retry.py::test_anneal_retries_a_transport_blip_and_succeeds`
  -> `src/vortex/app.py`
* `tests/test_anneal_retry.py::test_anneal_still_rejects_a_completion_without_choices`
  -> `src/vortex/app.py`
* `tests/test_anneal_retry.py::test_harmonic_ready_probes_with_alias_then_public_id`
  -> `src/vortex/app.py`
