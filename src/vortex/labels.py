"""Menu labels for a model on disk: display name, quant, and MTP support.

Read-only: inspects the model folder (MLX) or file name (GGUF). Anything
missing or unreadable yields a weaker label, never an error — the operator's
Add click must not fail because a label could not be derived.
"""

from __future__ import annotations

import json
import os
import re
import struct
from dataclasses import dataclass, field

_SHARD = re.compile(r"-\d{5}-of-\d{5}$")
_BITS_TOKEN = re.compile(r"^(\d+)(?:[-–](\d+))?bits?$", re.IGNORECASE)
_BITS_RANGE = re.compile(r"(?<=\d)-(?=\d+bits?\b)", re.IGNORECASE)
_GGUF_QUANT = re.compile(r"^(?:I?Q\d\w*|BF16|F16|F32|FP16|MXFP4)$", re.IGNORECASE)
_JANG_TOKEN = re.compile(r"^JANG_\w+$", re.IGNORECASE)
# Tokens that describe packaging, not the model; dropped from the name.
_NOISE = {"mlx", "gguf", "serve", "mtp", "ud", "mixed", "community"}


@dataclass(frozen=True)
class Labels:
    display_name: str | None
    quant: str | None
    extras: list[str] = field(default_factory=list)
    has_mtp: bool = False


def describe(path: str, fmt: str | None, fallback_quant: str | None = None,
             architecture: str | None = None) -> Labels:
    """Derive menu labels for the model at `path` (an MLX folder or GGUF file).

    MTP is reported only when the weights actually ship an MTP head and the
    architecture is one mlx-serve's --mtp supports (Qwen).
    """
    stem = _BITS_RANGE.sub("–", _stem(path))
    tokens = [t for t in stem.split("-") if t]
    name = " ".join(t for t in tokens if not _is_quant_token(t) and t.lower() not in _NOISE)
    if fmt == "gguf":
        quant = _gguf_quant(tokens)
        has_mtp = False
    else:
        quant = _jang_quant(path) or _config_quant(path)
        has_mtp = "qwen" in (architecture or "").lower() and _has_mtp(path)
    named = _name_quant(tokens)
    # A uniform config can hide a per-tensor mix the publisher names (e.g. 4-8bit).
    if named and "mixed" in named and quant and "mixed" not in quant:
        quant = named
    quant = quant or named or _normalize_bits(fallback_quant)
    return Labels(display_name=name or None, quant=quant,
                  extras=["MTP"] if has_mtp else [], has_mtp=has_mtp)


def _stem(path: str) -> str:
    base = os.path.basename(path.rstrip("/"))
    if base.lower().endswith(".gguf"):
        base = base[: -len(".gguf")]
    return _SHARD.sub("", base)


def _is_quant_token(token: str) -> bool:
    return bool(_BITS_TOKEN.match(token) or _GGUF_QUANT.match(token) or _JANG_TOKEN.match(token))


def _read_json(path: str) -> dict[str, object] | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _jang_quant(folder: str) -> str | None:
    cfg = _read_json(os.path.join(folder, "jang_config.json"))
    q = cfg.get("quantization") if cfg else None
    if not isinstance(q, dict) or not isinstance(q.get("profile"), str):
        return None
    bits = q.get("actual_bits")
    return f"{q['profile']} ~{bits:.1f}-bit" if isinstance(bits, (int, float)) else str(q["profile"])


def _config_quant(folder: str) -> str | None:
    cfg = _read_json(os.path.join(folder, "config.json"))
    if cfg is None:
        return None
    q = cfg.get("quantization") or cfg.get("quantization_config")
    if not isinstance(q, dict) or not isinstance(q.get("bits"), int):
        return None
    bits = {q["bits"]}
    bits.update(v["bits"] for v in q.values() if isinstance(v, dict) and isinstance(v.get("bits"), int))
    lo, hi = min(bits), max(bits)
    return f"{lo}-bit" if lo == hi else f"{lo}–{hi} mixed"


def _has_mtp(folder: str) -> bool:
    """True when the weights carry MTP tensors (configs often declare a head the weights lack)."""
    if os.path.isdir(os.path.join(folder, "mtp")):
        return True
    index = _read_json(os.path.join(folder, "model.safetensors.index.json"))
    weight_map = index.get("weight_map") if index else None
    if isinstance(weight_map, dict):
        return any(_is_mtp_tensor(k) for k in weight_map)
    return any(_is_mtp_tensor(k) for k in _safetensors_keys(os.path.join(folder, "model.safetensors")))


def _is_mtp_tensor(name: str) -> bool:
    return "mtp" in name.split(".")


def _safetensors_keys(path: str) -> list[str]:
    try:
        with open(path, "rb") as f:
            (length,) = struct.unpack("<Q", f.read(8))
            header = json.loads(f.read(length))
    except (OSError, ValueError, struct.error):
        return []
    return list(header) if isinstance(header, dict) else []


def _gguf_quant(tokens: list[str]) -> str | None:
    for i, token in enumerate(tokens):
        if _GGUF_QUANT.match(token):
            quant = token.upper()
            return f"UD-{quant}" if i > 0 and tokens[i - 1].lower() == "ud" else quant
    return None


def _name_quant(tokens: list[str]) -> str | None:
    for token in tokens:
        if _BITS_TOKEN.match(token):
            return _normalize_bits(token)
    return None


def _normalize_bits(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _BITS_TOKEN.match(raw.strip())
    if m is None:
        return raw
    lo, hi = m.group(1), m.group(2)
    return f"{lo}–{hi} mixed" if hi else f"{lo}-bit"
