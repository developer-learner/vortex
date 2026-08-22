"""Frozen suite M1 (UI): dashboard shell content contract.

Observes only the locked surface: vortex.ui:UI_PAGE (contracts.entry_points).
These tests gate the ui.py task and run BEFORE the route exists.
"""

from vortex.ui import UI_PAGE


def test_title() -> None:
    assert "<title>vortex · model menu</title>" in UI_PAGE


def test_ram_meter_elements_present() -> None:
    assert 'id="ramlabel"' in UI_PAGE
    assert 'id="ramfill"' in UI_PAGE
    assert "/api/status" in UI_PAGE


def test_model_menu_elements_present() -> None:
    assert 'id="rows"' in UI_PAGE
    assert "/api/catalog" in UI_PAGE
    assert 'data-act="load"' in UI_PAGE
    assert 'data-act="unload"' in UI_PAGE
    assert "data-id=" in UI_PAGE
    assert "/api/models/" in UI_PAGE
    assert "/api/operations/" in UI_PAGE


def test_conflict_card_elements_present() -> None:
    assert 'id="conflict"' in UI_PAGE
    assert 'id="conflictbody"' in UI_PAGE


def test_down_state_elements_present() -> None:
    assert 'id="down"' in UI_PAGE
    assert ":9000" in UI_PAGE


def test_ram_bar_zones_present() -> None:
    assert "warn" in UI_PAGE
    assert "danger" in UI_PAGE


def test_no_external_assets() -> None:
    assert 'src="http' not in UI_PAGE
    assert 'href="http' not in UI_PAGE
