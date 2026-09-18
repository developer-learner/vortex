"""Frozen UI-content tests for the Discovered models section (ERD-DELTA v32)."""

from vortex.ui import UI_PAGE


def test_ui_has_discovered_models_section():
    assert "Discovered models" in UI_PAGE
    assert 'id="modelrows"' in UI_PAGE
    assert 'data-act="scan-models"' in UI_PAGE


def test_ui_fetches_the_discovered_models_endpoint():
    assert 'fetch("/api/discovered-models")' in UI_PAGE


def test_ui_renders_discovered_model_fields_from_the_api():
    for code_field in ("m.key", "m.publisher", "m.quantization", "m.in_catalog"):
        assert code_field in UI_PAGE


def test_scan_button_posts_to_the_rescan_route():
    assert 'data-act="scan-models"' in UI_PAGE
    assert "discovered-models/discover" in UI_PAGE
    assert 'method: "POST"' in UI_PAGE


def test_poll_models_runs_on_the_existing_cadence():
    assert "setInterval(pollModels, POLL_MS)" in UI_PAGE
