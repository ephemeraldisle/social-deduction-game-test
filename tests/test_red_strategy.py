"""Concealment must buy future options without sacrificing decisive results."""
import json
import unittest
from copy import deepcopy

from mission_game.policy import restore_policy
from mission_game.red_strategy import public_cover
from mission_game.social_policy import SocialPolicy, VERSION
from tests.helpers import tokens
from tests.test_ability_strategy import CALM, ready, view


def red_view(score=None, pot=None, wallet=12, objective="loyalist"):
    o = view("auditor", wallet=wallet, score=score or {"blue": 0, "red": 0},
             pot=pot, objective=objective)
    o["private"]["team"] = "red"
    o["public"]["public_badges"] = {}
    o["public"]["pledges"]["p0"] = tokens(blue=min(10, wallet))
    return o


class RedStrategyTests(unittest.TestCase):
    def test_early_covert_red_can_build_cover_and_keep_a_reserve(self):
        o = red_view()
        p = ready(o)
        action = p.choose_action(o)
        self.assertGreater(action["tokens"]["blue"], 0)
        self.assertEqual(action["tokens"]["red"], 0)
        self.assertLess(sum(action["tokens"].values()), o["public"]["players"][0]["wallet"])
        self.assertGreater(p.last_decision["details"]["red_strategy"]["cover_value"], 0)
        legacy = restore_policy({**ready(o).snapshot(), "version": "social.11"})
        self.assertGreaterEqual(legacy.choose_action(o)["tokens"]["red"], 8)

    def test_publicly_exposed_red_takes_the_point_instead_of_buying_cover(self):
        o = red_view()
        o["public"]["public_badges"]["p0"] = "red"
        p = ready(o)
        action = p.choose_action(o)
        self.assertGreaterEqual(action["tokens"]["red"], o["public"]["mission"]["threshold"])
        self.assertEqual(p.last_decision["details"]["red_strategy"]["cover_value"], 0)
        self.assertEqual(p.last_decision["details"]["outcome_likelihoods"]["red"], 1)

    def test_red_takes_a_terminal_win_despite_a_blue_promise(self):
        o = red_view(score={"blue": 0, "red": 2})
        p = ready(o)
        action = p.choose_action(o)
        self.assertGreaterEqual(action["tokens"]["red"], 8)
        self.assertEqual(p.last_decision["details"]["outcome_likelihoods"]["personal_win"], 1)
        self.assertEqual(p.last_decision["details"]["red_strategy"]["continuation_value"], 0)

    def test_red_defends_against_blue_match_point(self):
        o = red_view(score={"blue": 2, "red": 0}, pot=tokens(blue=7))
        p = ready(o)
        action = p.choose_action(o)
        self.assertGreater(action["tokens"]["red"], action["tokens"]["blue"] + 7)
        self.assertEqual(p.last_decision["details"]["outcome_likelihoods"]["personal_loss"], 0)
        self.assertEqual(p.last_decision["details"]["outcome_likelihoods"]["red"], 1)

    def test_no_large_blue_donation_just_to_honor_a_losing_cover_pledge(self):
        o = red_view(score={"blue": 1, "red": 0}, pot=tokens(blue=20))
        p = ready(o)
        action = p.choose_action(o)
        self.assertLessEqual(sum(action["tokens"].values()), 2)
        self.assertGreaterEqual(p.last_decision["details"]["expected_wallet_after_effects"], 10)

    def test_does_not_dump_red_when_the_pot_already_secures_the_point(self):
        o = red_view(pot=tokens(red=12), wallet=20)
        p = ready(o)
        action = p.choose_action(o)
        self.assertEqual(action["tokens"]["red"], 0)
        self.assertLessEqual(sum(action["tokens"].values()), 2)
        self.assertEqual(p.last_decision["details"]["outcome_likelihoods"]["red"], 1)

    def test_terminal_personal_condition_still_controls_spending(self):
        for objective, wallet, pot, remaining in (
                ("saver", 12, tokens(red=6), 10),
                ("spendthrift", 12, tokens(), 0),
                ("exact_change", 9, tokens(red=6), 7)):
            with self.subTest(objective=objective):
                o = red_view(score={"blue": 0, "red": 2}, pot=pot, wallet=wallet, objective=objective)
                p = ready(o)
                action = p.choose_action(o)
                self.assertEqual(wallet - sum(action["tokens"].values()), remaining)
                self.assertEqual(p.last_decision["details"]["outcome_likelihoods"]["personal_win"], 1)

    def test_close_race_can_help_blue_then_stop_at_its_required_score(self):
        o = red_view(score={"blue": 0, "red": 1}, objective="close_race")
        p = ready(o)
        self.assertGreater(p.choose_action(o)["tokens"]["blue"], 0)
        o["public"]["score"]["blue"] = 2
        p = ready(o)
        self.assertGreater(p.choose_action(o)["tokens"]["red"], 0)

    def test_private_receipts_and_blue_claims_do_not_create_public_cover(self):
        o = red_view()
        before = public_cover(o)
        o["private"]["receipts"] = [{"type": "audit", "target": "p0", "attempt": 1, "tokens": tokens(red=12)}]
        o["private"]["last_contribution"] = {"attempt": 1, "tokens": tokens(red=12)}
        self.assertEqual(public_cover(o), before)
        o["history"] = [
            {"id": 1, "type": "crew_selected", "crew": ["p0", "p1"]},
            {"id": 2, "type": "vote_income", "wallets": {f"p{i}": 12 for i in range(8)}},
            {"id": 3, "type": "attempt_resolved", "penalty": False,
             "mission": {"pot": tokens(red=24)},
             "wallets": {f"p{i}": 0 if i < 2 else 12 for i in range(8)}},
        ]
        exposed = public_cover(o)
        self.assertGreater(exposed["public_exposure"], before["public_exposure"])
        o["history"].extend({"id": i, "type": "reports_revealed", "reports": {
            "p0": [{"player_id": "p0", "verb": "gave", "color": "blue", "quantity": 12}]}}
                              for i in range(4, 30))
        self.assertEqual(public_cover(o), exposed)

    def test_blue_actions_and_legacy_versions_are_preserved(self):
        for ability in ("auditor", "recolorer", "thief"):
            o = view(ability, wallet=12, score={"blue": 0, "red": 0})
            state = ready(o).snapshot()
            old = restore_policy({**state, "version": "social.11"})
            new = restore_policy({**state, "version": VERSION})
            self.assertEqual(old.choose_action(o), new.choose_action(o))
            self.assertNotIn("red_strategy", new.last_decision["details"])
        for version in ("social.9", "social.10", "social.11", VERSION):
            p = SocialPolicy(traits=CALM)
            p.version = version
            o = red_view()
            p.choose_action(o)
            clone = restore_policy(json.loads(json.dumps(p.snapshot())))
            self.assertEqual(p.choose_action(o), clone.choose_action(deepcopy(o)))
            self.assertEqual(p.last_decision, clone.last_decision)
            self.assertEqual(p.snapshot(), clone.snapshot())


if __name__ == "__main__":
    unittest.main()
