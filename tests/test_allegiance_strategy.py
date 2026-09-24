"""Verified teams must affect decisions without becoming guaranteed payments."""

import json
import unittest
from copy import deepcopy

from mission_game.policy import restore_policy
from mission_game.social_policy import SocialPolicy
from tests.test_ability_strategy import CALM, ready, view
from tests.test_abilities import ability_game, start, batch
from tests.helpers import tokens


def proposal(objective="loyalist", phase="select_crew", private=False):
    o = view("scout", phase, objective=objective, score={"blue": 1, "red": 0})
    o["action_spec"].update(crew_size=2, players=[f"p{i}" for i in range(8)])
    for player in o["public"]["players"]:
        player["wallet"] = 5
    o["public"].update(public_badges={"p2": "blue"}, crew=["p1", "p2"], votes=[],
                       pledges={"p1": tokens(blue=4), "p2": tokens(blue=4)})
    if private:
        o["private"]["receipts"] = [{"type": "scout", "attempt": 1, "target": "p1", "team": "red"}]
    else:
        o["public"]["public_badges"]["p1"] = "red"
    return o


class AllegianceStrategyTests(unittest.TestCase):
    def test_repeating_blue_pledges_earns_neither_allegiance_nor_reliability(self):
        o = proposal(private=True)
        p = ready(o)
        before = {pid: p.beliefs.estimate(pid) for pid in ("p1", "p3")}
        o["history"] = [{"id": n, "type": "pledges_revealed", "attempt": 1,
                          "pledges": {"p1": tokens(blue=5), "p3": tokens(blue=5)}}
                         for n in range(1, 51)]
        p.beliefs.observe(o, p.memory)
        for pid in before:
            self.assertEqual(p.beliefs.estimate(pid)["blue_preference"], before[pid]["blue_preference"])
            self.assertEqual(p.beliefs.estimate(pid)["pledge_reliability"], before[pid]["pledge_reliability"])
        self.assertEqual(p.beliefs.pledges["p3"], tokens(blue=5))

    def test_blue_claims_cannot_erase_a_badge_or_scout_result(self):
        for private in (False, True):
            o = proposal(private=private)
            p = ready(o)
            for _ in range(100):
                p.beliefs.side("p1", 1., .35)
            estimate = p.beliefs.estimate("p1")
            self.assertEqual(estimate["known_team"], "red")
            self.assertGreater(estimate["behavioral_blue_preference"], .9)
            self.assertGreater(estimate["blue_preference"], 0)
            self.assertLess(estimate["blue_preference"], .25)
            # A Blue badge likewise remains Blue despite contrary behavior.
            p.beliefs.side("p2", 0., 100)
            self.assertGreater(p.beliefs.estimate("p2")["blue_preference"], .75)
            self.assertLess(p.beliefs.estimate("p2")["blue_preference"], 1)

    def test_blue_private_objectives_do_not_recruit_known_red(self):
        for objective in ("loyalist", "opposition_patron", "close_race"):
            for private in (False, True):
                with self.subTest(objective=objective, private=private):
                    o = proposal(objective, private=private)
                    if objective == "close_race":
                        o["public"]["score"]["blue"] = 2
                    # Rich Red and poor alternatives used to tempt crew planning.
                    o["public"]["players"][1]["wallet"] = 20
                    p = ready(o)
                    if objective == "close_race":
                        self.assertEqual(p.tactical_side(o), "red")
                    crew = p.choose_action(o)["crew"]
                    self.assertNotIn("p1", crew)
                    self.assertEqual(len(set(crew)), 2)
                    self.assertEqual(p.last_decision["details"]["known_teams"]["p1"], "red")

    def test_forced_crew_minimizes_known_red_instead_of_becoming_illegal(self):
        o = proposal()
        o["public"]["public_badges"]["p3"] = "red"
        o["action_spec"].update(players=["p0", "p1", "p3"], crew_size=2)
        crew = ready(o).choose_action(o)["crew"]
        self.assertIn("p0", crew)
        self.assertEqual(len(set(crew) & {"p1", "p3"}), 1)

    def test_covert_red_keeps_public_cover_but_exposed_red_can_choose_allies(self):
        o = proposal()
        o["private"]["team"] = "red"
        p = ready(o)
        self.assertNotIn("p1", p.choose_action(o)["crew"])
        o["public"]["public_badges"]["p0"] = "red"
        self.assertEqual(p.crew_concerns(o, ["p0", "p1"]), [])

    def test_enemy_color_promise_gets_discounted_without_becoming_impossible(self):
        o = proposal(phase="vote")
        p = ready(o)
        cases, deposits = p.raw_cases(o, ["p1"], tokens(), o["public"]["pledges"])
        unknown = deepcopy(o)
        unknown["public"]["public_badges"].pop("p1")
        _, naive = ready(unknown).raw_cases(unknown, ["p1"], tokens(), unknown["public"]["pledges"])
        self.assertLess(deposits["p1"]["blue"], naive["p1"]["blue"])
        self.assertGreater(deposits["p1"]["red"], naive["p1"]["red"])
        self.assertGreater(deposits["p1"]["blue"], 0)
        self.assertAlmostEqual(sum(case["mass"] for case in cases), 1)

    def test_a_verified_kept_promise_earns_payment_trust(self):
        g = ability_game({"p0": "auditor"})
        pledges = {"p0": tokens(blue=2), "p1": tokens(blue=2)}
        start(g, pledges)
        o = g.observe("p0")
        p = ready(o)
        _, before = p.raw_cases(o, ["p1"], tokens(), pledges)
        trust = p.beliefs.estimate("p1")["pledge_reliability"]
        batch(g, {pid: {"tokens": payment} for pid, payment in pledges.items()})
        batch(g, {"p0": {"target": "p1"}})
        o = g.observe("p0")
        p.choose_action(o)
        _, after = p.raw_cases(o, ["p1"], tokens(), pledges)
        self.assertGreater(p.beliefs.estimate("p1")["pledge_reliability"], trust)
        self.assertGreater(after["p1"]["blue"], before["p1"]["blue"])

    def test_vote_objects_to_confirmed_red_despite_private_objective_reward(self):
        for objective in ("loyalist", "opposition_patron", "close_race"):
            for private in (False, True):
                o = proposal(objective, "vote", private)
                p = ready(o)
                action = p.choose_action(o)
                self.assertFalse(action["approve"])
                self.assertEqual(action["complaints"], [{"modifier": "less", "player_id": "p1"}])
                self.assertIn("confirms Red", p.last_decision["details"]["complaint_reason"])

    def test_rejection_pressure_and_a_near_certain_personal_win_can_override_objection(self):
        o = proposal(phase="vote")
        o["public"]["mission"]["pot"] = tokens(blue=20)
        o["public"]["score"]["blue"] = 2  # This fixture uses the legacy first-to-three rules.
        self.assertTrue(ready(o).choose_action(o)["approve"])
        o["public"]["score"]["blue"] = 1
        self.assertFalse(ready(o).choose_action(o)["approve"])
        o["public"]["rejections"] = 5
        self.assertTrue(ready(o).choose_action(o)["approve"])

    def test_vote_forecast_uses_public_badges_and_preserves_cast_ballots(self):
        o = proposal(phase="vote", private=True)
        p = ready(o)
        def predicted():
            return p.predict_votes(o, o["public"]["crew"], tokens(blue=8), tokens(), tokens())
        private_only = predicted()
        # Same observer knowledge and pot: only other voters' public knowledge changes.
        o["public"]["public_badges"]["p1"] = "red"
        public = predicted()
        self.assertLess(public["p2"], private_only["p2"])
        self.assertLess(public["p3"], private_only["p3"])
        self.assertEqual(public["p1"], private_only["p1"])
        o["public"]["votes"] = [{"player_id": "p2", "approve": True}, {"player_id": "p3", "approve": False}]
        self.assertEqual(predicted()["p2"], 1)
        self.assertEqual(predicted()["p3"], 0)

    def test_new_and_legacy_controllers_restore_their_own_decisions(self):
        o = proposal("close_race")
        for version in ("social.9", "social.10", "social.11", "social.12"):
            with self.subTest(version=version):
                p = SocialPolicy(traits=CALM)
                p.version = version
                first = p.choose_action(o)
                if version in ("social.11", "social.12"):
                    self.assertNotIn("p1", first["crew"])
                else:
                    self.assertIn("p1", first["crew"])
                restored = restore_policy(json.loads(json.dumps(p.snapshot())))
                self.assertEqual(p.choose_action(o), restored.choose_action(o))
                self.assertEqual(p.last_decision, restored.last_decision)
                self.assertEqual(p.snapshot(), restored.snapshot())


if __name__ == "__main__":
    unittest.main()
