"""Social bots that jointly plan their own payments and hidden abilities."""

from copy import deepcopy
from math import ceil

from .social_baseline import (SocialPolicy as BaselinePolicy, SocialSettings, Traits,
                              approval_probability, vector, winner, COLORS)
from .ability_forecasts import EffectEvidence, apply_own, choices, pending_vote_income
from .beliefs import SocialBeliefs
from .bot_memory import EvidenceMemory
from .rng import tuple_tree

VERSION = "social.10"


class SocialPolicy(BaselinePolicy):
    version = VERSION
    limitations = [
        "Beliefs and vote likelihoods are heuristic estimates, not calibrated probabilities.",
        "Own payments and abilities are planned together; other players' payments remain uncertain.",
        "Other players' cards are hidden. Repeated residual effects are tentative predictions, not identified roles.",
        "Unknown ability interactions and future objective swaps are not exhaustively modeled.",
        "Wallet theft shortlists three public sources; objective and information values use short-horizon heuristics.",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.effects = EffectEvidence()
        self._case_cache = None
        self._extra = {}

    def enabled(self, observation):
        return observation["public"]["rules"].get("abilities_enabled", False)

    def choose_action(self, observation):
        self.effects.observe(observation)
        self._case_cache = {}
        try:
            return super().choose_action(observation)
        finally:
            self._case_cache = None

    def candidates(self, observation, crew=None):
        crew = observation["public"]["crew"] if crew is None else crew
        if self.enabled(observation) and observation["viewer"] not in crew:
            return [vector()]
        # Pledges must be affordable now; voting can plan the deposit available
        # after everyone receives revenue. The observation itself stays intact.
        budget_view = observation
        revenue = pending_vote_income(observation)
        if revenue and observation["phase"] in ("select_crew", "vote"):
            budget_view = {**observation, "public": {**observation["public"], "players": [
                {**p, "wallet": p["wallet"] + revenue} for p in observation["public"]["players"]]}}
        result = super().candidates(budget_view, crew)
        if not self.enabled(observation):
            return result
        # Ability swings and wallet gains can move the best payment a few
        # tokens away from the old funding/wallet breakpoints.
        if observation["private"]["ability"]["id"] in ("echo", "thief", "recolorer"):
            budget = self.wallet(budget_view, observation["viewer"])
            totals = {sum(v.values()) for v in result}
            amounts = {max(0, min(budget, n + offset)) for n in totals for offset in (-3, -2, -1, 1, 2, 3)}
            vectors = {tuple(v[c] for c in COLORS) for v in result}
            vectors.update(tuple(vector(c, n)[k] for k in COLORS) for n in amounts for c in COLORS)
            result = [dict(zip(COLORS, v)) for v in sorted(vectors)]
        return result

    def raw_cases(self, observation, crew, own, pledges, penalty=False):
        """Retain spending/source-wallet correlation for clipping wallet theft."""
        public, me = observation["public"], observation["viewer"]
        mission = public["mission"]
        gap = max(0, mission["threshold"] - sum(mission["pot"].values()))
        share = max(int(mission["pot"]["blue"] + mission["pot"]["red"] == 0), ceil(gap / max(1, len(crew))))
        if pledges is None and me in crew:
            share = max(int(mission["pot"]["blue"] + mission["pot"]["red"] + own["blue"] + own["red"] == 0),
                        ceil(max(0, gap - sum(own.values())) / max(1, len(crew) - 1)))
        key = (tuple(crew), share, penalty, tuple((pid, tuple(pledges[pid][c] for c in COLORS))
                                                for pid in crew if pledges and pid in pledges))
        if self._case_cache is not None and key in self._case_cache:
            return self._case_cache[key]
        pot = dict(mission["pot"])
        if penalty:
            pot["red"] += public["rules"]["rejection_red_tokens"]
        revenue = pending_vote_income(observation)
        cases = [{"pot": pot, "paid": vector(), "wallets": {p["id"]: p["wallet"] + revenue for p in public["players"]}, "mass": 1.}]
        deposits = {}
        for pid in crew:
            if pid == me:
                continue
            belief = self.beliefs.estimate(pid)
            blue = belief["blue_preference"]
            reliability = belief["pledge_reliability"] ** (1 + self.traits.skepticism)
            amount = min(self.wallet(observation, pid) + revenue, share)
            if pledges is not None and pid in pledges:
                promise = pledges[pid]
                amount = min(self.wallet(observation, pid) + revenue, sum(promise.values()))
                options = [(promise, reliability), (vector(), (1 - reliability) * .3),
                           (vector("blue", amount), (1 - reliability) * .7 * blue),
                           (vector("red", amount), (1 - reliability) * .7 * (1 - blue))]
            else:
                options = [(vector("blue", amount), blue), (vector("red", amount), 1 - blue)]
            deposits[pid] = {c: sum(v[c] * mass for v, mass in options) for c in COLORS}
            cases = [{"pot": {c: case["pot"][c] + paid[c] for c in COLORS},
                      "paid": {c: case["paid"][c] + paid[c] for c in COLORS},
                      "wallets": {**case["wallets"], pid: case["wallets"][pid] - sum(paid.values())},
                      "mass": case["mass"] * mass}
                     for case in cases for paid, mass in options if mass > 0]
        result = cases, deposits
        if self._case_cache is not None:
            self._case_cache[key] = result
        return result

    def condition(self, observation, pot, own, crew, pledge, penalty=False, wallet_after=None, paid=None):
        kind = observation["private"]["objective"]["id"]
        if wallet_after is not None:
            if kind == "saver": return wallet_after >= 10
            if kind == "exact_change": return wallet_after == 7
            if kind == "spendthrift": return wallet_after == 0
        if paid is not None and kind == "opposition_patron":
            other = "red" if observation["private"]["team"] == "blue" else "blue"
            return self.beliefs.paid[other] + paid[other] >= 20
        return super().condition(observation, pot, own, crew, pledge, penalty)

    def objective_incentive(self, observation, pot, own, crew, pledge, penalty=False, realized=False,
                            wallet_after=None, paid=None):
        if wallet_after is None:
            return super().objective_incentive(observation, pot, own, crew, pledge, penalty, realized)
        public, private, me = observation["public"], observation["private"], observation["viewer"]
        wallet = self.wallet(observation, me)
        after = wallet_after + self.expected_income(observation, pot)
        kind = private["objective"]["id"]
        if kind == "saver":
            protected = max(0, min(10, wallet) - wallet_after)
            return (min(10, after) - min(10, wallet)) / 2 - 2 * protected
        if kind == "exact_change": return 2 * (abs(wallet - 7) - abs(after - 7))
        if kind == "spendthrift": return (wallet - after) * (.7 + (.5 if max(public["score"].values()) == public["rules"]["missions_to_win"] - 1 else 0))
        if kind == "opposition_patron" and paid is not None:
            other = "red" if private["team"] == "blue" else "blue"
            return .6 * (min(20, self.beliefs.paid[other] + paid[other]) - min(20, self.beliefs.paid[other]))
        return super().objective_incentive(observation, pot, own, crew, pledge, penalty, realized)

    def evaluate_cases(self, observation, cases, own, crew, pledge, choice, penalty=False):
        public = observation["public"]
        likelihoods = dict.fromkeys(("blue", "red", "incomplete", "personal_win", "personal_loss", "continues"), 0.)
        values = []
        incentive = satisfied = income = wallet = transfer = 0.
        mean, paid_mean = vector(), vector()
        for case in cases:
            pot, mass = case["pot"], case["mass"]
            completed = winner(pot, public["mission"]["threshold"])
            condition = self.condition(observation, pot, own, crew, pledge, penalty, case["wallet"], case["paid"])
            extra = self.objective_incentive(observation, pot, own, crew, pledge, penalty, True, case["wallet"], case["paid"])
            terminal = completed and public["score"][completed] == public["rules"]["missions_to_win"] - 1
            likelihoods[completed or "incomplete"] += mass
            if terminal:
                won = completed == self.memory.desired_side and condition
                likelihoods["personal_win" if won else "personal_loss"] += mass
                value = self.settings.terminal_weight * (1 if won else -1)
            else:
                likelihoods["continues"] += mass
                side = self.tactical_side(observation)
                other = "red" if side == "blue" else "blue"
                progress = sum(pot.values()) - sum(public["mission"]["pot"].values())
                margin = (pot[side] - pot[other]) / max(1, sum(pot.values()))
                value = self.settings.funding_weight * min(1, progress / public["mission"]["threshold"]) * (1 if margin >= 0 else -1)
                value += self.settings.ownership_weight * margin
                if completed:
                    value += 4 if completed == side else -4
                value += self.settings.objective_weight * extra
                if observation["private"]["ability"]["id"] == "thief" and choice:
                    # Preserve the limited use unless spending it has a concrete
                    # tactical or objective benefit. Empty attempts still use it.
                    value -= .6
                    if choice["source"] == "wallet":
                        blue = self.beliefs.estimate(choice["target"])["blue_preference"]
                        alignment = blue if side == "blue" else 1 - blue
                        value += .15 * case["transferred"] * (1 - 2 * alignment)
            values.append((value, mass))
            incentive += mass * extra
            satisfied += mass * condition
            income += mass * self.expected_income(observation, pot)
            wallet += mass * case["wallet"]
            transfer += mass * case["transferred"]
            for c in COLORS:
                mean[c] += mass * pot[c]
                paid_mean[c] += mass * case["paid"][c]
        expected = sum(v * mass for v, mass in values)
        risk = .1 * self.traits.caution * sum(mass * max(0., expected - v) for v, mass in values)
        # Merge only display pots, after source-wallet and paid-history scoring.
        display = {}
        for case in cases:
            key = tuple(case["pot"][c] for c in COLORS)
            display[key] = display.get(key, 0.) + case["mass"]
        return expected - risk, {"forecast_pot": mean, "outcome_likelihoods": likelihoods,
            "expected_outcome_utility": expected, "risk_adjustment": risk,
            "expected_income": income, "condition_likelihood": satisfied,
            "expected_objective_incentive": incentive, "expected_wallet_after_effects": wallet,
            "expected_paid_deposits": paid_mean, "expected_transfer": transfer,
            "outcome_scenarios": [{"pot": dict(zip(COLORS, pot)), "likelihood": mass}
                                  for pot, mass in sorted(display.items(), key=lambda item: -item[1])]}

    def evaluate(self, observation, crew, own, pledges, phase, announced=None, penalty=False):
        if not self.enabled(observation):
            return super().evaluate(observation, crew, own, pledges, phase, announced)
        me = observation["viewer"]
        claim = self.public_promise(observation, own) if announced is None else announced
        pledge = (pledges or {}).get(me, claim)
        raw, deposits = self.raw_cases(observation, crew, own, pledges, penalty)
        plans = []
        for choice in choices(observation, crew, self.tactical_side(observation), self.beliefs):
            cases = [shifted for case in raw for shifted in self.effects.scenarios(
                apply_own(observation, case, crew, own, choice), crew)]
            value, details = self.evaluate_cases(observation, cases, own, crew, pledge, choice, penalty)
            plans.append((value, choice, details))
        side = self.tactical_side(observation)
        other = "red" if side == "blue" else "blue"
        def rank(plan):
            value, choice, details = plan
            return round(value, 10), details["forecast_pot"][side] - details["forecast_pot"][other], choice is None
        utility, ability, uncertainty = max(plans, key=rank)
        pot = uncertainty["forecast_pot"]
        # Other voters do not know my hidden ability or private plan. Their
        # forecast uses the public promise without my secret modifications.
        public_payment = (pledges or {}).get(me, claim) if me in crew else vector()
        advertised_cases = [({c: case["pot"][c] + public_payment[c] for c in COLORS}, case["mass"]) for case in raw]
        advertised = {c: sum(p[c] * mass for p, mass in advertised_cases) for c in COLORS}
        votes = self.predict_votes(observation, crew, advertised, own, pledge,
                                   include_observed=phase not in ("select_crew", "pledge"),
                                   outcomes=advertised_cases, own_value=utility)
        personal_win = uncertainty["outcome_likelihoods"]["personal_win"] > .5
        protest = not personal_win and (self.protest(observation, crew, pot, self.traits.selfishness)
                                        or self.objective_protest(observation, crew, pot, own, pledge))
        if phase in ("select_crew", "pledge", "vote"):
            votes[me] = 0. if protest else float(utility > 0)
        approval = approval_probability(votes.values())
        if phase in ("select_crew", "pledge"):
            utility = approval * utility - .5 * (1 - approval)
        if phase == "select_crew":
            utility += self.settings.inclusion_weight * self.traits.selfishness * (me in crew)
        elif phase == "contribute" and me in crew:
            promise = observation["public"]["pledges"][me]
            utility -= .3 * (1 - self.traits.selfishness) * sum(abs(own[c] - promise[c]) for c in COLORS)
        return utility, {**uncertainty, "expected_deposits": {**deposits, **({me: own} if me in crew else {})},
            "vote_likelihoods": votes, "advertised_pot": advertised, "planned_deposit": own,
            "planned_ability": ability, "own_ability": observation["private"]["ability"]["id"],
            **({"pending_vote_income": pending_vote_income(observation)} if observation["public"]["rules"].get("vote_income") else {}),
            "ability_alternatives": [{"action": a, "utility": v} for v, a, _ in sorted(plans, key=rank, reverse=True)[:3]],
            "effect_hypotheses": self.effects.hypotheses(crew), "approval_likelihood": approval,
            "objective_utility": utility, "wallet_after_deposit": self.wallet(observation, me) - sum(own.values())}

    def extra_action(self, observation):
        if not self.enabled(observation):
            return super().extra_action(observation)
        spec = observation["action_spec"]
        kind = spec["type"]
        self._extra = {}
        if kind == "contribute" and spec.get("on_crew") is False:
            public = observation["public"]
            _, details = self.evaluate(observation, public["crew"], vector(), public["pledges"], kind,
                                       penalty=not public["crew"])
            self._extra = details
            self._extra["ability_reason"] = "Compared my off-crew ability and passing using final mission totals, wallet, income, and objective."
            return {"type": kind, "tokens": vector(), "ability": details["planned_ability"]}
        if kind not in ("prepare", "audit"):
            return None
        choice = None
        rationale = "No ability choice is available in this private window."
        available = spec.get("ability")
        scores = {}
        if available and available["id"] in ("scout", "auditor"):
            for pid in available["targets"]:
                if pid == observation["viewer"]:
                    continue
                belief = self.beliefs.estimate(pid)
                if available["id"] == "scout":
                    if pid in self.beliefs.known_teams:
                        continue
                    # Allegiance uncertainty is separate from preference; even
                    # a strong behavioral signal can have an unknown team.
                    evidence = self.beliefs.players[pid]
                    uncertainty = 4 * belief["blue_preference"] * (1 - belief["blue_preference"])
                    relevance = 1 + self.wallet(observation, pid) / 5 + (pid == observation["public"]["chairman"])
                    scores[pid] = relevance * (.5 + uncertainty) / (1 + .03 * (evidence["blue"] + evidence["red"]))
                else:
                    last = self.beliefs.last_resolution or {}
                    if pid in last.get("known", {}):
                        continue
                    pledge = observation["public"]["pledges"].get(pid, vector())
                    ambiguity = 4 * belief["pledge_reliability"] * (1 - belief["pledge_reliability"])
                    scores[pid] = (1 + sum(pledge.values())) * (.5 + ambiguity)
                    # On a two-person crew, inspecting the other deposit also
                    # makes aggregate modifications distinguishable from lies.
                    if observation["viewer"] in observation["public"]["crew"]:
                        scores[pid] += 2
            if scores:
                best = max(scores.values())
                choice = {"target": self.rng.choice([pid for pid, score in scores.items() if abs(score - best) < 1e-9])}
                rationale = "Chose an unknown, relevant team inspection." if available["id"] == "scout" else "Chose an unverified crew payment with useful pledge evidence; use the receipt before judging reports."
            else:
                rationale = "Passed because the available information is already independently known."
        elif available and available["id"] == "switcher":
            private, public = observation["private"], observation["public"]
            objective = private["objective"]
            progress = objective.get("progress", {})
            wallet = self.wallet(observation, observation["viewer"])
            urgent = max(public["score"].values()) >= public["rules"]["missions_to_win"] - 1
            awkward_race = objective["id"] == "close_race" and public["score"][private["team"]] == public["rules"]["missions_to_win"] - 1 and public["score"]["red" if private["team"] == "blue" else "blue"] == 0
            difficult = ((objective["id"] == "saver" and wallet < 8)
                         or (objective["id"] == "exact_change" and wallet < 5)
                         or (objective["id"] == "reliable_partner" and (progress.get("value") or 0) == 0)
                         or (objective["id"] == "passenger" and not progress.get("condition_met")))
            if (objective["id"] != "loyalist" and progress.get("condition_met") is not True
                    and (awkward_race or urgent and difficult)):
                choice = {"target": self.rng.choice(available["targets"])}
                rationale = "Gambled on an unknown objective because my current condition is difficult near the finish; no target card was inspected."
            else:
                rationale = "Kept my current objective and saved the swap; there is no evidence the unknown replacement would be better."
        self._extra = {"ability_reason": rationale, "planned_ability": choice, "information_target_scores": scores}
        return {"type": kind, "ability": choice}

    def extra_reason(self):
        return self._extra.get("ability_reason", super().extra_reason())

    def extra_details(self):
        return self._extra

    def finalize_action(self, action, observation):
        if not self.enabled(observation):
            return super().finalize_action(action, observation)
        if action["type"] == "contribute":
            action["ability"] = deepcopy(self.last_decision["details"]["planned_ability"])
            self.last_decision["reason"] = "Compared joint payment and ability plans, including final wallet, funding, ownership, and paid-history objectives. " + self.last_decision["reason"]
        return action

    def _choose_action(self, observation):
        if not self.enabled(observation) or observation["action_spec"]["type"] != "vote":
            return super()._choose_action(observation)
        self.memory.observe(observation)
        self.beliefs.observe(observation, self.memory, report_weight=self.settings.report_weight * (1 - .75 * self.traits.skepticism),
                            association_weight=self.settings.association_weight, accusation_weight=self.settings.accusation_weight)
        public, me = observation["public"], observation["viewer"]
        plans = self.candidates(observation) if me in public["crew"] else [vector()]
        _, planned = max((self.evaluate(observation, public["crew"], own, public["pledges"], "contribute") for own in plans),
                         key=lambda p: self.plan_rank(observation, *p))
        own = planned["planned_deposit"]
        value, forecast = self.evaluate(observation, public["crew"], own, public["pledges"], "vote")
        pot = forecast["forecast_pot"]
        victory = forecast["outcome_likelihoods"]["personal_win"] > .5
        protest = not victory and (self.protest(observation, public["crew"], pot, self.traits.selfishness)
                                  or self.objective_protest(observation, public["crew"], pot, own, public["pledges"].get(me, vector())))
        rejection, penalty_plan = 0., None
        if public["rules"].get("vote_income"):
            rejection_view = {**observation, "public": {**public, "rules": {**public["rules"], "income": 0}}}
            rejection = self.settings.objective_weight * self.objective_incentive(
                rejection_view, public["mission"]["pot"], vector(), [], vector(),
                wallet_after=self.wallet(observation, me) + pending_vote_income(observation), paid=vector())
        if public["rejections"] == 7:
            rejection, penalty_plan = self.evaluate(observation, [], vector(), {}, "contribute", penalty=True)
        target = self.blue_target(observation, public["crew"])
        advancing = forecast["expected_objective_incentive"] > 0
        blue_block = (not victory and not advancing and self.tactical_side(observation) == "red" and target is not None
                      and self.beliefs.estimate(target)["blue_preference"] >= self.settings.blue_reject_threshold
                      and not (forecast["outcome_likelihoods"]["red"] > .5 and value > 0))
        red_block = (not victory and not advancing and self.tactical_side(observation) == "blue"
                     and public["rejections"] < self.settings.protest_relax_at
                     and any(1 - self.beliefs.estimate(pid)["blue_preference"] >= self.settings.red_reject_threshold for pid in public["crew"] if pid != me)
                     and not (forecast["outcome_likelihoods"]["blue"] > .5 and value > 0))
        approve = not protest and not blue_block and not red_block and value > rejection
        complaint, explanation = self.complaint(observation, forecast, protest) if not approve else (None, None)
        forecast["vote_likelihoods"][me] = float(approve)
        forecast["approval_likelihood"] = approval_probability(forecast["vote_likelihoods"].values())
        from dataclasses import asdict
        self.last_decision = {"reason": f"Voted {'Yes' if approve else 'No'} using my joint payment/ability forecast and the consequences of rejection.",
            "details": {**forecast, "traits": asdict(self.traits), "objective": observation["private"]["objective"]["id"],
                "desired_side": self.memory.desired_side, "tactical_side": self.tactical_side(observation),
                "objective_plan": self.objective_plan(observation), "concealing_red_intent": self.conceals_intent(observation),
                "beliefs": {pid: self.beliefs.estimate(pid) for pid in self.beliefs.players if pid != me},
                "new_evidence": deepcopy(self.beliefs.updates), "exclusion_protest": bool(protest),
                "rejection_value": rejection, "penalty_plan": penalty_plan, "complaint_reason": explanation},
            "limitations": self.limitations}
        return {"type": "vote", "approve": approve, "complaints": [complaint] if complaint else []}

    def snapshot(self):
        return {**super().snapshot(), "effects": self.effects.snapshot()}

    @classmethod
    def from_snapshot(cls, data):
        if data["version"] not in (VERSION, "social.9"):
            raise ValueError("Unsupported social policy version")
        policy = cls(traits=Traits(**data["traits"]), settings=data["settings"])
        policy.version = data["version"]
        policy.rng.setstate(tuple_tree(data["rng"]))
        policy.memory = EvidenceMemory.from_snapshot(data["memory"])
        policy.beliefs = SocialBeliefs.from_snapshot(data["beliefs"])
        policy.effects = EffectEvidence.from_snapshot(data["effects"])
        return policy
