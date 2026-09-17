"""Trusted CLI runner for a tool-free, source-blind external model player.

Only protocol documentation, seat observations, and the player's own notes enter
model requests. No source, seeds, snapshots, or scripted-policy internals do.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PLAYER_INSTRUCTIONS = """You are one participant in a hidden-team mission game.
Play to win your current personal objective. You have no tools or access to any
files, source code, other players' private information, or previous playtests.
Use only the public guide, protocol contract, supplied seat observation, and your
own prior notes. Reports, pledges, and complaints are claims. Predict allegiance
(Blue/Red), which can differ from a player's current objective-driven behavior.
Do not assume implementation details or undocumented abilities. Keep brief
decision explanations and a compact player_memory for the next decision.

The observation includes all public history and your own private records. For an
action request, return action_json encoding exactly one legal action object plus
a brief reason and updated player_memory. The trusted runner handles transport
identifiers; never select an actor. For a prediction request, take no game action:
estimate P(Blue) for all eight players and explain the main evidence for each.
P(Red) is 1-P(Blue). Respect confirmed teams and the public five-Blue/three-Red
count: your eight marginal probabilities should sum to five (within 0.03).
Use uncertainty when the evidence does not distinguish team from personal goals.
"""

ACTION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {k: {"type": "string"} for k in ("action_json", "reason", "player_memory")},
    "required": ["action_json", "reason", "player_memory"],
}
PREDICTION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "estimates": {"type": "array", "minItems": 8, "maxItems": 8, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"player_id": {"type": "string", "enum": [f"p{i}" for i in range(8)]},
                           "p_blue": {"type": "number", "minimum": 0, "maximum": 1},
                           "evidence": {"type": "string"}},
            "required": ["player_id", "p_blue", "evidence"]}},
        "summary": {"type": "string"}, "player_memory": {"type": "string"}},
    "required": ["estimates", "summary", "player_memory"],
}


def append_json(path, value):
    with path.open("a") as handle:
        handle.write(json.dumps(value, allow_nan=False) + "\n")
        handle.flush()


def validate_predictions(result, observation):
    estimates = result["estimates"]
    probabilities = {entry["player_id"]: entry["p_blue"] for entry in estimates}
    if len(estimates) != 8 or set(probabilities) != {f"p{i}" for i in range(8)}:
        raise ValueError("Include each of the eight players exactly once")
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
           for p in probabilities.values()):
        raise ValueError("Each P(Blue) must be a finite number from zero to one")
    known = {**observation["public"]["public_badges"], observation["viewer"]: observation["private"]["team"]}
    for receipt in observation["private"].get("receipts", []):
        if receipt["type"] == "scout":
            known[receipt["target"]] = receipt["team"]
    if any(probabilities[pid] != int(team == "blue") for pid, team in known.items()):
        raise ValueError("Use probability 1 for confirmed Blue teams and 0 for confirmed Red teams")
    if abs(sum(probabilities.values()) - observation["public"]["rules"]["team_counts"]["blue"]) > 0.030001:
        raise ValueError("The eight P(Blue) values must sum to five, within 0.03")


class ModelPlayer:
    def __init__(self, root, model, key, public_guide, protocol):
        self.root, self.model, self.key = root, model, key
        self.instructions = PLAYER_INSTRUCTIONS + "\nPUBLIC GUIDE\n" + public_guide + "\nACTION CONTRACT\n" + protocol
        self.memory = ""
        self.predictions = []
        self.calls = 0

    def ask(self, kind, observation, feedback=None):
        # This allowlisted construction is the entire model input boundary.
        prompt = {"request": kind, "observation": observation,
                  "player_memory": self.memory, "previous_predictions": self.predictions,
                  "validation_feedback": feedback}
        body = {"model": self.model, "instructions": self.instructions,
                "input": [{"role": "user", "content": json.dumps(prompt)}],
                "tools": [], "tool_choice": "none", "store": False,
                "reasoning": {"effort": "medium"}, "max_output_tokens": 6000,
                "text": {"format": {"type": "json_schema", "name": kind,
                                     "strict": True, "schema": PREDICTION_SCHEMA if kind == "prediction" else ACTION_SCHEMA}}}
        self.calls += 1
        append_json(self.root / "model-inputs.jsonl", {"call": self.calls, "body": body})
        request = Request("https://api.openai.com/v1/responses", data=json.dumps(body).encode(),
                          headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        for retry in range(3):
            try:
                with urlopen(request, timeout=180) as response:
                    raw = json.load(response)
                break
            except HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and retry < 2:
                    time.sleep(2 ** retry)
                    continue
                message = exc.read().decode().replace(self.key, "[redacted]")[:1200]
                raise RuntimeError(f"Model request failed (HTTP {exc.code}): {message}") from None
        append_json(self.root / "model-outputs.jsonl", {"call": self.calls, "response": raw})
        if raw.get("status") != "completed":
            raise RuntimeError(f"Model response did not complete: {raw.get('status')}")
        if any(item["type"] not in ("message", "reasoning") for item in raw["output"]):
            raise RuntimeError("Unexpected tool output from a tool-free player")
        answer = "".join(part["text"] for item in raw["output"] if item["type"] == "message"
                         for part in item["content"] if part["type"] == "output_text")
        parsed = json.loads(answer)
        self.memory = parsed["player_memory"]
        return parsed


def finalize(root, decisions, predictions, model):
    # Only after all predictions are written do we load any authoritative state.
    from .session import Session, write_json
    session = Session.load(root / "session.json")
    session.replay()
    original = session.game.snapshot()
    write_json(root / "cli-session-original.json", session.snapshot())
    for decision in decisions:
        index, record = next((i, r) for i, r in enumerate(session.game.action_log)
                             if r["request_id"] == decision["request_id"])
        assert record["player_id"] == session.human_id and record["action"] == decision["action"]
        session.bot_decisions.append({"action_index": index, "player_id": session.human_id,
                                     "request_id": record["request_id"], "policy_version": f"blind-api/{model}",
                                     "reason": decision["reason"], "details": {"action": decision["action"], "source_blind": True},
                                     "limitations": ["Tool-free model using only public rules and its seat observations.",
                                                     "Qualitative judgments, not calibrated probabilities."]})
    from .engine import Game
    replayed = Game.from_snapshot(session.initial)
    positions = {replayed.revision: 0}
    for index, record in enumerate(session.game.action_log, 1):
        replayed.submit(**record)
        positions.setdefault(replayed.revision, index)
    for prediction in predictions:
        prediction["position"] = positions[prediction["revision"]]
        prediction["player_id"] = session.human_id
        prediction["model"] = model
    assert len(predictions) == len(session.game.completed_missions)
    session.agent_predictions = predictions
    session.bot_decisions.sort(key=lambda entry: entry["action_index"])
    assert session.game.snapshot() == original
    session.save(root / "session.json")
    session.replay()
    write_json(root / "metrics.json", {**session.metrics(), "external_model": model,
                                      "external_decisions": len(decisions), "prediction_checkpoints": len(predictions),
                                      "source_blind": True, "player_tools": []})
    write_json(root / "team-predictions.json", predictions)
    names = {p.id: p.name for p in session.game.players}
    lines = ["# Blind AI playthrough", "", f"Model: {model}. Seat: {names[session.human_id]}. No tools or source access.", "",
             f"Result: {session.game.score}. {len(session.game.action_log)} actions replayed exactly.", "",
             "Each cell is the model's probability of Blue; Red is the complement.", "",
             "| Mission | " + " | ".join(names.values()) + " |", "| --- | " + " | ".join(["---:"] * 8) + " |"]
    for prediction in predictions:
        probabilities = {e["player_id"]: e["p_blue"] for e in prediction["estimates"]}
        lines.append(f"| {prediction['mission']} | " + " | ".join(f"{probabilities[pid]:.0%}" for pid in names) + " |")
    lines += ["", "Actual teams (revealed only after the final prediction): " + "; ".join(f"{p.name}: {p.team}" for p in session.game.players), ""]
    for prediction in predictions:
        lines += [f"## After mission {prediction['mission']}", "", prediction["summary"], ""]
        lines += [f"- **{names[e['player_id']]} ({e['p_blue']:.0%} Blue):** {e['evidence']}" for e in prediction["estimates"]]
        lines += [""]
    (root / "review.md").write_text("\n".join(lines))
    print(json.dumps({"finished": True, "game_id": session.game.game_id, "score": session.game.score,
                      "decisions": len(decisions), "predictions": len(predictions), "verified": True}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--human-seat", type=int, choices=range(8), default=0)
    parser.add_argument("--seed", type=int, help="Trusted development seed passed only to the CLI, never to the player")
    parser.add_argument("--api-key-file", help="Existing JSON credential file containing OPENAI_API_KEY; otherwise use the environment")
    args = parser.parse_args(argv)
    key = os.environ.get("OPENAI_API_KEY")
    if args.api_key_file:
        key = json.loads(Path(args.api_key_file).read_text()).get("OPENAI_API_KEY")
    if not key:
        parser.error("Set OPENAI_API_KEY or provide --api-key-file; credentials never enter model input")
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.chmod(root, 0o700)
    # Public participant docs only, not implementation or bot descriptions.
    protocol_doc = Path(__file__).with_name("public_agent_contract.md").read_text()
    cli_command = [sys.executable, "-m", "mission_game.cli", "agent", "--mission-checkpoints",
                   "--human-seat", str(args.human_seat), "--session", str(root)]
    if args.seed is not None:
        cli_command.extend(["--seed", str(args.seed)])
    process = subprocess.Popen(cli_command,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    decisions, predictions = [], []
    player = None
    observation = None
    pending = None
    rejected_actions = 0
    try:
        for line in process.stdout:
            event = json.loads(line)
            append_json(root / "cli-transcript.jsonl", event)
            kind = event["type"]
            if kind == "instructions":
                player = ModelPlayer(root, args.model, key, event["text"], protocol_doc)
                (root / "player-instructions.txt").write_text(player.instructions)
                continue
            if kind == "acceptance":
                rejected_actions = 0
                if pending is not None:
                    decisions.append(pending)
                    append_json(root / "decisions.jsonl", pending)
                    pending = None
                continue
            if kind == "mission_checkpoint":
                view = event["observation"]
                feedback = None
                for retry in range(3):
                    result = player.ask("prediction", view, feedback)
                    try:
                        validate_predictions(result, view)
                        break
                    except (ValueError, KeyError, TypeError) as exc:
                        feedback = str(exc)
                else:
                    raise RuntimeError("Prediction validation failed repeatedly")
                prediction = {"mission": event["mission"], "revision": view["revision"],
                              "history_event_id": view["history"][-1]["id"],
                              "observation_sha256": hashlib.sha256(json.dumps(view, sort_keys=True).encode()).hexdigest(),
                              "estimates": result["estimates"], "summary": result["summary"]}
                predictions.append(prediction)
                player.predictions.append(prediction)
                append_json(root / "predictions.jsonl", prediction)
                print(json.dumps({"checkpoint": event["mission"], "score": view["public"]["score"],
                                  "estimates": result["estimates"], "summary": result["summary"]}), flush=True)
                continue
            if kind == "observation":
                observation = event["observation"]
                if observation["phase"] == "game_over":
                    break
            elif kind != "error":
                continue
            else:
                rejected_actions += 1
                if rejected_actions >= 3:
                    raise RuntimeError("CLI rejected three consecutive model actions; inspect the saved transcript")
            feedback = event if kind == "error" else None
            for retry in range(3):
                result = player.ask("action", observation, feedback)
                try:
                    action = json.loads(result["action_json"])
                    if not isinstance(action, dict) or action.get("type") != observation["action_spec"]["type"]:
                        raise ValueError("Action type must match action_spec.type")
                    break
                except (ValueError, KeyError, TypeError) as exc:
                    feedback = str(exc)
            else:
                raise RuntimeError("Action JSON validation failed repeatedly")
            payload = {"request_id": observation["request_id"], "revision": observation["revision"], "action": action}
            pending = {**payload, "reason": result["reason"]}
            append_json(root / "submitted-decisions.jsonl", pending)
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()
            print(json.dumps({"decision": len(decisions) + 1, "attempt": observation["public"]["attempt"],
                              "phase": observation["phase"], "action": action, "reason": result["reason"]}), flush=True)
    finally:
        process.stdin.close()
        process.wait(timeout=30)
    if observation is None or observation["phase"] != "game_over":
        raise RuntimeError("CLI did not finish; saved session and transcripts remain available")
    finalize(root, decisions, predictions, args.model)


if __name__ == "__main__":
    main()
