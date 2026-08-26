"""Frozen suite: the anneal probe retries transport failures, bounded.

The D-174 anneal (a real 1-token completion before ready) shipped as a
single 5s shot: one transient transport blip the instant a listener comes
up would fail an otherwise-loaded model's readiness cycle. Hardening: up to
ANNEAL_ATTEMPTS attempts for EXCEPTIONS only — a non-200 answer is the
upstream speaking (503 Loading model) and stays single-shot, so the spawn
loop's poll cadence governs load waits, unchanged.
"""

import httpx

import vortex.lifecycle as lifecycle


def _resp(status: int, payload: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=payload if payload is not None else {})


def test_anneal_retries_a_transport_blip_and_succeeds(monkeypatch) -> None:
    calls: list[int] = []

    def flaky(url: str, **kwargs: object) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("connection reset by peer")
        return _resp(200, {"choices": [{"message": {"content": "pong"}}]})

    monkeypatch.setattr(lifecycle.httpx, "post", flaky)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda seconds: None)
    assert lifecycle._anneal_probe("http://127.0.0.1:9/v1/chat/completions") is True
    assert len(calls) == 2, "exactly one retry after the blip"


def test_anneal_gives_up_after_bounded_attempts(monkeypatch) -> None:
    calls: list[int] = []

    def dead(url: str, **kwargs: object) -> httpx.Response:
        calls.append(1)
        raise ConnectionError("down")

    monkeypatch.setattr(lifecycle.httpx, "post", dead)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda seconds: None)
    assert lifecycle._anneal_probe("http://127.0.0.1:9/v1/chat/completions") is False
    assert len(calls) == lifecycle.ANNEAL_ATTEMPTS


def test_anneal_does_not_retry_a_loading_503(monkeypatch) -> None:
    """503 Loading model is the upstream's answer about WEIGHTS, not noise:
    retrying inside the probe would mask it from the spawn loop's poll
    cadence. One attempt, False, let the loop decide."""
    calls: list[int] = []

    def loading(url: str, **kwargs: object) -> httpx.Response:
        calls.append(1)
        return _resp(503)

    monkeypatch.setattr(lifecycle.httpx, "post", loading)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda seconds: None)
    assert lifecycle._anneal_probe("http://127.0.0.1:9/v1/chat/completions") is False
    assert len(calls) == 1


def test_anneal_still_rejects_a_completion_without_choices(monkeypatch) -> None:
    def empty_choices(url: str, **kwargs: object) -> httpx.Response:
        return _resp(200, {"choices": [], "probed": url})

    monkeypatch.setattr(lifecycle.httpx, "post", empty_choices)
    assert lifecycle._anneal_probe("http://127.0.0.1:9/v1/chat/completions") is False


def test_anneal_bounds_are_bounded() -> None:
    """Guard against someone 'hardening' the probe into an unbounded loop:
    attempts stay finite and small; the delay stays non-negative."""
    assert 2 <= lifecycle.ANNEAL_ATTEMPTS <= 5
    assert lifecycle.ANNEAL_RETRY_DELAY_SECONDS >= 0
