# ERD delta — spec v47

Ratify restatement (D-63): the builder edits nothing. This freeze restates the
active milestone inventory so that every frozen test the milestone owns is mapped
inside a closing verdict: the six speed files, plus the two files v46 built outside
its inventory (`src/vortex/catalog_synth.py`, `src/vortex/manager.py`, both already
committed at 289e3c6), plus the two files v44 tuned tests for outside its inventory
(`src/vortex/discovery.py`, `src/vortex/labels.py`). All ten are no-edit files.
The freeze also states the one entry point the v46 code introduced with no spec
declaration: `src.vortex.manager:ADMISSION_BUDGET_GIB`.

## Changed acceptance criteria

AC-51 (plain-GiB synthesis estimate) and AC-52 (flat 107 GiB admission ceiling) are
accepted inside this milestone: their file is an inventory member and their frozen
tests are mapped into the plan, such that the verdict runs the oracle for both.
The v44 discovery-unindexed acceptance is likewise accepted: its frozen tests are
mapped to the files that implement it.

## Superseded acceptance criteria

None. AC-30 was superseded by AC-51 at v46 and stays recorded there.

## Changed files

No source file changes: every inventory file is a no-edit file and the coder is
never called. This freeze restates the milestone inventory and declares one new
entry point, src.vortex.manager:ADMISSION_BUDGET_GIB, implemented by
src/vortex/manager.py.

## Coder briefs (verbatim)

### T1 — src/vortex/speedtest.py (speedtest)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T2 — src/vortex/speed_runner.py (speed_runner)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T3 — src/vortex/speed_routes.py (speed_routes)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T4 — src/vortex/speed_ui.py (speed_ui)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T5 — src/vortex/app.py (app)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T6 — src/vortex/ui.py (ui)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T7 — src/vortex/catalog_synth.py (catalog_synth)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T8 — src/vortex/manager.py (manager)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T9 — src/vortex/discovery.py (discovery)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

### T10 — src/vortex/labels.py (labels)

No change. This file is already built and committed; do not edit it. Its
acceptance is its frozen tests, which must pass unchanged.

## Dependency order

The DAG restates the v45 order unchanged and adds the restated files where the
application imports them:

- `src/vortex/speed_runner.py` depends on `src/vortex/speedtest.py`
- `src/vortex/speed_routes.py` depends on `src/vortex/speed_runner.py`
- `src/vortex/speed_routes.py` depends on `src/vortex/speed_ui.py`
- `src/vortex/app.py` depends on `src/vortex/speed_routes.py`
- `src/vortex/app.py` depends on `src/vortex/ui.py`
- `src/vortex/app.py` depends on `src/vortex/catalog_synth.py`
- `src/vortex/app.py` depends on `src/vortex/manager.py`
- `src/vortex/app.py` depends on `src/vortex/discovery.py`
- `src/vortex/app.py` depends on `src/vortex/labels.py`

## Test-to-file mapping

* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts[verified0]` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_identified_runtime_still_counts[verified1]` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_refusal_without_candidates_names_the_unidentified_process` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_scan_unknown_entry_held_ready_is_counted_once` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_scan_unknown_neighbour_counts_and_refuses_the_load` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_target_is_never_counted_against_itself` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_uncertain_entry_is_not_an_eviction_candidate` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_unidentified_occupant_counts_and_refuses_the_load` -> `src/vortex/manager.py`
* `tests/test_admission_uncertain.py::test_unloaded_entries_do_not_count` -> `src/vortex/manager.py`
* `tests/test_catalog_synth.py::test_a_model_already_in_the_catalog_is_refused` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_gguf_model_becomes_a_llama_server_entry` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_lowest_free_port_skips_ports_the_catalog_uses` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_mlx_model_becomes_an_mlx_serve_entry` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_no_free_port_is_refused` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_port_range_and_binaries_are_the_ceo_policy` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_public_id_is_sanitized_from_the_key` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_ram_estimate_is_plain_gib_and_sets_exclusive` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason[overrides0-path]` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason[overrides1-format]` -> `src/vortex/catalog_synth.py`
* `tests/test_catalog_synth.py::test_unsynthesizable_models_raise_with_a_reason[overrides2-architecture]` -> `src/vortex/catalog_synth.py`
* `tests/test_discovery_unindexed.py::test_discover_models_uses_row_path_when_not_in_lms_listing` -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_disk_rows_dropped_when_lm_studio_reports_the_folder` -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_disk_rows_find_folders_lm_studio_skips` -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_publisher_for_paths_and_aliases` -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_quant_label_affine_mix_unchanged` -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_quant_label_mxfp4_with_affine_overrides_is_mixed` -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_quant_label_names_non_affine_base_format` -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_unindexed_rows_skip_known_and_resolve_path` -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_unindexed_rows_tolerate_bad_body` -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_unindexed_rows_unknown_publisher_dir_has_no_path` -> `src/vortex/discovery.py`
* `tests/test_speed_api.py::test_build_app_keeps_its_existing_routes` -> `src/vortex/app.py`
* `tests/test_speed_api.py::test_build_app_wires_the_speed_routes_and_results_path` -> `src/vortex/app.py`
* `tests/test_speed_api.py::test_loads_unloads_and_new_runs_are_refused_while_a_run_is_in_progress` -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_list_has_every_catalog_model_in_order` -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_page_is_served` -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_run_rejects_bad_selections` -> `src/vortex/speed_routes.py`
* `tests/test_speed_api.py::test_speed_run_tests_a_model_and_reports_its_result` -> `src/vortex/speed_routes.py`
* `tests/test_speed_runner.py::test_a_failed_model_does_not_stop_the_run` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_a_loaded_model_whose_test_fails_is_unloaded_again` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_a_second_start_while_running_is_refused` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_model_that_will_not_fit_is_skipped_without_loading` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_serving_model_is_tested_and_left_loaded` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_start_rejects_bad_selections` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner.py::test_unloaded_model_is_loaded_tested_and_unloaded_again` -> `src/vortex/speed_runner.py`
* `tests/test_speed_runner_reconcile.py::test_late_load_success_is_unloaded_by_reconciler` -> `src/vortex/speed_runner.py`
* `tests/test_speed_ui.py::test_dashboard_header_links_to_the_speed_page` -> `src/vortex/ui.py`
* `tests/test_speed_ui.py::test_failures_are_visible` -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_adds_no_external_urls` -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_has_one_test_button_and_a_capped_checklist` -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_polls_and_starts_runs_through_the_api` -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_page_reads_only_fields_the_api_returns` -> `src/vortex/app.py`
* `tests/test_speed_ui.py::test_page_shows_status_banner_picks_and_warning` -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_speed_page_links_back_to_the_dashboard` -> `src/vortex/speed_ui.py`
* `tests/test_speed_ui.py::test_untested_values_show_a_dash` -> `src/vortex/speed_ui.py`
* `tests/test_speedtest.py::test_load_results_is_empty_for_a_missing_or_unreadable_file` -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_fails_when_nothing_is_listening` -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_fails_when_the_model_answers_an_error` -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_fails_when_the_reply_has_no_token_count` -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_returns_the_three_speeds_from_real_replies` -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_measure_sends_one_first_word_one_full_then_concurrent_requests` -> `src/vortex/speedtest.py`
* `tests/test_speedtest.py::test_save_result_stamps_and_keeps_the_latest_per_model` -> `src/vortex/speedtest.py`
