# ERD-DELTA v44 — pin shipped discovery fallbacks, menu publisher, MXFP4 quant label

Regression pin for behavior already shipped in the non-frozen commit `52f4f65`
("feat(discovery): surface models LM Studio's index misses; show publisher").
Scope is tests only: `src/` behavior, routes, and `contracts.json` are
unchanged. The new tests pass on the current tree (expected for a regression
pin; the D-75 "tests ALREADY PASS" warning is anticipated).

## Changed acceptance criteria

None new in the PRD. The pinned behavior refines existing criteria:

- **AC-9 / AC-25 (discovery + path)**: besides LM Studio `/api/v1/models`,
  the default library fetch also reads `/api/v0/models` and appends rows
  whose id the v1 library lacks (a model LM Studio holds but has not put in its
  library listing). Their path resolves to `<models_root>/<publisher>/<dir>`
  (dir name starting with the id, else the publisher's only dir; else no
  path). It also scans `<models_root>/<publisher>/<model>` on disk for model
  folders (GGUF file, or `config.json` + safetensors); `discover_models` drops
  any disk row whose folder LM Studio already reported and labels the rest
  `source: "disk"`. A GGUF disk row's path is its first `.gguf` file.
- **AC-36 (dashboard menu)**: `/api/catalog` entries carry `publisher` — the
  entry's explicit `publisher` field, else derived by `labels.publisher_for`
  from the `<publisher>` dir under the LM Studio models root, an `org/name`
  launch arg or alias, or an omlx `org--name` alias; else null. The menu shows
  it in a Publisher column.
- **Quant label (labels.describe)**: a non-affine base quantization mode is
  named in upper case (`MXFP4`), with ` mixed` when per-layer overrides
  exist; affine mixes keep the `lo–hi mixed` label.

## Superseded acceptance criteria

None. No AC, route, or schema is removed or replaced.

## Changed files

- `tests/test_discovery_unindexed.py` — NEW (frozen test). Ten tests covering
  the v0 fallback, the disk scan and its de-duplication, `publisher_for`, and
  the non-affine quant label.

Implementation (`src/vortex/discovery.py`, `labels.py`, `catalog.py`,
`app.py`, `ui.py`) already landed in `52f4f65`; it is not part of this freeze.

## Task DAG

None. Tests-only regression pin — no coder tasks; the implementation already
exists and is carried acceptance-only.

## Test-to-file mapping

* `tests/test_discovery_unindexed.py::test_unindexed_rows_skip_known_and_resolve_path`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_unindexed_rows_unknown_publisher_dir_has_no_path`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_unindexed_rows_tolerate_bad_body`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_discover_models_uses_row_path_when_not_in_lms_listing`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_disk_rows_find_folders_lm_studio_skips`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_disk_rows_dropped_when_lm_studio_reports_the_folder`
    -> `src/vortex/discovery.py`
* `tests/test_discovery_unindexed.py::test_publisher_for_paths_and_aliases`
    -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_quant_label_names_non_affine_base_format`
    -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_quant_label_mxfp4_with_affine_overrides_is_mixed`
    -> `src/vortex/labels.py`
* `tests/test_discovery_unindexed.py::test_quant_label_affine_mix_unchanged`
    -> `src/vortex/labels.py`
