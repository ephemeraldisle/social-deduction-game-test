"""Behavioral regressions for signalling and the deadlocks seen in 0325EC."""

import json
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from math import ceil

from mission_game.coordination import NegotiationEvidence
from mission_game.cli import main
from mission_game.policy import restore_policy
from mission_game.session import Session
from mission_game.social_policy import SocialPolicy, Traits, VERSION
from tests.helpers import tokens
from tests.test_ability_strategy import view, ready


def table(phase="vote", objective="loyalist", score=None):
    o = view("standard_bearer", phase, objective=objective, crew=("p1", "p2"),
             score=score or {"blue": 1, "red": 1})
    o["action_spec"].update(crew_size=2, players=[f"p{i}" for i in range(8)])
    o["public"].update(votes=[], public_badges={"p1": "blue", "p2": "blue"})
    o["public"]["rules"]["missions_to_win"] = 4
    for player in o["public"]["players"]:
        player["wallet"] = 10
    o["public"]["pledges"] = {"p1": tokens(blue=4), "p2": tokens(blue=4)}
    o["history"] = [{"id": 1, "type": "mission_drawn", "attempt": 1,
                     "mission": deepcopy(o["public"]["mission"])}]
    return o


def proposal(o, crew=("p1", "p2"), ballots=None, complaint=None, pledges=None, attempt=1):
    """Append public proposal events, including only ballots actually cast."""
    history = o["history"]
    def event(kind, **data):
        history.append({"id": len(history) + 1, "type": kind, "attempt": attempt, **data})
    event("crew_selected", chairman="p1", crew=list(crew))
    event("pledges_revealed", pledges=pledges or {pid: tokens(blue=4) for pid in crew})
    for pid, approve in (ballots or {"p4": False}).items():
        event("vote", player_id=pid, approve=approve,
              complaints=[] if approve else [complaint or {"player_id": "p2", "color": "red"}])
    if ballots and len(ballots) == 8 and sum(ballots.values()) < 5:
        event("proposal_rejected", rejections=1)


class NegotiationTests(unittest.TestCase):
    def test_all_named_objection_forms_affect_ballots_without_revealing_a_team(self):
        for complaint in ({"player_id": "p2"}, {"player_id": "p2", "color": "red"},
                          {"player_id": "p2", "modifier": "less"}):
            o = table()
            o["public"]["public_badges"] = {}
            proposal(o, complaint=complaint)
            p = ready(o)
            votes = p.predict_votes(o, ["p1", "p2"], tokens(blue=8), tokens(), tokens())
            replaced = p.predict_votes(o, ["p1", "p3"], tokens(blue=8), tokens(), tokens())
            self.assertLess(votes["p4"], .15)
            self.assertGreater(replaced["p4"], votes["p4"])
            self.assertNotIn("p2", p.beliefs.known_teams)
            self.assertEqual(p.beliefs.players["p4"]["soft_red"], 0)
            self.assertEqual(p.beliefs.players["p4"]["red"], 4 * (1 - p.beliefs.prior))

    def test_repeated_refusals_persist_but_do_not_multiply_allegiance_evidence(self):
        o = table()
        o["public"]["public_badges"] = {}
        proposal(o, complaint={"modifier": "less", "player_id": "p2"})
        p = ready(o)
        before = p.beliefs.estimate("p2")["blue_preference"]
        for _ in range(5):
            proposal(o, complaint={"modifier": "less", "player_id": "p2"})
        p.beliefs.observe(o, p.memory)
        self.assertAlmostEqual(p.beliefs.estimate("p2")["blue_preference"], before)
        self.assertLess(p.predict_votes(o, ["p1", "p2"], tokens(blue=8), tokens(), tokens())["p4"], .15)

    def test_more_and_exact_are_not_removal_requests_and_yes_supersedes_a_refusal(self):
        for modifier in ("more", "exact"):
            o = table()
            proposal(o, complaint={"modifier": modifier, "player_id": "p2"})
            self.assertEqual(NegotiationEvidence(o).objections, {})
        o = table()
        proposal(o)
        proposal(o, ballots={"p4": True})
        self.assertEqual(NegotiationEvidence(o).objections, {})

    def test_objections_expire_and_current_ballots_always_win(self):
        o = table()
        proposal(o)
        o["public"]["votes"] = [{"player_id": "p4", "approve": True}]
        self.assertEqual(ready(o).predict_votes(o, ["p1", "p2"], tokens(blue=8), tokens(), tokens())["p4"], 1)
        o["public"]["votes"] = []
        for _ in range(17):
            proposal(o, crew=("p5", "p6"), ballots={"p3": True})
        self.assertGreater(ready(o).predict_votes(o, ["p1", "p2"], tokens(blue=8), tokens(), tokens())["p4"], .4)

    def test_rejected_coalition_changes_next_crew_choice(self):
        o = table("select_crew")
        o["action_spec"]["players"] = ["p0", "p1", "p2", "p3"]
        ballots = {f"p{i}": i in (1, 2, 3) for i in range(8)}
        for _ in range(3):
            proposal(o, ballots=ballots, complaint={"modifier": "more", "color": "blue"})
        p = ready(o)
        votes = p.predict_votes(o, ["p1", "p2"], tokens(blue=8), tokens(), tokens())
        self.assertLess(votes["p4"], .2)
        self.assertNotEqual(set(p.choose_action(o)["crew"]), {"p1", "p2"})

    def test_better_funding_or_a_new_mission_can_rehabilitate_a_rejected_crew(self):
        o = table()
        ballots = {f"p{i}": i < 3 for i in range(8)}
        proposal(o, ballots=ballots, complaint={"modifier": "more", "color": "blue"},
                 pledges={"p1": tokens(blue=1), "p2": tokens(blue=1)})
        evidence = NegotiationEvidence(o)
        self.assertEqual(len(evidence.matching_rejections(["p1", "p2"], tokens(blue=2), o["public"])), 1)
        self.assertEqual(evidence.matching_rejections(["p1", "p2"], tokens(blue=8), o["public"]), [])
        o["public"]["mission"]["number"] += 1
        self.assertEqual(NegotiationEvidence(o).proposals, [])


class CooperationTests(unittest.TestCase):
    def test_legacy_complaints_change_only_when_a_saved_bot_is_upgraded(self):
        o = table(score={"blue": 3, "red": 1})
        o["private"]["team"] = "red"
        old = SocialPolicy(2)
        old.version = "social.13"
        old = restore_policy(json.loads(json.dumps(old.snapshot())))
        self.assertEqual(old.choose_action(o)["complaints"],
                         [{"modifier": "exact", "player_id": "p1", "color": "blue"}])
        self.assertEqual(SocialPolicy(2).choose_action(o)["complaints"],
                         [{"modifier": "more", "color": "blue"}])

    def test_uncertain_reliability_never_becomes_an_exact_blue_player_complaint(self):
        for team in ("blue", "red"):
            for reliability in (.75, .819):
                for seed in range(16):
                    o = table(score={"blue": 3, "red": 1})
                    o["private"]["team"] = team
                    p = SocialPolicy(seed)
                    p.memory.observe(o)
                    p.beliefs.observe(o, p.memory)
                    for pid in ("p1", "p2"):
                        p.beliefs.players[pid].update(kept=4 * reliability, broken=4 * (1 - reliability))
                    complaint, _ = p.complaint(o, {"advertised_pot": tokens(blue=8)}, False)
                    self.assertEqual(complaint, {"modifier": "more", "color": "blue"})
                    if team == "red":
                        action = p.choose_action(o)
                        self.assertFalse(action["approve"])
                        self.assertNotEqual(action["complaints"][0].get("modifier"), "exact")
                        self.assertNotIn("player_id", action["complaints"][0])

    def test_unresolved_public_objection_can_support_a_coalition_complaint(self):
        for team in ("blue", "red"):
            o = table()
            o["private"]["team"] = team
            o["public"]["public_badges"].pop("p1")
            proposal(o, complaint={"player_id": "p1"})
            p = ready(o)
            complaint, reason = p.complaint(o, {"advertised_pot": tokens(blue=8)}, False)
            self.assertEqual(complaint, {"modifier": "less", "player_id": "p1"})
            self.assertIn("build support", reason)
            self.assertNotIn("p1", p.beliefs.known_teams)
            # A dispute does not justify repeating an attack on confirmed Blue.
            p.beliefs.known_teams["p1"] = "blue"
            complaint, _ = p.complaint(o, {"advertised_pot": tokens(blue=8)}, False)
            self.assertNotIn("player_id", complaint)

    def test_named_funding_requests_require_a_funding_problem(self):
        o = table()
        o["public"]["pledges"] = {"p1": tokens(blue=10), "p2": tokens(blue=1)}
        for seed in range(16):
            p = SocialPolicy(seed)
            p.memory.observe(o)
            p.beliefs.observe(o, p.memory)
            complaint, _ = p.complaint(o, {"advertised_pot": tokens(blue=11)}, False)
            self.assertNotIn("player_id", complaint)
        o["public"]["pledges"] = {"p1": tokens(blue=4), "p2": tokens()}
        complaints = set()
        for seed in range(16):
            p = SocialPolicy(seed)
            p.memory.observe(o)
            p.beliefs.observe(o, p.memory)
            complaint, _ = p.complaint(o, {"advertised_pot": tokens(blue=4)}, False)
            complaints.add(json.dumps(complaint, sort_keys=True))
        self.assertIn(json.dumps({"modifier": "more", "player_id": "p2", "color": "blue"}, sort_keys=True), complaints)

    def test_repeated_unsupported_attacks_on_blue_add_bounded_suspicion(self):
        for complaint in ({"player_id": "p2"}, {"modifier": "less", "player_id": "p2"},
                          {"modifier": "more", "color": "blue"}):
            o = table()
            baseline = ready(o).beliefs.estimate("p4")["blue_preference"]
            proposal(o, complaint=complaint)
            p = ready(o)
            self.assertEqual(p.beliefs.estimate("p4")["blue_preference"], baseline)
            for _ in range(5):
                proposal(o, complaint=complaint)
            p.beliefs.observe(o, p.memory)
            self.assertLess(p.beliefs.estimate("p4")["blue_preference"], .3)
            self.assertEqual(p.beliefs.players["p4"]["hostility_weight"], 6)
            self.assertNotIn("p4", p.beliefs.known_teams)
            self.assertEqual(p.beliefs.known_teams["p2"], "blue")
            self.assertGreater(p.beliefs.estimate("p2")["blue_preference"], .75)
            clone = restore_policy(json.loads(json.dumps(p.snapshot())))
            clone.beliefs.observe(o, clone.memory)
            self.assertEqual(clone.beliefs.players, p.beliefs.players)

    def test_earned_blue_reputation_counts_but_rumors_alone_do_not(self):
        for earned in (False, True):
            o = table()
            o["public"]["public_badges"] = {}
            p = ready(o)
            target = p.beliefs.players["p2"]
            if earned:
                target.update(blue=20, public_kept=1)
            else:
                target.update(soft_blue=20)
            for _ in range(4):
                proposal(o, complaint={"modifier": "less", "player_id": "p2"})
            p.beliefs.observe(o, p.memory)
            self.assertEqual(p.beliefs.players["p4"].get("hostility_count", 0), 4 if earned else 0)

    def test_concrete_concerns_and_access_requests_do_not_become_team_accusations(self):
        for concern in ("underfunded", "red_funding", "unreliable", "access", "mixed_crew"):
            o = table()
            p = ready(o)
            pledges = {"p1": tokens(blue=4), "p2": tokens(blue=4)}
            complaint = {"modifier": "less", "player_id": "p2"}
            if concern == "underfunded":
                pledges["p2"] = tokens()
            elif concern == "red_funding":
                pledges["p2"] = tokens(red=4)
            elif concern == "unreliable":
                p.beliefs.players["p2"]["broken"] = 8
            elif concern == "access":
                complaint = {"modifier": "more", "player_id": "p4"}
            elif concern == "mixed_crew":
                o["public"]["public_badges"].pop("p1")
                complaint = {"modifier": "more", "color": "blue"}
            for _ in range(6):
                proposal(o, complaint=complaint, pledges=pledges)
            p.beliefs.observe(o, p.memory)
            self.assertEqual(p.beliefs.players["p4"].get("hostility_count", 0), 0, concern)

    def test_red_changes_ballot_to_avoid_repeated_obstruction_of_established_blue(self):
        o = table(score={"blue": 0, "red": 0})
        o["private"]["team"] = "red"
        p = SocialPolicy(traits=Traits(0, 0, 1))
        self.assertFalse(p.choose_action(o)["approve"])
        proposal(o, ballots={"p0": False}, complaint={"modifier": "less", "player_id": "p2"})
        self.assertTrue(p.choose_action(o)["approve"])
        self.assertGreater(p.last_decision["details"]["vote_assessment"]["opposition_exposure_cost"], 0)
        # Cover cannot justify conceding a likely game-ending loss.
        o["public"]["score"]["blue"] = 3
        self.assertFalse(p.choose_action(o)["approve"])
        self.assertEqual(p.last_decision["details"]["vote_assessment"]["opposition_exposure_cost"], 0)

    def test_proposers_support_their_crew_when_the_expected_pledges_arrive(self):
        for team in ("blue", "red"):
            for seed in range(4):
                o = table("select_crew", score={"blue": 0, "red": 0})
                o["private"]["team"] = team
                o["public"]["chairman"] = "p0"
                p = SocialPolicy(seed, traits=Traits(.5, .8, .2))
                crew = p.choose_action(o)["crew"]
                d = p.last_decision["details"]
                self.assertTrue(d["self_supported"])
                planned = d["planned_deposit"]
                share = max(1, ceil((8 - sum(planned.values())) / max(1, len(crew) - 1))) if "p0" in crew else 4
                o["public"].update(crew=crew, pledges={pid: tokens(blue=min(10, share)) for pid in crew}, votes=[])
                if "p0" in crew:
                    o["public"]["pledges"]["p0"] = p.public_promise(o, planned)
                o["phase"] = o["action_spec"]["type"] = "vote"
                p = restore_policy(json.loads(json.dumps(p.snapshot())))
                self.assertTrue(p.choose_action(o)["approve"])
                self.assertIn("sponsorship_review", p.last_decision["details"])

    def test_proposer_can_reconsider_when_revealed_pledges_cannot_fund_anything(self):
        o = table("select_crew")
        o["public"]["chairman"] = "p0"
        o["public"]["players"][0]["wallet"] = 0
        o["action_spec"]["players"] = ["p1", "p2"]
        p = ready(o)
        crew = p.choose_action(o)["crew"]
        self.assertTrue(p.last_decision["details"]["self_supported"])
        o["public"].update(crew=crew, pledges={pid: tokens() for pid in crew})
        o["phase"] = o["action_spec"]["type"] = "vote"
        self.assertFalse(p.choose_action(o)["approve"])
        self.assertIn("revealed pledges changed", p.last_decision["reason"])
        self.assertTrue(p.last_decision["details"]["vote_assessment"]["no_progress"])

    def test_red_cover_votes_and_public_complaints_are_varied_and_reproducible(self):
        ballots, complaints = set(), set()
        for seed in range(24):
            o = table(score={"blue": 0, "red": 0})
            o["public"]["mission"]["pot"]["red"] = 1
            o["private"]["team"] = "red"
            first, second = SocialPolicy(seed), SocialPolicy(seed)
            action = first.choose_action(o)
            self.assertEqual(action, second.choose_action(o))
            ballots.add(action["approve"])
            if not action["approve"]:
                complaints.add(json.dumps(action["complaints"], sort_keys=True))
                self.assertIn(action["complaints"][0], ({"modifier": "more", "color": "blue"},
                                                       {"modifier": "less", "color": "red"}))
        self.assertEqual(ballots, {False, True})
        self.assertGreaterEqual(len(complaints), 2)

    def test_cover_vote_cannot_concede_a_likely_terminal_loss(self):
        o = table(score={"blue": 3, "red": 1})
        o["private"]["team"] = "red"
        for seed in range(4):
            p = SocialPolicy(seed, traits=Traits(.5, 1, 0))
            self.assertFalse(p.choose_action(o)["approve"])
            self.assertEqual(p.last_decision["details"]["vote_assessment"]["cover_vote_value"], 0)

    def test_completed_passenger_and_selfish_loyalist_support_blue_without_a_seat(self):
        for objective in ("passenger", "loyalist"):
            o = table(objective=objective)
            o["private"]["objective"]["progress"] = {"value": 1, "condition_met": True}
            p = SocialPolicy(traits=Traits(1, .3, .3))
            self.assertTrue(p.choose_action(o)["approve"])
            self.assertFalse(p.last_decision["details"]["exclusion_protest"])

    def test_wallet_objectives_release_seat_demand_after_two_rejections(self):
        for objective in ("spendthrift", "exact_change"):
            o = table(objective=objective)
            p = ready(o)
            p.choose_action(o)
            self.assertTrue(p.last_decision["details"]["objective_inclusion_protest"])
            o["public"]["rejections"] = 2
            self.assertTrue(p.choose_action(o)["approve"])
            self.assertFalse(p.last_decision["details"]["objective_inclusion_protest"])

    def test_match_point_blue_progress_beats_waiting_despite_some_sabotage_risk(self):
        o = table(objective="close_race", score={"blue": 2, "red": 3})
        o["public"]["public_badges"].pop("p1")
        o["public"]["mission"].update(pot=tokens(blue=1, red=11), threshold=17)
        o["public"]["pledges"] = {"p1": tokens(blue=50), "p2": tokens(blue=30)}
        for player in o["public"]["players"]:
            player["wallet"] = 80
        o["public"]["rejections"] = 1
        p = ready(o)
        action = p.choose_action(o)
        d = p.last_decision["details"]
        self.assertGreater(d["outcome_likelihoods"]["personal_loss"], .08)
        self.assertTrue(action["approve"])
        self.assertLess(d["rejection_value"], 0)

    def test_rejection_cost_grows_before_the_eighth_ballot(self):
        o = table(score={"blue": 2, "red": 3})
        o["public"]["mission"]["pot"] = tokens(red=4)
        p = ready(o)
        values = []
        for count in (0, 3, 6):
            o["public"]["rejections"] = count
            p.choose_action(o)
            values.append(p.last_decision["details"]["rejection_value"])
        self.assertGreater(values[0], values[1])
        self.assertGreater(values[1], values[2])

    def test_majority_terminal_loss_is_still_rejected(self):
        o = table(score={"blue": 2, "red": 3})
        o["public"]["public_badges"] = {"p1": "red", "p2": "red"}
        o["public"]["pledges"] = {pid: tokens(red=10) for pid in ("p1", "p2")}
        self.assertFalse(ready(o).choose_action(o)["approve"])

    def test_close_race_builds_own_score_before_helping_opponent_and_stops_in_time(self):
        o = table(objective="close_race")
        for score, side in (({"blue": 2, "red": 2}, "blue"),
                            ({"blue": 3, "red": 2}, "red"), ({"blue": 3, "red": 3}, "blue")):
            o["public"]["score"] = score
            self.assertEqual(ready(o).tactical_side(o), side)

    def test_public_success_builds_limited_trust_without_certifying_payments(self):
        o = table()
        o["public"]["public_badges"] = {}
        proposal(o, ballots={"p4": True})
        before = ready(o)
        for index in range(3):
            if index:
                proposal(o, ballots={"p4": True}, attempt=index + 1)
            o["history"].append({"id": len(o["history"]) + 1, "type": "attempt_resolved", "attempt": index + 1,
                                 "penalty": False, "mission": {"pot": tokens(blue=8 * (index + 1))},
                                 "wallets": {f"p{i}": max(0, 5 - 4 * (index + 1)) if i in (1, 2) else 5 for i in range(8)}})
        after = ready(o)
        self.assertGreater(after.beliefs.estimate("p1")["pledge_reliability"], before.beliefs.estimate("p1")["pledge_reliability"])
        self.assertLess(after.beliefs.estimate("p1")["pledge_reliability"], .9)
        self.assertEqual(after.beliefs.known_teams, {})
        self.assertEqual(after.beliefs.last_resolution["known"], {})
        self.assertEqual(after.beliefs.paid, {"blue": 0, "red": 0})
        saved = after.beliefs.snapshot()
        after.beliefs.observe(o, after.memory)
        self.assertEqual(after.beliefs.players, saved["players"])

    def test_large_wallet_reward_cannot_outweigh_a_game_result(self):
        p = SocialPolicy()
        self.assertLess(p.objective_value(1000), p.settings.terminal_weight / 3)
        self.assertGreater(p.objective_value(1000), p.objective_value(100))

    def test_versions_restore_deterministically_and_legacy_seat_veto_survives(self):
        o = table()
        for version in ("social.9", "social.10", "social.11", "social.12", "social.13", VERSION):
            p = SocialPolicy(traits=Traits(1, .3, .3))
            p.version = version
            action = p.choose_action(o)
            self.assertEqual(action["approve"], version in ("social.13", VERSION))
            clone = restore_policy(json.loads(json.dumps(p.snapshot())))
            self.assertEqual(p.choose_action(o), clone.choose_action(o))
            self.assertEqual(p.last_decision, clone.last_decision)
            self.assertEqual(p.snapshot(), clone.snapshot())


class UpgradeTests(unittest.TestCase):
    def test_upgrade_backs_up_exact_save_and_preserves_game_history_and_randomness(self):
        session = Session(42, human_seat=0)
        for policy in session.policies.values():
            policy.version = "social.13"
        original = session.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            session.save(path)
            original_bytes = path.read_bytes()
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["upgrade-bots", str(path)]), 0)
            self.assertEqual(path.with_name(f"session.before-{VERSION}.json").read_bytes(), original_bytes)
            upgraded = Session.load(path)
            current = upgraded.snapshot()
            for key in ("game", "initial", "bot_decisions", "human_id"):
                self.assertEqual(json.loads(json.dumps(current[key])), json.loads(json.dumps(original[key])))
            for pid, policy in upgraded.policies.items():
                self.assertEqual(policy.version, VERSION)
                self.assertEqual(policy.rng.getstate(), session.policies[pid].rng.getstate())
                self.assertEqual(policy.memory.own_deposits, session.policies[pid].memory.own_deposits)
            upgraded.replay()
            unchanged = path.read_bytes()
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["upgrade-bots", str(path)]), 0)
            self.assertEqual(path.read_bytes(), unchanged)

    def test_upgrade_does_not_share_another_seats_scout_receipt(self):
        session = Session(42, human_seat=0)
        for policy in session.policies.values():
            policy.version = "social.12"
        unbadged = next(p for p in session.game.players if p.id != "p0" and p.ability != "standard_bearer")
        session.game.private_receipts["p0"].append({"type": "scout", "attempt": 1, "target": unbadged.id, "team": unbadged.team})
        session.upgrade_social_policies()
        for policy in session.policies.values():
            self.assertNotIn(unbadged.id, policy.beliefs.known_teams)


if __name__ == "__main__":
    unittest.main()
