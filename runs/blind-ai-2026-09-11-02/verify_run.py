"""Postgame verification; run after the source-blind player has finished."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from mission_game.blind_runner import validate_predictions
from mission_game.engine import Game
from mission_game.session import Session, write_json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def lines(name):
    return [json.loads(line) for line in (HERE / name).read_text().splitlines() if line]


def main():
    session = Session.load(HERE / "session.json")
    assert session.game.status == "FINISHED", "Wait until the player finishes"
    session.replay()
    original = json.loads((HERE / "cli-session-original.json").read_text())
    current = json.loads((HERE / "session.json").read_text())
    for field in ("initial", "game", "human_id", "policies"):
        assert original[field] == current[field]
    setup = json.loads((HERE / "setup.json").read_text())
    assert session.initial["config"] == setup["config"]
    me = next(p for p in session.initial["players"] if p["id"] == session.human_id)
    assert me["ability"] != "recolorer"
    assert {"team": me["team"], "ability": me["ability"], "objective": me["objective"]["kind"]} == setup["initial_own_card"]
    for name, expected in setup["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected

    transcript = lines("cli-transcript.jsonl")
    inputs, outputs = lines("model-inputs.jsonl"), lines("model-outputs.jsonl")
    assert len(inputs) == len(outputs)
    observed = {digest(e["observation"]) for e in transcript if "observation" in e}
    prior_memory = ""
    request_types = {}
    for index, (request, response) in enumerate(zip(inputs, outputs), 1):
        assert request["call"] == response["call"] == index
        body = request["body"]
        assert set(body) == {"model", "instructions", "input", "tools", "tool_choice", "store", "reasoning", "max_output_tokens", "text"}
        assert body["tools"] == [] and body["tool_choice"] == "none" and body["store"] is False
        assert body["instructions"] == (HERE / "player-instructions.txt").read_text()
        assert len(body["input"]) == 1 and body["input"][0]["role"] == "user"
        prompt = json.loads(body["input"][0]["content"])
        assert set(prompt) == {"request", "observation", "player_memory", "previous_predictions", "validation_feedback"}
        assert digest(prompt["observation"]) in observed
        assert prompt["observation"]["viewer"] == session.human_id
        assert prompt["player_memory"] == prior_memory
        assert str(setup["seed"]) not in json.dumps(body)
        if index == 1:
            assert prompt["previous_predictions"] == []
        for prediction in prompt["previous_predictions"]:
            assert prediction["revision"] <= prompt["observation"]["revision"]
        raw = response["response"]
        assert raw["status"] == "completed"
        assert all(item["type"] in ("message", "reasoning") for item in raw["output"])
        answer = json.loads("".join(part["text"] for item in raw["output"] if item["type"] == "message"
                                   for part in item["content"] if part["type"] == "output_text"))
        prior_memory = answer["player_memory"]
        request_types[prompt["request"]] = request_types.get(prompt["request"], 0) + 1

    actions = {a["request_id"]: a for a in session.game.action_log}
    decisions = lines("decisions.jsonl")
    for decision in decisions:
        record = actions[decision["request_id"]]
        assert record["player_id"] == session.human_id and record["action"] == decision["action"]
    assert len(session.agent_predictions) == len(session.game.completed_missions)
    by_position = {p["position"]: p for p in session.agent_predictions}
    replay = Game.from_snapshot(session.initial)
    accuracy = []
    truth = {p.id: int(p.team == "blue") for p in session.game.players}
    for position, action in enumerate(session.game.action_log, 1):
        replay.submit(**action)
        if position not in by_position:
            continue
        prediction = by_position[position]
        view = replay.observe(session.human_id)
        assert digest(view) == prediction["observation_sha256"]
        validate_predictions(prediction, view)
        known = {**view["public"]["public_badges"], session.human_id: view["private"]["team"]}
        for receipt in view["private"].get("receipts", []):
            if receipt["type"] == "scout":
                known[receipt["target"]] = receipt["team"]
        unknown = set(truth) - set(known)
        estimates = {e["player_id"]: e["p_blue"] for e in prediction["estimates"]}
        prior = (5 - sum(team == "blue" for team in known.values())) / len(unknown) if unknown else 0
        accuracy.append({"mission": prediction["mission"], "position": position,
                         "correct": sum((estimates[p] >= .5) == truth[p] for p in truth), "of": len(truth),
                         "correct_unknown": sum((estimates[p] >= .5) == truth[p] for p in unknown),
                         "unknown_count": len(unknown),
                         "brier_unknown": sum((estimates[p] - truth[p]) ** 2 for p in unknown) / len(unknown) if unknown else None,
                         "prior_brier_unknown": sum((prior - truth[p]) ** 2 for p in unknown) / len(unknown) if unknown else None})
    assert len(accuracy) == len(session.agent_predictions)
    result = {"action_replay_verified": True, "actions": len(session.game.action_log),
              "game_state_unchanged_after_metadata": True, "source_unchanged_during_run": True,
              "all_checkpoint_observation_digests_verified": True,
              "prediction_accuracy": accuracy, "model_requests": len(inputs), "request_types": request_types,
              "accepted_external_decisions": len(decisions), "cli_errors": [e for e in transcript if e["type"] == "error"],
              "all_model_tools_disabled": True, "all_model_observations_match_cli": True,
              "memory_is_only_models_own_previous_output": True, "no_prior_model_conversation": True,
              "trusted_seed_absent_from_model_requests": True,
              "agent_ability": me["ability"], "selection_rule": setup["selection_rule"]}
    write_json(HERE / "verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
