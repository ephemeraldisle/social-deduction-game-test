"""Local trusted sessions and replay, with atomic JSON persistence."""

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from .engine import Game
from .config import GameConfig
from .objectives import condition_satisfied
from .policy import make_policy, restore_policy
from .types import Phase


def write_json(path, data):
    """Replace a snapshot atomically; newly written files are owner-readable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(data, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Session:
    def __init__(self, seed=0, config=None, human_seat=None, game_id=None, policy="social", policy_settings=None):
        if human_seat is not None and (type(human_seat) is not int or not 0 <= human_seat < 8):
            raise ValueError("human_seat must be an integer from 0 to 7")
        self.game = Game(seed, config=config or GameConfig.abilities(), game_id=game_id)
        self.initial = self.game.snapshot()
        self.human_id = f"p{human_seat}" if human_seat is not None else None
        self.session_version = 2
        self.bot_decisions = []  # Designer-only explanations, separate from engine events.
        self.agent_predictions = []  # Designer-only, externally recorded mission checkpoints.
        self.policies = {f"p{i}": make_policy(policy, seed, i, policy_settings) for i in range(8) if f"p{i}" != self.human_id}

    def step_bot(self):
        """Run one decision; stop when the human has a request in this batch."""
        requests = self.game.pending_requests()
        if not requests:
            return False
        if self.human_id in requests:
            action = self.game.automatic_action(self.human_id)
            if action is None:
                return False
            observation = self.game.observe(self.human_id)
            self.game.submit(self.human_id, observation["request_id"], observation["revision"], action)
            return True
        player_id = next(iter(requests))
        observation = self.game.observe(player_id)
        action = self.policies[player_id].choose_action(observation)
        self.game.submit(player_id, observation["request_id"], observation["revision"], action)
        policy = self.policies[player_id]
        if self.session_version >= 2 and getattr(policy, "last_decision", None):
            self.bot_decisions.append(deepcopy({"action_index": len(self.game.action_log) - 1,
                                               "player_id": player_id, "request_id": observation["request_id"],
                                               "policy_version": policy.version, **policy.last_decision}))
        return True

    def run(self):
        while self.step_bot():
            pass
        return self.game.status

    def snapshot(self):
        data = {"session_version": self.session_version, "initial": self.initial, "game": self.game.snapshot(),
                "human_id": self.human_id, "policies": {pid: policy.snapshot() for pid, policy in self.policies.items()}}
        if self.session_version >= 2:
            data["bot_decisions"] = deepcopy(self.bot_decisions)
            if self.agent_predictions:
                data["agent_predictions"] = deepcopy(self.agent_predictions)
        return data

    def save(self, path):
        write_json(path, self.snapshot())

    def upgrade_social_policies(self):
        """Opt in to current bots without changing any game actions or cards.

        Relearn from each seat's own evidence rather than carrying forward old
        interpretations of complaints. Preserve randomness and private memories.
        Callers are responsible for backing up the session before saving it.
        """
        from .social_policy import SocialPolicy, VERSION
        upgraded = []
        for pid, previous in self.policies.items():
            if not previous.version.startswith("social.") or previous.version == VERSION:
                continue
            policy = SocialPolicy(traits=previous.traits, settings=previous.settings)
            policy.rng.setstate(previous.rng.getstate())
            policy.memory = deepcopy(previous.memory)
            observation = self.game.observe(pid)
            policy.memory.observe(observation)
            policy.beliefs.observe(observation, policy.memory,
                                  report_weight=policy.settings.report_weight * (1 - .75 * policy.traits.skepticism),
                                  association_weight=policy.settings.association_weight,
                                  accusation_weight=policy.settings.accusation_weight)
            if hasattr(previous, "effects"):
                policy.effects = deepcopy(previous.effects)
            policy.effects.observe(observation)
            self.policies[pid] = policy
            upgraded.append(pid)
        return upgraded

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data["session_version"] not in (1, 2):
            raise ValueError("Unsupported session version")
        session = cls.__new__(cls)
        session.session_version = data["session_version"]
        session.bot_decisions = data["bot_decisions"] if session.session_version >= 2 else []
        session.agent_predictions = data.get("agent_predictions", [])
        session.initial = data["initial"]
        session.game = Game.from_snapshot(data["game"])
        session.human_id = data["human_id"]
        session.policies = {pid: restore_policy(policy) for pid, policy in data["policies"].items()}
        return session

    def replay(self):
        """Rebuild from the initial state and actions; never invoke policies."""
        replayed = Game.from_snapshot(self.initial)
        for record in self.game.action_log:
            replayed.submit(**record)
        if replayed.snapshot() != self.game.snapshot():
            raise ValueError("Replay diverged from the saved state")
        return replayed

    def metrics(self):
        game = self.game
        return {
            "game_id": game.game_id, "rules_version": game.config.rules_version,
            "mode": game.config.mode, "status": game.status,
            "policy_versions": sorted({policy.version for policy in self.policies.values()}),
            "winner": game.frozen_result["winner"] if game.phase == Phase.GAME_OVER else None,
            "blue_players": sum(p.team == "blue" for p in game.players),
            "abilities_enabled": game.config.abilities_enabled,
            "contrarian_present": any(p.objective.kind == "contrarian" for p in game.players),
            "attempts": len(game.resolutions), "missions": len(game.completed_missions),
            "mission_attempts": [m["attempts"] for m in game.completed_missions],
            "rejected_proposals": sum(r["rejections"] for r in game.resolutions),
            "penalty_attempts": sum(r["penalty"] for r in game.resolutions),
            "individual_winners": (sum(p["won"] for p in game.frozen_result["players"].values())
                                   if game.phase == Phase.GAME_OVER else 0),
            "actions": len(game.action_log), "score": dict(game.score),
            "objectives": [{"player_id": p.id, "objective": p.objective.kind, "team": p.team,
                            "won": game.frozen_result["players"][p.id]["won"],
                            "condition_satisfied": condition_satisfied(
                                p, game.score, game.resolutions, game.frozen_result["winner"], game.config.missions_to_win)}
                           for p in game.players] if game.phase == Phase.GAME_OVER else [],
        }
