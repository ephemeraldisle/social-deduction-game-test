"""Public negotiation evidence, separate from guesses about hidden allegiance."""

from functools import lru_cache

from .social_baseline import winner


def objection_target(complaint, speaker):
    """A named No is an objection even when the optional modifier is absent.

    'More player' requests inclusion; 'exact player' requests a payment change.
    Neither is an allegation that the named player should be removed.
    """
    target = complaint.get("player_id")
    return target if target != speaker and complaint.get("modifier") in (None, "less") else None


class NegotiationEvidence:
    def __init__(self, observation):
        self.proposals = []
        self.objections = {}
        self.inclusion_requests = {}
        current = None
        mission = None
        pot = dict.fromkeys(("blue", "red", "green"), 0)
        number = 0
        for event in observation["history"]:
            kind = event["type"]
            if kind == "mission_drawn":
                mission = event["mission"].get("number")
                pot = dict(event["mission"]["pot"])
            elif kind == "crew_selected":
                number += 1
                current = {"number": number, "mission": mission, "crew": set(event["crew"]),
                           "pot": dict(pot), "pledges": {}, "votes": {}, "rejected": False}
                self.proposals.append(current)
            elif kind == "pledges_revealed" and current:
                current["pledges"] = event["pledges"]
            elif kind == "vote" and current:
                pid = event["player_id"]
                current["votes"][pid] = event["approve"]
                if event["approve"]:
                    if pid not in current["crew"]:
                        self.inclusion_requests.pop(pid, None)
                    # Actual support supersedes an earlier refusal about this player.
                    for target in current["crew"]:
                        self.objections.pop((pid, target), None)
                else:
                    for complaint in event["complaints"]:
                        if complaint.get("modifier") == "more" and complaint.get("player_id") == pid and not complaint.get("color"):
                            self.inclusion_requests[pid] = number
                        target = objection_target(complaint, pid)
                        if target:
                            self.objections[pid, target] = number
            elif kind == "proposal_rejected" and current:
                current["rejected"] = True
            elif kind == "attempt_resolved":
                pot = dict(event["mission"]["pot"])
        self.number = number
        self.proposals = [p for p in self.proposals[-32:]
                          if p["mission"] == observation["public"]["mission"].get("number")]

    def matching_rejections(self, crew, pot, public):
        result = []
        for proposal in self.proposals:
            if not proposal["rejected"] or proposal["crew"] != set(crew):
                continue
            previous = {c: proposal["pot"][c] + sum(v[c] for v in proposal["pledges"].values()) for c in pot}
            threshold = public["mission"]["threshold"]
            # A failed funding plan can become viable. Do not blacklist a crew
            # after the pot, funding, or ownership prospects materially improve.
            old_winner, new_winner = winner(previous, threshold), winner(pot, threshold)
            if new_winner and new_winner != old_winner:
                continue
            if sum(pot.values()) > sum(previous.values()) + max(2, threshold / 4):
                continue
            old_margin = (previous["blue"] - previous["red"]) / max(1, sum(previous.values()))
            new_margin = (pot["blue"] - pot["red"]) / max(1, sum(pot.values()))
            if abs(new_margin - old_margin) > .3:
                continue
            result.append(proposal)
        return result[-3:]

    def adjust_votes(self, observation, crew, pot, votes, include_observed):
        public, me = observation["public"], observation["viewer"]
        observed = {v["player_id"] for v in public["votes"]} if include_observed else set()
        rejected = self.matching_rejections(crew, pot, public)
        for pid in votes:
            if pid == me or pid in observed:
                continue
            if (pid not in crew and pid in self.inclusion_requests and public["rejections"] < 2
                    and self.number - self.inclusion_requests[pid] <= 8):
                votes[pid] = min(votes[pid], .08 + .02 * (self.number - self.inclusion_requests[pid]))
            ballots = [p["votes"][pid] for p in rejected if pid in p["votes"]]
            if ballots:
                strength = min(.9, .65 + .1 * len(ballots))
                support = .05 + .9 * sum(ballots) / len(ballots)
                votes[pid] = (1 - strength) * votes[pid] + strength * support
            for (speaker, target), latest in self.objections.items():
                age = self.number - latest
                if speaker == pid and target in crew and age <= 16:
                    # This predicts a ballot, not the truth of an accusation.
                    votes[pid] = min(votes[pid], .08 + .02 * age)
        return votes

    def describe(self, crew, pot, public):
        return {"recent_matching_rejections": len(self.matching_rejections(crew, pot, public)),
                "active_objections": [{"voter": pid, "target": target}
                                      for (pid, target), latest in self.objections.items()
                                      if target in crew and self.number - latest <= 16]}


@lru_cache(maxsize=128)
def race_probability(needed, opposing_needed):
    """Neutral continuation estimate: equally likely future mission winners.

    This is a bounded planning heuristic, not a learned win probability.
    """
    if needed <= 0:
        return 1.
    if opposing_needed <= 0:
        return 0.
    return .5 * (race_probability(needed - 1, opposing_needed)
                 + race_probability(needed, opposing_needed - 1))
