#!/usr/bin/env python3
"""UI demo server: serves index.html and proxies /api/* to the vortex daemon.

Throwaway preview only — the real implementation (form factor A) mounts the
page inside the daemon at :9000 and needs no proxy at all.
"""

from __future__ import annotations

import http.server
import urllib.error
import urllib.request
from pathlib import Path

DEMON_PORT = 8050
DAEMON = "http://127.0.0.1:9000"
INDEX = Path(__file__).parent / "index.html"


class Handler(http.server.BaseHTTPRequestHandler):
    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(
            DAEMON + self.path, data=body, method=self.command,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self._relay(resp.status, resp.read())
        except urllib.error.HTTPError as exc:
            self._relay(exc.code, exc.read())
        except urllib.error.URLError:
            self._relay(503, b'{"detail": "daemon unreachable"}')

    def _relay(self, status: int, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy()
        elif self.path in ("/", "/index.html"):
            html = INDEX.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[ui-demo] {fmt % args}")


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", DEMON_PORT), Handler)
    print(f"ui-demo serving http://127.0.0.1:{DEMON_PORT} (api -> {DAEMON})")
    server.serve_forever()
