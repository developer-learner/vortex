"""Coverage + behavior pin for the modelmux CLI (src/modelmux/cli.py).

The CLI is a thin argparse shell over the daemon's HTTP API. Every test
monkeypatches ``cli.httpx.request`` with canned responses (or a raised
``httpx.ConnectError``) so nothing touches the network or a live daemon, and
monkeypatches ``cli.time.sleep`` so the poll loop does not wait.
"""

from __future__ import annotations

import httpx
import pytest

from modelmux import cli


class _Resp:
    """Minimal stand-in for httpx.Response covering the surface the CLI uses."""

    def __init__(
        self, status_code: int = 200, payload: dict | None = None, text: str = ""
    ) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=None
            )


def _install(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route cli.httpx.request through ``handler(method, path, **kwargs)``."""

    def fake(method: str, url: str, **kwargs: object) -> _Resp:
        assert url.startswith(cli.BASE_URL)
        return handler(method, url[len(cli.BASE_URL):], **kwargs)

    monkeypatch.setattr(cli.httpx, "request", fake)
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)


def test_main_returns_3_when_daemon_unreachable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        raise httpx.ConnectError("refused")

    _install(monkeypatch, handler)
    assert cli.main(["status"]) == 3
    assert "not reachable" in capsys.readouterr().err


def test_status_no_models(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        assert (method, path) == ("GET", "/api/status")
        return _Resp(payload={"ram_used_gb": 12, "ram_total_gb": 128, "loaded": []})

    _install(monkeypatch, handler)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "no models loaded" in out
    assert "12/128" in out


def test_status_with_loaded_models(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        return _Resp(payload={
            "ram_used_gb": 30, "ram_total_gb": 128,
            "loaded": [{
                "id": "m1", "runtime": "mtplx", "engine": "mlx",
                "port": 8001, "ram_estimate_gb": 27,
            }],
        })

    _install(monkeypatch, handler)
    assert cli.main(["status"]) == 0
    assert "m1" in capsys.readouterr().out


def test_models_table_marks_and_sort(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        assert (method, path) == ("GET", "/api/catalog")
        return _Resp(payload={"entries": [
            {"public_id": "z", "state": "ready", "runtime": "mtplx",
             "port": 8001, "ram_estimate_gb": 27},
            {"public_id": "a", "state": "loading", "runtime": "vmlx",
             "port": 8002, "ram_estimate_gb": 5},
            {"public_id": "m", "state": "idle", "runtime": "ds4",
             "port": 8003, "ram_estimate_gb": 3},
        ]})

    _install(monkeypatch, handler)
    assert cli.main(["models"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if " GB" in ln]
    # each row is "<mark> <public_id padded> ..."; mark is one char, then a
    # space, so the id is the first token from index 2 regardless of the mark.
    assert [ln[2:].split()[0] for ln in lines] == ["a", "m", "z"]  # sorted
    assert lines[0].startswith("○")  # a: loading -> hollow circle
    assert lines[1].startswith(" ")        # m: idle    -> blank
    assert lines[2].startswith("●")  # z: ready   -> filled circle


def test_load_conflict_returns_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        assert (method, path) == ("POST", "/api/models/m1/load")
        return _Resp(status_code=409, payload={"detail": "need 40 GB"})

    _install(monkeypatch, handler)
    assert cli.main(["load", "m1"]) == 2
    assert "conflict" in capsys.readouterr().out


def test_load_success_polls_to_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    states = iter(["loading", "ready"])

    def handler(method: str, path: str, **_kw: object) -> _Resp:
        if method == "POST":
            return _Resp(status_code=202, payload={"operation": "op1"})
        assert path == "/api/operations/op1"
        return _Resp(payload={"phase": "load", "state": next(states)})

    _install(monkeypatch, handler)
    assert cli.main(["load", "m1"]) == 0


def test_load_failure_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        if method == "POST":
            return _Resp(status_code=202, payload={"operation": "op1"})
        return _Resp(payload={"phase": "load", "state": "error", "message": "boom"})

    _install(monkeypatch, handler)
    assert cli.main(["load", "m1"]) == 1


def test_unload_success(monkeypatch: pytest.MonkeyPatch) -> None:
    states = iter(["unloading", "unloaded"])

    def handler(method: str, path: str, **_kw: object) -> _Resp:
        if method == "POST":
            assert path == "/api/models/m1/unload"
            return _Resp(payload={"operation": "op2"})
        return _Resp(payload={"phase": "unload", "state": next(states)})

    _install(monkeypatch, handler)
    assert cli.main(["unload", "m1"]) == 0


def test_unload_failure_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        if method == "POST":
            return _Resp(payload={"operation": "op2"})
        return _Resp(payload={"phase": "unload", "state": "error", "message": "x"})

    _install(monkeypatch, handler)
    assert cli.main(["unload", "m1"]) == 1


# --- bounded / normalized failure behavior -------------------------------------

def test_request_timeout_is_controlled_not_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A request timeout must produce a controlled exit code + message, not an
    uncaught traceback."""
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        raise httpx.TimeoutException("timed out")

    _install(monkeypatch, handler)
    assert cli.main(["status"]) == 1
    assert capsys.readouterr().err.strip(), "a timeout must print a message to stderr"


def test_http_error_status_is_controlled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An HTTP error response (500) must exit 1 with a message, not a traceback."""
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        return _Resp(status_code=500, text="boom")

    _install(monkeypatch, handler)
    assert cli.main(["status"]) == 1
    assert capsys.readouterr().err.strip()


def test_malformed_load_response_is_controlled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 202 whose body is missing 'operation' must exit 1 with a message."""
    def handler(method: str, path: str, **_kw: object) -> _Resp:
        return _Resp(status_code=202, payload={})  # no 'operation'

    _install(monkeypatch, handler)
    assert cli.main(["load", "m1"]) == 1
    assert capsys.readouterr().err.strip()


def test_poll_has_a_deadline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A never-completing operation must not poll forever: once the poll deadline
    is exceeded the CLI exits 1 with a timeout message."""
    monkeypatch.setattr(cli, "POLL_DEADLINE_SECONDS", 0.0)

    def handler(method: str, path: str, **_kw: object) -> _Resp:
        if method == "POST":
            return _Resp(status_code=202, payload={"operation": "op1"})
        return _Resp(payload={"phase": "load", "state": "loading"})  # never terminal

    _install(monkeypatch, handler)
    assert cli.main(["load", "m1"]) == 1
    assert "tim" in capsys.readouterr().err.lower()


def test_load_no_wait_skips_polling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--no-wait fires the load and returns immediately (operation id printed),
    without polling /api/operations."""
    seen: list[tuple[str, str]] = []

    def handler(method: str, path: str, **_kw: object) -> _Resp:
        seen.append((method, path))
        return _Resp(status_code=202, payload={"operation": "op1"})

    _install(monkeypatch, handler)
    assert cli.main(["load", "m1", "--no-wait"]) == 0
    assert not any(p.startswith("/api/operations") for _, p in seen), "no polling under --no-wait"
    assert "op1" in capsys.readouterr().out
