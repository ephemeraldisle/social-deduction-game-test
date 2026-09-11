"""Preserved social.7/social.8 policy, also the shared social decision baseline."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from itertools import combinations
from math import ceil, floor, isfinite

from .ability_policy import ability_action, with_ability, echo_payment
from .beliefs import SocialBeliefs, bounded
from .bot_memory import EvidenceMemory
from .policy import truthful_statements
from .rng import stream, tuple_tree

VERSION = "social.8"
COLORS = ("blue", "red", "green")


@dataclass(frozen=True)
class SocialSettings:
    funding_weight: float = 2.0
    ownership_weight: float = 3.0
    objective_weight: float = 5.0
    terminal_weight: float = 100.0
    inclusion_weight: float = 2.0
    report_weight: float = .3
    association_weight: float = .2
    accusation_weight: float = .8
    blue_reject_threshold: float = .65
    red_reject_threshold: float = .65
    protest_threshold: float = .75
    protest_relax_at: int = 5

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError("Social policy settings must be finite nonnegative numbers")
        if not 0 <= self.protest_threshold <= 1 or type(self.protest_relax_at) is not int or not 0 <= self.protest_relax_at <= 7:
            raise ValueError("Use a protest threshold in 0..1 and an integer relaxation count in 0..7")
        if any(not 0 <= value <= 1 for value in (self.blue_reject_threshold, self.red_reject_threshold)):
            raise ValueError("Side rejection thresholds must be in 0..1")


@dataclass(frozen=True)
class Traits:
    selfishness: float
    caution: float
    skepticism: float

    def __post_init__(self):
        if any(type(v) not in (int, float) or not isfinite(v) or not 0 <= v <= 1 for v in asdict(self).values()):
            raise ValueError("Personality traits must be numbers in 0..1")


def vector(color=None, amount=0):
    return {c: amount if c == color else 0 for c in COLORS}


def winner(pot, threshold):
    if sum(pot.values()) + 1e-9 < threshold or pot["blue"] + pot["red"] <= 0:
        return None
    return "blue" if pot["blue"] >= pot["red"] else "red"


def approval_probability(votes, required=5):
    """Poisson-binomial estimate; independence is a simplifying assumption."""
    distribution = [1.]
    for probability in votes:
        updated = [0.] * (len(distribution) + 1)
        for count, mass in enumerate(distribution):
            updated[count] += mass * (1 - probability)
            updated[count + 1] += mass * probability
        distribution = updated
    return sum(distribution[required:])


class SocialPolicy:
    version = VERSION
    limitations = ["Belief and vote likelihoods are heuristic estimates, not calibrated probabilities.",
                   "Payment scenarios assume independent players and a small set of possible deposits; they are not a full strategy model.",
                   "Votes are forecast independently; other players' private objectives are unknown.",
                   "Uses only seat-visible evidence. With abilities enabled, public accounting cannot certify original deposits; unknown modifications are not forecast.",
                   "Objective scoring is a short-horizon approximation, not optimal play."]

    def __init__(self, seed=0, seat=0, traits=None, settings=None):
        self.rng = stream(seed, f"policy:{seat}")
        personality = stream(seed, f"personality:{seat}")
        self.traits = traits or Traits(personality.random(), personality.random(), personality.random())
        if settings is not None and not isinstance(settings, (dict, SocialSettings)):
            raise ValueError("Social policy settings must be a JSON object")
        self.settings = settings if isinstance(settings, SocialSettings) else SocialSettings(**(settings or {}))
        self.memory = EvidenceMemory()
        self.beliefs = SocialBeliefs()
        self.last_decision = None
        self._forecast_cache = None

    def tactical_side(self, observation):
        desired = self.memory.desired_side
        private, score = observation["private"], observation["public"]["score"]
        if private["objective"]["id"] == "close_race":
            other = "red" if private["team"] == "blue" else "blue"
            if score[other] < observation["public"]["rules"]["missions_to_win"] - 1 and score[private["team"]] >= 1:
                return other
        return desired

    def wallet(self, observation, pid):
        return next(p["wallet"] for p in observation["public"]["players"] if p["id"] == pid)

    def conceals_intent(self, observation):
        # Temporary Red goals need cover too. A report describes the previous
        # deposit even if that mission has just satisfied the private condition.
        private = observation["private"]
        receipt = private.get("last_contribution") or {}
        return (self.memory.desired_side == "red" or self.tactical_side(observation) == "red"
                or (private["team"] == "blue" and private["objective"]["id"] == "opposition_patron"
                    and self.beliefs.paid["red"] < 20)
                or (observation["action_spec"]["type"] == "report"
                    and receipt.get("tokens", {}).get("red", 0) > 0))

    def blue_target(self, observation, crew):
        candidates = [pid for pid in crew if pid != observation["viewer"]]
        return max(candidates, key=lambda pid: self.beliefs.estimate(pid)["blue_preference"], default=None)

    def candidates(self, observation, crew=None):
        public, me = observation["public"], observation["viewer"]
        crew = public["crew"] if crew is None else crew
        wallet = self.wallet(observation, me)
        mission = public["mission"]
        gap = max(0, mission["threshold"] - sum(mission["pot"].values()))
        pledge = public["pledges"].get(me, vector())
        desired = self.tactical_side(observation)
        other = "red" if desired == "blue" else "blue"
        swing = max(0, mission["pot"][other] - mission["pot"][desired] + (desired == "red"))
        # Include both terminal balances and balances after a continuing
        # attempt's income. Exact Change often needs to pay down to six first.
        income = public["rules"]["income"]
        totals = {0, 1, 2, ceil(gap / mission["crew_size"]), gap, swing, wallet,
                  wallet - 7, wallet - 7 + income, wallet - 10, wallet - 10 + income,
                  sum(pledge.values())}
        others, _ = self.forecast(observation, crew, vector(), public["pledges"] or None)
        totals.add(ceil(max(0, mission["threshold"] - sum(others.values()))))
        totals.add(ceil(max(0, others["red"] - others["blue"])))
        totals.add(max(0, floor(others["blue"] - others["red"]) + 1))
        opposing = "red" if observation["private"]["team"] == "blue" else "blue"
        patron_gap = max(0, ceil(20 - self.beliefs.paid[opposing]))
        if observation["private"]["objective"]["id"] == "opposition_patron":
            totals.add(patron_gap)
        choices = {tuple(pledge[c] for c in COLORS)}
        for n in {max(0, min(wallet, amount)) for amount in totals}:
            for c in COLORS:
                choices.add(tuple(vector(c, n)[k] for k in COLORS))
            if n >= 2:
                choices.add((n // 2, n - n // 2, 0))
                choices.add((n - n // 2, n // 2, 0))
                # Fund the opposing-color counter without needlessly handing
                # over this mission; half-and-half alone misses these plans.
                blue_to_win = ceil((n + others["red"] - others["blue"]) / 2)
                red_to_win = floor((n + others["blue"] - others["red"]) / 2) + 1
                for blue in (blue_to_win, n - red_to_win,
                             n - patron_gap if opposing == "red" else patron_gap):
                    if 0 <= blue <= n:
                        choices.add((blue, n - blue, 0))
        return [dict(zip(COLORS, choice)) for choice in sorted(choices) if sum(choice) <= wallet]

    def payment_model(self, observation, crew, own=None, pledges=None):
        """Combine legal integer payments, merging identical resulting pots.

        A promise can be kept, withheld, or redirected to Blue or Red. Its
        reliability and the speaker's estimated preference weight those cases.
        Unannounced payments use an affordable share in either competitive color.
        Cache only within one decision: own colors cannot change others' plans.
        """
        public, me = observation["public"], observation["viewer"]
        mission = public["mission"]
        gap = max(0, mission["threshold"] - sum(mission["pot"].values()))
        share = max(int(mission["pot"]["blue"] + mission["pot"]["red"] == 0), ceil(gap / max(1, len(crew))))
        if pledges is None and me in crew and own is not None:
            remaining = max(0, gap - sum(own.values()))
            share = max(int(mission["pot"]["blue"] + mission["pot"]["red"] + own["blue"] + own["red"] == 0),
                        ceil(remaining / max(1, len(crew) - 1)))
        key = (tuple(crew), own is not None, share,
               tuple((pid, tuple(pledges[pid][c] for c in COLORS)) for pid in crew if pledges and pid in pledges))
        if self._forecast_cache is not None and key in self._forecast_cache:
            return self._forecast_cache[key]
        deposits, distribution = {}, {tuple(mission["pot"][c] for c in COLORS): 1.}
        for pid in crew:
            if pid == me and own is not None:
                continue
            belief = self.beliefs.estimate(pid)
            blue, reliability = belief["blue_preference"], belief["pledge_reliability"]
            reliability **= 1 + self.traits.skepticism
            amount = min(self.wallet(observation, pid), share)
            if pledges is not None and pid in pledges:
                promise = pledges[pid]
                amount = sum(promise.values())
                options = [(tuple(promise[c] for c in COLORS), reliability),
                           ((0, 0, 0), (1 - reliability) * .3),
                           ((amount, 0, 0), (1 - reliability) * .7 * blue),
                           ((0, amount, 0), (1 - reliability) * .7 * (1 - blue))]
            else:
                options = [((amount, 0, 0), blue), ((0, amount, 0), 1 - blue)]
            deposits[pid] = {c: sum(payment[i] * mass for payment, mass in options) for i, c in enumerate(COLORS)}
            updated = {}
            for pot, probability in distribution.items():
                for payment, mass in options:
                    if mass <= 0:
                        continue
                    result = tuple(a + b for a, b in zip(pot, payment))
                    updated[result] = updated.get(result, 0.) + probability * mass
            distribution = updated
        result = distribution, deposits
        if self._forecast_cache is not None:
            self._forecast_cache[key] = result
        return result

    def forecast(self, observation, crew, own=None, pledges=None):
        _, others = self.payment_model(observation, crew, own, pledges)
        deposits = dict(others)
        if observation["viewer"] in crew and own is not None:
            deposits[observation["viewer"]] = dict(own)
        pot = {c: observation["public"]["mission"]["pot"][c] + sum(v[c] for v in deposits.values()) for c in COLORS}
        if observation["viewer"] in crew and own is not None:
            echoed = echo_payment(observation, own)
            pot = {c: pot[c] + echoed[c] - own[c] for c in COLORS}
        return pot, deposits

    def forecast_outcomes(self, observation, crew, own=None, pledges=None):
        distribution, _ = self.payment_model(observation, crew, own, pledges)
        payment = echo_payment(observation, own) if observation["viewer"] in crew and own is not None else vector()
        return [({c: pot[i] + payment[c] for i, c in enumerate(COLORS)}, mass)
                for pot, mass in distribution.items()]

    def condition(self, observation, pot, own, crew, pledge, penalty=False):
        private, public, me = observation["private"], observation["public"], observation["viewer"]
        kind, team = private["objective"]["id"], private["team"]
        other = "red" if team == "blue" else "blue"
        wallet = self.wallet(observation, me) - sum(own.values())
        progress = private["objective"].get("progress", {}).get("value") or 0
        kept = me in crew and sum(own.values()) >= 2 and own == pledge
        completes = winner(pot, public["mission"]["threshold"])
        if kind == "saver": return wallet >= 10
        if kind == "spendthrift": return wallet == 0
        if kind == "exact_change": return wallet == 7
        if kind == "reliable_partner": return progress + kept >= 2
        if kind == "passenger": return progress + (me in crew and sum(own.values()) == 0 and completes is not None) >= 1
        if kind == "close_race": return public["score"][other] + (completes == other) == public["rules"]["missions_to_win"] - 1
        if kind == "opposition_patron":
            # With abilities off, paid history is deducible from public deltas.
            # With abilities on, beliefs.paid is only a verified lower bound;
            # future deposits remain a forecast. Never query the engine counter.
            paid = self.beliefs.paid[other] + (0 if penalty else pot[other] - public["mission"]["pot"][other])
            return paid >= 20
        return True

    def expected_income(self, observation, pot):
        public = observation["public"]
        completed = winner(pot, public["mission"]["threshold"])
        if ((completed and public["score"][completed] == public["rules"]["missions_to_win"] - 1)
                or public["attempt"] >= public["rules"]["development_attempt_limit"]):
            return 0
        return public["rules"]["income"]

    def completion_support(self, observation, crew, own, pot):
        """Completion estimate including the possibility of honored promises.

        Discounted deposits are means, not a guarantee that a just-funded crew
        will fall short. For Passenger, also consider everyone honoring their
        announced amount, discounted by those speakers' reliability.
        """
        public, me = observation["public"], observation["viewer"]
        mission = public["mission"]
        if winner(pot, mission["threshold"]) is not None:
            return 1.
        promised = dict(mission["pot"])
        confidence = 1.
        for pid in crew:
            pledge = own if pid == me else public["pledges"].get(pid)
            if pledge is None:
                return 0.
            for color in COLORS:
                promised[color] += pledge[color]
            if pid != me and sum(pledge.values()):
                confidence *= self.beliefs.estimate(pid)["pledge_reliability"] ** (1 + self.traits.skepticism)
        return confidence if winner(promised, mission["threshold"]) is not None else 0.

    def objective_incentive(self, observation, pot, own, crew, pledge, penalty=False, realized=False):
        public, private, me = observation["public"], observation["private"], observation["viewer"]
        wallet, amount = self.wallet(observation, me), sum(own.values())
        after = wallet - amount + self.expected_income(observation, pot)
        kind = private["objective"]["id"]
        progress = private["objective"].get("progress", {}).get("value") or 0
        if kind == "saver":
            protected_spend = max(0, amount - max(0, wallet - 10))
            return (min(10, after) - min(10, wallet)) / 2 - 2 * protected_spend
        if kind == "exact_change":
            return 2 * (abs(wallet - 7) - abs(after - 7))
        if kind == "spendthrift":
            urgency = .5 if max(public["score"].values()) == public["rules"]["missions_to_win"] - 1 else 0
            return (wallet - after) * (.7 + urgency)
        if kind == "reliable_partner" and progress < 2:
            return 2 * float(me in crew and amount >= 2 and own == pledge)
        if kind == "passenger" and progress < 1:
            completes = float(winner(pot, public["mission"]["threshold"]) is not None) if realized else self.completion_support(observation, crew, own, pot)
            return 2.5 * completes if me in crew and amount == 0 else 0.
        if kind == "opposition_patron":
            opposing = "red" if private["team"] == "blue" else "blue"
            added = 0 if penalty else pot[opposing] - public["mission"]["pot"][opposing]
            return .6 * (min(20, self.beliefs.paid[opposing] + added) - min(20, self.beliefs.paid[opposing]))
        return 0.

    def objective_plan(self, observation):
        private, public, me = observation["private"], observation["public"], observation["viewer"]
        wallet = self.wallet(observation, me)
        progress = private["objective"].get("progress", {}).get("value") or 0
        kind = private["objective"]["id"]
        if kind == "saver":
            return f"Protect a 10-token reserve; current wallet {wallet}, available surplus {max(0, wallet - 10)}. Let other crew members fund missions while I save."
        if kind == "spendthrift":
            return f"Seek a crew seat while I have money ({wallet}) and spend it; the final deposit must leave zero before income."
        if kind == "exact_change":
            return f"Current wallet {wallet}: save below 7, seek spending opportunities above it. Target 7 at the finish, or {7 - public['rules']['income']} before continuing income."
        if kind == "reliable_partner":
            return (f"Seek a crew and honor a pledge of at least 2; {progress}/2 qualifying attempts so far."
                    if progress < 2 else "Both qualifying pledges are complete; focus on my side winning.")
        if kind == "passenger":
            return ("Seek a crew whose other members can complete this mission while I pay zero; either side can qualify."
                    if progress < 1 else "My passenger attempt is complete; I can contribute normally to help my side win.")
        if kind == "opposition_patron":
            opposing = "red" if private["team"] == "blue" else "blue"
            needed = max(0, 20 - self.beliefs.paid[opposing])
            return f"Need approximately {needed:g} more paid {opposing.title()} tokens across the table. Prefer mixed deposits that also protect my side; penalties do not count."
        if kind == "close_race":
            return f"Steer toward a {public['rules']['missions_to_win']}–{public['rules']['missions_to_win'] - 1} finish; currently favor {self.tactical_side(observation).title()}, then stop helping the opposing side once it has {public['rules']['missions_to_win'] - 1} points."
        return f"Help {self.memory.desired_side.title()} win {'four' if public['rules']['missions_to_win'] == 4 else 'three'} missions."

    def objective_protest(self, observation, crew, pot, own, pledge):
        public, private, me = observation["public"], observation["private"], observation["viewer"]
        if me in crew or public["rejections"] >= self.settings.protest_relax_at:
            return False
        completed = winner(pot, public["mission"]["threshold"])
        if (completed == self.memory.desired_side and public["score"][completed] == public["rules"]["missions_to_win"] - 1
                and self.condition(observation, pot, own, crew, pledge)):
            return False  # Never protest a forecast personal victory.
        kind = private["objective"]["id"]
        wallet = self.wallet(observation, me)
        progress = private["objective"].get("progress", {}).get("value") or 0
        if kind == "spendthrift": return wallet > 0
        if kind == "exact_change": return wallet > 7 or (wallet == 7 and self.expected_income(observation, pot) > 0)
        if kind == "reliable_partner": return progress < 2 and wallet >= 2
        if kind == "passenger" and progress < 1:
            # Could I replace a member and ride for free using the remaining
            # public promises? Do not demand a seat on a hopelessly short crew.
            for pid in crew:
                replacement = [p for p in crew if p != pid] + [me]
                carried, _ = self.forecast(observation, replacement, vector(), public["pledges"])
                if self.completion_support(observation, replacement, vector(), carried) >= .35:
                    return True
        return False

    def outcome_value(self, observation, pot, own, crew, pledge, penalty=False):
        public, private, me = observation["public"], observation["private"], observation["viewer"]
        mission, score = public["mission"], public["score"]
        desired = self.memory.desired_side
        completed = winner(pot, mission["threshold"])
        if completed and score[completed] == public["rules"]["missions_to_win"] - 1:
            personal_win = completed == desired and self.condition(observation, pot, own, crew, pledge, penalty)
            return self.settings.terminal_weight * (1 if personal_win else -1)
        tactical = self.tactical_side(observation)
        opposite = "red" if tactical == "blue" else "blue"
        paid = sum(pot.values()) - sum(mission["pot"].values())
        advantage = (pot[tactical] - pot[opposite]) / max(1, sum(pot.values()))
        value = self.settings.funding_weight * min(1, paid / mission["threshold"]) * (1 if advantage >= 0 else -1)
        value += self.settings.ownership_weight * advantage
        if completed:
            value += 4 if completed == tactical else -4
        incentive = self.objective_incentive(observation, pot, own, crew, pledge, penalty, realized=True)
        value += self.settings.objective_weight * incentive
        return value

    def protest(self, observation, crew, pot, demand):
        public = observation["public"]
        completed = winner(pot, public["mission"]["threshold"])
        terminal = completed and public["score"][completed] == public["rules"]["missions_to_win"] - 1
        return (observation["viewer"] not in crew and demand >= self.settings.protest_threshold
                and public["rejections"] < self.settings.protest_relax_at and not terminal)

    def complaint(self, observation, forecast, protest):
        """Both sides use the same public reasons; private goals decide the vote."""
        public, me = observation["public"], observation["viewer"]
        if protest:
            return {"modifier": "more", "player_id": me}, "I want a place on this crew."
        mission = public["mission"]
        gap = max(0, mission["threshold"] - sum(mission["pot"].values()))
        share = max(1, ceil(gap / len(public["crew"])))
        advertised = forecast["advertised_pot"]
        shortfall = max(0, mission["threshold"] - sum(advertised.values())) / mission["threshold"]
        options = [(.7 + shortfall, {"modifier": "more", "color": "blue"},
                    "I am asking for stronger Blue funding.")]
        for pid in public["crew"]:
            if pid == me:
                continue
            belief = self.beliefs.estimate(pid)
            pledge = public["pledges"][pid]
            concerns = {
                "observed support for Red": max(0, self.beliefs.prior - belief["blue_preference"]) * 4,
                "unreliable promises": max(0, .75 - belief["pledge_reliability"]) * 3,
                "a public Red pledge": pledge["red"] / max(1, sum(pledge.values())) * 1.5,
                "a small Blue pledge for this mission": max(0, share - pledge["blue"]) / share * .7,
            }
            concern = sum(concerns.values())
            if concern < .3:
                continue  # Being cooperative is not itself a plausible accusation.
            # A covert bot can prefer removing a likely Blue supporter, but only
            # among people for whom it has an ordinary public objection.
            strategic = .2 * belief["blue_preference"] if self.conceals_intent(observation) else 0
            options.append((.6 + concern + strategic, {"modifier": "less", "player_id": pid},
                            f"I object to {pid} because of {max(concerns, key=concerns.get)}."))
        self.rng.shuffle(options)
        _, complaint, explanation = max(options, key=lambda option: option[0])
        return complaint, explanation

    def predict_votes(self, observation, crew, pot, own, pledge, include_observed=True, outcomes=None, own_value=None):
        public, me = observation["public"], observation["viewer"]
        outcomes = outcomes if outcomes is not None else [(pot, 1.)]
        alignments = [(winner(result, public["mission"]["threshold"]),
                       (result["blue"] - result["red"]) / max(1, sum(result.values())), mass)
                      for result, mass in outcomes]
        observed = {v["player_id"]: float(v["approve"]) for v in public["votes"]} if include_observed else {}
        votes = {}
        for player in public["players"]:
            pid = player["id"]
            if pid in observed:
                votes[pid] = observed[pid]
                continue
            if pid == me:
                value = self.outcome_value(observation, pot, own, crew, pledge) if own_value is None else own_value
                protest = (self.protest(observation, crew, pot, self.traits.selfishness)
                           or self.objective_protest(observation, crew, pot, own, pledge))
                votes[pid] = 0. if protest else float(value > 0)
                continue
            belief = self.beliefs.estimate(pid)
            blue = belief["blue_preference"]
            alignment = sum(mass * ((blue if completed == "blue" else 1 - blue) if completed else .5 + (blue - .5) * margin)
                            for completed, margin, mass in alignments)
            probability = .1 + .8 * alignment
            if pid not in crew and public["rejections"] < self.settings.protest_relax_at:
                probability -= .5 * belief["inclusion_demand"]
            votes[pid] = bounded(probability)
        return votes

    def evaluate_outcomes(self, observation, outcomes, own, crew, pledge):
        public = observation["public"]
        likelihoods = dict.fromkeys(("blue", "red", "incomplete", "personal_win", "personal_loss", "continues"), 0.)
        values, income, condition, incentive = [], 0., 0., 0.
        for pot, mass in outcomes:
            completed = winner(pot, public["mission"]["threshold"])
            satisfied = self.condition(observation, pot, own, crew, pledge)
            likelihoods[completed or "incomplete"] += mass
            if completed and public["score"][completed] == public["rules"]["missions_to_win"] - 1:
                won = completed == self.memory.desired_side and satisfied
                likelihoods["personal_win" if won else "personal_loss"] += mass
            else:
                likelihoods["continues"] += mass
            values.append((self.outcome_value(observation, pot, own, crew, pledge), mass))
            income += mass * self.expected_income(observation, pot)
            condition += mass * satisfied
            incentive += mass * self.objective_incentive(observation, pot, own, crew, pledge, realized=True)
        expected = sum(value * mass for value, mass in values)
        # Caution concerns uncertain outcomes, not an arbitrary price on paying.
        risk = .1 * self.traits.caution * sum(mass * max(0., expected - value) for value, mass in values)
        return expected - risk, {"outcome_likelihoods": likelihoods, "expected_outcome_utility": expected,
                                 "risk_adjustment": risk, "expected_income": income,
                                 "condition_likelihood": condition, "expected_objective_incentive": incentive,
                                 "outcome_scenarios": [{"pot": pot, "likelihood": mass}
                                                       for pot, mass in sorted(outcomes, key=lambda item: -item[1])]}

    def evaluate(self, observation, crew, own, pledges, phase, announced=None):
        pot, deposits = self.forecast(observation, crew, own, pledges)
        me = observation["viewer"]
        claim = self.public_promise(observation, own) if announced is None else announced
        pledge = (pledges or {}).get(me, claim)
        outcomes = self.forecast_outcomes(observation, crew, own, pledges)
        utility, uncertainty = self.evaluate_outcomes(observation, outcomes, own, crew, pledge)
        advertised = pot
        advertised_outcomes = outcomes
        if (self.conceals_intent(observation) or own["red"] > 0) and me in crew and phase in ("select_crew", "pledge", "vote"):
            claim = (pledges or {}).get(me, claim)
            advertised, _ = self.forecast(observation, crew, claim, pledges)
            advertised_outcomes = self.forecast_outcomes(observation, crew, claim, pledges)
        votes = self.predict_votes(observation, crew, advertised, own, pledge, include_observed=phase not in ("select_crew", "pledge"),
                                   outcomes=advertised_outcomes, own_value=utility)
        if phase in ("select_crew", "pledge", "vote"):
            protest = (self.protest(observation, crew, pot, self.traits.selfishness)
                       or self.objective_protest(observation, crew, pot, own, pledge))
            votes[me] = 0. if protest else float(utility > 0)
        approval = approval_probability(votes.values())
        if phase in ("select_crew", "pledge"):
            utility = approval * utility - .5 * (1 - approval)
        if phase == "select_crew":
            utility += self.settings.inclusion_weight * self.traits.selfishness * (me in crew)
        elif phase == "contribute":
            promise = observation["public"]["pledges"][me]
            deviation = sum(abs(own[c] - promise[c]) for c in COLORS)
            utility -= .3 * (1 - self.traits.selfishness) * deviation
        return utility, {"forecast_pot": pot, "expected_deposits": deposits, "vote_likelihoods": votes,
                         "advertised_pot": advertised, "planned_deposit": own,
                         "approval_likelihood": approval, "objective_utility": utility,
                         "wallet_after_deposit": self.wallet(observation, me) - sum(own.values()),
                         **uncertainty}

    def public_promise(self, observation, own):
        if self.conceals_intent(observation) or own["red"]:
            return vector("blue", sum(own.values()))
        return own

    def choose_action(self, observation):
        self._forecast_cache = {}
        try:
            return self._choose_action(observation)
        finally:
            self._forecast_cache = None

    def plan_rank(self, observation, score, forecast):
        """Personal utility first; tied plans protect the tactical color margin."""
        side = self.tactical_side(observation)
        other = "red" if side == "blue" else "blue"
        pot = forecast["forecast_pot"]
        return round(score, 10), pot[side] - pot[other], -pot["green"]

    def _choose_action(self, observation):
        self.memory.observe(observation)
        self.beliefs.observe(observation, self.memory,
                            report_weight=self.settings.report_weight * (1 - .75 * self.traits.skepticism),
                            association_weight=self.settings.association_weight,
                            accusation_weight=self.settings.accusation_weight)
        public, private, me = observation["public"], observation["private"], observation["viewer"]
        kind = observation["action_spec"]["type"]
        details = {"traits": asdict(self.traits), "objective": private["objective"]["id"],
                   "desired_side": self.memory.desired_side, "tactical_side": self.tactical_side(observation),
                   "objective_plan": self.objective_plan(observation),
                   "concealing_red_intent": self.conceals_intent(observation),
                   "beliefs": {pid: self.beliefs.estimate(pid) for pid in self.beliefs.players if pid != me},
                   "new_evidence": deepcopy(self.beliefs.updates)}
        extra = self.extra_action(observation)
        if extra is not None:
            self.last_decision = deepcopy({"reason": self.extra_reason(),
                                           "details": {**details, **self.extra_details()}, "limitations": self.limitations})
            return extra
        if kind in ("select_crew", "pledge", "contribute"):
            options = []
            if kind == "select_crew":
                for crew in combinations(observation["action_spec"]["players"], observation["action_spec"]["crew_size"]):
                    # Rank crews using a real affordable plan for my objective,
                    # including a zero-paying Passenger/Saver or a two-token
                    # Reliable Partner. Inclusion never implies a generic share.
                    plans = self.candidates(observation, crew) if me in crew else [vector()]
                    score, forecast = max((self.evaluate(observation, crew, own, None, kind) for own in plans),
                                          key=lambda option: self.plan_rank(observation, *option))
                    options.append((score, {"type": kind, "crew": list(crew)}, forecast))
            else:
                choices = self.candidates(observation)
                for own in choices:
                    pledges = public["pledges"] if kind == "contribute" else None
                    claim = self.public_promise(observation, own) if kind == "pledge" else own
                    score, forecast = self.evaluate(observation, public["crew"], own, pledges, kind, announced=claim)
                    options.append((score, {"type": kind, "tokens": claim}, forecast))
            self.rng.shuffle(options)
            options.sort(key=lambda option: self.plan_rank(observation, option[0], option[2]), reverse=True)
            _, action, forecast = options[0]
            details.update(forecast)
            details["alternatives"] = [{"score": s, "action": a} for s, a, _ in options[:3]]
            reason = {"select_crew": "Selected a crew using expected contributions, predicted votes, my objective, and my preference for inclusion.",
                      "pledge": "Chose a pledge using expected support, my wallet, and my personal objective.",
                      "contribute": "Compared affordable deposits against expected crew behavior, my objective, and the cost of breaking my pledge."}[kind]
            if kind == "pledge" and (self.conceals_intent(observation) or forecast["planned_deposit"]["red"]):
                details["concealing_red_intent"] = True
                reason = "Promised Blue to gain the majority's support; evaluated my private spending plan separately from the public promise."
        elif kind == "vote":
            own = public["pledges"].get(me, vector()) if me in public["crew"] else vector()
            if me in public["crew"]:
                _, planned = max((self.evaluate(observation, public["crew"], v, public["pledges"], "contribute")
                                  for v in self.candidates(observation)), key=lambda option: self.plan_rank(observation, *option))
                own = planned["planned_deposit"]
            value, forecast = self.evaluate(observation, public["crew"], own, public["pledges"], kind)
            pot = forecast["forecast_pot"]
            objective_protest = self.objective_protest(observation, public["crew"], pot, own, public["pledges"].get(me, vector()))
            protest = self.protest(observation, public["crew"], pot, self.traits.selfishness) or objective_protest
            advancing = forecast["expected_objective_incentive"] > 0
            reject_value = 0.
            if public["rejections"] == 7:
                penalty = dict(public["mission"]["pot"])
                penalty["red"] += public["rules"]["rejection_red_tokens"]
                reject_value = self.outcome_value(observation, penalty, vector(), [], vector(), penalty=True)
            target = self.blue_target(observation, public["crew"])
            blue_block = (not advancing and self.tactical_side(observation) == "red" and target is not None
                          and self.beliefs.estimate(target)["blue_preference"] >= self.settings.blue_reject_threshold
                          and not (forecast["outcome_likelihoods"]["red"] > .5 and value > 0))
            red_block = (not advancing and self.tactical_side(observation) == "blue"
                         and public["rejections"] < self.settings.protest_relax_at
                         and any(1 - self.beliefs.estimate(pid)["blue_preference"] >= self.settings.red_reject_threshold
                                 for pid in public["crew"] if pid != me)
                         and not (forecast["outcome_likelihoods"]["blue"] > .5 and value > 0))
            approve = not protest and not blue_block and not red_block and value > reject_value
            complaint, explanation = self.complaint(observation, forecast, protest) if not approve else (None, None)
            complaints = [complaint] if complaint else []
            action = {"type": kind, "approve": approve, "complaints": complaints}
            forecast["vote_likelihoods"][me] = float(approve)
            forecast["approval_likelihood"] = approval_probability(forecast["vote_likelihoods"].values())
            details.update(forecast)
            details.update(exclusion_protest=bool(protest), rejection_value=reject_value,
                           objective_inclusion_protest=bool(objective_protest),
                           suspected_blue_block=bool(blue_block), suspected_red_block=bool(red_block),
                           accusation_target=complaint.get("player_id") if complaint and complaint["modifier"] == "less" else None,
                           complaint_reason=explanation)
            reason = ("Voted No and asked 'More me': I want a place on this crew. This protest relaxes near the rejection limit or a forecast game-ending result."
                      if protest else f"Voted {'Yes' if approve else 'No'} using possible payments, observed cooperation, my objective, and rejection consequences.")
            if not approve:
                reason += " Public explanation: " + explanation
                if self.conceals_intent(observation):
                    reason += " This keeps my private Red goals out of the public complaint."
        elif kind == "report":
            action = {"type": kind, "statements": truthful_statements(observation)}
            reason = "Reported only my own original deposit, or passed when I had none. Beliefs about others are not facts."
            if self.conceals_intent(observation):
                receipt = private["last_contribution"]
                amount = sum(receipt["tokens"].values())
                action["statements"] = [{"player_id": me, "verb": "gave", "quantity": amount, "color": "blue"}]
                details["actual_deposit"] = deepcopy(receipt["tokens"])
                reason = "Reported my spending as Blue to maintain cover. Public accounting or another player's receipt may contradict this claim."
        else:
            raise ValueError(f"Unsupported decision: {kind}")
        reason += " Objective plan: " + details["objective_plan"]
        self.last_decision = deepcopy({"reason": reason, "details": details, "limitations": self.limitations})
        return self.finalize_action(action, observation)

    def extra_action(self, observation):
        return ability_action(observation, self.rng, self.tactical_side(observation))

    def extra_reason(self):
        return "Used my own ability instructions and visible evidence, or passed."

    def extra_details(self):
        return {}

    def finalize_action(self, action, observation):
        return with_ability(action, observation, self.rng, self.tactical_side(observation))

    def snapshot(self):
        return {"version": self.version, "rng": self.rng.getstate(), "traits": asdict(self.traits),
                "settings": asdict(self.settings), "memory": self.memory.snapshot(), "beliefs": self.beliefs.snapshot()}

    @classmethod
    def from_snapshot(cls, data):
        if data["version"] not in (VERSION, "social.7"):
            raise ValueError("Unsupported social policy version")
        policy = cls(traits=Traits(**data["traits"]), settings=data["settings"])
        policy.version = data["version"]
        policy.rng.setstate(tuple_tree(data["rng"]))
        policy.memory = EvidenceMemory.from_snapshot(data["memory"])
        policy.beliefs = SocialBeliefs.from_snapshot(data["beliefs"])
        return policy
