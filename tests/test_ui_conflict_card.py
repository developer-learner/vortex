"""Frozen suite M1 (v4): conflict card ⇄ the real 409 source.

A load refusal arrives as a 409 on POST /api/models/{id}/load with detail
{message, required_gb, eviction_candidates} (src/vortex/app.py). The dashboard
must drive the #conflict card from THAT response, not from a non-existent
GET /api/status field, and must clear it when an action succeeds. Observes only
the locked surface (contracts.entry_points): UI_PAGE and build_app.
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from vortex.app import build_app
from vortex.catalog import Catalog
from vortex.ui import UI_PAGE


def test_conflict_card_reads_the_409_detail() -> None:
    # the action handler must recognize the 409 and read the detail fields the
    # API actually returns.
    assert "409" in UI_PAGE, "the action handler must branch on the 409 refusal"
    for field in ("required_gb", "eviction_candidates"):
        assert field in UI_PAGE, f"the conflict card must read {field} from the 409 detail"
    assert "setConflict(" in UI_PAGE


def test_conflict_no_longer_read_from_status(tmp_path: Path) -> None:
    # /api/status never carries a conflict; the dead read must be gone.
    status_reads = set(re.findall(r"\bs\.([A-Za-z_][A-Za-z0-9_]*)", UI_PAGE))
    assert "conflict" not in status_reads, "the card is driven by the 409, not /api/status"
    body = TestClient(
        build_app(catalog=Catalog(entries=[]), sidecar_dir=tmp_path / "s")
    ).get("/api/status").json()
    assert "conflict" not in body


def test_conflict_clears_on_successful_action() -> None:
    # a successful load/unload clears any standing conflict card.
    assert "setConflict(null)" in UI_PAGE
