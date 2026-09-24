"""Decision failures found in A72C20, using only seat-visible information."""

import unittest
import json
from copy import deepcopy

from mission_game.ability_forecasts import EffectEvidence
from mission_game.coordination import NegotiationEvidence
from mission_game.policy import restore_policy
from tests.test_ability_strategy import view, ready
from tests.test_coordination import table, proposal
from tests.helpers import tokens


def result(o, blue, red, spending, reports=False):
    history = o["history"]
    def event(kind, **values):
        history.append({"id": len(history) + 1, "attempt": len(history) + 1, "type": kind, **values})
    attempt = len(history) + 1
    event("mission_drawn", mission={"number": attempt, "threshold": 30, "pot": tokens()})
    event("income", wallets={f"p{i}": 20 for i in range(8)})
    event("crew_selected", chairman="p1", crew=["p1", "p2"])
    event("pledges_revealed", pledges={"p1": tokens(blue=1), "p2": tokens(blue=2)})
    event("attempt_resolved", attempt=attempt, penalty=False, mission={"pot": tokens(blue=blue, red=red)},
          wallets={f"p{i}": 20 - spending.get(f"p{i}", 0) for i in range(8)})
    if reports:
        event("reports_revealed", attempt=attempt, reports={pid: [{"player_id": pid, "verb": "gave", "color": "blue", "quantity": 3}]
                                                          for pid in ("p1", "p2")})


class ReplayStrategyTests(unittest.TestCase):
    def test_current_saved_table_relearns_new_evidence_from_its_own_history(self):
        o = table()
        o["public"]["public_badges"] = {}
        result(o, 3, 16, {"p1": 15, "p2": 2})
        p = ready(o)
        saved = json.loads(json.dumps(p.snapshot()))
        saved["beliefs"].pop("public_paid_estimates")  # Save from before this revision.
        restored = restore_policy(saved)
        self.assertEqual(restored.beliefs.cursor, 0)
        restored.choose_action(o)
        self.assertLess(restored.beliefs.estimate("p1")["blue_preference"], .4)
        self.assertEqual(restored.beliefs.known_teams, {})
        self.assertEqual(restored.memory.own_deposits, p.memory.own_deposits)

    def test_tiny_or_zero_pledge_cannot_hide_full_wallet_sabotage(self):
        for pledge in (0, 1):
            o = table()
            o["public"]["public_badges"] = {}
            o["public"]["rules"]["vote_income"] = 1
            o["public"]["crew"] = ["p1"]
            o["public"]["players"][1]["wallet"] = 15
            o["public"]["pledges"] = {"p1": tokens(blue=pledge)}
            p = ready(o)
            cases, _ = p.raw_cases(o, ["p1"], tokens(), o["public"]["pledges"])
            self.assertTrue(any(c["pot"]["red"] == 16 and c["mass"] > 0 for c in cases))
            self.assertAlmostEqual(sum(c["mass"] for c in cases), 1)
            self.assertTrue(all(c["wallets"]["p1"] >= 0 for c in cases))

    def test_large_public_red_surge_implicates_large_spender_without_revealing_role(self):
        o = table()
        o["public"]["public_badges"] = {}
        result(o, 3, 16, {"p1": 15, "p2": 2})
        p = ready(o)
        self.assertLess(p.beliefs.estimate("p1")["blue_preference"], .4)
        self.assertGreater(p.beliefs.estimate("p2")["blue_preference"], .5)
        self.assertEqual(p.beliefs.known_teams, {})
        self.assertEqual(p.beliefs.last_resolution["known"], {})
        before = deepcopy(p.beliefs.players)
        p.beliefs.observe(o, p.memory)
        self.assertEqual(p.beliefs.players, before)

    def test_small_unexplained_red_change_does_not_frame_a_cooperator(self):
        o = table()
        o["public"]["public_badges"] = {}
        result(o, 14, 1, {"p1": 12, "p2": 3})
        p = ready(o)
        self.assertEqual(p.beliefs.players["p1"].get("public_red_support", 0), 0)
        self.assertEqual(p.beliefs.players["p2"].get("public_red_support", 0), 0)

    def test_patron_uses_discounted_table_progress_without_fabricating_receipts(self):
        o = table(objective="opposition_patron")
        o["private"]["team"] = "red"
        for _ in range(3):
            result(o, 14, 1, {"p1": 10, "p2": 5})
        p = ready(o)
        self.assertEqual(p.beliefs.paid["blue"], 0)
        self.assertEqual(p.beliefs.verified_deposits, {})
        self.assertGreaterEqual(p.patron_progress("blue"), 20)
        self.assertTrue(p.condition(o, tokens(red=30), tokens(), [], tokens(), paid=tokens()))
        incentive = p.objective_incentive(o, tokens(blue=10), tokens(blue=10), ["p0"], tokens(),
                                          wallet_after=0, paid=tokens(blue=10))
        self.assertEqual(incentive, 0)

    def test_spendthrift_pledge_plans_the_income_before_choosing_a_color(self):
        o = view("stowaway", "pledge", wallet=1, objective="spendthrift", pot=tokens(blue=4, red=6),
                 score={"blue": 3, "red": 3})
        o["public"]["rules"].update(vote_income=1, missions_to_win=4)
        o["public"]["mission"]["threshold"] = 21
        o["public"]["players"][1]["wallet"] = 14
        o["public"]["pledges"] = {}
        p = ready(o)
        action = p.choose_action(o)
        self.assertEqual(action["tokens"], tokens(blue=1))
        self.assertEqual(p.last_decision["details"]["planned_deposit"], tokens(blue=2))
        self.assertGreater(p.last_decision["details"]["outcome_likelihoods"]["personal_win"], .3)

    def test_terminal_color_safety_beats_honoring_an_obsolete_green_pledge(self):
        o = view("stowaway", wallet=2, objective="spendthrift", pot=tokens(blue=4, red=6),
                 score={"blue": 3, "red": 3})
        o["public"]["rules"]["missions_to_win"] = 4
        o["public"]["mission"]["threshold"] = 21
        o["public"]["players"][1]["wallet"] = 15
        o["public"]["pledges"] = {"p0": tokens(green=1), "p1": tokens(blue=14)}
        self.assertEqual(ready(o).choose_action(o)["tokens"], tokens(blue=2))

    def test_repeated_small_discrepancies_create_contingencies_not_verified_effects(self):
        o = table()
        for _ in range(3):
            result(o, 5, 1, {"p1": 3, "p2": 3}, reports=True)
        model = EffectEvidence()
        model.observe(o)
        hypotheses = model.hypotheses(["p3", "p4"])
        self.assertEqual(len(hypotheses), 1)
        self.assertEqual(hypotheses[0]["delta"], {"blue": -1, "red": 1, "green": 0})
        self.assertLessEqual(hypotheses[0]["confidence"], .25)
        self.assertTrue(all(r["residual"] is None and r["known"] == {} for r in model.attempts.values()))
        cases = model.scenarios({"pot": tokens(blue=4, red=4), "mass": 1}, ["p3", "p4"])
        self.assertTrue(any(c["pot"] == tokens(blue=3, red=5) for c in cases))
        self.assertTrue(any(c["pot"] == tokens(blue=4, red=4) for c in cases))

    def test_named_seat_demand_changes_coalition_forecast_until_recanted(self):
        o = table()
        proposal(o, complaint={"modifier": "more", "player_id": "p4"})
        p = ready(o)
        votes = p.predict_votes(o, ["p1", "p2"], tokens(blue=8), tokens(), tokens())
        self.assertLess(votes["p4"], .15)
        proposal(o, ballots={"p4": True})
        self.assertNotIn("p4", NegotiationEvidence(o).inclusion_requests)


if __name__ == "__main__":
    unittest.main()
