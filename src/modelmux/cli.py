"""modelmux — the vortex process/daemon. CLI entry point."""

from __future__ import annotations

import argparse
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:9000"


def _get(path: str) -> dict:
    r = httpx.get(BASE_URL + path, timeout=10)
    r.raise_for_status()
    return r.json()


def _cmd_status(_args: argparse.Namespace) -> int:
    status = _get("/api/status")
    print(f"RAM  {status['ram_used_gb']}/{status['ram_total_gb']} GB")
    loaded = status["loaded"]
    if not loaded:
        print("no models loaded")
        return 0
    for m in loaded:
        print(f"  ● {m['id']:<28} {m['runtime']:<12} {m['engine']:<10} :{m['port']}  ~{m['ram_estimate_gb']} GB")
    return 0


def _cmd_models(_args: argparse.Namespace) -> int:
    catalog = _get("/api/catalog")["entries"]
    print(f"{'MODEL':<32} {'STATE':<10} {'RUNTIME':<12} {'PORT':<6} RAM")
    for e in sorted(catalog, key=lambda x: x["public_id"]):
        mark = "●" if e["state"] == "ready" else ("○" if e["state"] in ("loading", "unloading") else " ")
        print(f"{mark} {e['public_id']:<30} {e['state']:<10} {e['runtime']:<12} {e['port']:<6} ~{e['ram_estimate_gb']} GB")
    return 0


def _poll(op_id: str) -> dict:
    while True:
        op = _get(f"/api/operations/{op_id}")
        print(f"  {op['phase']}: {op['state']}", flush=True)
        if op["state"] not in ("loading", "unloading"):
            return op
        time.sleep(0.5)


def _cmd_load(args: argparse.Namespace) -> int:
    r = httpx.post(f"{BASE_URL}/api/models/{args.model}/load", timeout=60)
    if r.status_code == 409:
        print(f"conflict: {r.json().get('detail', r.text)}")
        return 2
    r.raise_for_status()
    op = _poll(r.json()["operation"])
    if op["state"] == "ready":
        print(f"loaded {args.model}")
        return 0
    print(f"load failed: {op.get('message', '')}")
    return 1


def _cmd_unload(args: argparse.Namespace) -> int:
    r = httpx.post(f"{BASE_URL}/api/models/{args.model}/unload", timeout=60)
    r.raise_for_status()
    op = _poll(r.json()["operation"])
    if op["state"] == "unloaded":
        print(f"unloaded {args.model}")
        return 0
    print(f"unload failed: {op.get('message', '')}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="modelmux", description="vortex process CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("models")
    p_load = sub.add_parser("load")
    p_load.add_argument("model")
    p_load.add_argument("--wait", action="store_true", default=True)
    p_unload = sub.add_parser("unload")
    p_unload.add_argument("model")
    p_unload.add_argument("--wait", action="store_true", default=True)

    args = parser.parse_args(argv)
    handlers = {
        "status": _cmd_status,
        "models": _cmd_models,
        "load": _cmd_load,
        "unload": _cmd_unload,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())