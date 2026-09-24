"""Social bots that jointly plan their own payments and hidden abilities."""

from copy import deepcopy
from math import ceil, comb

from .social_baseline import (SocialPolicy as BaselinePolicy, SocialSettings, Traits,
                              approval_probability, vector, winner, COLORS)
from .ability_forecasts import EffectEvidence, apply_own, choices, pending_vote_income
from .beliefs import SocialBeliefs, AllegianceBeliefs, CooperativeBeliefs
from .bot_memory import EvidenceMemory
from .rng import tuple_tree
from .red_strategy import public_cover, continuation
from .coordination import NegotiationEvidence, race_probability

VERSION = "social.16"
COORDINATION_VERSIONS = ("social.13", "social.15", VERSION)
ALLEGIANCE_VERSIONS = ("social.11", "social.12", *COORDINATION_VERSIONS)


def belief_class(version):
    return CooperativeBeliefs if version in COORDINATION_VERSIONS else AllegianceBeliefs if version in ALLEGIANCE_VERSIONS else SocialBeliefs


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
        self.beliefs = CooperativeBeliefs()
        self.effects = EffectEvidence()
        self._case_cache = None
        self._extra = {}
        self._red_context = None
        self._negotiation = None
        self._rejection_cache = None
        self.sponsored = None

    def enabled(self, observation):
        return observation["public"]["rules"].get("abilities_enabled", False)

    def choose_action(self, observation):
        if observation["public"]["rules"].get("hidden_wallets"):
            from .hidden_policy import choose_action
            return choose_action(self, observation)
        belief_type = belief_class(self.version)
        if type(self.beliefs) is not belief_type:
            self.beliefs = belief_type.from_snapshot(self.beliefs.snapshot())
        self.effects.observe(observation, self.memory.own_deposits)
        self._case_cache = {}
        self._red_context = None
        self._negotiation = NegotiationEvidence(observation) if self.version in COORDINATION_VERSIONS else None
        self._rejection_cache = None
        try:
            action = super().choose_action(observation)
            if self._negotiation is not None and action["type"] in ("select_crew", "vote"):
                crew = action.get("crew", observation["public"]["crew"])
                d = self.last_decision["details"]
                d["negotiation"] = self._negotiation.describe(crew, d["advertised_pot"], observation["public"])
                if action["type"] == "select_crew":
                    self.sponsored = {"attempt": observation["public"]["attempt"], "crew": sorted(crew),
                                      "supported": d["self_supported"], "outcomes": d["outcome_likelihoods"]}
                    if not d["self_supported"]:
                        self.last_decision["reason"] += " No preferred candidate met my voting requirements; this is the best available proposal and needs better pledges."
                elif self.sponsored and observation["public"]["chairman"] == observation["viewer"] and (
                        self.sponsored["attempt"] == observation["public"]["attempt"]
                        and self.sponsored["crew"] == sorted(crew)):
                    d["sponsorship_review"] = {"before_pledges": deepcopy(self.sponsored["outcomes"]),
                                               "after_pledges": deepcopy(d["outcome_likelihoods"])}
                    if self.sponsored["supported"] and not action["approve"]:
                        side = self.memory.desired_side
                        before, after = self.sponsored["outcomes"][side], d["outcome_likelihoods"][side]
                        self.last_decision["reason"] += f" The revealed pledges changed my proposal's forecast: {side.title()} completion {before:.0%} to {after:.0%}, personal loss risk {d['outcome_likelihoods']['personal_loss']:.0%}."
            if self.version in ALLEGIANCE_VERSIONS:
                self.last_decision["details"]["known_teams"] = dict(self.beliefs.known_teams)
                players = [p["id"] for p in observation["public"]["players"]]
                if action["type"] == "select_crew" and self.crew_concerns(observation, players):
                    self.last_decision["reason"] = "Prioritized crews with the fewest confirmed Red players, then compared funding, votes, and my private objective."
            return action
        finally:
            self._case_cache = None
            self._red_context = None
            self._negotiation = None
            self._rejection_cache = None

    def red_context(self, observation):
        if self.version not in ("social.12", *COORDINATION_VERSIONS) or observation["private"]["team"] != "red":
            return None
        if self._red_context is None:
            context = public_cover(observation)
            if self._case_cache is not None:
                self._red_context = context
            return context
        return self._red_context

    def tactical_side(self, observation):
        if self.version not in COORDINATION_VERSIONS or observation["private"]["objective"]["id"] != "close_race":
            return super().tactical_side(observation)
        public, team = observation["public"], observation["private"]["team"]
        other = "red" if team == "blue" else "blue"
        target = public["rules"]["missions_to_win"] - 1
        # Reach our own match point before engineering the opponent's score.
        return other if public["score"][team] == target and public["score"][other] < target else team

    def protest(self, observation, crew, pot, demand):
        if self.version in COORDINATION_VERSIONS:
            return False  # Personality affects crew preference, never a seat veto.
        return super().protest(observation, crew, pot, demand)

    def objective_protest(self, observation, crew, pot, own, pledge):
        if self.version in COORDINATION_VERSIONS:
            public = observation["public"]
            other = "red" if self.memory.desired_side == "blue" else "blue"
            if public["rejections"] >= 2 or public["score"][other] == public["rules"]["missions_to_win"] - 1:
                return False
        return super().objective_protest(observation, crew, pot, own, pledge)

    def position_value(self, observation, completed=None):
        """Value a continuing race at match point on the terminal utility scale."""
        if self.version not in COORDINATION_VERSIONS:
            return 0.
        public = observation["public"]
        target = public["rules"]["missions_to_win"]
        if max(public["score"].values()) < target - 1:
            return 0.
        side = self.memory.desired_side
        other = "red" if side == "blue" else "blue"
        needed = target - public["score"][side] - (completed == side)
        opposing = target - public["score"][other] - (completed == other)
        chance = race_probability(needed, opposing)
        if observation["private"]["objective"]["id"] == "close_race":
            # Count only finishes with the required opposing score. Otherwise
            # the team-race heuristic would penalize necessary Close Race help.
            chance = (comb(needed + opposing - 2, needed - 1) / 2 ** (needed + opposing - 1)
                      if needed > 0 and opposing > 0 else float(needed == 0 and opposing == 1))
        return self.settings.terminal_weight * (2 * chance - 1)

    def objective_value(self, incentive):
        # Large rejection incomes must not make spending a wallet more valuable
        # than avoiding a loss. Actual terminal conditions are scored separately.
        value = self.settings.objective_weight * incentive
        if self.version not in COORDINATION_VERSIONS:
            return value
        limit = .3 * self.settings.terminal_weight
        return limit * value / (limit + abs(value)) if limit else 0.

    def rejection_forecast(self, observation):
        if self._rejection_cache is not None:
            return self._rejection_cache
        public, me = observation["public"], observation["viewer"]
        penalty, plan = self.evaluate(observation, [], vector(), {}, "contribute", penalty=True)
        if public["rejections"] == public["rules"]["rejection_limit"] - 1:
            value = penalty
        else:
            view = {**observation, "public": {**public, "rules": {**public["rules"], "income": 0}}}
            incentive = self.objective_incentive(view, public["mission"]["pot"], vector(), [], vector(),
                                                  wallet_after=self.wallet(observation, me) + pending_vote_income(observation), paid=vector())
            waiting = self.position_value(observation) + self.objective_value(incentive) - .5
            pressure = ((public["rejections"] + 1) / public["rules"]["rejection_limit"]) ** 2
            value = (1 - pressure) * waiting + pressure * penalty
        result = value, plan
        if self._case_cache is not None:
            self._rejection_cache = result
        return result

    def vote_assessment(self, observation, own, forecast, value, rejection):
        """One decision rule for proposed plans and the actual ballot."""
        public, me = observation["public"], observation["viewer"]
        crew, outcomes = public["crew"], forecast["outcome_likelihoods"]
        objective_protest = self.objective_protest(observation, crew, forecast["forecast_pot"], own,
                                                  public["pledges"].get(me, vector()))
        protest = outcomes["personal_win"] <= .5 and objective_protest
        allegiance = self.allegiance_objection(observation, crew, forecast)
        terminal_risk = outcomes["personal_loss"] > .5 and public["rejections"] < self.settings.protest_relax_at
        red_block = (outcomes["personal_win"] <= .5 and forecast["expected_objective_incentive"] <= 0
                     and self.tactical_side(observation) == "blue" and public["rejections"] < self.settings.protest_relax_at
                     and any(1 - self.beliefs.estimate(pid)["blue_preference"] >= self.settings.red_reject_threshold
                             for pid in crew if pid != me)
                     and not (outcomes["blue"] > .5 and value > rejection))
        no_progress = (outcomes["incomplete"] > .95 and forecast["expected_objective_incentive"] <= 0
                       and sum(forecast["forecast_pot"].values()) <= sum(public["mission"]["pot"].values())
                       and public["rejections"] < self.settings.protest_relax_at)
        side = self.tactical_side(observation)
        no_progress |= (outcomes[side] < 1e-9 and forecast["expected_objective_incentive"] <= 0
                        and forecast["forecast_pot"][side] <= public["mission"]["pot"][side]
                        and public["rejections"] < self.settings.protest_relax_at)
        others = [p for pid, p in forecast["vote_likelihoods"].items() if pid != me]
        needed = public["rules"]["approval_votes"]
        pivotal = approval_probability(others, needed - 1) - approval_probability(others, needed)
        cover = 0.
        opposition_cost = 0.
        context = self.red_context(observation)
        advertised = forecast["advertised_pot"]
        if (context is not None and context["public_exposure"] < .5
                and max(public["score"].values()) < public["rules"]["missions_to_win"] - 1
                and outcomes["personal_loss"] < .25
                and advertised["blue"] >= advertised["red"] and advertised["blue"] > 0):
            # A cover vote has political value even when it cannot change the
            # result. Vary investment by personality and remaining exposure.
            cover = (1 - context["public_exposure"]) * context["future_weight"] * (
                .75 + 2 * self.traits.caution + 1.5 * (1 - self.traits.skepticism))
            previous = self.beliefs.players[me].get("hostility_count", 0)
            if previous and self.beliefs.clean_blue_crew(crew, public["pledges"], public["mission"]["pot"],
                                                        public["mission"]["threshold"]):
                opposition_cost = ((1 - context["public_exposure"]) * context["future_weight"]
                                   * min(12, 3 + 3 * previous))
                cover += opposition_cost
        benefit = value - rejection
        approve = not protest and not allegiance and not terminal_risk and not red_block and not no_progress and (
            benefit > 0 or cover > 0 and pivotal * benefit + cover > 0)
        return {"approve": bool(approve), "objective_protest": objective_protest,
                "protest": bool(protest), "allegiance_target": allegiance, "terminal_risk": terminal_risk,
                "red_block": red_block, "no_progress": no_progress,
                "pivotal_likelihood": pivotal, "cover_vote_value": cover,
                "opposition_exposure_cost": opposition_cost}

    def complaint(self, observation, forecast, protest):
        if self.version not in COORDINATION_VERSIONS or protest:
            return super().complaint(observation, forecast, protest)
        public, me = observation["public"], observation["viewer"]
        gap = max(0, public["mission"]["threshold"] - sum(public["mission"]["pot"].values()))
        share = max(1, ceil(gap / max(1, len(public["crew"]))))
        options = []
        advertised = forecast["advertised_pot"]
        shortfall = max(0, public["mission"]["threshold"] - sum(advertised.values()))
        if shortfall:
            options.append((1 + shortfall / max(1, gap), {"modifier": "more", "color": "blue"},
                            "The expected funding falls short; I want more Blue funding."))
        if self.version == VERSION:
            # A public complaint needs a legible proposed change. 'Exact player
            # Blue' reads as an allegiance assertion, not a payment assurance.
            # Existing objections can justify a different coalition without
            # pretending that the accusation proves anyone's team.
            negotiation = self._negotiation or NegotiationEvidence(observation)
            objections = negotiation.describe(public["crew"], advertised, public)["active_objections"]
            for pid in public["crew"]:
                objectors = {entry["voter"] for entry in objections
                             if entry["target"] == pid and entry["voter"] != me}
                if (pid != me and objectors and not self.beliefs.established_blue(pid)
                        and self.beliefs.known_teams.get(pid) != "blue"):
                    options.append((.8 + .25 * min(3, len(objectors)), {"modifier": "less", "player_id": pid},
                                    f"Other voters still object to {pid}; replacing them could build support for this crew."))
            if public["mission"]["pot"]["red"] and advertised["red"]:
                margin_weight = .8 + advertised["red"] / max(1, advertised["blue"])
                options.extend([
                    (margin_weight, {"modifier": "less", "color": "red"},
                     "The pot already contains Red funding; I want its influence reduced."),
                    (margin_weight, {"modifier": "more", "color": "blue"},
                     "The existing Red funding needs a larger Blue margin.")])
        for pid in public["crew"]:
            if pid == me:
                continue
            pledge = public["pledges"].get(pid, vector())
            belief = self.beliefs.estimate(pid)
            reliability = belief["pledge_reliability"]
            suspicion = max(0, self.beliefs.prior - belief["blue_preference"])
            justified = not self.beliefs.established_blue(pid) or self.beliefs.grounded_objection(pid, public)
            if suspicion > .08 and justified:
                options.append((6 * suspicion, {"modifier": "less", "player_id": pid},
                                f"I want to replace {pid} because the observed evidence favors Red support."))
            if pledge["red"]:
                options.append((1.5, {"modifier": "less", "color": "red"}, "The proposal includes Red funding; I want less of it."))
                if self.version != VERSION:
                    options.append((1.5, {"modifier": "exact", "player_id": pid, "color": "blue"},
                                    f"I want {pid} to commit to Blue instead of the Red pledge."))
            needs_funding = shortfall or advertised["blue"] <= advertised["red"]
            if (pledge["blue"] < share and sum(pledge.values()) < self.wallet(observation, pid)
                    and (self.version != VERSION or needs_funding)):
                options.append((.8 + (share - pledge["blue"]) / share,
                                {"modifier": "more", "player_id": pid, "color": "blue"},
                                f"{pid} can afford more of this mission's Blue funding."))
            if self.version != VERSION and sum(pledge.values()) and reliability < .85:
                options.append(((1 - reliability) * (2 + 2 * self.traits.caution),
                                {"modifier": "exact", "player_id": pid, "color": "blue"},
                                f"I want assurance that {pid}'s Blue payment will match the promise."))
            if reliability < .6 and justified:
                options.append(((.75 - reliability) * (3 + 2 * self.traits.skepticism),
                                {"modifier": "less", "player_id": pid},
                                f"I want to replace {pid} because their promises have been unreliable."))
        if not options:
            return {"modifier": "more", "color": "blue"}, "I want a larger Blue margin before accepting this risk."
        best = max(weight for weight, _, _ in options)
        plausible = [option for option in options if option[0] >= .4 * best]
        if self.version == VERSION:
            # Preserve a concrete objection while avoiding an automatic chorus
            # when several equally useful public requests are available.
            recent = [c for vote in public["votes"] if not vote["approve"] for c in vote["complaints"]]
            plausible = [(weight / (1 + 2 * recent.count(complaint)), complaint, reason)
                         for weight, complaint, reason in plausible]
        _, complaint, reason = self.rng.choices(plausible, weights=[w for w, _, _ in plausible])[0]
        return complaint, reason

    def candidates(self, observation, crew=None):
        crew = observation["public"]["crew"] if crew is None else crew
        if self.enabled(observation) and observation["viewer"] not in crew:
            return [vector()]
        # Pledges must be affordable now; voting can plan the deposit available
        # after everyone receives revenue. The observation itself stays intact.
        budget_view = observation
        revenue = pending_vote_income(observation)
        if revenue and observation["phase"] in ("select_crew", "pledge", "vote"):
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

    def public_promise(self, observation, own):
        promise = super().public_promise(observation, own)
        # Plan the post-vote deposit, but never promise money not yet held.
        remaining = self.wallet(observation, observation["viewer"])
        affordable = vector()
        for color in COLORS:
            affordable[color] = min(promise[color], remaining)
            remaining -= affordable[color]
        return affordable

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
            promise = pledges.get(pid) if pledges is not None else (vector("blue", min(amount, self.wallet(observation, pid))) if self.version in COORDINATION_VERSIONS else None)
            if promise is not None:
                colored = promise["blue"] + promise["red"]
                if self.version in ALLEGIANCE_VERSIONS and colored:
                    # A fresh Blue promise is cheap talk. Trust in its color
                    # starts with inferred cooperation and must be earned by
                    # independently verified kept promises, not further claims.
                    kept_evidence = max(0., self.beliefs.players[pid]["kept"] - 3.)
                    alignment = (promise["blue"] * blue + promise["red"] * (1 - blue)) / colored
                    reliability *= (alignment + kept_evidence) / (1 + kept_evidence)
                amount = min(self.wallet(observation, pid) + revenue, sum(promise.values()))
                # A pledge is not a spending ceiling. An opponent can redirect
                # their whole wallet, including the imminent voting revenue.
                budget = self.wallet(observation, pid) + revenue
                options = [(promise, reliability), (vector(), (1 - reliability) * .3),
                           (vector("blue", amount), (1 - reliability) * .7 * blue),
                           (vector("red", budget), (1 - reliability) * .7 * (1 - blue))]
            else:
                options = [(vector("blue", amount), blue), (vector("red", amount), 1 - blue)]
            merged = {}
            for payment, mass in options:
                key_payment = tuple(payment[c] for c in COLORS)
                merged[key_payment] = merged.get(key_payment, 0.) + mass
            options = [(dict(zip(COLORS, payment)), mass) for payment, mass in merged.items()]
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

    def crew_concerns(self, observation, crew):
        """Private knowledge guides Blue; covert Red must maintain public cover."""
        if self.version not in ALLEGIANCE_VERSIONS:
            return []
        me = observation["viewer"]
        badges = observation["public"].get("public_badges", {})
        if observation["private"]["team"] == "blue":
            known = self.beliefs.known_teams
        elif badges.get(me) != "red":
            known = badges
        else:
            return []  # An exposed Red player no longer has a Blue cover to keep.
        return [pid for pid in crew if pid != me and known.get(pid) == "red"]

    def plan_rank(self, observation, score, forecast):
        rank = super().plan_rank(observation, score, forecast)
        if self.version in COORDINATION_VERSIONS and observation["action_spec"]["type"] == "select_crew":
            rank = (bool(forecast.get("self_supported")), *rank)
        if self.version in ALLEGIANCE_VERSIONS and observation["action_spec"]["type"] == "select_crew":
            # Minimize avoidable known-Red seats before optimizing private goals.
            # This also yields a legal crew if every candidate crew has a concern.
            return (-len(forecast.get("crew_allegiance_concerns", [])), *rank)
        return rank

    def allegiance_objection(self, observation, crew, forecast):
        concerns = self.crew_concerns(observation, crew)
        public = observation["public"]
        if (not concerns or public["rejections"] >= self.settings.protest_relax_at
                or forecast["outcome_likelihoods"]["personal_win"] >= .95):
            return None
        players = [p["id"] for p in public["players"]]
        alternatives = len(players) - len(self.crew_concerns(observation, players))
        unavoidable = max(0, len(crew) - alternatives)
        return concerns[0] if len(concerns) > unavoidable else None

    def predict_votes(self, observation, crew, pot, own, pledge, include_observed=True, outcomes=None, own_value=None):
        votes = self._predict_badge_votes(observation, crew, pot, own, pledge, include_observed, outcomes, own_value)
        if self.version in COORDINATION_VERSIONS:
            evidence = self._negotiation or NegotiationEvidence(observation)
            return evidence.adjust_votes(observation, crew, pot, votes, include_observed)
        return votes

    def _predict_badge_votes(self, observation, crew, pot, own, pledge, include_observed=True, outcomes=None, own_value=None):
        votes = super().predict_votes(observation, crew, pot, own, pledge, include_observed, outcomes, own_value)
        public = observation["public"]
        badges = public.get("public_badges", {})
        if (self.version not in ALLEGIANCE_VERSIONS or public["rejections"] >= self.settings.protest_relax_at
                or not any(badges.get(pid) == "red" for pid in crew)):
            return votes
        outcomes = outcomes if outcomes is not None else [(pot, 1.)]
        blue_win = sum(mass for result, mass in outcomes
                       if winner(result, public["mission"]["threshold"]) == "blue")
        if public["score"]["blue"] == public["rules"]["missions_to_win"] - 1 and blue_win >= .95:
            return votes
        observed = {v["player_id"] for v in public["votes"]} if include_observed else set()
        for pid in votes:
            if pid != observation["viewer"] and pid not in observed and badges.get(pid) != "red":
                # Everyone sees the badge; a Blue promise does not make this an
                # ordinary proposal. Private Scout receipts are not public facts.
                votes[pid] *= .25
        return votes

    def condition(self, observation, pot, own, crew, pledge, penalty=False, wallet_after=None, paid=None):
        kind = observation["private"]["objective"]["id"]
        if wallet_after is not None:
            if kind == "saver": return wallet_after >= 10
            if kind == "exact_change": return wallet_after == 7
            if kind == "spendthrift": return wallet_after == 0
        if paid is not None and kind == "opposition_patron":
            other = "red" if observation["private"]["team"] == "blue" else "blue"
            return self.patron_progress(other) + paid[other] >= 20
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
            progress = self.patron_progress(other)
            return .6 * (min(20, progress + paid[other]) - min(20, progress))
        return super().objective_incentive(observation, pot, own, crew, pledge, penalty, realized)

    def patron_progress(self, color):
        return self.beliefs.paid_estimate(color) if isinstance(self.beliefs, CooperativeBeliefs) else self.beliefs.paid[color]

    def objective_plan(self, observation):
        if observation["private"]["objective"]["id"] == "opposition_patron":
            other = "red" if observation["private"]["team"] == "blue" else "blue"
            return (f"Need 20 paid {other.title()} tokens across the table. Receipts confirm {self.beliefs.paid[other]:g}; "
                    f"discounted public outcomes suggest {self.patron_progress(other):g}, with hidden-effect uncertainty. "
                    "Avoid buying the condition again when the table has probably already supplied it.")
        return super().objective_plan(observation)

    def evaluate_cases(self, observation, cases, own, crew, pledge, choice, penalty=False):
        public = observation["public"]
        likelihoods = dict.fromkeys(("blue", "red", "incomplete", "personal_win", "personal_loss", "continues"), 0.)
        values = []
        incentive = satisfied = income = wallet = transfer = 0.
        mean, paid_mean = vector(), vector()
        context = self.red_context(observation)
        future = dict.fromkeys(("cover_value", "exposure_cost", "reserve_cost", "continuation_value"), 0.)
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
                value += self.objective_value(extra) + self.position_value(observation, completed)
                if observation["private"]["ability"]["id"] == "thief" and choice:
                    # Preserve the limited use unless spending it has a concrete
                    # tactical or objective benefit. Empty attempts still use it.
                    # Saving a one-use transfer matters, especially if the
                    # target tokens exist only in speculative payment cases.
                    target = public["rules"]["missions_to_win"]
                    value -= 1.5 + 2 * (target - max(public["score"].values())) / target
                    if choice["source"] == "wallet":
                        blue = self.beliefs.estimate(choice["target"])["blue_preference"]
                        alignment = blue if side == "blue" else 1 - blue
                        value += .15 * case["transferred"] * (1 - 2 * alignment)
                if context is not None:
                    adjustment = continuation(observation, context, case, own, crew, choice)
                    value += adjustment["continuation_value"]
                    for key in future:
                        future[key] += mass * adjustment[key]
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
            **({"red_strategy": {**context, **future}} if context is not None else {}),
            "expected_outcome_utility": expected, "risk_adjustment": risk,
            "expected_income": income, "condition_likelihood": satisfied,
            "expected_objective_incentive": incentive, "expected_wallet_after_effects": wallet,
            "expected_paid_deposits": paid_mean, "expected_transfer": transfer,
            "outcome_scenarios": [{"pot": dict(zip(COLORS, pot)), "likelihood": mass}
                                  for pot, mass in sorted(display.items(), key=lambda item: -item[1])]}

    def evaluate(self, observation, crew, own, pledges, phase, announced=None, penalty=False):
        if not self.enabled(observation) and self.version not in COORDINATION_VERSIONS:
            value, details = super().evaluate(observation, crew, own, pledges, phase, announced)
            if self.version in ALLEGIANCE_VERSIONS:
                details["crew_allegiance_concerns"] = self.crew_concerns(observation, crew)
            return value, details
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
        assessment = None
        if phase in ("select_crew", "pledge", "vote"):
            if self.version in COORDINATION_VERSIONS:
                promises = pledges if pledges is not None else {
                    pid: self.public_promise(observation, own) if pid == me else vector("blue", sum(deposits[pid].values())) for pid in crew}
                proposed = {**observation, "public": {**observation["public"], "crew": list(crew), "pledges": promises}}
                rejection, _ = self.rejection_forecast(observation)
                assessment = self.vote_assessment(proposed, own, {**uncertainty, "vote_likelihoods": votes,
                                                                 "advertised_pot": advertised}, utility, rejection)
                votes[me] = float(assessment["approve"])
            else:
                votes[me] = 0. if protest or self.allegiance_objection(observation, crew, uncertainty) else float(utility > 0)
        approval = approval_probability(votes.values())
        if phase in ("select_crew", "pledge"):
            utility = approval * (utility - self.position_value(observation)) - .5 * (1 - approval)
        if phase == "select_crew":
            utility += self.settings.inclusion_weight * self.traits.selfishness * (me in crew)
        elif phase == "contribute" and me in crew:
            promise = observation["public"]["pledges"][me]
            deviation = .3 * (1 - self.traits.selfishness) * sum(abs(own[c] - promise[c]) for c in COLORS)
            context = self.red_context(observation)
            if context is not None:
                # A cover story is not an unlimited debt to the opposing side.
                # Actual pledge-dependent objectives are scored separately.
                deviation = min(1., deviation) * (1 - context["public_exposure"])
            # No future reputation to protect after the game ends. Actual
            # pledge-dependent objectives are already scored in the outcome.
            deviation *= uncertainty["outcome_likelihoods"]["continues"]
            utility -= deviation
        return utility, {**uncertainty, "expected_deposits": {**deposits, **({me: own} if me in crew else {})},
            **({"crew_allegiance_concerns": self.crew_concerns(observation, crew)} if self.version in ALLEGIANCE_VERSIONS else {}),
            "vote_likelihoods": votes, "advertised_pot": advertised, "planned_deposit": own,
            "planned_ability": ability, "own_ability": observation["private"]["ability"]["id"],
            **({"pending_vote_income": pending_vote_income(observation)} if observation["public"]["rules"].get("vote_income") else {}),
            "ability_alternatives": [{"action": a, "utility": v} for v, a, _ in sorted(plans, key=rank, reverse=True)[:3]],
            "effect_hypotheses": self.effects.hypotheses(crew), "approval_likelihood": approval,
            **({"self_supported": assessment["approve"], "vote_assessment": assessment} if assessment is not None else {}),
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
            if "red_strategy" in self.last_decision["details"]:
                self.last_decision["reason"] += " Weighed public cover and reserves for future missions. Terminal outcomes receive no continuation bonus or cost."
        return action

    def _choose_action(self, observation):
        if (not self.enabled(observation) and self.version not in COORDINATION_VERSIONS) or observation["action_spec"]["type"] != "vote":
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
        objective_protest = self.objective_protest(observation, public["crew"], pot, own, public["pledges"].get(me, vector()))
        protest = not victory and (self.protest(observation, public["crew"], pot, self.traits.selfishness) or objective_protest)
        rejection, penalty_plan = 0., None
        if public["rules"].get("vote_income"):
            rejection_view = {**observation, "public": {**public, "rules": {**public["rules"], "income": 0}}}
            rejection = self.settings.objective_weight * self.objective_incentive(
                rejection_view, public["mission"]["pot"], vector(), [], vector(),
                wallet_after=self.wallet(observation, me) + pending_vote_income(observation), paid=vector())
        if public["rejections"] == 7:
            rejection, penalty_plan = self.evaluate(observation, [], vector(), {}, "contribute", penalty=True)
        if self.version in COORDINATION_VERSIONS:
            rejection, penalty_plan = self.rejection_forecast(observation)
        target = self.blue_target(observation, public["crew"])
        advancing = forecast["expected_objective_incentive"] > 0
        blue_block = (not victory and not advancing and self.tactical_side(observation) == "red" and target is not None
                      and self.beliefs.estimate(target)["blue_preference"] >= self.settings.blue_reject_threshold
                      and not (forecast["outcome_likelihoods"]["red"] > .5 and value > 0))
        red_block = (not victory and not advancing and self.tactical_side(observation) == "blue"
                     and public["rejections"] < self.settings.protest_relax_at
                     and any(1 - self.beliefs.estimate(pid)["blue_preference"] >= self.settings.red_reject_threshold for pid in public["crew"] if pid != me)
                     and not (forecast["outcome_likelihoods"]["blue"] > .5 and value > 0))
        allegiance_target = self.allegiance_objection(observation, public["crew"], forecast)
        terminal_risk = (self.version in COORDINATION_VERSIONS and forecast["outcome_likelihoods"]["personal_loss"] > .5
                         and public["rejections"] < self.settings.protest_relax_at)
        approve = not protest and not blue_block and not red_block and not allegiance_target and not terminal_risk and value > rejection
        if self.version in COORDINATION_VERSIONS:
            assessment = self.vote_assessment(observation, own, forecast, value, rejection)
            approve, protest = assessment["approve"], assessment["protest"]
            objective_protest, allegiance_target = assessment["objective_protest"], assessment["allegiance_target"]
            terminal_risk = assessment["terminal_risk"]
            blue_block, red_block = False, assessment["red_block"]
            forecast["vote_assessment"] = assessment
            forecast["self_supported"] = approve
        complaint, explanation = self.complaint(observation, forecast, protest) if not approve else (None, None)
        if allegiance_target:
            complaint = {"modifier": "less", "player_id": allegiance_target}
            source = "public badge" if public.get("public_badges", {}).get(allegiance_target) == "red" else "private Scout receipt"
            explanation = f"I want to replace {allegiance_target}: the {source} confirms Red, and another crew can avoid that risk."
        forecast["vote_likelihoods"][me] = float(approve)
        forecast["approval_likelihood"] = approval_probability(forecast["vote_likelihoods"].values())
        from dataclasses import asdict
        self.last_decision = {"reason": f"Voted {'Yes' if approve else 'No'} using my joint payment/ability forecast and the consequences of rejection.",
            "details": {**forecast, "traits": asdict(self.traits), "objective": observation["private"]["objective"]["id"],
                "desired_side": self.memory.desired_side, "tactical_side": self.tactical_side(observation),
                "objective_plan": self.objective_plan(observation), "concealing_red_intent": self.conceals_intent(observation),
                "beliefs": {pid: self.beliefs.estimate(pid) for pid in self.beliefs.players if pid != me},
                "new_evidence": deepcopy(self.beliefs.updates), "exclusion_protest": bool(protest),
                **({"objective_inclusion_protest": bool(objective_protest),
                    "suspected_blue_block": bool(blue_block), "suspected_red_block": bool(red_block),
                    "terminal_risk_objection": terminal_risk,
                    "accusation_target": complaint.get("player_id") if complaint and complaint.get("modifier") == "less" else None}
                   if self.version in COORDINATION_VERSIONS else {}),
                "rejection_value": rejection, "penalty_plan": penalty_plan, "complaint_reason": explanation},
            "limitations": self.limitations}
        if self.version in COORDINATION_VERSIONS and approve and value <= rejection:
            self.last_decision["reason"] += " Supported a plausible Blue proposal to preserve public cover, weighing how likely my ballot is to change the result."
        return {"type": "vote", "approve": approve, "complaints": [complaint] if complaint else []}

    def snapshot(self):
        return {**super().snapshot(), "effects": self.effects.snapshot(),
                **({"sponsored": deepcopy(self.sponsored)} if self.version in COORDINATION_VERSIONS else {})}

    @classmethod
    def from_snapshot(cls, data):
        if data["version"] not in (*COORDINATION_VERSIONS, "social.9", "social.10", "social.11", "social.12"):
            raise ValueError("Unsupported social policy version")
        policy = cls(traits=Traits(**data["traits"]), settings=data["settings"])
        policy.version = data["version"]
        policy.rng.setstate(tuple_tree(data["rng"]))
        policy.memory = EvidenceMemory.from_snapshot(data["memory"])
        belief_type = belief_class(data["version"])
        policy.beliefs = belief_type.from_snapshot(data["beliefs"])
        policy.effects = EffectEvidence.from_snapshot(data["effects"])
        if belief_type is CooperativeBeliefs and "public_paid_estimates" not in data["beliefs"]:
            # Existing current-policy tables learn the new evidence rules from
            # their own visible history on the next action, without a migration.
            policy.beliefs = CooperativeBeliefs()
            policy.effects = EffectEvidence()
        policy.sponsored = deepcopy(data.get("sponsored")) if data["version"] in COORDINATION_VERSIONS else None
        return policy
