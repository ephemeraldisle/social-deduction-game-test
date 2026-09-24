"""Versioned scripted controllers: a random diagnostic and a simple baseline.

The only decision input is a seat's observation. Each instance owns an isolated
random stream. It knows no other cards and never receives a Game reference.
"""

from .bot_memory import EvidenceMemory
from .ability_policy import ability_action, with_ability
from .rng import stream, tuple_tree
from .types import Tokens

POLICY_VERSION = "random-legal.4"
STRAIGHTFORWARD_VERSION = "straightforward.5"
POLICY_NAMES = ("social", "straightforward", "random")


class RandomLegalPolicy:
    version = POLICY_VERSION

    def __init__(self, seed=0, seat=0):
        self.rng = stream(seed, f"policy:{seat}")

    def choose_action(self, observation):
        extra = ability_action(observation, self.rng, random=True)
        if extra is not None:
            return extra
        spec = observation["action_spec"]
        kind = spec["type"]
        if kind == "select_crew":
            return {"type": kind, "crew": self.rng.sample(spec["players"], spec["crew_size"])}
        if kind == "pledge":
            return {"type": kind, "quantity": self.rng.randint(0, spec["max_total"])}
        if kind == "contribute":
            total = self.rng.randint(0, spec["max_total"])
            # Uniform compositions conditional on total, symmetric in colors.
            first, second = sorted(self.rng.sample(range(total + 2), 2))
            return with_ability({"type": kind, "tokens": {"blue": first, "red": second - first - 1,
                                               "green": total + 1 - second}}, observation, self.rng, random=True)
        if kind == "vote":
            approve = self.rng.random() < 0.7
            return {"type": kind, "approve": approve, "influence": self.rng.randint(0, spec["max_influence"]),
                    "complaints": [] if approve else [{"modifier": "more", "color": observation["private"]["team"]}]}
        if kind == "report":
            statements = truthful_statements(observation) if spec["min_statements"] else []
            return {"type": kind, "statements": statements}
        raise ValueError(f"Unsupported decision: {kind}")

    def snapshot(self):
        return {"version": self.version, "rng": self.rng.getstate()}

    @classmethod
    def from_snapshot(cls, data):
        if data["version"] not in (POLICY_VERSION, "random-legal.2"):
            raise ValueError("Unsupported policy version")
        policy = cls()
        policy.version = data["version"]
        policy.rng.setstate(tuple_tree(data["rng"]))
        return policy


class StraightforwardPolicy:
    """Simple pledge-based forecasts using private funds and ability heuristics."""

    version = STRAIGHTFORWARD_VERSION

    def __init__(self, seed=0, seat=0):
        self.rng = stream(seed, f"policy:{seat}")
        self.memory = EvidenceMemory()
        self.last_decision = None

    def choose_action(self, observation):
        from .hidden_policy import choose_action
        return choose_action(self, observation, social=False)

    def snapshot(self):
        return {"version": self.version, "rng": self.rng.getstate(), "memory": self.memory.snapshot()}

    @classmethod
    def from_snapshot(cls, data):
        if data["version"] not in (cls.version, "straightforward.4", "straightforward.2"):
            raise ValueError("Unsupported policy version")
        policy = cls()
        policy.version = data["version"]
        policy.rng.setstate(tuple_tree(data["rng"]))
        policy.memory = EvidenceMemory.from_snapshot(data["memory"])
        return policy


def make_policy(name, seed=0, seat=0, settings=None):
    if name == "social":
        from .social_policy import SocialPolicy
        return SocialPolicy(seed, seat, settings=settings)
    if settings is not None:
        raise ValueError("Only the social policy accepts custom settings")
    classes = {"random": RandomLegalPolicy, "straightforward": StraightforwardPolicy}
    if name not in classes:
        raise ValueError(f"Unknown policy: {name}")
    return classes[name](seed, seat)


def restore_policy(data):
    from .social_policy import SocialPolicy
    if data["version"] in (SocialPolicy.version, "social.9", "social.10", "social.11", "social.12", "social.13", "social.15"):
        return SocialPolicy.from_snapshot(data)
    if data["version"] in ("social.7", "social.8"):
        from .social_baseline import SocialPolicy as PreviousSocialPolicy
        return PreviousSocialPolicy.from_snapshot(data)
    classes = {POLICY_VERSION: RandomLegalPolicy, "random-legal.2": RandomLegalPolicy,
               STRAIGHTFORWARD_VERSION: StraightforwardPolicy, "straightforward.4": StraightforwardPolicy,
               "straightforward.2": StraightforwardPolicy}
    if data["version"] not in classes:
        raise ValueError("Unsupported policy version")
    return classes[data["version"]].from_snapshot(data)


def truthful_statements(observation):
    contribution = observation["private"]["last_contribution"]
    if not contribution or contribution["attempt"] != observation["public"]["attempt"]:
        return []
    statements = [{"player_id": observation["viewer"], "verb": "gave", "quantity": amount, "color": color}
                  for color, amount in contribution["tokens"].items() if amount]
    return statements or [{"player_id": observation["viewer"], "verb": "gave", "quantity": 0, "color": "blue"}]
