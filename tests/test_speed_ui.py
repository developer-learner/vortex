"""Frozen suite v45: the Speed page and the dashboard link to it (AC-47, AC-48).

Static content-contract checks on the locked SPEED_PAGE / UI_PAGE surfaces,
in the style of tests/test_ui_restart.py, plus a field contract: every
`row.<field>` / `res.<field>` the page's script reads must be a field the API
actually returns.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from vortex.speed_ui import SPEED_PAGE
from vortex.speedtest import save_result

from vortex.app import build_app
from vortex.catalog import Catalog, CatalogEntry
from vortex.ui import UI_PAGE


def _reads(prefix: str) -> set[str]:
    return set(re.findall(r"\b" + prefix + r"\.([A-Za-z_][A-Za-z0-9_]*)", SPEED_PAGE))


def _script() -> str:
    assert "<script>" in SPEED_PAGE, "the page needs its script inline"
    return SPEED_PAGE[SPEED_PAGE.index("<script>"):]


def test_page_reads_only_fields_the_api_returns(tmp_path: Path) -> None:
    """Every row.* and res.* field the script reads exists in /api/speed rows
    and results; the script reads rows, results and max_models (AC-47)."""
    results = tmp_path / "speed.json"
    save_result(results, "m1", {"single_tps": 1.0, "multi_tps": 2.0, "first_token_s": 0.1})
    entry = CatalogEntry(
        public_id="m1", runtime="fake", engine="fake",
        launch_command=[sys.executable, "-c", "pass"], port=1,
        ready_url="http://127.0.0.1:1/v1/models",
        chat_endpoint="http://127.0.0.1:1/v1/chat/completions",
    )
    app = build_app(catalog=Catalog(entries=[entry]), sidecar_dir=tmp_path / "sc",
                    speed_results_path=results)
    body = TestClient(app).get("/api/speed").json()
    row_keys, res_keys = set(body["models"][0]), set(body["models"][0]["result"])
    rows_read, res_read = _reads("row"), _reads("res")
    assert {"public_id", "result", "run_status"} <= rows_read, "the table must be built from row.* fields"
    assert {"single_tps", "multi_tps", "first_token_s", "tested_at"} <= res_read
    assert not rows_read - row_keys, f"page reads row fields the API never returns: {sorted(rows_read - row_keys)}"
    assert not res_read - res_keys, f"page reads result fields the API never returns: {sorted(res_read - res_keys)}"
    assert "max_models" in _script(), "the selection limit must come from the API"


def test_page_polls_and_starts_runs_through_the_api() -> None:
    """The script polls /api/speed on a timer and starts a run with a POST to
    /api/speed/run (AC-47)."""
    script = _script()
    assert '"/api/speed"' in script
    assert "setInterval(" in script
    s = script.index("/api/speed/run")
    assert 'method: "POST"' in script[s:s + 120], "a run must be started with a POST"


def test_page_has_one_test_button_and_a_capped_checklist() -> None:
    """The page offers checkboxes and a single "Test selected" control that is
    disabled when nothing is selected or a run is in progress; boxes beyond the
    limit are disabled (AC-47)."""
    assert SPEED_PAGE.count("Test selected") == 1
    script = _script()
    assert 'type="checkbox"' in SPEED_PAGE or "checkbox" in script
    assert "disabled" in script
    assert "running" in script


def test_untested_values_show_a_dash() -> None:
    """Untested speeds and dates are shown as an em dash (AC-47)."""
    assert "—" in _script()


def test_page_shows_status_banner_picks_and_warning() -> None:
    """The page shows each row's run status, a banner that loads and unloads
    are paused during a run, best picks, and the milestone warning (AC-47)."""
    lower = SPEED_PAGE.lower()
    assert "run_status" in _script()
    assert "paused" in lower
    assert "fastest" in lower
    assert "milestone" in lower and "gpu" in lower


def test_failures_are_visible() -> None:
    """A failed run request shows an error beginning "Speed test failed" (AC-47)."""
    assert 'Speed test failed' in _script()


def test_page_adds_no_external_urls() -> None:
    """The page loads nothing from the network (AC-47)."""
    assert not re.search(r"https?://", SPEED_PAGE)


def test_speed_page_links_back_to_the_dashboard() -> None:
    """The Speed page header links to the dashboard at / (AC-48)."""
    header = SPEED_PAGE[SPEED_PAGE.index("<header>"):SPEED_PAGE.index("</header>")]
    assert 'href="/"' in header


def test_dashboard_header_links_to_the_speed_page() -> None:
    """The dashboard header links to /speed; Stop and Restart Vortex stay in the
    header (AC-48)."""
    header = UI_PAGE[UI_PAGE.index("<header>"):UI_PAGE.index("</header>")]
    assert 'href="/speed"' in header
    assert 'id="stopvortex"' in header and 'id="restartvortex"' in header
