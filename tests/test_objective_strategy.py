"""Behavioral scenarios for pursuing a card before the final contribution."""

import unittest
from copy import deepcopy

from mission_game.social_policy import SocialPolicy, Traits
from tests.helpers import tokens
from tests.test_policy import observation


CALM = Traits(0, .3, .3)


def table(objective, phase="contribute", wallet=5):
    view = observation(phase, objective=objective, crew_size=3, threshold=10)
    view["public"].update(crew=["p0", "p1", "p2"],
                          pledges={"p0": tokens(blue=2), "p1": tokens(blue=4), "p2": tokens(blue=4)})
    view["public"]["players"][0]["wallet"] = wallet
    return view


def off_crew(objective, wallet=5):
    view = table(objective, "vote", wallet)
    view["public"].update(crew=["p1", "p2", "p3"],
                          pledges={p: tokens(blue=5) for p in ("p1", "p2", "p3")})
    return view


def choose(view):
    return SocialPolicy(3, traits=CALM).choose_action(view)


class ObjectiveStrategyTests(unittest.TestCase):
    def test_saver_protects_reserve_in_both_promises_and_actual_payments(self):
        for phase in ("pledge", "contribute"):
            for wallet in (5, 9, 10):
                with self.subTest(phase=phase, wallet=wallet):
                    self.assertEqual(choose(table("saver", phase, wallet))["tokens"], tokens())
            paid = choose(table("saver", phase, 12))["tokens"]
            self.assertGreater(sum(paid.values()), 0)
            self.assertGreaterEqual(12 - sum(paid.values()), 10)

    def test_crew_planning_uses_saver_and_passenger_zero_payment(self):
        for objective in ("saver", "passenger"):
            view = table(objective, "select_crew")
            view["public"].update(crew=[], pledges={})
            # Only these two other players can fund a ten-token mission.
            for player in view["public"]["players"][3:]:
                player["wallet"] = 0
            policy = SocialPolicy(3, traits=CALM)
            action = policy.choose_action(view)
            self.assertEqual(set(action["crew"]), {"p0", "p1", "p2"})
            self.assertEqual(policy.last_decision["details"]["planned_deposit"], tokens())
            self.assertGreaterEqual(sum(policy.last_decision["details"]["forecast_pot"].values()), 10)

    def test_spendthrift_seeks_a_seat_and_spends_even_early_without_selfish_trait(self):
        view = off_crew("spendthrift")
        self.assertEqual(choose(view), {"type": "vote", "approve": False,
                                       "complaints": [{"modifier": "more", "player_id": "p0"}]})
        self.assertTrue(choose(off_crew("spendthrift", 0))["approve"])
        view = table("spendthrift", "select_crew")
        view["public"].update(crew=[], pledges={})
        self.assertIn("p0", choose(view)["crew"])
        for phase in ("pledge", "contribute"):
            self.assertEqual(sum(choose(table("spendthrift", phase))["tokens"].values()), 5)

    def test_exact_change_distinguishes_continuing_income_from_terminal_wallet(self):
        for phase in ("pledge", "contribute"):
            continuing = table("exact_change", phase, 16)
            terminal = deepcopy(continuing)
            terminal["public"]["score"]["blue"] = 2
            for view, expected in ((continuing, 10), (terminal, 9)):
                paid = sum(choose(view)["tokens"].values())
                self.assertEqual(paid, expected)
        for wallet in (5, 6):
            self.assertEqual(choose(table("exact_change", wallet=wallet))["tokens"], tokens())
        # Maintaining seven through another income payment requires spending one.
        self.assertEqual(sum(choose(table("exact_change", wallet=7))["tokens"].values()), 1)

    def test_exact_change_seeks_access_when_it_needs_to_spend(self):
        self.assertTrue(choose(off_crew("exact_change", 6))["approve"])
        for wallet in (7, 9):
            action = choose(off_crew("exact_change", wallet))
            self.assertFalse(action["approve"])
            self.assertEqual(action["complaints"], [{"modifier": "more", "player_id": "p0"}])
        winning = off_crew("exact_change", 7)
        winning["public"]["score"]["blue"] = 2
        self.assertTrue(choose(winning)["approve"])

    def test_unready_wallet_objectives_do_not_approve_a_personal_loss(self):
        for objective, bad, good in (("saver", 9, 10), ("spendthrift", 1, 0), ("exact_change", 6, 7)):
            for wallet, expected in ((bad, False), (good, True)):
                view = off_crew(objective, wallet)
                view["public"]["score"]["blue"] = 2
                self.assertEqual(choose(view)["approve"], expected)

    def test_reliable_partner_seeks_and_keeps_two_qualifying_pledges(self):
        view = off_crew("reliable_partner")
        self.assertEqual(choose(view)["complaints"], [{"modifier": "more", "player_id": "p0"}])
        view["private"]["objective"]["progress"] = {"value": 2}
        self.assertTrue(choose(view)["approve"])
        self.assertTrue(choose(off_crew("reliable_partner", 1))["approve"])
        for team in ("blue", "red"):
            view = table("reliable_partner", "pledge")
            view["private"]["team"] = team
            for progress in (0, 1):
                view["private"]["objective"]["progress"] = {"value": progress}
                policy = SocialPolicy(3, traits=CALM)
                pledge = policy.choose_action(view)["tokens"]
                self.assertGreaterEqual(sum(pledge.values()), 2)
                self.assertEqual(pledge["red"], 0)
                view["phase"], view["action_spec"]["type"] = "contribute", "contribute"
                view["public"]["pledges"]["p0"] = pledge
                self.assertEqual(policy.choose_action(view)["tokens"], pledge)
                view["phase"], view["action_spec"]["type"] = "pledge", "pledge"

    def test_passenger_demands_a_plausibly_completing_seat_not_any_seat(self):
        view = off_crew("passenger")
        self.assertEqual(choose(view)["complaints"], [{"modifier": "more", "player_id": "p0"}])
        # With weak funding, replacing someone with a zero-paying rider cannot finish.
        for pid in view["public"]["crew"]:
            view["public"]["pledges"][pid] = tokens(blue=1)
        policy = SocialPolicy(3, traits=CALM)
        policy.choose_action(view)
        self.assertFalse(policy.last_decision["details"]["objective_inclusion_protest"])
        view = off_crew("passenger")
        view["private"]["objective"]["progress"] = {"value": 1}
        self.assertTrue(choose(view)["approve"])

    def test_passenger_counts_honored_promises_as_possible_not_guaranteed_completion(self):
        view = table("passenger")
        view["public"]["pledges"] = {p: tokens(blue=5) for p in view["public"]["crew"]}
        self.assertEqual(choose(view)["tokens"], tokens())
        policy = SocialPolicy(3, traits=CALM)
        policy.memory.observe(view)
        policy.beliefs.observe(view, policy.memory)
        for pid in ("p1", "p2"):
            policy.beliefs.players[pid]["broken"] = 30
        policy.choose_action(view)
        pot, _ = policy.forecast(view, ["p0", "p1", "p2"], tokens(), view["public"]["pledges"])
        self.assertLess(policy.completion_support(view, ["p0", "p1", "p2"], tokens(), pot), .1)

    def test_passenger_stops_free_riding_after_qualifying(self):
        view = table("passenger", "pledge")
        self.assertEqual(choose(view)["tokens"], tokens())
        view["private"]["objective"]["progress"] = {"value": 1}
        self.assertGreater(sum(choose(view)["tokens"].values()), 0)

    def test_patron_accepts_opposing_deposits_but_not_an_opposing_final_win(self):
        view = off_crew("opposition_patron")
        view["public"]["pledges"] = {pid: tokens(red=5) for pid in view["public"]["crew"]}
        self.assertTrue(choose(view)["approve"])
        loyalist = deepcopy(view)
        loyalist["private"]["objective"]["id"] = "loyalist"
        self.assertFalse(choose(loyalist)["approve"])
        view["public"]["score"]["red"] = 2
        self.assertFalse(choose(view)["approve"])

    def test_patron_mixes_colors_to_finish_counter_and_win_own_mission(self):
        for team, opposing in (("blue", "red"), ("red", "blue")):
            view = observation("contribute", objective="opposition_patron", team=team, threshold=10)
            view["public"].update(crew=["p0", "p1"], score={team: 2, opposing: 0},
                                  pledges={"p0": tokens(blue=8), "p1": tokens()})
            view["public"]["players"][0]["wallet"] = 8
            view["public"]["mission"]["pot"] = tokens(**{team: 4})
            policy = SocialPolicy(3, traits=CALM)
            policy.memory.observe(view)
            policy.beliefs.observe(view, policy.memory)
            policy.beliefs.paid[opposing] = 17
            paid = policy.choose_action(view)["tokens"]
            self.assertGreaterEqual(paid[opposing], 3)
            self.assertGreater(paid[team], 0)
            self.assertGreater(policy.last_decision["details"]["objective_utility"], 90)
        # Once Blue's counter is filled, a Blue payment wins without further Red.
        view["private"]["team"] = "blue"
        view["public"]["score"] = {"blue": 2, "red": 0}
        view["public"]["mission"]["pot"] = tokens(blue=4)
        policy.beliefs.paid["red"] = 20
        self.assertEqual(policy.choose_action(view)["tokens"]["red"], 0)

    def test_close_race_switches_back_before_giving_opponent_a_third_point(self):
        for team, opposing in (("blue", "red"), ("red", "blue")):
            view = table("close_race")
            view["private"]["team"] = team
            view["public"].update(crew=["p0", "p1", "p2"],
                                  pledges={p: tokens() for p in ("p0", "p1", "p2")})
            for other_score, desired in ((0, opposing), (1, opposing), (2, team)):
                view["public"]["score"] = {team: 1, opposing: other_score}
                paid = choose(view)["tokens"]
                self.assertGreater(paid[desired], paid["red" if desired == "blue" else "blue"])

    def test_objective_protests_relax_under_rejection_pressure(self):
        for objective in ("spendthrift", "exact_change", "reliable_partner", "passenger"):
            view = off_crew(objective, 9)
            policy = SocialPolicy(3, traits=CALM)
            policy.choose_action(view)
            self.assertTrue(policy.last_decision["details"]["objective_inclusion_protest"])
            view["public"]["rejections"] = 5
            policy.choose_action(view)
            self.assertFalse(policy.last_decision["details"]["objective_inclusion_protest"])


if __name__ == "__main__":
    unittest.main()
