import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from mission_game import ActionError
from mission_game.policy import RandomLegalPolicy
from mission_game.replay import ReplayTimeline
from mission_game.server import TableStore, WebError, make_server
from mission_game.session import Session
from mission_game.types import Phase
from tests.helpers import proposal, submit, tokens


class WebStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = TableStore(self.root)

    def saved(self, session, filename="session.json"):
        path = self.root / session.game.game_id / filename
        session.save(path)
        return path

    def test_catalog_discovers_existing_terminal_and_simulation_sessions(self):
        human = Session(1, human_seat=3, game_id="terminal-game")
        completed = Session(2, game_id="simulation-game")
        completed.run()
        self.saved(human)
        self.saved(completed, "example-replay.json")
        (self.root / "summary.json").write_text('{"completed":100}')
        (self.root / "broken" ).mkdir()
        (self.root / "broken" / "session.json").write_text('not json')
        games = self.store.catalog()
        self.assertEqual({g["id"] for g in games}, {"terminal-game", "simulation-game"})
        self.assertEqual(next(g for g in games if g["id"] == "terminal-game")["human_id"], "p3")
        for entry in games:
            self.assertNotIn("seed", entry)
            self.assertNotIn("path", entry)
            self.assertNotIn("players", entry)

    def test_web_actions_complete_game_and_resume_from_disk(self):
        game = self.store.create(2)
        controller = RandomLegalPolicy(999, 2)
        observation = self.store.state(game["id"])["observation"]
        decisions = 0
        while observation["phase"] != "game_over":
            self.assertEqual(observation["viewer"], "p2")
            self.assertIsNotNone(observation["request_id"])
            payload = {"request_id": observation["request_id"], "revision": observation["revision"],
                       "action": controller.choose_action(observation)}
            response = self.store.submit(game["id"], payload)
            decisions += 1
            observation = response["observation"]
            if decisions == 2:
                restored = TableStore(self.root)
                self.assertEqual(restored.state(game["id"]), self.store.state(game["id"]))
                self.store = restored
        self.assertGreater(decisions, 5)
        session, _ = self.store.load(game["id"])
        session.replay()
        self.assertEqual(self.store.replay(game["id"], -1)["observation"], observation)

    def test_actions_are_bound_to_saved_seat_and_retry_is_idempotent(self):
        game = self.store.create(0)
        observation = self.store.state(game["id"])["observation"]
        payload = {"request_id": observation["request_id"], "revision": observation["revision"],
                   "action": RandomLegalPolicy(10, 0).choose_action(observation)}
        before = self.store.load(game["id"])[0].snapshot()
        with self.assertRaises(WebError):
            self.store.submit(game["id"], {**payload, "player_id": "p1"})
        self.assertEqual(self.store.load(game["id"])[0].snapshot(), before)
        accepted = self.store.submit(game["id"], payload)
        snapshot = self.store.load(game["id"])[0].snapshot()
        retried = self.store.submit(game["id"], payload)
        self.assertEqual(accepted["acceptance"], retried["acceptance"])
        self.assertEqual(self.store.load(game["id"])[0].snapshot(), snapshot)

    def test_live_replay_cannot_change_seats_or_enable_inspection(self):
        game = self.store.create(4)
        ordinary = self.store.replay(game["id"])
        self.assertEqual(ordinary["viewing_seat"], "p4")
        self.assertIsNone(ordinary["designer"])
        self.assertFalse(ordinary["can_inspect"])
        for seat, designer in (("p1", False), ("p4", True)):
            with self.assertRaises(WebError) as error:
                self.store.replay(game["id"], seat=seat, designer=designer)
            self.assertEqual(error.exception.status, 403)

    def test_completed_replay_has_explicit_designer_view(self):
        session = Session(7, game_id="completed")
        session.run()
        self.saved(session)
        ordinary = self.store.replay("completed", -1)
        designer = self.store.replay("completed", -1, seat="p3", designer=True)
        self.assertIsNone(ordinary["designer"])
        self.assertEqual(designer["observation"]["viewer"], "p3")
        self.assertEqual([p["team"] for p in designer["designer"]["players"]], [p.team for p in session.game.players])
        self.assertNotIn("mission_rng", designer["designer"])
        self.assertGreaterEqual(designer["total_steps"], ordinary["total_steps"])

    def test_replay_does_not_mutate_saved_game_or_bot_streams(self):
        session = Session(25, game_id="unchanged")
        session.run()
        path = self.saved(session)
        before = path.read_bytes()
        self.store.replay("unchanged", 0)
        self.store.replay("unchanged", 5)
        self.store.replay("unchanged", -1, designer=True)
        self.assertEqual(path.read_bytes(), before)

    def test_replay_detects_saved_state_tampering(self):
        session = Session(6, game_id="tampered")
        session.run()
        session.game.players[0].name = "Edited after play"
        self.saved(session)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.store.replay("tampered")

    def test_unknown_and_out_of_range_replay_requests_fail(self):
        game = self.store.create()
        with self.assertRaises(WebError):
            self.store.state("../../secret")
        with self.assertRaises(ValueError):
            self.store.replay(game["id"], 999999)

    def test_other_sealed_submissions_add_no_player_replay_steps(self):
        from mission_game.config import GameConfig
        session = Session(42, config=GameConfig(crew_min=2, crew_max=2), human_seat=7, game_id="sealed")
        proposal(session.game)
        before = ReplayTimeline(session, "p7")
        submit(session.game, "p0", {"type": "contribute", "tokens": tokens(blue=1)})
        after = ReplayTimeline(session, "p7")
        self.assertEqual(before.timeline, after.timeline)
        self.assertEqual(before.frames, after.frames)
        own = ReplayTimeline(session, "p0")
        self.assertEqual(own.timeline[-1]["label"], "Your contribution is sealed")
        self.assertEqual(own.frames[-1]["observation"]["private"]["submissions"][-1]["action"]["tokens"], tokens(blue=1))


class WebHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.server = make_server(cls.directory.name, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.directory.cleanup()

    def request(self, path, payload=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        body = json.dumps(payload) if payload is not None else None
        defaults = {"Content-Type": "application/json"} if body else {}
        connection.request("POST" if body is not None else "GET", path, body, {**defaults, **(headers or {})})
        response = connection.getresponse()
        raw = response.read()
        result = json.loads(raw) if response.getheader("Content-Type", "").startswith("application/json") else raw.decode()
        status = response.status
        connection.close()
        return status, result

    def test_static_assets_and_bootstrap(self):
        for path, expected in (("/", "Hidden Rules"), ("/app.js", "submitDecision"), ("/style.css", ".mission")):
            status, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertIn(expected, body)
        status, bootstrap = self.request("/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertIn("token", bootstrap)
        self.assertIn("guide", bootstrap)

    def test_cross_origin_and_missing_csrf_cannot_mutate(self):
        _, bootstrap = self.request("/api/bootstrap")
        self.assertEqual(self.request("/api/games", {})[0], 403)
        self.assertEqual(self.request("/api/games", {}, {"X-Table-Token": bootstrap["token"], "Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/api/bootstrap", headers={"Host": "attacker.example"})[0], 403)

    def test_api_creates_resumes_and_binds_seat(self):
        _, bootstrap = self.request("/api/bootstrap")
        headers = {"X-Table-Token": bootstrap["token"]}
        status, created = self.request("/api/games", {"human_seat": 3}, headers)
        self.assertEqual(status, 201)
        game_id = created["game"]["id"]
        status, state = self.request(f"/api/games/{game_id}/state?seat=p0")
        self.assertEqual(status, 200)
        self.assertEqual(state["observation"]["viewer"], "p3")
        self.assertEqual(self.request(f"/api/games/{game_id}/replay?designer=true")[0], 403)
        self.assertEqual(self.request(f"/api/games/{game_id}/resume", {}, headers)[0], 200)

    def test_filesystem_and_snapshots_are_not_served(self):
        for path in ("/../README.md", "/runs/session.json", "/mission_game/engine.py", "/api/games/unknown/snapshot"):
            self.assertEqual(self.request(path)[0], 404)

    def test_invalid_json_and_wrong_media_type_fail_cleanly(self):
        _, bootstrap = self.request("/api/bootstrap")
        headers = {"X-Table-Token": bootstrap["token"]}
        self.assertEqual(self.request("/api/games", {"human_seat": True}, headers)[0], 400)
        self.assertEqual(self.request("/api/games", {}, {**headers, "Content-Type": "text/plain"})[0], 415)
