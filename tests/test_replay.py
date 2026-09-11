import json
import tempfile
import unittest
from pathlib import Path

from mission_game import ActionError, Game
from mission_game.policy import RandomLegalPolicy
from mission_game.session import Session
from mission_game.types import Phase
from tests.helpers import game, proposal, submit, tokens


class ReplayTests(unittest.TestCase):
    def test_identical_retry_does_not_execute_twice(self):
        g = game()
        proposal(g)
        observation = g.observe("p0")
        payload = {"player_id": "p0", "request_id": observation["request_id"],
                   "revision": observation["revision"], "action": {"type": "contribute", "tokens": tokens(blue=1)}}
        response = g.submit(**payload)
        snapshot = g.snapshot()
        self.assertEqual(g.submit(**payload), response)
        self.assertEqual(g.snapshot(), snapshot)
        submit(g, "p1", {"type": "contribute", "tokens": tokens()})
        snapshot = g.snapshot()
        self.assertEqual(g.submit(**payload), response)
        self.assertEqual(g.snapshot(), snapshot)
        altered = {**payload, "action": {"type": "contribute", "tokens": tokens(blue=True)}}
        with self.assertRaises(ActionError) as error:
            g.submit(**altered)
        self.assertEqual(error.exception.code, "conflicting_retry")
        self.assertEqual(g.snapshot(), snapshot)

    def test_partial_commit_survives_serialization_and_retry(self):
        g = game()
        proposal(g)
        observation = g.observe("p0")
        submit(g, "p0", {"type": "contribute", "tokens": tokens(blue=3)})
        restored = Game.from_snapshot(json.loads(json.dumps(g.snapshot())))
        for pid in ("p0", "p1", "p7"):
            self.assertEqual(restored.observe(pid), g.observe(pid))
        restored.submit("p0", observation["request_id"], observation["revision"],
                        {"type": "contribute", "tokens": tokens(blue=3)})
        for engine in (g, restored):
            submit(engine, "p1", {"type": "contribute", "tokens": tokens(red=2)})
        self.assertEqual(g.snapshot(), restored.snapshot())
        self.assertEqual(g.players[0].wallet, 2)

    def test_resume_at_every_phase_matches_uninterrupted_run(self):
        session = Session(123, game_id="resume-fixture")
        checkpoints = {}
        with tempfile.TemporaryDirectory() as directory:
            while session.game.phase != Phase.GAME_OVER:
                key = (session.game.phase.value, bool(session.game.pending))
                if key not in checkpoints:
                    path = Path(directory) / f"{key[0]}-{key[1]}.json"
                    session.save(path)
                    checkpoints[key] = path
                self.assertTrue(session.step_bot())
            expected = session.game.snapshot()
            for key, path in checkpoints.items():
                with self.subTest(checkpoint=key):
                    resumed = Session.load(path)
                    resumed.run()
                    self.assertEqual(resumed.game.snapshot(), expected)
                    self.assertEqual(resumed.replay().snapshot(), expected)
                    self.assertEqual({p: b.snapshot() for p, b in resumed.policies.items()},
                                     {p: b.snapshot() for p, b in session.policies.items()})
                    self.assertEqual(resumed.bot_decisions, session.bot_decisions)
            self.assertIn(("contribute", True), checkpoints)
            self.assertIn(("pledge", True), checkpoints)
            self.assertIn(("report", True), checkpoints)
            self.assertIn(("vote", False), checkpoints)

    def test_policy_sampling_cannot_advance_mission_stream(self):
        one = Game(42, game_id="streams")
        two = Game(42, game_id="streams")
        policy = RandomLegalPolicy(42, one.chairman)
        observation = one.observe(f"p{one.chairman}")
        for _ in range(100):
            policy.choose_action(observation)
        self.assertEqual(one.snapshot(), two.snapshot())
        self.assertEqual([one._draw_mission(i).to_dict() for i in range(2, 20)],
                         [two._draw_mission(i).to_dict() for i in range(2, 20)])

    def test_replay_detects_tampered_saved_result(self):
        session = Session(11)
        session.run()
        session.game.players[0].name = "changed after play"
        with self.assertRaisesRegex(ValueError, "diverged"):
            session.replay()

    def test_multiple_seeded_games_preserve_invariants(self):
        for seed in range(10):
            with self.subTest(seed=seed):
                session = Session(seed)
                session.run()
                self.assertIn(session.game.status, ("FINISHED", "UNRESOLVED"))
                session.game.assert_invariants()
                session.replay()
