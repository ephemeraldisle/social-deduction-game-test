"""Bounded evidence estimates from a single seat's observations.

These are heuristic beliefs, not calibrated probabilities or role inspections.
The contribution bounds below apply only to the current ability-free profiles.
"""

from copy import deepcopy
from math import ceil

COLORS = ("blue", "red", "green")


def bounded(value, low=.05, high=.95):
    return max(low, min(high, value))


def blue_prior(observation):
    """Allegiance prior from public counts, excluding my known team.

    Other players' objectives remain unknown; this does not certify that a
    Blue player wants Blue to win or reveal whether Contrarian was dealt.
    """
    own_blue = observation["private"]["team"] == "blue"
    counts = observation["public"]["rules"]["team_counts"]
    return (counts["blue"] - own_blue) / (sum(counts.values()) - 1)


class SocialBeliefs:
    def __init__(self):
        self.abilities_enabled = False
        self.verified_deposits = {}
        self.known_teams = {}
        self.cursor = 0
        self.players = {}
        self.prior = None
        self.pot = dict.fromkeys(COLORS, 0)
        self.wallets = {f"p{i}": 5 for i in range(8)}
        self.crew = []
        self.pledges = {}
        self.threshold = 8
        self.last_resolution = None
        self.paid = {"blue": 0, "red": 0}
        self.public_paid_estimates = {}
        self.associations = {}
        self.accusations = {}
        self.updates = []

    def estimate(self, pid, direct=False):
        p = self.players[pid]
        extra_blue, extra_red = (0, 0) if direct else (p["soft_blue"], p["soft_red"])
        return {
            "blue_preference": bounded((p["blue"] + extra_blue) / (p["blue"] + p["red"] + extra_blue + extra_red)),
            "pledge_reliability": bounded(p["kept"] / (p["kept"] + p["broken"])),
            "report_credibility": bounded(p["credible"] / (p["credible"] + p["false"])),
            "inclusion_demand": bounded(p["demands"] / (p["demands"] + p["accepts_exclusion"])),
            "evidence": deepcopy(p["evidence"]),
        }

    def note(self, pid, event, text):
        item = {"event_id": event["id"], "player_id": pid, "text": text}
        self.players[pid]["evidence"] = [*self.players[pid]["evidence"], item][-5:]
        self.updates.append(item)

    def side(self, pid, blue, weight, soft=False):
        p = self.players[pid]
        b, r = ("soft_blue", "soft_red") if soft else ("blue", "red")
        p[b] += weight * blue
        p[r] += weight * (1 - blue)
        if soft and p[b] + p[r] > 2:
            scale = 2 / (p[b] + p[r])
            p[b] *= scale
            p[r] *= scale

    def associate(self, pid, event, weight):
        # At most one association per actor/attempt. Only direct observations
        # inform the source reputation, so suspicion cannot recurse through votes.
        key = f"{event['attempt']}:{pid}"
        others = [p for p in self.crew if p != pid]
        if not others or key in self.associations:
            return
        quality = sum(self.estimate(p, direct=True)["blue_preference"] *
                      self.estimate(p)["pledge_reliability"] for p in others) / len(others)
        difference = quality - self.prior * .75
        if abs(difference) < .025:
            return
        self.associations[key] = event["id"]
        self.side(pid, float(difference > 0), weight * min(1, abs(difference) * 4), soft=True)
        self.note(pid, event, "Weak association: supported a crew with " +
                  ("better" if difference > 0 else "worse") + " observed Blue/cooperation evidence.")

    def accusation(self, event, weight, viewer=None):
        """Treat 'Less player' as an attributed accusation, not a role reveal."""
        speaker = event["player_id"]
        targets = [c["player_id"] for c in event["complaints"]
                   if c.get("modifier") == "less" and c.get("player_id") in self.players
                   and c["player_id"] != speaker]
        if event["approve"] or not targets:
            return False
        if speaker == viewer:
            return True  # My own assertion supplies no independent evidence.
        target = targets[0]
        key = f"{event['attempt']}:{speaker}:{target}"
        if key in self.accusations:
            return True  # Repeated votes do not create independent evidence.
        source = self.estimate(speaker)
        direct = self.estimate(speaker, direct=True)
        def trust(belief):
            return (.5 * belief["blue_preference"] + .3 * belief["pledge_reliability"]
                    + .2 * belief["report_credibility"])
        confidence = trust(source)
        # Rumors cannot bootstrap an unknown speaker into a trusted accuser.
        trusted = (confidence >= .72 and trust(direct) >= .72
                   and self.players[speaker]["kept"] >= 4.5)
        target_direct = self.estimate(target, direct=True)
        pledge = self.pledges.get(target)
        share = max(1, ceil(max(0, self.threshold - sum(self.pot.values())) / max(1, len(self.crew))))
        grounded = (target_direct["blue_preference"] < self.prior - .08
                    or target_direct["pledge_reliability"] < .65
                    or (target in self.crew and pledge is not None
                        and (pledge["red"] > 0 or pledge["blue"] < share)))
        influence = weight * (confidence if trusted else confidence ** 3)
        # Even a new player can object to an observable problem. Do not make
        # legitimate criticism a Red tell; grounding does not create more proof.
        backlash = 0. if trusted or grounded else weight * (1 - confidence)
        self.accusations[key] = {"event_id": event["id"], "speaker": speaker, "target": target,
                                 "trusted": trusted, "grounded": bool(grounded),
                                 "influence": influence, "backlash": backlash}
        self.side(target, 0., influence, soft=True)
        self.note(target, event, f"Accused by {speaker}; {'earned trust gives the claim more weight' if trusted else 'limited weight from an unproven/suspect speaker'}. This is not verified guilt.")
        if backlash:
            self.side(speaker, 0., backlash, soft=True)
            self.note(speaker, event, f"Blamed {target} without earned trust; possible attempt to divert suspicion.")
        elif trusted:
            self.note(speaker, event, f"Blamed {target} with corroborated cooperation history; no suspicion added merely for accusing.")
        else:
            self.note(speaker, event, f"Objected to {target} with supporting contribution or pledge evidence; no suspicion added merely for accusing.")
        return True

    def pledge_evidence(self, pid, vector, event):
        competitive = vector["blue"] + vector["red"]
        if competitive:
            self.side(pid, vector["blue"] / competitive, .35)
            self.note(pid, event, f"Pledged {vector['blue']} Blue and {vector['red']} Red; a weak preference signal.")

    def public_context(self, observation):
        pass

    def observe(self, observation, memory, report_weight=.2, association_weight=.2, accusation_weight=.8):
        self.abilities_enabled = observation["public"]["rules"].get("abilities_enabled", False)
        if self.prior is None:
            self.prior = blue_prior(observation)
            self.players = {p["id"]: {"blue": 4 * self.prior, "red": 4 * (1 - self.prior),
                                       "soft_blue": 0., "soft_red": 0., "kept": 3., "broken": 1.,
                                       "credible": 2., "false": 1., "demands": 1., "accepts_exclusion": 3.,
                                       "evidence": []} for p in observation["public"]["players"]}
        self.updates = []
        self.public_context(observation)
        known = dict(observation["public"].get("public_badges", {}))
        known.update({r["target"]: r["team"] for r in observation["private"].get("receipts", []) if r["type"] == "scout"})
        for pid, team in known.items():
            if pid not in self.known_teams:
                self.known_teams[pid] = team
                self.side(pid, float(team == "blue"), 2.)
                self.note(pid, {"id": self.cursor}, "Official allegiance learned; personal incentives remain unknown.")
        self.private_evidence(observation, memory)
        for event in observation["history"]:
            if event["id"] <= self.cursor:
                continue
            kind = event["type"]
            if kind == "mission_drawn":
                self.pot = deepcopy(event["mission"]["pot"])
                self.threshold = event["mission"]["threshold"]
            elif kind in ("income", "vote_income"):
                self.wallets = deepcopy(event["wallets"])
            elif kind == "crew_selected":
                self.crew, self.pledges = list(event["crew"]), {}
                self.associate(event["chairman"], event, association_weight)
            elif kind == "pledges_revealed":
                self.pledges = deepcopy(event["pledges"])
                for pid, vector in self.pledges.items():
                    self.pledge_evidence(pid, vector, event)
            elif kind == "vote":
                pid = event["player_id"]
                accusing = self.accusation(event, accusation_weight, memory.viewer)
                excluded = pid not in self.crew
                more_me = excluded and any(c.get("modifier") == "more" and c.get("player_id") == pid
                                           and not c.get("color") for c in event["complaints"])
                if more_me:
                    self.players[pid]["demands"] += 2
                    self.note(pid, event, "Requested own inclusion; an exclusion protest is not a team label.")
                elif excluded and event["approve"]:
                    self.players[pid]["accepts_exclusion"] += .7
                forecast = {c: self.pot[c] + sum(v[c] for v in self.pledges.values()) for c in COLORS}
                margin = forecast["blue"] - forecast["red"]
                if not more_me and not accusing and (margin or forecast["blue"]):
                    favors_blue = margin >= 0
                    blue = favors_blue == event["approve"]
                    self.side(pid, float(blue), .18)
                    self.note(pid, event, "Vote weakly suggests a " + ("Blue" if blue else "Red") + " preference; other motives remain possible.")
                if event["approve"] and not more_me:
                    self.associate(pid, event, association_weight)
            elif kind == "attempt_resolved":
                self.resolve(event, memory)
                self.private_evidence(observation, memory)
            elif kind == "reports_revealed":
                self.reports(event, report_weight)
            self.cursor = event["id"]
        self.updates = self.updates[-12:]

    def resolve(self, event, memory):
        final = event["mission"]["pot"]
        delta = {c: final[c] - self.pot[c] for c in COLORS}
        crew = [] if event["penalty"] else self.crew
        amounts = {pid: self.wallets[pid] - event["wallets"][pid] for pid in crew}
        self.last_resolution = {"crew": list(crew), "known": {}, "bounds": {}, "amounts": amounts,
                                "attempt": event["attempt"], "event_id": event["id"]}
        result = self.last_resolution
        if not self.abilities_enabled and not event["penalty"] and all(n >= 0 for n in amounts.values()) and sum(amounts.values()) == sum(delta.values()):
            for c in self.paid:
                self.paid[c] += delta[c]
            unknown = list(crew)
            remaining = dict(delta)
            receipt = memory.own_deposits.get(str(event["attempt"]))
            if memory.viewer in crew and receipt:
                result["known"][memory.viewer] = deepcopy(receipt["tokens"])
                unknown.remove(memory.viewer)
                remaining = {c: remaining[c] - receipt["tokens"][c] for c in COLORS}
            for pid in unknown:
                amount = amounts[pid]
                other_total = sum(amounts[p] for p in unknown if p != pid)
                bounds = {c: [max(0, remaining[c] - other_total), min(amount, remaining[c])] for c in COLORS}
                result["bounds"][pid] = bounds
                if all(lo == hi for lo, hi in bounds.values()):
                    result["known"][pid] = {c: bounds[c][0] for c in COLORS}
            mismatch = any(sum(v[c] for v in self.pledges.values()) != delta[c] for c in COLORS)
            for pid in crew:
                pledge = self.pledges[pid]
                known = result["known"].get(pid)
                bounds = result["bounds"].get(pid, {})
                impossible = sum(pledge.values()) != amounts[pid] or any(not lo <= pledge[c] <= hi for c, (lo, hi) in bounds.items())
                if known is not None:
                    kept = known == pledge
                    self.players[pid]["kept" if kept else "broken"] += 1.5
                    competitive = known["blue"] + known["red"]
                    if competitive:
                        self.side(pid, known["blue"] / competitive, 3.)
                    self.note(pid, event, "Original colors deducible from public accounting/own receipt: " +
                              ("pledge kept." if kept else "pledge broken."))
                elif impossible:
                    self.players[pid]["broken"] += 1.2
                    self.note(pid, event, "Public spending/color bounds rule out this player's pledge.")
                elif mismatch:
                    self.players[pid]["broken"] += .25
                    self.note(pid, event, "Crew totals differ from pledges; responsibility remains uncertain.")
                else:
                    self.players[pid]["kept"] += .25
                    self.note(pid, event, "Crew totals fit pledges; individual colors remain uncertain.")
                if known is None and bounds:
                    competitive = remaining["blue"] + remaining["red"]
                    if competitive and amounts[pid]:
                        self.side(pid, remaining["blue"] / competitive, .25)
        if self.abilities_enabled:
            result["amounts"] = {}  # Wallet deltas include transfers; they are not paid quantities.
        self.pot, self.wallets = deepcopy(final), deepcopy(event["wallets"])

    def private_evidence(self, observation, memory):
        if not self.abilities_enabled or not self.last_resolution:
            return
        result = self.last_resolution
        attempt = result["attempt"]
        evidence = []
        own = memory.own_deposits.get(str(attempt))
        if own:
            evidence.append((memory.viewer, own["tokens"]))
        evidence.extend((r["target"], r["tokens"]) for r in observation["private"].get("receipts", [])
                        if r["type"] == "audit" and r["attempt"] == attempt)
        for pid, tokens in evidence:
            result["known"][pid] = deepcopy(tokens)
            key = f"{attempt}:{pid}"
            if key in self.verified_deposits:
                continue
            self.verified_deposits[key] = deepcopy(tokens)
            for c in self.paid:
                self.paid[c] += tokens[c]  # A verified lower bound, not the hidden table-wide total.
            if pid in result["crew"]:
                kept = tokens == self.pledges[pid]
                self.players[pid]["kept" if kept else "broken"] += 1.5
                competitive = tokens["blue"] + tokens["red"]
                if competitive:
                    self.side(pid, tokens["blue"] / competitive, 3.)
                self.note(pid, {"id": result["event_id"]}, "Original deposit verified by a private receipt: " +
                          ("pledge kept." if kept else "pledge broken."))

    def reports(self, event, weight):
        result = self.last_resolution
        if not result or result["attempt"] != event["attempt"]:
            return
        credibility = {pid: self.estimate(pid)["report_credibility"] *
                       (.5 + .5 * self.estimate(pid)["pledge_reliability"]) for pid in self.players}
        for speaker, claims in event["reports"].items():
            verdicts = []
            influenced = set()
            for claim in claims:
                pid, color, amount = claim["player_id"], claim["color"], claim["quantity"]
                known = result["known"].get(pid)
                if claim["verb"] == "took" or (pid not in result["crew"] and not self.abilities_enabled):
                    if not self.abilities_enabled:
                        verdicts.append(amount == 0)  # No removals/off-crew deposits in these profiles.
                elif known is not None:
                    verdicts.append(known[color] == amount)
                else:
                    lo, hi = result["bounds"].get(pid, {}).get(color, (0, float("inf") if self.abilities_enabled else result["amounts"].get(pid, 0)))
                    if not lo <= amount <= hi:
                        verdicts.append(False)
                    elif amount and color in ("blue", "red") and pid not in influenced:
                        self.side(pid, float(color == "blue"), weight * credibility[speaker], soft=True)
                        self.note(pid, event, f"Unverified {color.title()} deposit reported by {speaker}; weighted by that speaker's credibility.")
                        influenced.add(pid)
            if False in verdicts:
                self.players[speaker]["false"] += 1.5
                self.note(speaker, event, "A report conflicts with publicly deducible facts or my own receipt.")
            elif verdicts:
                self.players[speaker]["credible"] += .6
                self.note(speaker, event, "A report agrees with independently available evidence.")

    def snapshot(self):
        return deepcopy(vars(self))

    @classmethod
    def from_snapshot(cls, data):
        model = cls()
        data = {"abilities_enabled": False, "verified_deposits": {}, "known_teams": {}, "public_paid_estimates": {}, **data}
        if set(data) != set(vars(model)):
            raise ValueError("Unsupported social belief snapshot")
        model.__dict__.update(deepcopy(data))
        return model


class AllegianceBeliefs(SocialBeliefs):
    """Keep verified teams distinct from uncertain cooperation (social.11)."""

    def pledge_evidence(self, pid, vector, event):
        if vector["red"]:
            # Openly promising Red is a costly public signal; promising Blue
            # is the normal cover story for either side and earns no trust.
            self.side(pid, 0., .35 * vector["red"] / (vector["blue"] + vector["red"]))
            self.note(pid, event, "Publicly pledged Red; weak evidence of Red support, not verified payment or allegiance.")
        elif vector["blue"]:
            self.note(pid, event, "Pledged Blue; a funding claim, not evidence of Blue allegiance or a kept promise.")

    def estimate(self, pid, direct=False):
        estimate = super().estimate(pid, direct)
        team = self.known_teams.get(pid)
        if team is not None:
            behavior = estimate["blue_preference"]
            # A team fact cannot be washed away by repeated claims. It still
            # does not certify a payment: objectives can reward off-color play.
            estimate.update(known_team=team, behavioral_blue_preference=behavior,
                            blue_preference=.75 * (team == "blue") + .25 * behavior)
        return estimate


class CooperativeBeliefs(AllegianceBeliefs):
    """Learn cautiously from outcomes without confusing objections with teams."""

    def public_context(self, observation):
        badges = observation["public"].get("public_badges", {})
        for pid, player in self.players.items():
            player["public_badge"] = badges.get(pid)

    def established_blue(self, pid):
        player = self.players[pid]
        direct = self.estimate(pid, direct=True)
        return (player.get("public_badge") == "blue" or
                direct["blue_preference"] >= .8 and (player["kept"] >= 4.5 or player.get("public_kept", 0.) >= .5))

    def grounded_objection(self, pid, public=None):
        belief = self.estimate(pid, direct=True)
        if belief["pledge_reliability"] < .65 or belief.get("behavioral_blue_preference", 1.) < .45:
            return True
        crew, pledges, pot, threshold = self.crew, self.pledges, self.pot, self.threshold
        if public is not None:
            crew, pledges = public["crew"], public["pledges"]
            pot, threshold = public["mission"]["pot"], public["mission"]["threshold"]
        pledge = pledges.get(pid)
        if pledge is None:
            return False
        advertised = sum(pot.values()) + sum(sum(v.values()) for v in pledges.values())
        share = ceil(max(0, threshold - sum(pot.values())) / max(1, len(crew)))
        return pledge["red"] > 0 or (advertised < threshold and pledge["blue"] < share)

    def clean_blue_crew(self, crew, pledges, pot, threshold):
        return (bool(crew) and all(self.established_blue(pid) and self.estimate(pid)["pledge_reliability"] >= .75
                                 and self.estimate(pid).get("behavioral_blue_preference", 1.) >= .45 for pid in crew)
                and not any(v["red"] for v in pledges.values())
                and pot["blue"] + sum(v["blue"] for v in pledges.values()) >= max(1, pot["red"])
                and sum(pot.values()) + sum(sum(v.values()) for v in pledges.values()) >= threshold)

    def hostility_evidence(self, event, viewer):
        from .coordination import objection_target
        speaker = event["player_id"]
        if event["approve"] or any(c.get("modifier") == "more" and c.get("player_id") == speaker for c in event["complaints"]):
            return
        targets = [objection_target(c, speaker) for c in event["complaints"]]
        targets = [pid for pid in targets if pid in self.players]
        unsupported = [pid for pid in targets if self.established_blue(pid) and not self.grounded_objection(pid)]
        clean_rejection = not targets and self.clean_blue_crew(self.crew, self.pledges, self.pot, self.threshold)
        if not unsupported and not clean_rejection:
            return
        player = self.players[speaker]
        if event["id"] <= player.get("hostility_event", 0):
            return
        player["hostility_event"] = event["id"]
        player["hostility_count"] = player.get("hostility_count", 0) + 1
        weight = min(1.5, max(0., 6 - player.get("hostility_weight", 0.))) if player["hostility_count"] >= 2 else 0.
        player["hostility_weight"] = player.get("hostility_weight", 0.) + weight
        if speaker != viewer and weight:
            self.side(speaker, 0., weight)
        self.note(speaker, event, "Repeated unsupported opposition to established Blue cooperation is evidence of Red intent, not a certified team reveal."
                  if weight else "Opposed established Blue cooperation without a concrete funding or reliability problem; watch for repetition.")

    def accusation(self, event, weight, viewer=None):
        from .coordination import objection_target
        if event["approve"]:
            return False
        self.hostility_evidence(event, viewer)
        speaker = event["player_id"]
        for complaint in event["complaints"]:
            target = objection_target(complaint, speaker)
            if target not in self.players or speaker == viewer:
                continue
            key = f"{event['attempt']}:{speaker}:{target}"
            if key in self.accusations:
                continue  # Repetition strengthens a voting stance, not proof.
            source = self.estimate(speaker)
            confidence = (.5 * source["blue_preference"] + .3 * source["pledge_reliability"]
                          + .2 * source["report_credibility"])
            allegation = complaint.get("modifier") == "less" or complaint.get("color") == "red"
            influence = .3 * weight * confidence if allegation else 0.
            self.accusations[key] = {"event_id": event["id"], "speaker": speaker, "target": target,
                                     "influence": influence, "backlash": 0.}
            if influence:
                self.side(target, 0., influence, soft=True)
            self.note(target, event, f"{speaker} objects to {target}'s inclusion; a voting constraint, not verified allegiance.")
        # Ordinary No votes are ambiguous. Only the repeated, unsupported
        # opposition evaluated above adds evidence against their speaker.
        return True

    def resolve(self, event, memory):
        before, wallets = dict(self.pot), dict(self.wallets)
        super().resolve(event, memory)
        if not self.abilities_enabled or event["penalty"]:
            return
        delta = {c: event["mission"]["pot"][c] - before[c] for c in COLORS}
        # Keep uncertain table-wide progress separate from certified receipts.
        # Discount a generous amount for unknown bonuses/color changes. This
        # is an estimate, not a catalogue of other players' hidden abilities.
        slack = 2 + len(self.crew)
        self.public_paid_estimates[str(event["attempt"])] = {c: max(0, delta[c] - slack) for c in self.paid}
        self.last_resolution.update(public_delta=delta,
                                    wallet_losses={pid: max(0, wallets[pid] - event["wallets"][pid]) for pid in self.crew},
                                    red_evidence={})
        promised = {c: sum(v[c] for v in self.pledges.values()) for c in COLORS}
        error = sum(abs(delta[c] - promised[c]) for c in COLORS)
        # Bonuses, transfers, and recoloring can obscure individual payments.
        # Aggregate consistency earns limited credit, never a certified receipt.
        tolerance = 2 + len(self.crew)
        for pid in self.crew:
            if pid == memory.viewer:
                continue
            spent = max(0, wallets[pid] - event["wallets"][pid])
            if not spent or not sum(self.pledges.get(pid, {}).values()):
                continue
            player = self.players[pid]
            if error <= tolerance and sum(delta.values()) > 0:
                player["public_kept"] = min(2., player.get("public_kept", 0.) + .25)
                self.note(pid, event, "Public crew results broadly fit promises; limited cooperation credit, individual payments remain unknown.")
            elif error > 2 * tolerance:
                player["public_broken"] = min(2., player.get("public_broken", 0.) + .15 / len(self.crew))
                self.note(pid, event, "Crew results differ substantially from promises; responsibility and hidden effects remain uncertain.")
            competitive = max(0, delta["blue"]) + max(0, delta["red"])
            if competitive > tolerance:
                self.side(pid, max(0, delta["blue"]) / competitive, .4 / len(self.crew))

    def paid_estimate(self, color):
        return max(self.paid[color], sum(attempt[color] for attempt in self.public_paid_estimates.values()))

    def private_evidence(self, observation, memory):
        super().private_evidence(observation, memory)
        result = self.last_resolution or {}
        if "public_delta" not in result:
            return
        delta, losses, crew = result["public_delta"], result["wallet_losses"], result["crew"]
        known = result["known"]
        for pid in crew:
            if pid == memory.viewer or not losses[pid]:
                continue
            others = [other for other in crew if other != pid]
            # Ask whether the other spenders could plausibly explain the Red
            # surge. Allow noise and hidden transfers; never turn it into a
            # certified deposit or an official team assignment.
            other_red = sum(known[p]["red"] if p in known else losses[p] for p in others)
            slack = 2 + len(crew) + (3 if any(p not in known for p in others) else 0)
            unexplained = max(0, delta["red"] - other_red - slack)
            weight = 0.
            if unexplained >= 2:
                weight = 4 + 6 * min(1, unexplained / max(1, losses[pid]))
            elif delta["red"] >= 4 and all(self.estimate(p, direct=True)["blue_preference"] >= .9 for p in others):
                weight = min(3., max(0, delta["red"] - (2 + len(crew))) / 2)
            previous = result["red_evidence"].get(pid, 0.)
            if weight > previous:
                self.side(pid, 0., weight - previous)
                self.players[pid]["public_red_support"] = self.players[pid].get("public_red_support", 0.) + weight - previous
                result["red_evidence"][pid] = weight
                self.note(pid, {"id": result["event_id"]}, "Large Red gains and public spending implicate this player even allowing for hidden effects; strong behavioral evidence, not a role reveal.")

    def reports(self, event, weight):
        super().reports(event, weight)
        result = self.last_resolution or {}
        if result.get("attempt") != event["attempt"] or "public_delta" not in result:
            return
        for speaker, claims in event["reports"].items():
            if speaker in result["known"]:
                continue
            if any(c["player_id"] == speaker and c["verb"] == "gave" and c["quantity"] >
                   max(0, result["public_delta"][c["color"]]) + 4 + len(result["crew"]) for c in claims):
                self.players[speaker]["false"] += .5
                self.note(speaker, event, "Self-report is difficult to reconcile with the public color totals; discounted while hidden effects remain possible.")

    def estimate(self, pid, direct=False):
        estimate = super().estimate(pid, direct)
        p = self.players[pid]
        kept, broken = p.get("public_kept", 0.), p.get("public_broken", 0.)
        estimate["pledge_reliability"] = bounded((p["kept"] + kept) / (p["kept"] + p["broken"] + kept + broken))
        return estimate
