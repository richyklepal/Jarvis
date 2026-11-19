"""Jarvis in the browser: a chat page with a mic button and a spoken voice.

    python main.py --web            then open http://localhost:8765

Runs on your own computer only (127.0.0.1) unless you set WEB_HOST. To open it
from your phone on the same Wi-Fi, set WEB_HOST=0.0.0.0 and WEB_TOKEN to a
password; the page will ask for it once.
"""

import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).with_name("web_page.html")
MAX_BODY = 64_000


def serve(jarvis):
    host = os.environ.get("WEB_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("WEB_PORT", "8765"))
    token = os.environ.get("WEB_TOKEN", "").strip()
    local = host in ("127.0.0.1", "localhost", "::1")
    if not local and not token:
        raise SystemExit("[Web] WEB_HOST opens Jarvis to your network. Set WEB_TOKEN to a password first.")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            if not token:
                return True
            given = self.headers.get("X-Jarvis-Token", "")
            return secrets.compare_digest(given.encode(), token.encode())

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                html = PAGE.read_text(encoding="utf-8").replace("__NEEDS_TOKEN__", "true" if token else "false")
                self._send(200, html.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/health":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return self._send(401, {"error": "Wrong password."})
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > MAX_BODY:
                return self._send(413, {"error": "Message too long."})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "Bad request."})
            conv = "web:" + str(body.get("conv", "default"))[:64]

            if self.path == "/api/chat":
                try:
                    reply = jarvis.ask(conv, str(body.get("text", ""))[:8000])
                except Exception as e:  # keep the server up whatever a turn does
                    return self._send(500, {"error": f"Jarvis hit an error: {e}"})
                return self._send(200, {"reply": reply})
            if self.path == "/api/reset":
                jarvis.reset(conv)
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

    server = ThreadingHTTPServer((host, port), Handler)
    shown = "localhost" if local else host
    print(f"[Web] Jarvis chat page: http://{shown}:{port}  (Ctrl+C to stop)")
    server.serve_forever()
