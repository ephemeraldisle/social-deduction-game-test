"""Small ability heuristics using only a seat's own instructions and evidence."""

from .types import COLORS, Tokens


def remaining_green(observation):
    """Green Machine target from the official resolved table-wide counter."""
    private, public = observation["private"], observation["public"]
    if private["objective"]["id"] != "green_machine":
        return 0
    progress = private["objective"].get("progress", {})
    if progress.get("value") is not None:
        return max(0, 20 - progress["value"] - public.get("reserve", 0))
    known = progress.get("own_paid", 0)
    known += sum(r.get("amount", 1) for r in private.get("receipts", [])
                 if r["type"] == "echo" and r["color"] == "green")
    visible = sum(max(e.get("reserve_added", 0), e["mission"]["pot"]["green"] - e["previous_pot"]["green"])
                  for e in observation["history"] if e["type"] == "attempt_resolved")
    return max(0, 20 - max(known, visible) - public.get("reserve", 0))


def choose_ability(observation, rng, desired=None, random=False):
    spec = observation["action_spec"].get("ability")
    if not spec:
        return None
    public, private = observation["public"], observation["private"]
    me, kind = observation["viewer"], spec["id"]
    desired = desired or private["objective"].get("desired_winner", private["team"])
    other = "red" if desired == "blue" else "blue"
    if random and rng.random() < .35:
        return None
    if kind in ("scout", "auditor"):
        known = dict(public.get("public_badges", {}))
        known.update({r["target"]: r["team"] for r in private.get("receipts", []) if r["type"] == "scout"})
        targets = [p for p in spec["targets"] if p != me and (kind != "scout" or p not in known)]
        if kind == "scout" and not targets and not random:
            return None
        return {"target": rng.choice(targets or spec["targets"])}
    if kind == "switcher":
        objective = private["objective"]
        # The incoming card is unknown. Gamble only when our current condition
        # is still unmet and we have evidence that it is becoming difficult.
        if not random and (objective["id"] == "loyalist" or public["attempt"] < 3
                           or objective.get("progress", {}).get("condition_met") is True):
            return None
        return {"target": rng.choice(spec["targets"])}
    wallet = private["wallet"]
    objective = private["objective"]["id"]
    if kind == "stowaway":
        if not random and ((objective == "saver" and wallet <= 10) or (objective == "exact_change" and wallet <= 7)):
            return None
        color = "green" if remaining_green(observation) else desired
        return {"color": rng.choice(COLORS) if random else color}
    pot = dict(public["mission"]["pot"])
    if public["rejections"] == public["rules"]["rejection_limit"]:
        pot["red"] += public["rules"]["rejection_red_tokens"]
    else:
        pot["blue"] += sum(public["pledges"].values())
    pot["green"] += public.get("reserve", 0)
    if kind == "recolorer":
        if random:
            source, destination = rng.sample(COLORS, 2)
            return {"from": source, "to": destination}
        if remaining_green(observation):
            source = other if pot[other] else desired if pot[desired] > 1 else None
            if source:
                return {"from": source, "to": "green"}
        source = other if pot[other] else "green" if pot["green"] else None
        return {"from": source, "to": desired} if source else None
    if kind == "thief":
        if random:
            if rng.random() < .5:
                return {"source": "mission", "tokens": Tokens(**{rng.choice(COLORS): rng.randint(1, 3)}).to_dict()}
            return {"source": "wallet", "target": rng.choice(spec["targets"]), "amount": rng.randint(1, 3)}
        if objective == "spendthrift":
            return None
        if pot[other] and (max(public["score"].values()) >= 2 or pot[other] >= pot[desired]):
            return {"source": "mission", "tokens": Tokens(**{other: min(3, pot[other])}).to_dict()}
        if objective in ("saver", "exact_change") and wallet < (10 if objective == "saver" else 7):
            return {"source": "wallet", "target": rng.choice(spec["targets"]),
                    "amount": min(3, (10 if objective == "saver" else 7) - wallet)}
        return None
    return None


def ability_action(observation, rng, desired=None, random=False):
    """Return a standalone decision, or None for an ordinary crew decision."""
    spec = observation["action_spec"]
    kind = spec["type"]
    if kind in ("prepare", "audit"):
        return {"type": kind, "ability": choose_ability(observation, rng, desired, random)}
    if kind == "contribute" and spec.get("on_crew") is False:
        return {"type": kind, "tokens": Tokens().to_dict(),
                "ability": choose_ability(observation, rng, desired, random)}
    return None


def with_ability(action, observation, rng, desired=None, random=False):
    if action["type"] == "contribute" and "ability" in observation["action_spec"]:
        action["ability"] = choose_ability(observation, rng, desired, random)
    return action


def echo_payment(observation, paid):
    result = dict(paid)
    if (observation["private"]["ability"]["id"] == "echo"
            and sum(paid.values()) >= 2 and sum(n > 0 for n in paid.values()) == 1):
        result[next(c for c, n in paid.items() if n)] += 1
    return result
