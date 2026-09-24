"""Vote bidding and social evidence from public actions, never hidden wallets."""

from collections import defaultdict
from math import ceil

from .social_evidence import claim_evidence


def voting_evidence(observation, social=True, own_deposits=None):
    public, private = observation["public"], observation["private"]
    known = dict(public.get("public_badges", {}))
    known.update({r["target"]: r["team"] for r in private.get("receipts", []) if r["type"] == "scout"})
    known[observation["viewer"]] = private["team"]
    # Behavior may change with objectives. A confirmed team never does.
    beliefs = {p["id"]: 1. if known.get(p["id"]) == "blue" else 0. if known.get(p["id"]) == "red" else .625
               for p in public["players"]}
    behavior = dict(beliefs)
    inclusion = dict.fromkeys(beliefs, 0.)
    evidence = {pid: [] for pid in beliefs}
    spending = {pid: [] for pid in beliefs}
    bonuses = dict.fromkeys(beliefs, 0)
    crew, pledges, ballots = [], {}, []
    pot = {"blue": 0, "red": 0, "green": 0}

    def update(vote, blue, confidence, event, context, hindsight=False):
        if not confidence:
            return
        pid, paid = vote["player_id"], vote.get("influence", 0)
        # An automatic ability bonus says nothing about willingness to sacrifice.
        strength = (.035 + (.5 if hindsight else .3) * paid / (paid + 10)) * confidence
        if not vote["approve"] and any(c.get("player_id") == pid and c.get("modifier") == "more"
                                       for c in vote.get("complaints", [])):
            strength *= .25  # Wanting a seat is weaker allegiance evidence.
        favored_blue = blue if vote["approve"] else 1 - blue
        behavior[pid] = max(.03, min(.97, (1 - strength) * behavior[pid] + strength * favored_blue))
        if pid not in known:
            beliefs[pid] = behavior[pid]
        if paid:
            evidence[pid].append({"event_id": event["id"],
                "text": f"Spent {paid} tokens voting {'Yes' if vote['approve'] else 'No'} {context}; "
                        "costly support/opposition is evidence of preference, not proof of team."})

    for event in observation["history"]:
        kind = event["type"]
        if kind == "mission_drawn":
            pot = dict(event["mission"]["pot"])
        elif kind == "crew_selected":
            crew, pledges, ballots = event["crew"], {}, []
        elif kind == "pledges_revealed":
            pledges = event["pledges"]
        elif kind == "vote":
            pid = event["player_id"]
            spending[pid].append(event.get("influence", 0))
            bonuses[pid] = max(bonuses[pid], event.get("bonus", 0))
            ballots.append(event)
            for complaint in event.get("complaints", []):
                if complaint.get("player_id") == pid and complaint.get("modifier") == "more":
                    inclusion[pid] = 1.
            blue = pot["blue"] + sum(n * beliefs[p] for p, n in pledges.items())
            red = pot["red"] + sum(n * (1 - beliefs[p]) for p, n in pledges.items())
            confidence = min(1., 2 * abs(blue - red) / max(1, blue + red))
            update(event, .95 if blue > red else .05, confidence, event,
                   f"on a proposal estimated to favor {'Blue' if blue > red else 'Red'}")
        elif kind == "attempt_resolved":
            after, before = event["mission"]["pot"], event["previous_pot"]
            if crew and not event["penalty"]:
                blue_gain, red_gain = max(0, after["blue"] - before["blue"]), max(0, after["red"] - before["red"])
                colored = blue_gain + red_gain
                if social and colored:
                    for pid in crew:
                        behavior[pid] = .9 * behavior[pid] + .1 * blue_gain / colored
                        if pid not in known:
                            beliefs[pid] = behavior[pid]
                winner = event["mission"]["winner"]
                confidence = 1. if winner else abs(blue_gain - red_gain) / max(1, colored)
                blue = float(winner == "blue") if winner else blue_gain / max(1, colored)
                context = f"on the crew that later gave {winner.title()} the mission" if winner else "on the crew, reassessed against its revealed token changes"
                for vote in ballots:
                    update(vote, blue, confidence, event, context, hindsight=True)
            pot = dict(after)
    claims = claim_evidence(observation, known, own_deposits) if social else None
    if claims:
        for pid, (blue, red) in claims["support"].items():
            behavior[pid] = (2 * behavior[pid] + blue) / (2 + blue + red)
            if pid not in known:
                beliefs[pid] = behavior[pid]
            evidence[pid].extend(claims["evidence"][pid])
    return {"beliefs": beliefs, "behavior": behavior, "known_teams": known,
            "claims": claims, "inclusion": inclusion, "evidence": {p: e[-10:] for p, e in evidence.items()},
            "spending": {p: s[-8:] for p, s in spending.items()}, "bonuses": bonuses}


def influence_plan(observation, approve, forecast, evidence, limit, urgent=False):
    """Small discrete forecast of uncast ballots and plausible counter-bids.

    Each ballot is worth ten influence units. Comparing total units is exactly
    equivalent to comparing whole votes and then their remainders.
    Future spending is a forecast, never a guarantee about another wallet.
    """
    public, spec = observation["public"], observation["action_spec"]
    votes, me = public["votes"], observation["viewer"]
    margin = 10 + spec.get("vote_bonus", 0) + sum(
        (1 if v["approve"] == approve else -1) * (10 + v.get("influence", 0) + v.get("bonus", 0)) for v in votes)
    cast = {v["player_id"] for v in votes} | {me}
    remaining = [p["id"] for p in public["players"] if p["id"] not in cast]
    orientation = (forecast["blue"] - forecast["red"]) / max(1, forecast["blue"] + forecast["red"])
    distribution, likelihoods, future_bids = {0: 1.}, {}, {}
    for pid in remaining:
        yes = .5 + .44 * (2 * evidence["beliefs"][pid] - 1) * orientation
        yes += .08 if pid in public["crew"] else -.12 * evidence["inclusion"][pid]
        yes = max(.08, min(.92, yes))
        likelihoods[pid] = yes
        previous = evidence["spending"][pid]
        paid = [n for n in previous if n]
        bid = ceil((sum(paid) / len(paid) if paid else 5) * (1.5 if urgent else 1))
        willingness = max(.2, len(paid) / len(previous)) if previous else .5
        future_bids[pid] = {"bid": bid, "spending_chance": willingness}
        weight = 10 + evidence["bonuses"][pid]
        next_distribution = defaultdict(float)
        for existing, probability in distribution.items():
            for choice, choice_chance in ((True, yes), (False, 1 - yes)):
                sign = 1 if choice == approve else -1
                for spend, spend_chance in ((0, 1 - willingness), (bid, willingness)):
                    if probability and spend_chance:
                        next_distribution[existing + sign * (weight + spend)] += probability * choice_chance * spend_chance
        distribution = next_distribution
    threshold = int(approve)  # A complete tie rejects, so No only needs equality.
    requirements = defaultdict(float)
    for future, probability in distribution.items():
        requirements[max(0, threshold - margin - future)] += probability
    target = .99 if urgent else .95
    cumulative, required = 0., 0
    for amount, probability in sorted(requirements.items()):
        cumulative += probability
        required = amount
        if cumulative >= target - 1e-9:
            break
    worst_case = max(requirements)
    success = lambda amount: sum(p for needed, p in requirements.items() if needed <= amount)
    if not remaining:
        # With no future ballots, a successful affordable bid is an exact
        # decision, not a speculative purchase of a small probability gain.
        spend = worst_case if worst_case <= limit else 0
    else:
        # Wallet tokens can fund missions or later ballots. Price that cost
        # instead of draining a wallet for any positive improvement. Stop at
        # the confidence target; do not pay to insure negligible tail cases.
        stake = 120 if urgent else 40
        spend = max((0, *(amount for amount in requirements if amount <= limit)),
                    key=lambda amount: (stake * min(target, success(amount)) - amount, -amount))
    return spend, {"remaining_voters": len(remaining), "spending_limit": limit,
                   "target_confidence": target, "needed_for_target": required,
                   "success_before": success(0), "success_after": success(spend),
                   "success_at_limit": success(limit),
                   "confidence_value": (120 if urgent else 40) if remaining else None,
                   "vote_likelihoods": likelihoods, "counter_bid_estimates": future_bids,
                   "settled": not remaining, "forecast_covers_all_scenarios": spend >= worst_case}
