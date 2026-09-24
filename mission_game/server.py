"""Local web adapter. The Python engine remains the only rules authority."""

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit

from .engine import ActionError
from .table_store import TableStore, WebError
from .table_api import table_request


def make_server(root="runs", port=8765, policy="social", policy_settings=None, config_path=None):
    store = TableStore(root, policy, policy_settings, config_path)
    store.lock = threading.RLock()
    token = secrets.token_urlsafe(32)
    assets = {"/": ("index.html", "text/html; charset=utf-8"),
              "/app.js": ("app.js", "text/javascript; charset=utf-8"),
              "/style.css": ("style.css", "text/css; charset=utf-8")}

    class Handler(BaseHTTPRequestHandler):
        server_version = "MissionTable/0.1"

        def log_message(self, *_):
            pass

        def respond(self, status, payload, content_type="application/json; charset=utf-8"):
            body = json.dumps(payload, allow_nan=False).encode() if content_type.startswith("application/json") else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def check_origin(self):
            port = self.server.server_port
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in hosts:
                raise WebError(403, "Use the local table address printed by the server")
            if self.headers.get("Origin") not in (None, *(f"http://{host}" for host in hosts)):
                raise WebError(403, "Requests must come from this local table")

        def do_GET(self):
            self.dispatch(False)

        def do_POST(self):
            self.dispatch(True)

        def dispatch(self, mutate):
            try:
                self.check_origin()
                parsed = urlsplit(self.path)
                if not mutate and parsed.path in assets:
                    filename, content_type = assets[parsed.path]
                    return self.respond(200, files("mission_game").joinpath("web", filename).read_bytes(), content_type)
                with store.lock:
                    if not mutate and parsed.path == "/api/bootstrap":
                        return self.respond(200, {"token": token, "games": store.catalog(),
                                                  "guide": files("mission_game").joinpath("public_player_guide.md").read_text()})
                    payload = None
                    if mutate:
                        if not secrets.compare_digest(self.headers.get("X-Table-Token", ""), token):
                            raise WebError(403, "Refresh the page to reconnect to this table")
                        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                            raise WebError(415, "Actions must be sent as JSON")
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 65536:
                            raise WebError(413, "The action payload is too large or empty")
                        payload = json.loads(self.rfile.read(length))
                    result = table_request(store, self.path, mutate, payload)
                    return self.respond(201 if mutate and parsed.path == "/api/games" else 200, result)
            except ActionError as exc:
                self.respond(409 if exc.code in ("stale_request", "conflicting_retry") else 400,
                             {"error": {"code": exc.code, "message": str(exc)}})
            except WebError as exc:
                self.respond(exc.status, {"error": {"code": "web_error", "message": str(exc)}})
            except (ValueError, TypeError, KeyError, AssertionError) as exc:
                self.respond(400, {"error": {"code": "invalid_request", "message": str(exc) or "Invalid saved game or request"}})
            except OSError:
                self.respond(500, {"error": {"code": "storage_error", "message": "The table could not be saved. Check the server's game directory."}})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.store = store
    return server


def serve(root="runs", port=8765, policy="social", policy_settings=None, config_path=None):
    server = make_server(root, port, policy, policy_settings, config_path)
    print(f"Hidden Rules table: http://127.0.0.1:{server.server_port}", flush=True)
    print("Games save automatically. Press Ctrl+C to stop the local server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
