"""Shared saved-game operations for local HTTP and browser workers."""

import secrets
from collections import OrderedDict
from pathlib import Path

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

