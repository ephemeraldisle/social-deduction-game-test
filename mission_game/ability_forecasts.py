"""Counterfactuals for the bot's own card; never reads authoritative game state."""

from copy import deepcopy
from itertools import product

from .types import COLORS


def zero():
    return dict.fromkeys(COLORS, 0)


def pending_vote_income(observation):
    return (observation["public"]["rules"].get("vote_income", 0)
            if observation["phase"] in ("preparation", "select_crew", "pledge", "vote") else 0)


def choices(observation, crew, desired, beliefs):
    """Use our private card to plan future windows as well as the current one."""
    card = observation["private"]["ability"]
    kind = card["id"]
    if card.get("uses_remaining") == 0:
        return [None]
    me = observation["viewer"]
    players = observation["public"]["players"]
    wallet = next(p["wallet"] for p in players if p["id"] == me) + pending_vote_income(observation)
    if kind == "stowaway" and me not in crew and wallet:
        return [None, *({"color": c} for c in COLORS)]
    if kind == "recolorer":
        return [None, *({"from": a, "to": b} for a in COLORS for b in COLORS if a != b)]
    if kind != "thief":
        return [None]
    mission = [{"source": "mission", "tokens": dict(zip(COLORS, v))}
               for v in product(range(4), repeat=3) if 1 <= sum(v) <= 3]
    # Mission-vector choices are exhaustive. For wallets, shortlist the three
    # most promising public sources; no opponent's private commitment is read.
    pledges = observation["public"]["pledges"]
    def target_rank(p):
        balance = p["wallet"] + pending_vote_income(observation)
        retained = max(0, balance - sum(pledges.get(p["id"], {}).values())) if p["id"] in crew else balance
        blue = beliefs.estimate(p["id"])["blue_preference"]
        opponent = (1 - blue) if desired == "blue" else blue
        return retained, opponent, p["wallet"]
    targets = sorted((p for p in players if p["id"] != me and p["wallet"] + pending_vote_income(observation)), key=target_rank, reverse=True)[:3]
    wallets = [{"source": "wallet", "target": p["id"], "amount": n} for p in targets for n in range(1, 4)]
    return [None, *mission, *wallets]


def apply_own(observation, case, crew, own, choice):
    """Deposits, own bonus, own transfer or color change, then scoring upstream.

    Wallet and paid histories are separate: theft never funds a committed
    payment and Echo/recoloring never earn paid-deposit credit.
    """
    me, kind = observation["viewer"], observation["private"]["ability"]["id"]
    pot, paid, wallets = dict(case["pot"]), dict(case["paid"]), dict(case["wallets"])
    cost = 0
    original = zero()
    if me in crew:
        original = dict(own)
    elif kind == "stowaway" and choice:
        original[choice["color"]] = 1
    for c in COLORS:
        pot[c] += original[c]
        paid[c] += original[c]
    cost = sum(original.values())
    wallets[me] -= cost
    if wallets[me] < 0:
        raise ValueError("An ability forecast cannot spend future stolen tokens")
    if kind == "echo" and me in crew and cost >= 2 and sum(n > 0 for n in original.values()) == 1:
        pot[next(c for c in COLORS if original[c])] += 1
    transferred = 0
    if kind == "thief" and choice:
        if choice["source"] == "mission":
            for c in COLORS:
                amount = min(pot[c], choice["tokens"][c])
                pot[c] -= amount
                transferred += amount
        else:
            target = choice["target"]
            transferred = min(wallets[target], choice["amount"])
            wallets[target] -= transferred
        wallets[me] += transferred
    if kind == "recolorer" and choice and pot[choice["from"]]:
        pot[choice["from"]] -= 1
        pot[choice["to"]] += 1
    return {"pot": pot, "paid": paid, "wallet": wallets[me], "mass": case["mass"],
            "transferred": transferred, "ability_cost": cost - sum(own.values())}


class EffectEvidence:
    """Learn tentative net effects without a catalogue of other players' cards.

    Only cases with every crew payment independently known are used to predict
    colored residuals. Unknown off-crew actions can still explain the residual;
    this is never a certified ability identity or an accusation of dishonesty.
    """
    def __init__(self):
        self.cursor = 0
        self.pot = zero()
        self.crew = []
        self.wallets = {f"p{i}": 5 for i in range(8)}
        self.attempts = {}

    def observe(self, observation):
        if not observation["public"]["rules"].get("abilities_enabled"):
            return
        for event in observation["history"]:
            if event["id"] <= self.cursor:
                continue
            if event["type"] == "mission_drawn":
                self.pot = deepcopy(event["mission"]["pot"])
            elif event["type"] == "crew_selected":
                self.crew = list(event["crew"])
            elif event["type"] in ("income", "vote_income"):
                self.wallets = dict(event["wallets"])
            elif event["type"] == "attempt_resolved":
                self.attempts[str(event["attempt"])] = {
                    "attempt": event["attempt"], "event_id": event["id"],
                    "crew": [] if event["penalty"] else list(self.crew), "penalty": event["penalty"],
                    "before": dict(self.pot), "after": dict(event["mission"]["pot"]),
                    "created": sum(event["wallets"].values()) + sum(event["mission"]["pot"].values())
                               - sum(self.wallets.values()) - sum(self.pot.values())
                               - (observation["public"]["rules"]["rejection_red_tokens"] if event["penalty"] else 0),
                    "known": {}, "residual": None,
                }
                self.pot, self.wallets = dict(event["mission"]["pot"]), dict(event["wallets"])
            self.cursor = event["id"]
        me = observation["viewer"]
        receipts = observation["private"].get("receipts", [])
        for receipt in receipts:
            record = self.attempts.get(str(receipt["attempt"]))
            if record and receipt["type"] == "audit":
                record["known"][receipt["target"]] = dict(receipt["tokens"])
        own = observation["private"].get("last_contribution")
        if own and str(own["attempt"]) in self.attempts:
            self.attempts[str(own["attempt"])]["known"][me] = dict(own["tokens"])
        # Audit results arrive after resolution. Revisit saved visible contexts
        # so evidence learned in that later window is not lost.
        for record in self.attempts.values():
            if not record["crew"] or not all(pid in record["known"] for pid in record["crew"]):
                continue
            # An active own Recolorer has no truthful success receipt. Do not
            # misattribute its potentially changed token to somebody else.
            if observation["private"]["ability"]["id"] == "recolorer":
                continue
            deposited = {c: sum(v[c] for v in record["known"].values()) for c in COLORS}
            own_effect = zero()
            for receipt in receipts:
                if receipt["attempt"] != record["attempt"]:
                    continue
                if receipt["type"] == "echo":
                    own_effect[receipt["color"]] += receipt["amount"]
                elif receipt["type"] == "thief" and receipt["source"] == "mission":
                    for c in COLORS:
                        own_effect[c] -= receipt["tokens"][c]
            residual = {c: record["after"][c] - record["before"][c] - deposited[c] - own_effect[c] for c in COLORS}
            record["residual"] = residual

    def hypotheses(self, crew):
        groups = {}
        # Require the same crew and two matching independent attempts. This is
        # deliberately cautious: unverified reports never become training labels.
        for record in self.attempts.values():
            delta = record["residual"]
            if sorted(record["crew"]) != sorted(crew) or delta is None or not any(delta.values()):
                continue
            if sum(abs(n) for n in delta.values()) > 4:
                continue
            key = tuple(delta[c] for c in COLORS)
            groups.setdefault(key, []).append(record["event_id"])
        return [{"delta": dict(zip(COLORS, delta)), "evidence_events": events,
                 "confidence": min(.4, len(events) / (len(events) + 6)),
                 "interpretation": "Recurring net effect after verified crew payments; source and mechanism remain uncertain."}
                for delta, events in groups.items() if len(events) >= 2]

    def scenarios(self, case, crew):
        hypotheses = self.hypotheses(crew)
        if not hypotheses:
            return [case]
        hypothesis = max(hypotheses, key=lambda h: (len(h["evidence_events"]), tuple(h["delta"].values())))
        shifted = {c: case["pot"][c] + hypothesis["delta"][c] for c in COLORS}
        if min(shifted.values()) < 0:
            return [case]
        chance = hypothesis["confidence"]
        return [{**case, "mass": case["mass"] * (1 - chance)},
                {**case, "pot": shifted, "mass": case["mass"] * chance}]

    def snapshot(self):
        return deepcopy(vars(self))

    @classmethod
    def from_snapshot(cls, data):
        model = cls()
        if set(data) != set(vars(model)):
            raise ValueError("Unsupported effect-evidence snapshot")
        model.__dict__.update(deepcopy(data))
        return model
