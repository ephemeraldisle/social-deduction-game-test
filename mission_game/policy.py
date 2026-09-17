"""Versioned scripted controllers: a random diagnostic and a simple baseline.

The only decision input is a seat's observation. Each instance owns an isolated
random stream. It knows no other cards and never receives a Game reference.
"""

from copy import deepcopy

from .bot_memory import EvidenceMemory
from .ability_policy import ability_action, with_ability
from .rng import stream, tuple_tree
from .types import Tokens, mission_winner

POLICY_VERSION = "random-legal.3"
STRAIGHTFORWARD_VERSION = "straightforward.3"
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
        if kind in ("pledge", "contribute"):
            total = self.rng.randint(0, spec["max_total"])
            # Uniform compositions conditional on total, symmetric in colors.
            first, second = sorted(self.rng.sample(range(total + 2), 2))
            return with_ability({"type": kind, "tokens": {"blue": first, "red": second - first - 1,
                                               "green": total + 1 - second}}, observation, self.rng, random=True)
        if kind == "vote":
            approve = self.rng.random() < 0.7
            return {"type": kind, "approve": approve,
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
    """Section 12.4's contribution baseline, extended with private ability heuristics.

    Memory records visible evidence, but this policy does not infer trust or
    use that evidence to rank players. Additional personal conditions are not
    optimized. These deliberate limitations belong in designer diagnostics.
    """

    version = STRAIGHTFORWARD_VERSION
    limitations = ["Additional personal conditions are not optimized.",
                   "No trust or allegiance inference; recorded claims are not verified.",
                   "Forecasts assume pledges are honored; rejection pressure and hidden modifications are not modeled."]

    def __init__(self, seed=0, seat=0):
        self.rng = stream(seed, f"policy:{seat}")
        self.memory = EvidenceMemory()
        self.last_decision = None

    def choose_action(self, observation):
        self.memory.observe(observation)
        public, private = observation["public"], observation["private"]
        spec = observation["action_spec"]
        kind = spec["type"]
        desired = self.memory.desired_side
        other = "red" if desired == "blue" else "blue"
        details = {"allegiance": private["team"], "objective": private["objective"]["id"],
                   "desired_side": desired}
        extra = ability_action(observation, self.rng, desired)
        if extra is not None:
            self.last_decision = {"reason": "Used my own ability instructions and visible evidence, or passed.",
                                  "details": details, "limitations": self.limitations}
            return extra
        if kind == "select_crew":
            candidates = [p for p in public["players"] if p["id"] in spec["players"]]
            self.rng.shuffle(candidates)
            candidates.sort(key=lambda p: -p["wallet"])
            crew = [p["id"] for p in candidates[:spec["crew_size"]]]
            action = {"type": kind, "crew": crew}
            reason = "Selected the richest visible wallets; broke wallet ties with saved randomness."
            details["selected_wallets"] = {p["id"]: p["wallet"] for p in candidates[:spec["crew_size"]]}
        elif kind == "pledge":
            mission = public["mission"]
            pot = Tokens(**mission["pot"])
            gap = max(0, mission["threshold"] - pot.total)
            share = (gap + mission["crew_size"] - 1) // mission["crew_size"]
            if gap == 0 and pot.blue + pot.red == 0:
                share = 1
                reason = f"The funded pot is all Green; pledged one {desired.title()} token if affordable so it can complete."
            else:
                reason = f"Pledged an affordable share of the remaining funding in {desired.title()}, my desired winning color."
            amount = min(spec["max_total"], share)
            action = {"type": kind, "tokens": Tokens(**{desired: amount}).to_dict()}
            details.update(funding_gap=gap, fair_share=share, budget=spec["max_total"])
        elif kind == "vote":
            promised = Tokens()
            for vector in public["pledges"].values():
                promised += Tokens(**vector)
            forecast = Tokens(**public["mission"]["pot"]) + promised
            winner = mission_winner(forecast, public["mission"]["threshold"])
            if winner:
                approve = winner == desired
                reason = (f"Voted {'Yes' if approve else 'No'}: if pledges are honored, {winner.title()} wins this mission; "
                          f"my desired winner is {desired.title()}.")
            else:
                approve = promised.total > 0 and getattr(promised, desired) >= getattr(promised, other)
                reason = (f"Voted {'Yes' if approve else 'No'}: the forecast leaves the mission open. "
                          f"Pledged funding is {promised.total}, with {getattr(promised, desired)} {desired.title()} "
                          f"and {getattr(promised, other)} {other.title()} tokens.")
            action = {"type": kind, "approve": approve,
                      "complaints": [] if approve else [{"modifier": "more", "color": desired}]}
            details.update(forecast_pot=forecast.to_dict(), forecast_winner=winner,
                           promised=promised.to_dict(), rejections=public["rejections"])
        elif kind == "contribute":
            vector = Tokens(**public["pledges"][observation["viewer"]])
            if vector.total > spec["max_total"]:
                raise ValueError("Straightforward cannot honor this pledge with the current wallet")
            action = {"type": kind, "tokens": vector.to_dict()}
            reason = "Honored my accepted pledge exactly, including its colors."
        elif kind == "report":
            statements = truthful_statements(observation)
            action = {"type": kind, "statements": statements}
            reason = "Reported my original deposit accurately." if statements else "Passed: I have no original deposit to report this attempt."
        else:
            raise ValueError(f"Unsupported decision: {kind}")
        self.last_decision = deepcopy({"reason": reason, "details": details, "limitations": self.limitations})
        return with_ability(action, observation, self.rng, desired)

    def snapshot(self):
        return {"version": self.version, "rng": self.rng.getstate(), "memory": self.memory.snapshot()}

    @classmethod
    def from_snapshot(cls, data):
        if data["version"] not in (cls.version, "straightforward.2"):
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
    if data["version"] in (SocialPolicy.version, "social.9", "social.10", "social.11"):
        return SocialPolicy.from_snapshot(data)
    if data["version"] in ("social.7", "social.8"):
        from .social_baseline import SocialPolicy as PreviousSocialPolicy
        return PreviousSocialPolicy.from_snapshot(data)
    classes = {POLICY_VERSION: RandomLegalPolicy, "random-legal.2": RandomLegalPolicy,
               STRAIGHTFORWARD_VERSION: StraightforwardPolicy, "straightforward.2": StraightforwardPolicy}
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
