"""A fake OpenAI-compatible server for lifecycle/proxy tests.

Used two ways:
- in-process: `FakeChatServer()` binds an ephemeral port, serves /v1/models
  and /v1/chat/completions (stream + non-stream), records request bodies.
- as a real child process: `python -m tests.fake_server <port>` blocks and
  serves on the exact port (so modelmux-style spawn scripts can start it).
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class FakeChatServer:
    def __init__(self, port: int = 0) -> None:
        self.requests: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/v1/models":
                    self._json(200, {"object": "list", "data": [{"id": "fake-model", "object": "model"}]})
                else:
                    self._json(404, {"detail": "not found"})

            def do_POST(self) -> None:
                if self.path == "/v1/chat/completions":
                    length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(length) or b"{}")
                    self.server.requests.append(body)  # type: ignore[attr-defined]
                    if body.get("stream"):
                        self._stream()
                    else:
                        self._json(200, {
                            "id": "fake",
                            "object": "chat.completion",
                            "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello from fake"}, "finish_reason": "stop"}],
                            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                        })
                else:
                    self._json(404, {"detail": "not found"})

            def _json(self, status: int, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _stream(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for chunk in (
                    'data: {"choices":[{"delta":{"content":"hel"}}]}\n\n',
                    'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
                    "data: [DONE]\n\n",
                ):
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()

            def log_message(self, *args: object) -> None:  # type: ignore[override]
                pass

        self.server = HTTPServer(("127.0.0.1", port), Handler)
        self.server.requests = []  # exposed to the Handler as self.server.requests
        self.requests = self.server.requests
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    server = FakeChatServer(port=port)
    print(f"fake server on :{server.port}", flush=True)
    server.thread.join()


if __name__ == "__main__":
    main()