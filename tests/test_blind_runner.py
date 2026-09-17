import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mission_game.blind_runner import ModelPlayer, validate_predictions
from mission_game.replay import ReplayTimeline
from mission_game.session import Session


class BlindRunnerTests(unittest.TestCase):
    def test_model_request_has_no_tools_or_source_and_uses_only_supplied_observation(self):
        answer = {"action_json": '{"type":"vote","approve":true,"complaints":[]}',
                  "reason": "Fund the mission", "player_memory": "My notes"}
        response = {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(answer)}]}]}
        with tempfile.TemporaryDirectory() as directory:
            player = ModelPlayer(Path(directory), "test-model", "private-key", "Public guide", "Public contract")
            with patch("mission_game.blind_runner.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as send:
                self.assertEqual(player.ask("action", {"viewer": "p0"}), answer)
            body = json.loads(send.call_args.args[0].data)
            self.assertEqual(body["tools"], [])
            self.assertEqual(body["tool_choice"], "none")
            self.assertFalse(body["store"])
            self.assertNotIn("previous_response_id", body)
            prompt = json.loads(body["input"][0]["content"])
            self.assertEqual(prompt["observation"], {"viewer": "p0"})
            self.assertEqual(prompt["player_memory"], "")
            self.assertNotIn("private-key", (Path(directory) / "model-inputs.jsonl").read_text())

    def test_prediction_validation_respects_known_teams_and_population(self):
        view = {"viewer": "p0", "private": {"team": "blue", "receipts": []},
                "public": {"public_badges": {"p7": "red"}, "rules": {"team_counts": {"blue": 5}}}}
        result = {"estimates": [{"player_id": f"p{i}", "p_blue": 1 if i == 0 else 0 if i == 7 else 2 / 3}
                                for i in range(8)]}
        validate_predictions(result, view)
        result["estimates"][-1]["p_blue"] = 0.5
        with self.assertRaises(ValueError):
            validate_predictions(result, view)

    def test_predictions_survive_save_and_appear_only_at_recorded_designer_position(self):
        session = Session(123, policy="random")
        session.run()
        position = len(session.game.action_log)
        session.agent_predictions = [{"mission": 1, "position": position, "summary": "private hypothesis"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            session.save(path)
            restored = Session.load(path)
        self.assertEqual(restored.agent_predictions, session.agent_predictions)
        ordinary = ReplayTimeline(restored, "p0")
        self.assertIsNone(ordinary.at(len(ordinary.frames) - 1)["designer"])
        designer = ReplayTimeline(restored, "p0", True)
        self.assertEqual(designer.at_position(position - 1)["designer"]["agent_predictions"], [])
        self.assertEqual(designer.at_position(position)["designer"]["agent_predictions"], session.agent_predictions)
