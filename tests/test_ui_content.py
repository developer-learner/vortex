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


def test_dashboard_surfaces_fetch_failures() -> None:
    """No poll/action failure is silently discarded (audit finding #5): there are
    no empty catch handlers, and failures route to an operator-visible surface.

    Observes only the locked UI_PAGE surface, so it asserts on source shape —
    the same contract style as the rest of this file.
    """
    assert "catch(function () {})" not in UI_PAGE, "an empty catch silently drops a failure"
    assert 'id="uierror"' in UI_PAGE, "a visible error banner element must exist"
    assert "function setError" in UI_PAGE, "a setError surface must exist"
    # catalog, wrappers, operation-poll, action, discover — each surfaced.
    assert UI_PAGE.count("setError(") >= 5, "failure paths must route to setError"


def test_routine_polls_do_not_clear_error_banner() -> None:
    """An error the user needs to see (e.g. an operation failure surfaced by
    pollOperation) must not be wiped a beat later by a routine catalog/wrapper
    poll's success path — only a user action or a completed operation clears the
    banner. Static check on the locked UI_PAGE surface: the poll success bodies
    must not call setError(null).
    """
    marker = "\n  function "
    for fn in ("pollCatalog", "pollWrappers"):
        start = UI_PAGE.index(marker + fn)
        end = UI_PAGE.index(marker, start + len(marker))
        body = UI_PAGE[start:end]
        assert "setError(null)" not in body, (
            f"{fn} clears the error banner on a routine poll — it would clobber an operation error"
        )


def test_stop_vortex_button_in_header() -> None:
    """A Stop Vortex control lives in the dashboard header (v27, AC-8)."""
    assert 'id="stopvortex"' in UI_PAGE
    header = UI_PAGE[UI_PAGE.index("<header>"):UI_PAGE.index("</header>")]
    assert 'id="stopvortex"' in header, "the Stop Vortex control must be in the header"
    assert "Stop" in header, "the control must be labelled"


def test_stop_vortex_confirms_then_posts_shutdown() -> None:
    """Clicking Stop Vortex confirms first, then POSTs /api/shutdown (v27, AC-8).

    The confirm() argument must warn that loaded models will be unloaded, so a
    stray click cannot power the machine down. Static check on the locked
    UI_PAGE surface: the page's single confirm() gates the /api/shutdown POST.
    """
    assert "/api/shutdown" in UI_PAGE
    assert "confirm(" in UI_PAGE, "shutdown must be gated behind a confirm()"
    c = UI_PAGE.index("confirm(")
    warning = UI_PAGE[c:c + 200].lower()
    assert "unload" in warning and "model" in warning, (
        "the confirm warning must say loaded models will be unloaded"
    )
    s = UI_PAGE.index("/api/shutdown")
    near = UI_PAGE[s - 200:s + 200]
    assert 'method: "POST"' in near, "shutdown must be issued as a POST"


def test_ram_detail_parity_elements_present() -> None:
    """RAM display parity with testchat (v31): a detail line shows each loaded
    model's live RSS and the loadable figure. Static check on the locked
    UI_PAGE surface — the same content-contract style as the rest of this file.
    """
    assert 'id="ramdetail"' in UI_PAGE
    assert "function setRamDetail" in UI_PAGE
    assert "loadable_gb" in UI_PAGE, "the loadable figure must be consumed"
    assert "rss_gb" in UI_PAGE, "per-model RSS must be consumed"
