import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mission_game.cli import json_loop, main, summarize
from mission_game.policy import RandomLegalPolicy
from mission_game.session import Session
from mission_game.terminal import choose_action, parse_complaints, parse_reports
from mission_game.types import Phase
from tests.helpers import game, submit, tokens


class AdapterTests(unittest.TestCase):
    def test_terminal_and_json_actions_share_the_contract(self):
        g = game()
        observation = g.observe(f"p{g.chairman}")
        with patch("builtins.input", return_value="0 1"):
            action = choose_action(observation)
        submit(g, observation["viewer"], action)
        with patch("builtins.input", return_value="2 0 1"):
            action = choose_action(g.observe("p0"))
        self.assertEqual(action, {"type": "pledge", "tokens": tokens(blue=2, green=1)})
        submit(g, "p0", action)
        self.assertEqual(parse_complaints("less p2"), [{"modifier": "less", "player_id": "p2"}])
        for invalid in ("", "less p2; more green"):
            with self.assertRaises(ValueError):
                parse_complaints(invalid)
        self.assertEqual(parse_reports("p0 gave 3 blue")[0]["quantity"], 3)

    def test_terminal_only_prompts_for_a_complaint_on_no(self):
        view = {"action_spec": {"type": "vote"}}
        with patch("builtins.input", side_effect=["yes"]) as prompt:
            self.assertEqual(choose_action(view), {"type": "vote", "approve": True, "complaints": []})
            self.assertEqual(prompt.call_count, 1)
        with patch("builtins.input", side_effect=["no", "more blue"]):
            self.assertEqual(choose_action(view)["complaints"], [{"modifier": "more", "color": "blue"}])

    def test_json_adapter_completes_the_same_recorded_game(self):
        expected = Session(7, human_seat=0, game_id="adapter-fixture")
        controller = RandomLegalPolicy(999, 0)
        inputs = []
        while expected.game.phase != Phase.GAME_OVER:
            expected.run()
            if expected.game.phase == Phase.GAME_OVER:
                break
            observation = expected.game.observe("p0")
            payload = {"request_id": observation["request_id"], "revision": observation["revision"],
                       "action": controller.choose_action(observation)}
            inputs.append(json.dumps(payload) + "\n")
            expected.game.submit("p0", **payload)
        actual = Session(7, human_seat=0, game_id="adapter-fixture")
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO("".join(inputs))), patch("sys.stdout", output):
                json_loop(actual, Path(directory) / "session.json", mission_checkpoints=True)
            self.assertEqual(actual.game.snapshot(), expected.game.snapshot())
            messages = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(messages[0]["type"], "instructions")
            self.assertEqual(messages[-1]["observation"]["phase"], "game_over")
            self.assertFalse(any(message["type"] == "error" for message in messages))
            checkpoints = [m for m in messages if m["type"] == "mission_checkpoint"]
            self.assertEqual([m["mission"] for m in checkpoints],
                             list(range(1, len(actual.game.completed_missions) + 1)))
            for checkpoint in checkpoints:
                view = checkpoint["observation"]
                self.assertEqual(view["viewer"], "p0")
                self.assertNotIn(view["phase"], ("audit", "report"))
                self.assertTrue(view["phase"] == "game_over" or
                                view["public"]["mission"]["number"] == checkpoint["mission"] + 1)
                self.assertFalse(any("team" in p for p in view["public"]["players"]))
                self.assertNotIn("seed", view)
            self.assertEqual(messages[-2]["type"], "mission_checkpoint")

    def test_json_errors_do_not_accept_an_actor_override(self):
        session = Session(7, human_seat=0)
        session.run()
        before = session.game.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO('{"player_id":"p1"}\nnot json\n')), patch("sys.stdout", output):
                json_loop(session, Path(directory) / "session.json")
        self.assertEqual(session.game.snapshot(), before)
        errors = [json.loads(line) for line in output.getvalue().splitlines() if json.loads(line)["type"] == "error"]
        self.assertEqual(len(errors), 2)

    def test_statistics_keep_unresolved_and_failures_separate(self):
        completed = Session(3)
        completed.run()
        metrics = completed.metrics()
        unresolved = {**metrics, "status": "UNRESOLVED", "winner": None, "individual_winners": 0}
        summary = summarize([metrics, unresolved, {"status": "FAILED"}])
        self.assertEqual((summary["completed"], summary["unresolved"], summary["failed"]), (1, 1, 1))
        self.assertEqual(sum(summary["team_wins"].values()), 1)

    def test_cli_rejects_zero_game_simulation(self):
        with patch("sys.stderr", io.StringIO()):
            self.assertEqual(main(["simulate", "--games", "0"]), 1)
