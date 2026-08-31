"""modelmux — the vortex process/daemon. CLI entry point."""

from __future__ import annotations

import argparse
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:9000"

# Poll no longer than this for an operation to leave loading/unloading. Sits
# just beyond the daemon's own 300s ready ceiling so the server, not the client,
# governs a genuine slow load — but a wedged operation can never hang the CLI.
POLL_DEADLINE_SECONDS = 310.0


class DaemonUnavailable(Exception):
    pass


class PollTimeout(Exception):
    def __init__(self, op_id: str) -> None:
        super().__init__(op_id)
        self.op_id = op_id


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        return httpx.request(method, BASE_URL + path, **kwargs)
    except httpx.ConnectError:
        raise DaemonUnavailable() from None


def _get(path: str) -> dict:
    r = _request("GET", path, timeout=10)
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
    deadline = time.monotonic() + POLL_DEADLINE_SECONDS
    while True:
        op = _get(f"/api/operations/{op_id}")
        print(f"  {op['phase']}: {op['state']}", flush=True)
        if op["state"] not in ("loading", "unloading"):
            return op
        if time.monotonic() >= deadline:
            raise PollTimeout(op_id)
        time.sleep(0.5)


def _cmd_load(args: argparse.Namespace) -> int:
    r = _request("POST", f"/api/models/{args.model}/load", timeout=60)
    if r.status_code == 409:
        print(f"conflict: {r.json().get('detail', r.text)}")
        return 2
    r.raise_for_status()
    op_id = r.json()["operation"]
    if not args.wait:
        print(f"load started: {args.model} (operation {op_id})")
        return 0
    op = _poll(op_id)
    if op["state"] == "ready":
        print(f"loaded {args.model}")
        return 0
    print(f"load failed: {op.get('message', '')}")
    return 1


def _cmd_unload(args: argparse.Namespace) -> int:
    r = _request("POST", f"/api/models/{args.model}/unload", timeout=60)
    r.raise_for_status()
    op_id = r.json()["operation"]
    if not args.wait:
        print(f"unload started: {args.model} (operation {op_id})")
        return 0
    op = _poll(op_id)
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
    p_load.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True,
                        help="wait for the load to finish (default); --no-wait returns immediately")
    p_unload = sub.add_parser("unload")
    p_unload.add_argument("model")
    p_unload.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True,
                          help="wait for the unload to finish (default); --no-wait returns immediately")

    args = parser.parse_args(argv)
    handlers = {
        "status": _cmd_status,
        "models": _cmd_models,
        "load": _cmd_load,
        "unload": _cmd_unload,
    }
    try:
        return handlers[args.command](args)
    except DaemonUnavailable:
        print("vortex daemon is not reachable on http://127.0.0.1:9000", file=sys.stderr)
        print("start it from the vortex repo: .venv/bin/uvicorn vortex.app:build_app --factory --port 9000", file=sys.stderr)
        return 3
    except PollTimeout as exc:
        print(f"timed out after {POLL_DEADLINE_SECONDS:.0f}s waiting for operation {exc.op_id}", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        print(f"request failed: HTTP {code}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"request failed: {exc} ({type(exc).__name__})", file=sys.stderr)
        return 1
    except (KeyError, ValueError) as exc:
        print(f"unexpected response from daemon (missing/invalid {exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())