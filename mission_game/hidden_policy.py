"""Small current-rules controller using private funds and uncertain public evidence.

No wallet reconstruction: a pledge is a claim, and an aggregate pot cannot
identify any player's original payment. Old exact-payment forecasts are unused.
"""

from dataclasses import asdict
from math import ceil

from .ability_policy import ability_action, remaining_green, with_ability
from .types import Tokens
from .vote_strategy import influence_plan, voting_evidence
from .social_evidence import information_target


def cover_report(observation):
    """Keep a Blue cover story within the visible increase, not the secret spend.

    This is a conservative limit for a fabricated claim, not an inference bound
    on real deposits: theft and recoloring can make truthful deposits exceed the
    net increase. Only this attempt's private audits reserve known Blue payments.
    """
    public, private = observation["public"], observation["private"]
    me, attempt = observation["viewer"], public["attempt"]
    result = next((e for e in reversed(observation["history"])
                   if e["type"] == "attempt_resolved" and e["attempt"] == attempt), None)
    blue_added = max(0, result["mission"]["pot"]["blue"] - result["previous_pot"]["blue"]) if result else 0
    audited = {r["target"]: r["tokens"]["blue"] for r in private.get("receipts", [])
               if r["type"] == "audit" and r["attempt"] == attempt
               and r["target"] != me and r["target"] in public["crew"]}
    known_blue = sum(audited.values())
    quantity = min(public["pledges"].get(me, 0), max(0, blue_added - known_blue))
    return ({"player_id": me, "verb": "gave", "quantity": quantity, "color": "blue"},
            {"blue_added": blue_added, "audited_other_blue": known_blue, "claimed_blue": quantity})


def choose_action(policy, observation, social=True):
    from .policy import truthful_statements

    policy.memory.observe(observation)
    public, private = observation["public"], observation["private"]
    me, spec = observation["viewer"], observation["action_spec"]
    kind, objective = spec["type"], private["objective"]["id"]
    desired = policy.memory.desired_side
    other = "red" if desired == "blue" else "blue"
    target = public["rules"]["missions_to_win"]
    # Secure our own match point before engineering the required close finish.
    if (objective == "close_race" and public["score"][other] < target - 1
            and public["score"][desired] == target - 1):
        desired, other = other, desired
    budget = private["wallet"]
    # Proposal income has already arrived before pledging and voting.
    payment_budget = budget
    voting = voting_evidence(observation, social=social, own_deposits=policy.memory.own_deposits)
    beliefs, inclusion = voting["beliefs"], voting["inclusion"]
    facts = voting["claims"]

    progress = private["objective"].get("progress", {})
    condition_met = progress.get("condition_met") is True
    green_needed = remaining_green(observation)
    pot = dict(public["mission"]["pot"])
    pot["green"] += public.get("reserve", 0)
    threshold = public["mission"]["threshold"]
    gap = max(0, threshold - sum(pot.values()))
    share = max(1, ceil(gap / public["mission"]["crew_size"]))
    keep = 10 if objective == "saver" else 7 if objective == "exact_change" else 0
    available = max(0, budget - keep)
    promise = min(available, share)
    if objective == "reliable_partner" and not condition_met:
        promise = min(budget, max(2, share))
    if objective == "passenger" and not condition_met:
        promise = 0

    def forecast(own, higher_payments=False):
        result = dict(pot)
        for pid, pledged in public["pledges"].items():
            if pid == me:
                continue
            # Team certainty is not payment certainty: even a confirmed Blue
            # player can currently want Red. Neither forecast knows a wallet.
            blue_share = voting["behavior"][pid] if social else 1.
            amount = pledged
            if higher_payments:
                # A sensitivity case, not an affordability bound or a promise:
                # players can exceed pledges using funds they retained.
                amount += max(1, .5 * pledged)
            result["blue"] += amount * blue_share
            result["red"] += amount * (1 - blue_share)
        for color, amount in own.items():
            result[color] += amount
        if private["ability"]["id"] == "echo" and sum(own.values()) >= 2 and sum(n > 0 for n in own.values()) == 1:
            result[next(c for c, n in own.items() if n)] += 1
        return result

    def winner(result):
        if sum(result.values()) < threshold or result["blue"] + result["red"] == 0:
            return None
        return "blue" if result["blue"] >= result["red"] else "red"

    def utility(paid):
        result = forecast(paid)
        won = winner(result)
        spent = sum(paid.values())
        balance = payment_budget - spent
        lead = result[desired] - result[other]
        value = (20 if won == desired else -25 if won else 0) + .5 * lead
        value += 2 * min(1, sum(result.values()) / threshold) - .15 * spent
        objective_weight = getattr(getattr(policy, "settings", None), "objective_weight", 5.)
        if objective == "saver":
            value += objective_weight * min(balance / 10, 1)
        elif objective == "exact_change":
            value -= objective_weight * abs(balance - 7) / 7
        elif objective == "spendthrift":
            value -= objective_weight * balance / max(1, payment_budget)
        elif objective == "reliable_partner" and not condition_met:
            if paid["blue"] >= 2 and paid["blue"] == public["pledges"].get(me) and paid["red"] == paid["green"] == 0:
                value += objective_weight * 2
        elif objective == "passenger" and not condition_met and spent == 0 and won:
            value += objective_weight * 2
        elif objective == "opposition_patron":
            opposing = "red" if private["team"] == "blue" else "blue"
            paid_so_far = progress.get("value")
            if paid_so_far is None:
                paid_so_far = progress.get("own_paid", 0)
            if paid_so_far < 20:
                value += objective_weight * min(paid[opposing], 20 - paid_so_far) / 10
        elif objective == "green_machine":
            green = paid["green"] + int(private["ability"]["id"] == "echo" and paid["green"] >= 2 and spent == paid["green"])
            value += objective_weight * min(green, green_needed) / 2
        return value

    def planned_payment():
        if me not in public["crew"]:
            return Tokens().to_dict()
        pledged = public["pledges"].get(me, promise)
        funds = max(0, payment_budget - keep)
        if not social:
            if green_needed:
                amount = min(funds, pledged)
                green = min(amount, green_needed)
                return Tokens(green=green, **{desired: amount - green}).to_dict()
            return Tokens(**{desired: min(funds, pledged)}).to_dict()
        # Small candidate set even when wallets grow over many rejected proposals.
        amounts = {0, min(payment_budget, pledged), min(payment_budget, share), funds, payment_budget}
        without = forecast(Tokens().to_dict())
        needed = max(1, ceil(threshold - sum(without.values())),
                     ceil(without[other] - without[desired]) + (desired == "red"))
        amounts.add(min(payment_budget, needed))
        candidates = [Tokens(**{color: amount}).to_dict() for color in (desired, "blue", "red") for amount in sorted(amounts)]
        if green_needed:
            green = min(funds, green_needed)
            candidates.extend(Tokens(green=min(amount, green_needed)).to_dict() for amount in amounts)
            # Preserve enough team color to win the mission while funding Green.
            colored = min(funds, max(1, ceil(without[other] - without[desired]) + int(desired == "red")))
            candidates.append(Tokens(green=min(green, funds - colored), **{desired: colored}).to_dict())
            candidates.append(Tokens(green=green, **{desired: funds - green}).to_dict())
        return max(candidates, key=utility)

    details = {"objective": objective, "desired_side": policy.memory.desired_side, "tactical_side": desired,
               "wallet": budget, "hidden_wallets": True}
    if social:
        details.update(traits=asdict(policy.traits), known_teams=voting["known_teams"], beliefs={pid: {
            "blue_preference": chance, "known_team": voting["known_teams"].get(pid),
            "behavioral_blue_preference": voting["behavior"][pid],
            "pledge_reliability": facts["reliability"][pid], "report_credibility": facts["credibility"][pid],
            "inclusion_demand": inclusion[pid], "evidence": voting["evidence"][pid]} for pid, chance in beliefs.items() if pid != me})
    reason = "Used my private ability instructions and available public evidence."
    ability = spec.get("ability")
    if social and ability and ability["id"] in ("auditor", "scout"):
        target_player = information_target(observation, voting, policy.rng)
        action = {"type": kind, "ability": {"target": target_player} if target_player else None}
        reason = ("Investigated a disputed payment or a consequential unknown team using my own evidence."
                  if target_player else "No unverified target needs this inspection.")
    else:
        action = ability_action(observation, policy.rng, desired)
    if action is None:
        if kind == "select_crew":
            candidates = list(spec["players"])
            policy.rng.shuffle(candidates)
            def rank(pid):
                affinity = beliefs[pid] if desired == "blue" else 1 - beliefs[pid]
                demand = .2 * inclusion[pid]
                risk = 0
                if social and desired == "blue":
                    demand *= max(0., 2 * beliefs[pid] - 1) * facts["credibility"][pid]
                    risk = .5 * facts["concerns"].get(pid, {}).get("strength", 0)
                return (2 if pid == me else 0) + affinity + demand - risk
            candidates.sort(key=rank, reverse=True)
            action = {"type": kind, "crew": candidates[:spec["crew_size"]]}
            reason = "Selected using known teams, verified payments, claim credibility, and uncertain shared evidence; inclusion requests need earned trust."
        elif kind == "pledge":
            action = {"type": kind, "quantity": promise}
            reason = "Pledged an affordable quantity, publicly assumed Blue, considering my private objective."
        elif kind == "contribute":
            paid = planned_payment()
            action = {"type": kind, "tokens": paid}
            details["forecast_pot"] = forecast(paid)
            reason = "Chose a secret payment using my own budget, uncertain pledges, and personal objective."
        elif kind == "vote":
            paid = planned_payment()
            result = forecast(paid)
            higher = forecast(paid, higher_payments=True)
            won = winner(result)
            higher_winner = winner(higher)
            improvement = result[desired] - result[other] - (pot[desired] - pot[other])
            recovery = won is None and improvement > 0 and higher_winner != other
            approve = won == desired if won else result[desired] >= result[other]
            # A persistent pot can be recovered in stages. A useful crew need
            # not reverse the entire existing deficit in a single attempt.
            if recovery:
                approve = True
            # Red can maintain cover while retaining money for a later decisive deposit.
            if desired == "red" and won is None:
                approve = True
            wants_crew = (objective in ("passenger", "reliable_partner", "spendthrift") and not condition_met) or green_needed > 0
            protest = social and wants_crew and me not in public["crew"] and public["rejections"] < 5
            if protest:
                approve = False
            suspect = None
            if social and desired == "blue":
                risky = [pid for pid in public["crew"] if pid != me
                         and facts["concerns"].get(pid, {}).get("strength", 0) >= .75]
                suspect = max(risky, key=lambda pid: facts["concerns"][pid]["strength"], default=None)
                # A known opponent/verified liar deserves a replacement when
                # one exists. Still accept a favorable funded mission and
                # relax before repeated rejections trigger the Red penalty.
                cautious = dict(pot)
                for color, amount in paid.items():
                    cautious[color] += amount
                cautious["red"] += sum(n for pid, n in public["pledges"].items() if pid != me)
                alternatives = [pid for pid in beliefs if pid not in public["crew"]
                                and beliefs[pid] >= .55
                                and facts["concerns"].get(pid, {}).get("strength", 0) < .75]
                if suspect and alternatives and public["rejections"] < 5 and winner(cautious) != "blue":
                    approve = False
            if public["rejections"] >= 6 and won != other and desired == "blue":
                approve = True
            loss_risk = other in (won, higher_winner) and public["score"][other] >= target - 1
            if loss_risk:
                # Cover, seat requests, and rejection pressure must not endorse
                # a plausible game-ending loss just below a pledge threshold.
                approve = False
            complaint = ({"modifier": "less", "player_id": suspect} if suspect else
                         {"modifier": "more", "player_id": me} if protest else {"modifier": "more", "color": "blue"})
            urgent = any(side and public["score"][side] >= target - 1 for side in (won, higher_winner))
            # Rejected missions need no deposit. Saving the game takes priority
            # over a wallet target that can be rebuilt on later attempts.
            protected_wallet = 0 if not approve and urgent else keep
            limit = max(0, budget - protected_wallet)
            cover_only = approve and desired == "red" and improvement <= 0 and desired not in (won, higher_winner)
            if cover_only:
                limit = 0  # Concealment does not justify buying the other side's progress.
            if approve and me in public["crew"]:
                def safe_spending(amount):
                    usable = max(0, budget - amount - keep)
                    reduced = Tokens().to_dict()
                    for color in (desired, "green", other):
                        reduced[color] = min(paid[color], usable)
                        usable -= reduced[color]
                    after = forecast(reduced)
                    after["green"] += (public.get("reserve_credit", 0) + amount) // 10
                    if objective == "reliable_partner" and not condition_met and reduced != paid:
                        return False
                    if won == desired:
                        return winner(after) == desired
                    return (winner(after) != other and sum(after.values()) >= sum(result.values())
                            and after[desired] - after[other] >= min(0, result[desired] - result[other]))

                low, high = 0, limit
                while low < high:
                    middle = (low + high + 1) // 2
                    if safe_spending(middle):
                        low = middle
                    else:
                        high = middle - 1
                limit = low
            influence, plan = influence_plan(observation, approve, result, voting, limit, urgent)
            action = {"type": kind, "approve": approve, "influence": influence,
                      "complaints": [] if approve else [complaint]}
            details.update(forecast_pot=result, higher_payment_forecast=higher,
                           terminal_loss_risk=loss_risk, recovery_proposal=recovery,
                           planned_payment=paid, cover_only=cover_only,
                           vote_spending=influence, vote_plan=plan,
                           vote_likelihoods=plan["vote_likelihoods"],
                           approval_likelihood=plan["success_after"] if approve else 1 - plan["success_after"])
            outcome = "approve" if approve else "reject"
            if influence:
                reason = (f"Spent {influence} tokens to {outcome} this crew: estimated vote success "
                          f"{plan['success_before']:.1%} → {plan['success_after']:.1%}. "
                          + ("All other ballots are already cast." if plan["settled"] else
                             "Allowed for remaining voters and plausible counter-spending; their wallets are hidden."))
            else:
                reason = (f"Voted to {outcome} this crew without spending: "
                          + ("the vote forecast already meets the confidence target." if plan["success_before"] >= plan["target_confidence"] else
                             "no affordable bid is worth its cost while preserving necessary funding."))
            if loss_risk:
                reason += " Rejected a plausible terminal loss when payments exceed the pledges."
            elif approve and recovery:
                reason += " This crew improves our position in the persistent pot without a forecast opposing completion."
            elif cover_only:
                reason += " Kept cover without paying to accelerate the opposing side."
            if suspect and not approve:
                name = next(p["name"] for p in public["players"] if p["id"] == suspect)
                reason += f" Asked for less {name}: {facts['concerns'][suspect]['reason']}."

        elif kind == "report":
            statements = truthful_statements(observation)
            reason = "Reported my original payment accurately. Reports remain unverified claims."
            if social and private["last_contribution"]["tokens"]["red"]:
                statement, details["report_cover"] = cover_report(observation)
                statements = [statement]
                reason = "Kept my Blue cover claim within my pledge and this attempt's visible Blue increase, allowing for other deposits I audited."
            action = {"type": kind, "statements": statements}
        else:
            raise ValueError(f"Unsupported decision: {kind}")
        action = with_ability(action, observation, policy.rng, desired)
    policy.last_decision = {"reason": reason, "details": details, "limitations": [
        "Other wallets and individual payments are hidden; pledges are uncertain promises.",
        "Aggregate outcomes provide weak shared evidence, not exact individual contributions.",
        "Forecasts and influence spending use short-horizon heuristics, not optimal play."]}
    return action
