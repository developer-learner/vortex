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
    def __init__(self, port: int = 0, anneal_failures: int = 0, stream_status: int = 200) -> None:
        """anneal_failures: chat returns 503 (loading) for the first N calls
        while /v1/models keeps answering 200 — the llama-server phantom-ready
        class (D-174). -1 = chat never succeeds.

        stream_status: when != 200, a chat request with stream=True is answered
        with this status (JSON error, not SSE), while non-stream chats — the
        anneal probe included — still succeed. Lets a test load a healthy model
        whose STREAMING path then rejects, to check upstream-status preservation.
        """
        self.anneal_failures = anneal_failures
        self.stream_status = stream_status
        self.chat_calls = 0
        self.requests: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/v1/models":
                    self._json(200, {"object": "list", "data": [{"id": "fake-model", "object": "model"}]})
                elif self.path == "/mock/received":
                    self._json(200, {
                        "chat_calls": self.server.chat_calls,
                        "anneal_failures": self.server.anneal_failures,
                        "models": [r.get("model") for r in self.server.requests],
                    })
                else:
                    self._json(404, {"detail": "not found"})

            def do_POST(self) -> None:
                if self.path == "/v1/chat/completions":
                    length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(length) or b"{}")
                    self.server.requests.append(body)  # type: ignore[attr-defined]
                    self.server.chat_calls += 1
                    if self.server.anneal_failures != 0:
                        if self.server.anneal_failures > 0:
                            self.server.anneal_failures -= 1
                            self._json(503, {"detail": "Loading model"})
                            return
                        else:
                            self._json(503, {"detail": "Loading model"})
                            return
                    if body.get("stream"):
                        if self.server.stream_status != 200:
                            self._json(self.server.stream_status, {"detail": "upstream rejected stream"})
                            return
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
        self.server.chat_calls = 0
        self.server.anneal_failures = self.anneal_failures
        self.server.stream_status = self.stream_status
        self.requests = self.server.requests
        self.chat_calls = self.server.chat_calls
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    anneal = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    stream_status = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    server = FakeChatServer(port=port, anneal_failures=anneal, stream_status=stream_status)
    print(f"fake server on :{server.port} (anneal_failures={anneal}, stream_status={stream_status})", flush=True)
    server.thread.join()


if __name__ == "__main__":
    main()