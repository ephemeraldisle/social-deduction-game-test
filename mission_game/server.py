"""Local web adapter. The Python engine remains the only rules authority."""

import json
import secrets
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .engine import ActionError
from .config import GameConfig, DEFAULT_CONFIG_PATH
from .policy import make_policy
from .replay import ReplayTimeline, frame_label
from .session import Session
from .types import Phase


class WebError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class TableStore:
    """One trusted local library; paths and full snapshots stay server-side."""

    def __init__(self, root, policy="social", policy_settings=None, config_path=None):
        make_policy(policy, settings=policy_settings)  # Validate before creating a table.
        self.policy = policy
        self.policy_settings = policy_settings
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH).resolve()
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.paths = {}
        self.replays = OrderedDict()

    def catalog(self):
        candidates = set(self.root.rglob("session.json")) | set(self.root.rglob("example-replay.json"))
        entries = {}
        for path in sorted(candidates):
            if not path.resolve().is_relative_to(self.root):
                continue
            try:
                session = Session.load(path)
                entry = self.summary(session, path)
                if entry["id"] not in entries or entry["updated_at"] > entries[entry["id"]]["updated_at"]:
                    entries[entry["id"]] = entry
                    self.paths[entry["id"]] = path
            except (ValueError, TypeError, KeyError, OSError, AssertionError, AttributeError):
                # Metrics/config files and incompatible saves are not playable tables.
                continue
        return sorted(entries.values(), key=lambda e: e["updated_at"], reverse=True)

    @staticmethod
    def summary(session, path):
        game = session.game
        return {"id": game.game_id, "title": f"Table {game.game_id[:6].upper()}",
                "mode": game.config.mode, "rules_version": game.config.rules_version,
                "status": game.status, "score": dict(game.score), "attempt": game.attempt,
                "mission": game.mission.number, "human_id": session.human_id,
                "missions_to_win": game.config.missions_to_win,
                "can_resume": session.human_id is not None and game.phase != Phase.GAME_OVER,
                "updated_at": path.stat().st_mtime, "sample": session.human_id is None}

    def load(self, game_id):
        self.catalog()
        path = self.paths.get(game_id)
        if path is None or not path.exists() or not path.resolve().is_relative_to(self.root):
            raise WebError(404, "This table could not be found in the local game library")
        return Session.load(path), path

    @staticmethod
    def advance(session, path):
        while session.step_bot():
            session.save(path)

    def create(self, seat=0, demo=False, paced=False):
        if type(seat) is not int or not 0 <= seat <= 7:
            raise WebError(400, "Choose a seat from 0 to 7")
        # Read for each new table; saved sessions restore their embedded config.
        config = GameConfig.load(self.config_path)
        session = Session(secrets.randbits(128), config=config, human_seat=None if demo else seat,
                          policy=self.policy, policy_settings=self.policy_settings)
        path = self.root / "web" / session.game.game_id / "session.json"
        session.save(path)
        if demo or not paced:
            self.advance(session, path)
        self.paths[session.game.game_id] = path
        return self.summary(session, path)

    def state(self, game_id):
        session, path = self.load(game_id)
        return self.view(session, path)

    def view(self, session, path, previous=None):
        observation = session.game.observe(session.human_id or "p0")
        requests = session.game.pending_requests()
        can_advance = bool(session.human_id and requests and (
            session.human_id not in requests or session.game.automatic_action(session.human_id) is not None))
        return {"game": self.summary(session, path), "observation": observation,
                "can_advance": can_advance,
                "step_key": self.step_key(observation),
                "transition": frame_label(previous, observation) if previous else None}

    @staticmethod
    def step_key(observation):
        return f"{observation['revision']}:{len(observation['history'])}:{len(observation['private']['submissions'])}"

    def step(self, game_id, payload):
        if not isinstance(payload, dict) or set(payload) != {"step_key"} or not isinstance(payload["step_key"], str):
            raise WebError(400, "Supply the current step key")
        session, path = self.load(game_id)
        if session.human_id is None:
            raise WebError(409, "Recorded bot games are read-only")
        previous = session.game.observe(session.human_id)
        if payload["step_key"] != self.step_key(previous):
            raise WebError(409, "The table has already advanced; refresh its state")
        changed = False
        # Skip invisible sealed arrivals. One click reveals at most one visible
        # action or phase boundary, never the identity of a hidden ability user.
        while session.step_bot():
            changed = True
            if session.game.observe(session.human_id) != previous:
                break
        if changed:
            session.save(path)
        return self.view(session, path, previous)

    def resume(self, game_id, paced=False):
        session, path = self.load(game_id)
        if session.human_id is None:
            raise WebError(409, "This is a recorded bot game. Open its replay instead")
        if not paced:
            self.advance(session, path)
        return self.view(session, path)

    def submit(self, game_id, payload):
        if (not isinstance(payload, dict) or not {"request_id", "revision", "action"} <= set(payload)
                or set(payload) - {"request_id", "revision", "action", "paced"}
                or type(payload.get("paced", False)) is not bool):
            raise WebError(400, "Supply the current request, revision, and action")
        session, path = self.load(game_id)
        if session.human_id is None:
            raise WebError(409, "Recorded bot games are read-only")
        previous = session.game.observe(session.human_id)
        accepted = session.game.submit(session.human_id, **{k: payload[k] for k in ("request_id", "revision", "action")})
        session.save(path)
        if not payload.get("paced"):
            self.advance(session, path)
        return {"acceptance": accepted, **self.view(session, path, previous)}

    def replay(self, game_id, step=0, seat=None, designer=False, position=None):
        session, path = self.load(game_id)
        finished = session.game.phase == Phase.GAME_OVER
        bound_seat = session.human_id or "p0"
        if seat is None:
            seat = bound_seat
        if seat not in [f"p{i}" for i in range(8)]:
            raise WebError(400, "Unknown viewing seat")
        if not finished and (designer or seat != bound_seat or position is not None):
            raise WebError(403, "Hidden information stays private until the game is finished")
        stamp = path.stat()
        key = (game_id, stamp.st_mtime_ns, stamp.st_size, seat, designer)
        if key not in self.replays:
            self.replays[key] = ReplayTimeline(session, seat, designer)
            while len(self.replays) > 6:
                self.replays.popitem(last=False)
        replay = self.replays[key]
        self.replays.move_to_end(key)
        result = (replay.at_position(position) if position is not None
                  else replay.at(len(replay.frames) - 1 if step == -1 else step))
        if finished:
            # Keep the requested moment even if this seat's last visible change
            # happened earlier. Switching back can then restore the exact frame.
            result["position"] = position if position is not None else replay.positions[result["step"]]
        return {**result, "game": self.summary(session, path), "can_inspect": finished,
                "viewing_seat": seat, "designer_enabled": designer}


def make_server(root="runs", port=8765, policy="social", policy_settings=None, config_path=None):
    store = TableStore(root, policy, policy_settings, config_path)
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
                    if parsed.path == "/api/games":
                        if not mutate:
                            return self.respond(200, {"games": store.catalog()})
                        if not isinstance(payload, dict) or set(payload) - {"human_seat", "demo", "paced"}:
                            raise WebError(400, "Supply a seat and optional sample-game flag")
                        if type(payload.get("demo", False)) is not bool or type(payload.get("paced", False)) is not bool:
                            raise WebError(400, "The sample-game flag must be a boolean")
                        return self.respond(201, {"game": store.create(payload.get("human_seat", 0), payload.get("demo", False), payload.get("paced", False))})
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) != 4 or parts[:2] != ["api", "games"]:
                        raise WebError(404, "This page could not be found")
                    game_id, operation = parts[2:]
                    if mutate and operation == "actions":
                        return self.respond(200, store.submit(game_id, payload))
                    if mutate and operation == "resume":
                        if not isinstance(payload, dict) or set(payload) - {"paced"} or type(payload.get("paced", False)) is not bool:
                            raise WebError(400, "Supply an optional pacing preference")
                        return self.respond(200, store.resume(game_id, payload.get("paced", False)))
                    if mutate and operation == "advance":
                        return self.respond(200, store.step(game_id, payload))
                    if not mutate and operation == "state":
                        return self.respond(200, store.state(game_id))
                    if not mutate and operation == "replay":
                        query = parse_qs(parsed.query)
                        if set(query) - {"step", "seat", "designer", "position"}:
                            raise WebError(400, "Unknown replay option")
                        designer = query.get("designer", ["false"])[0]
                        if designer not in ("true", "false"):
                            raise WebError(400, "Choose a player or designer view")
                        return self.respond(200, store.replay(game_id, int(query.get("step", [0])[0]),
                                                            query.get("seat", [None])[0], designer == "true",
                                                            int(query["position"][0]) if "position" in query else None))
                    raise WebError(404, "This operation could not be found")
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
