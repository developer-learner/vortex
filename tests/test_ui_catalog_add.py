"""Frozen suite v39: dashboard Add / Add all new / Remove controls (AC-36, AC-37).

Static content-contract checks on the locked UI_PAGE surface, in the style of
tests/test_ui_discovered_models.py and tests/test_ui_restart.py. Each check
reads a handler's own region: from its anchor to the next 900 characters.
"""

from __future__ import annotations

import re

from vortex.ui import UI_PAGE


def _region(anchor: str, size: int = 900) -> str:
    assert anchor in UI_PAGE, f"missing {anchor!r}"
    i = UI_PAGE.index(anchor)
    return UI_PAGE[i:i + size]


def test_add_all_new_control_sits_with_the_discovered_models_scan() -> None:
    """An 'Add all new' button with id addnewmodels, near the Scan control (AC-36)."""
    assert 'id="addnewmodels"' in UI_PAGE
    scan = UI_PAGE.index('data-act="scan-models"')
    add_all = UI_PAGE.index('id="addnewmodels"')
    assert abs(add_all - scan) < 600, "Add all new must sit beside the Scan control"
    assert "Add all new" in UI_PAGE
    assert 'id="addresult"' in UI_PAGE, "add-all needs a place to report added/skipped"


def test_add_all_new_confirms_then_posts() -> None:
    """The add-all handler confirms before POSTing /api/discovered-models/add-new (AC-36)."""
    region = _region('getElementById("addnewmodels").addEventListener("click"')
    assert "confirm(" in region and "/api/discovered-models/add-new" in region
    c = region.index("confirm(")
    assert c < region.index("/api/discovered-models/add-new")
    assert "return" in region[c:c + 250], "a cancelled confirm must send nothing"
    s = region.index("/api/discovered-models/add-new")
    assert 'method: "POST"' in region[s:s + 80]


def test_add_all_reports_skips_and_failures() -> None:
    """Skipped keys and reasons are listed; a failed call says Add failed (AC-37)."""
    region = _region('getElementById("addnewmodels").addEventListener("click"', 1400)
    assert ".skipped" in region and ".reason" in region, "skips must be listed with reasons"
    assert 'setError("Add failed' in region


def test_each_new_discovered_model_gets_an_add_control() -> None:
    """Rows not in the catalog render an Add button posting to /{key}/add (AC-36)."""
    assert 'data-act="add-model"' in UI_PAGE
    assert "m.in_catalog" in UI_PAGE, "Add is offered only for models not in the catalog"
    url = re.search(
        r'"/api/discovered-models/"\s*\+\s*encodeURIComponent\([^)]*\)\s*\+\s*"/add"', UI_PAGE
    )
    assert url, "the add URL must carry the URL-encoded model key"
    assert 'method: "POST"' in UI_PAGE[url.end():url.end() + 80]
    assert 'setError("Add failed' in UI_PAGE


def test_local_entries_get_a_confirmed_remove_control() -> None:
    """Catalog rows with origin local render Remove, which confirms, then
    DELETEs /api/catalog/{id}; failures say Remove failed (AC-36, AC-37)."""
    assert 'data-act="remove-model"' in UI_PAGE
    assert 'm.origin === "local"' in UI_PAGE, "Remove is offered only for local entries"
    d = UI_PAGE.index('method: "DELETE"')
    around = UI_PAGE[max(0, d - 500):d + 200]
    assert "/api/catalog/" in around
    assert "confirm(" in around, "remove must be confirmed first"
    assert 'setError("Remove failed' in UI_PAGE


def test_successful_changes_refresh_both_lists() -> None:
    """After add, add-all, or remove the page re-polls catalog and discovered models."""
    region = _region('getElementById("addnewmodels").addEventListener("click"', 1400)
    assert "pollCatalog()" in region and "pollModels()" in region
