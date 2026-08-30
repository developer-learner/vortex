"""Frozen UI-content tests for the Engine wrappers section (ERD-DELTA v14)."""

from vortex.ui import UI_PAGE


def test_ui_has_engine_wrappers_section():
    assert "Engine wrappers" in UI_PAGE
    assert 'id="wrapperrows"' in UI_PAGE
    assert 'data-act="discover"' in UI_PAGE


def test_ui_fetches_the_inventory_endpoint():
    assert 'fetch("/api/engine-wrappers")' in UI_PAGE


def test_ui_renders_wrapper_fields_from_the_api():
    for code_field in ("w.name", "w.kind", "w.binary_path", "w.version", "w.in_catalog"):
        assert code_field in UI_PAGE


def test_discover_button_posts_to_rescan():
    assert 'data-act="discover"' in UI_PAGE
    assert "engine-wrappers/discover" in UI_PAGE
    assert 'method: "POST"' in UI_PAGE


def test_poll_wrappers_runs_on_the_existing_cadence():
    assert "setInterval(pollWrappers, POLL_MS)" in UI_PAGE