"""Frozen tests for discovery of models LM Studio's library misses, the menu publisher, and the non-affine quant label (ERD-DELTA v44)."""

from __future__ import annotations

from pathlib import Path

from vortex.discovery import _disk_rows, _unindexed_rows, discover_models

_V0 = {
    "data": [
        {"id": "indexed-model", "publisher": "pub", "state": "not-loaded"},
        {
            "id": "qwen-3.8-flash-next-uncensored-mlx",
            "publisher": "junafinity",
            "arch": "qwen4_exp",
            "compatibility_type": "mlx",
            "quantization": "MXFP4",
            "state": "loaded",
            "max_context_length": 262144,
        },
    ]
}


def _root(tmp_path: Path) -> Path:
    d = tmp_path / "junafinity" / "Qwen-3.8-Flash-Next-Uncensored-MLX-MXFP4"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{}")
    return tmp_path


def test_unindexed_rows_skip_known_and_resolve_path(tmp_path: Path) -> None:
    root = _root(tmp_path)
    rows = _unindexed_rows(_V0, {"indexed-model"}, root)
    assert [r["key"] for r in rows] == ["qwen-3.8-flash-next-uncensored-mlx"]
    row = rows[0]
    assert row["path"] == str(root / "junafinity" / "Qwen-3.8-Flash-Next-Uncensored-MLX-MXFP4")
    assert row["size_bytes"] == 2
    assert row["format"] == "mlx"
    assert row["loaded_instances"]


def test_unindexed_rows_unknown_publisher_dir_has_no_path(tmp_path: Path) -> None:
    rows = _unindexed_rows(_V0, {"indexed-model"}, tmp_path)
    assert rows[0]["path"] is None
    assert rows[0]["size_bytes"] is None


def test_unindexed_rows_tolerate_bad_body(tmp_path: Path) -> None:
    assert _unindexed_rows(None, set(), tmp_path) == []
    assert _unindexed_rows({"data": "x"}, set(), tmp_path) == []


def test_discover_models_uses_row_path_when_not_in_lms_listing(tmp_path: Path) -> None:
    root = _root(tmp_path)
    rows = _unindexed_rows(_V0, {"indexed-model"}, root)
    models = discover_models(catalog_entries=[], fetch=lambda _u: rows, paths=dict)
    assert len(models) == 1
    m = models[0]
    assert m.loaded is True
    assert m.quantization == "MXFP4"
    assert m.path == rows[0]["path"]


def test_disk_rows_find_folders_lm_studio_skips(tmp_path: Path) -> None:
    mlx = tmp_path / "ddalcu" / "Qwen3.8-Flash-Next-MLX-Serve-mixed-4-8bit"
    mlx.mkdir(parents=True)
    (mlx / "config.json").write_text(
        '{"model_type": "qwen4_exp", "quantization": {"bits": 4, "mode": "affine"},'
        ' "text_config": {"max_position_embeddings": 262144}}'
    )
    (mlx / "model-00001.safetensors").write_bytes(b"x")
    gguf = tmp_path / "pub" / "Some-GGUF"
    gguf.mkdir(parents=True)
    (gguf / "m-00002.gguf").write_bytes(b"x")
    (gguf / "m-00001.gguf").write_bytes(b"x")
    (tmp_path / "jmilnz").mkdir()
    rows = {r["publisher"]: r for r in _disk_rows(tmp_path)}
    assert set(rows) == {"ddalcu", "pub"}
    assert rows["ddalcu"]["path"] == str(mlx)
    assert rows["ddalcu"]["format"] == "mlx"
    assert rows["ddalcu"]["quantization"] == "4bit"
    assert rows["ddalcu"]["max_context_length"] == 262144
    assert rows["pub"]["path"] == str(gguf / "m-00001.gguf")


def test_disk_rows_dropped_when_lm_studio_reports_the_folder(tmp_path: Path) -> None:
    listed = tmp_path / "pub" / "Listed"
    listed.mkdir(parents=True)
    (listed / "w.gguf").write_bytes(b"x")
    hidden = tmp_path / "pub2" / "Hidden"
    hidden.mkdir(parents=True)
    (hidden / "w.gguf").write_bytes(b"x")
    rows = [{"key": "listed-key"}, *_disk_rows(tmp_path)]
    models = discover_models(
        catalog_entries=[],
        fetch=lambda _u: rows,
        paths=lambda: {"listed-key": str(listed / "w.gguf")},
    )
    assert [(m.key, m.source) for m in models] == [("listed-key", "lmstudio"), ("hidden", "disk")]


def test_publisher_for_paths_and_aliases() -> None:
    from vortex.labels import publisher_for

    root = "/m"
    assert publisher_for(["/m/junafinity/Qwen-X"], None, root) == "junafinity"
    assert publisher_for(["/opt/bin/mlx-serve", "/m/ddalcu/Q/w.gguf"], None, root) == "ddalcu"
    assert publisher_for([], "incoai/Qwen3.8-27B-Splash", root) == "incoai"
    assert publisher_for([], "mlx-community--Qwen3.8-27B-4bit", root) == "mlx-community"
    assert publisher_for(["/bin/mtplx", "--model", "Youssofal/Qwen-Q"], "x", root) == "Youssofal"
    assert publisher_for(["/elsewhere/x"], "plain-alias", root) is None


def _quant_label(tmp_path: Path, quant: dict) -> str | None:
    import json

    from vortex.labels import describe

    folder = tmp_path / "pub" / "Model"
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({"quantization": quant}))
    return describe(str(folder), "mlx").quant


def test_quant_label_names_non_affine_base_format(tmp_path: Path) -> None:
    base = {"group_size": 32, "bits": 4, "mode": "mxfp4"}
    assert _quant_label(tmp_path, base) == "MXFP4"


def test_quant_label_mxfp4_with_affine_overrides_is_mixed(tmp_path: Path) -> None:
    quant = {
        "group_size": 32, "bits": 4, "mode": "mxfp4",
        "layers.0.attn": {"group_size": 64, "bits": 8, "mode": "affine"},
    }
    assert _quant_label(tmp_path, quant) == "MXFP4 mixed"


def test_quant_label_affine_mix_unchanged(tmp_path: Path) -> None:
    quant = {"group_size": 64, "bits": 4, "layers.0.attn": {"group_size": 64, "bits": 8}}
    assert _quant_label(tmp_path, quant) == "4–8 mixed"
