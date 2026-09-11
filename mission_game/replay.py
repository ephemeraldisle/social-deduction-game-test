"""Observable replay boundaries, projected before they reach the browser."""

from copy import deepcopy

from .engine import Game


def frame_label(previous, current):
    new_events = current["history"][len(previous["history"]):] if previous else []
    if previous is None:
        return "The table is dealt"
    kinds = {event["type"] for event in new_events}
    if "game_over" in kinds:
        return "Final reports · game over"
    if "reports_revealed" in kinds:
        return "Reports revealed · income paid"
    if "attempt_resolved" in kinds:
        return "Mission result revealed"
    if "proposal_approved" in kinds:
        return "Vote complete · crew approved"
    if "proposal_rejected" in kinds:
        return "Vote complete · crew rejected"
    if "vote" in kinds:
        event = next(e for e in reversed(new_events) if e["type"] == "vote")
        name = next(p["name"] for p in current["public"]["players"] if p["id"] == event["player_id"])
        return f"{name} votes {'Yes' if event['approve'] else 'No'}"
    if "pledges_revealed" in kinds:
        return "Crew pledges revealed"
    if "crew_selected" in kinds:
        return "Chairman proposes a crew"
    if len(current["private"].get("receipts", [])) > len(previous["private"].get("receipts", [])):
        return "Your private result arrives"
    if current["phase"] == "preparation" and current["revision"] != previous["revision"]:
        return "Private preparation"
    if len(current["private"]["submissions"]) > len(previous["private"]["submissions"]):
        kind = current["private"]["submissions"][-1]["action"]["type"]
        return {"pledge": "Your pledge is sealed", "contribute": "Your contribution is sealed",
                "report": "Your report is sealed", "prepare": "Your preparation choice is sealed",
                "audit": "Your inspection choice is sealed"}.get(kind, "Your decision is recorded")
    return "Table updated"


def designer_view(game, last_action, bot_decision=None):
    """Explicit inspection data, never attached to ordinary player frames."""
    return deepcopy({
        "players": [{"id": p.id, "team": p.team, "wallet": p.wallet,
                     "objective": p.objective.kind, "ability": p.ability, "ability_used": p.ability_used,
                     "result": game.frozen_result["players"][p.id] if game.frozen_result else None}
                    for p in game.players],
        "private_receipts": game.private_receipts,
        "sealed_submissions": game.pending,
        "last_action": last_action,
        "bot_decision": bot_decision,
        "last_resolution": game.resolutions[-1] if game.resolutions else None,
    })


class ReplayTimeline:
    def __init__(self, session, seat, designer=False):
        self.frames = []
        self.timeline = []
        game = Game.from_snapshot(session.initial)
        explanations = {entry["request_id"]: entry for entry in session.bot_decisions} if designer else {}
        previous = None
        for record in [None, *session.game.action_log]:
            if record:
                game.submit(**record)
            observation = game.observe(seat)
            # Sealed responses by another seat create no player-visible step.
            if not designer and observation == previous:
                continue
            label = frame_label(previous, observation)
            if designer and record and observation == previous:
                name = next(p.name for p in game.players if p.id == record["player_id"])
                label = f"{name} seals a {record['action']['type']} action"
            entry = {"step": len(self.frames), "attempt": observation["public"]["attempt"],
                     "mission": observation["public"]["mission"]["number"],
                     "phase": observation["phase"], "label": label}
            self.timeline.append(entry)
            self.frames.append({"observation": observation,
                                "designer": designer_view(game, record, explanations.get(record["request_id"]) if record else None)
                                if designer else None})
            previous = observation
        if game.snapshot() != session.game.snapshot():
            raise ValueError("This replay does not match its saved state")

    def at(self, step):
        if type(step) is not int or not 0 <= step < len(self.frames):
            raise ValueError("Replay step is outside the saved game")
        return deepcopy({**self.frames[step], "step": step, "total_steps": len(self.frames),
                         "timeline": self.timeline, "verified": True})
