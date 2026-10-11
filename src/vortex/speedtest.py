"""Speed measurement: one fixed prompt, timed three ways against a serving model.

- first_token_s: wall time of a 1-token reply (rounded to 3 decimals)
- single_tps: completion tokens / wall seconds of one MAX_TOKENS request
- multi_tps: 4 concurrent MAX_TOKENS requests, summed tokens / wall seconds
  from first start to last finish

Token counts come from usage.completion_tokens; a connection error, a non-200
reply, or a reply without that count fails the test (SpeedTestError).
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx

# The one fixed prompt every model is measured with, so numbers are comparable.
PROMPT = "Count from one to twenty, one number per line. Nothing else."
MAX_TOKENS = 256
CONCURRENCY = 4

_TIMEOUT = httpx.Timeout(300.0)


class SpeedTestError(Exception):
    """A speed test could not be completed for this model."""


def _payload(model: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0,
        "stream": False,
        "max_tokens": max_tokens,
    }


def _tokens_for(client: httpx.Client, endpoint: str, model: str, max_tokens: int) -> int:
    """One non-streaming, temperature-0 completion; returns its token count."""
    try:
        reply = client.post(endpoint, json=_payload(model, max_tokens))
    except httpx.RequestError as exc:
        raise SpeedTestError(f"connection failed: {exc}") from exc
    if reply.status_code != 200:
        raise SpeedTestError(f"model answered {reply.status_code}, not 200")
    try:
        count = reply.json()["usage"]["completion_tokens"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SpeedTestError("reply has no completion token count") from exc
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise SpeedTestError("reply has no usable completion token count")
    return count


def measure(endpoint: str, model: str) -> dict[str, float]:
    """Time a serving model: first word, one full request, then four at once.

    Returns exactly {"single_tps", "multi_tps", "first_token_s"}.
    """
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            start = time.monotonic()
            _tokens_for(client, endpoint, model, 1)
            first_token_s = time.monotonic() - start

            start = time.monotonic()
            single_tokens = _tokens_for(client, endpoint, model, MAX_TOKENS)
            single_elapsed = time.monotonic() - start

            start = time.monotonic()
            with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
                counts = list(
                    pool.map(
                        lambda _: _tokens_for(client, endpoint, model, MAX_TOKENS),
                        range(CONCURRENCY),
                    )
                )
            multi_elapsed = time.monotonic() - start
    except httpx.RequestError as exc:
        raise SpeedTestError(f"connection failed: {exc}") from exc

    return {
        "single_tps": round(single_tokens / single_elapsed, 1),
        "multi_tps": round(sum(counts) / multi_elapsed, 1),
        "first_token_s": round(first_token_s, 3),
    }


def load_results(path: Path) -> dict[str, dict]:
    """Latest result per model id; {} for a missing, invalid, or non-object file."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_result(path: Path, public_id: str, result: dict[str, float]) -> dict[str, float | str]:
    """Store result + local tested_at under public_id, keeping other models.

    Creates parent directories; writes atomically. Returns the stored record.
    """
    data = load_results(path)
    record: dict[str, float | str] = {
        **result,
        "tested_at": datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
    }
    data[public_id] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    return record