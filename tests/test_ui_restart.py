"""Frozen suite v38: the Restart Vortex dashboard control (AC-22..AC-24).

Static content-contract checks on the locked UI_PAGE surface, in the same
style as tests/test_ui_content.py's Stop Vortex checks. The restart handler
region runs from the control's click listener to the end of the page, which
holds the handler and the wait-for-new-daemon poll it starts.
"""

from __future__ import annotations

from vortex.ui import UI_PAGE

LISTENER = 'getElementById("restartvortex").addEventListener("click"'


def _restart_region() -> str:
    assert LISTENER in UI_PAGE, "the Restart Vortex control needs a click listener"
    return UI_PAGE[UI_PAGE.index(LISTENER):]


def test_restart_vortex_button_in_header_beside_stop() -> None:
    """A labelled Restart Vortex control lives in the header with Stop (AC-22)."""
    header = UI_PAGE[UI_PAGE.index("<header>"):UI_PAGE.index("</header>")]
    assert 'id="restartvortex"' in header, "the Restart Vortex control must be in the header"
    assert 'id="stopvortex"' in header, "Stop Vortex must stay in the header"
    assert "Restart" in header, "the control must be labelled"


def test_restart_confirms_before_posting_restart() -> None:
    """The click handler confirms a warning that loaded models will be unloaded
    before it POSTs /api/restart; the confirm gates the request (AC-22)."""
    region = _restart_region()
    assert "confirm(" in region and "/api/restart" in region
    c = region.index("confirm(")
    assert c < region.index("/api/restart"), "the confirm must come before the request"
    warning = region[c:c + 200].lower()
    assert "unload" in warning and "model" in warning, (
        "the confirm warning must say loaded models will be unloaded"
    )
    assert "return" in region[c:c + 220], "a cancelled confirm must return without a request"
    s = region.index("/api/restart")
    assert 'method: "POST"' in region[s:s + 80], "restart must be issued as a POST"


def test_restart_disables_the_control_while_in_flight() -> None:
    """The control is disabled once the restart starts and re-enabled on
    failure (AC-23, AC-24)."""
    region = _restart_region()
    assert "disabled = true" in region, "the control must be disabled while restarting"
    assert "disabled = false" in region, "the control must be re-enabled on failure"


def test_restart_polls_status_then_reloads() -> None:
    """After the request is accepted the page polls /api/status and reloads
    once the new daemon answers (AC-23)."""
    region = _restart_region()
    assert '"/api/status"' in region, "the restart flow must poll /api/status"
    assert "location.reload()" in region, "the page must reload onto the new daemon"
    assert "setTimeout(" in region, "the poll must be paced, not a tight loop"


def test_restart_failure_is_visible() -> None:
    """A failed or unanswered restart surfaces an error that begins
    "Restart failed" (AC-24)."""
    region = _restart_region()
    assert region.count('setError("Restart failed') >= 2, (
        "both the request failure and the poll timeout must surface Restart failed"
    )
