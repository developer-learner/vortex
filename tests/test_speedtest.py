"""Frozen suite v45: the speed measurement and the results store (AC-38..AC-40).

Observes only the locked surface `vortex.speedtest` (measure, SpeedTestError,
load_results, save_result, MAX_TOKENS, CONCURRENCY). Measurements run against
the in-process fake OpenAI server, so request bodies are observable; the
missing-token-count case uses respx to shape the reply.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from vortex.speedtest import (
    CONCURRENCY,
    MAX_TOKENS,
    SpeedTestError,
    load_results,
    measure,
    save_result,
)

from tests.fake_server import FakeChatServer


def _endpoint(server: FakeChatServer) -> str:
    return f"http://127.0.0.1:{server.port}/v1/chat/completions"


def test_measure_returns_the_three_speeds_from_real_replies() -> None:
    """measure() returns positive single_tps and multi_tps and a non-negative
    first_token_s from a serving model's replies (AC-38)."""
    server = FakeChatServer()
    try:
        result = measure(_endpoint(server), "fake-model")
    finally:
        server.stop()
    assert set(result) == {"single_tps", "multi_tps", "first_token_s"}
    for key in ("single_tps", "multi_tps", "first_token_s"):
        assert isinstance(result[key], (int, float)), key
    assert result["single_tps"] > 0 and result["multi_tps"] > 0
    # a local fake answers in about a millisecond: the rounded first-token
    # time may legitimately be 0.0, so only its sign is pinned
    assert result["first_token_s"] >= 0


def test_measure_sends_one_first_word_one_full_then_concurrent_requests() -> None:
    """One 1-token request, one MAX_TOKENS request, then CONCURRENCY more
    MAX_TOKENS requests; every request is non-streaming at temperature 0 and
    names the given model (AC-38)."""
    assert MAX_TOKENS == 256
    assert CONCURRENCY == 4
    server = FakeChatServer()
    try:
        measure(_endpoint(server), "upstream-alias-x")
        bodies = list(server.requests)
    finally:
        server.stop()
    assert len(bodies) == 2 + CONCURRENCY
    assert bodies[0]["max_tokens"] == 1, "the first request times the first word"
    assert [b["max_tokens"] for b in bodies[1:]] == [MAX_TOKENS] * (1 + CONCURRENCY)
    for body in bodies:
        assert body["model"] == "upstream-alias-x"
        assert body["temperature"] == 0
        assert body.get("stream", False) is False
        assert body["messages"] and body["messages"][-1]["role"] == "user"
    prompts = {json.dumps(b["messages"]) for b in bodies}
    assert len(prompts) == 1, "every request must use the same fixed prompt"


def test_measure_fails_when_the_model_answers_an_error() -> None:
    """A non-200 reply raises SpeedTestError (AC-39)."""
    server = FakeChatServer(anneal_failures=-1)
    try:
        with pytest.raises(SpeedTestError):
            measure(_endpoint(server), "fake-model")
    finally:
        server.stop()


def test_measure_fails_when_nothing_is_listening() -> None:
    """A connection failure raises SpeedTestError, not a raw httpx error (AC-39)."""
    server = FakeChatServer()
    endpoint = _endpoint(server)
    server.stop()
    with pytest.raises(SpeedTestError):
        measure(endpoint, "fake-model")


@respx.mock
def test_measure_fails_when_the_reply_has_no_token_count() -> None:
    """A 200 reply without usage.completion_tokens raises SpeedTestError whose
    message says so (AC-39)."""
    url = "http://127.0.0.1:65530/v1/chat/completions"
    respx.post(url).mock(return_value=httpx.Response(200, json={
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
    }))
    with pytest.raises(SpeedTestError) as info:
        measure(url, "fake-model")
    assert "token" in str(info.value).lower()


def test_save_result_stamps_and_keeps_the_latest_per_model(tmp_path: Path) -> None:
    """save_result stores the result plus tested_at under the model id, replaces
    only that model's previous result, and load_results reads it back (AC-40)."""
    path = tmp_path / "nested" / "speed-results.json"
    first = {"single_tps": 10.0, "multi_tps": 30.0, "first_token_s": 0.5}
    save_result(path, "a", first)
    save_result(path, "b", {"single_tps": 20.0, "multi_tps": 40.0, "first_token_s": 0.4})
    record = save_result(path, "a", {"single_tps": 11.0, "multi_tps": 31.0, "first_token_s": 0.6})
    assert record["single_tps"] == 11.0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", record["tested_at"])
    results = load_results(path)
    assert set(results) == {"a", "b"}
    assert results["a"]["single_tps"] == 11.0, "the latest result replaces the old one"
    assert results["b"]["single_tps"] == 20.0, "other models are kept"
    assert "tested_at" in results["b"]


def test_load_results_is_empty_for_a_missing_or_unreadable_file(tmp_path: Path) -> None:
    """No file, invalid JSON, or a non-object all read as no results (AC-40)."""
    assert load_results(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_results(bad) == {}
    listy = tmp_path / "list.json"
    listy.write_text("[1, 2]", encoding="utf-8")
    assert load_results(listy) == {}
