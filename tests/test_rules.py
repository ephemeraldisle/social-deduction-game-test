import unittest

from mission_game import ActionError, Game, GameConfig
from mission_game.types import Phase, Tokens, mission_winner
from tests.helpers import game, proposal, reports, resolve, submit, tokens


class ScoringTests(unittest.TestCase):
    def test_designer_scoring_examples(self):
        cases = [(Tokens(2, 3, 5), "red"), (Tokens(3, 3, 4), "blue"),
                 (Tokens(0, 0, 10), None), (Tokens(4, 4, 1), None),
                 (Tokens(0, 1, 9), "red")]
        for pot, expected in cases:
            with self.subTest(pot=pot):
                self.assertEqual(mission_winner(pot, 10), expected)

    def test_incomplete_mission_accumulates_and_retains_card(self):
        g = game()
        first_card = (g.mission.number, g.mission.threshold, g.mission.crew_size)
        resolve(g, {"p0": tokens(blue=1), "p1": tokens(red=1)})
        self.assertEqual(g.mission.pot, Tokens(1, 1, 0))
        self.assertEqual(g.score, {"blue": 0, "red": 0})
        self.assertEqual(g.players[0].wallet, 4)
        reports(g)
        self.assertEqual(g.players[0].wallet, 5)
        self.assertEqual(g.mission.attempts, 2)
        self.assertEqual((g.mission.number, g.mission.threshold, g.mission.crew_size), first_card)
        resolve(g, {"p0": tokens(blue=3), "p1": tokens(red=3)})
        self.assertEqual(g.score["blue"], 1)
        self.assertEqual(g.mission.pot, Tokens(4, 4, 0))

    def test_all_green_stays_open_until_competitive_token(self):
        g = game()
        resolve(g, {"p0": tokens(green=4), "p1": tokens(green=4)})
        self.assertIsNone(g.mission.winner)
        reports(g)
        resolve(g, {"p0": tokens(red=1)})
        self.assertEqual(g.mission.winner, "red")
        self.assertEqual(g.mission.pot.total, 9)

    def test_surplus_awards_one_point_and_does_not_carry(self):
        g = game()
        resolve(g, {"p0": tokens(blue=5), "p1": tokens(blue=5)})
        self.assertEqual(g.score["blue"], 1)
        self.assertEqual(g.completed_missions[0]["pot"], tokens(blue=10))
        reports(g)
        self.assertEqual(g.mission.pot.total, 0)
        self.assertEqual(g.mission.number, 2)
        self.assertEqual(g.accounting["removed"], 10)
        g.assert_invariants()

    def test_third_mission_freezes_wallets_before_closing_reports(self):
        g = game(max_attempts=3)
        for index, crew in enumerate((("p0", "p1"), ("p2", "p3"), ("p4", "p5"))):
            resolve(g, {pid: tokens(blue=4) for pid in crew}, crew=crew)
            if index < 2:
                reports(g)
        self.assertEqual(g.status, "CLOSING")
        self.assertEqual(g.score["blue"], 3)
        wallets = [p.wallet for p in g.players]
        frozen = g.snapshot()["frozen_result"]
        reports(g)
        self.assertEqual(g.status, "FINISHED")
        self.assertEqual([p.wallet for p in g.players], wallets)
        self.assertEqual(g.frozen_result, frozen)
        self.assertEqual(g.accounting["income"], 16)
        self.assertEqual(g.frozen_result["reason"], "three_missions")
        for p in g.players:
            self.assertEqual(g.observe(p.id)["private"]["result"]["won"], p.team == "blue")
        before = g.snapshot()
        with self.assertRaises(ActionError):
            g.submit("p0", "new-request", g.revision, {"type": "select_crew", "crew": ["p0", "p1"]})
        self.assertEqual(g.snapshot(), before)

    def test_guard_closes_after_reports_without_income_or_winner(self):
        g = game(max_attempts=1)
        resolve(g)
        self.assertEqual(g.status, "ACTIVE")
        self.assertIsNone(g.frozen_result)
        reports(g)
        self.assertEqual(g.status, "UNRESOLVED")
        self.assertIsNone(g.frozen_result["winner"])
        self.assertFalse(any(p["won"] for p in g.frozen_result["players"].values()))
        self.assertEqual(g.accounting["income"], 0)
        self.assertEqual([p.wallet for p in g.players], [5] * 8)


class ProposalTests(unittest.TestCase):
    def test_all_eight_vote_clockwise_even_when_decided(self):
        g = game()
        chairman = g.chairman
        submit(g, f"p{chairman}", {"type": "select_crew", "crew": ["p0", "p1"]})
        for pid in g.crew:
            submit(g, pid, {"type": "pledge", "tokens": tokens()})
        for i in range(8):
            expected = f"p{(chairman + i) % 8}"
            self.assertEqual(list(g.pending_requests()), [expected])
            self.assertEqual(g.phase, Phase.VOTE)
            submit(g, expected, {"type": "vote", "approve": True})
        self.assertEqual(g.phase, Phase.CONTRIBUTE)
        self.assertEqual(len(g.votes), 8)

    def test_tied_vote_rejects_without_spending_or_income(self):
        g = game()
        chairman = g.chairman
        proposal(g, pledges={"p0": tokens(blue=5), "p1": tokens(red=5)}, approvals=4)
        self.assertEqual(g.phase, Phase.SELECT_CREW)
        self.assertEqual(g.chairman, (chairman + 1) % 8)
        self.assertEqual(g.rejections, 1)
        self.assertEqual(g.attempt, 1)
        self.assertEqual([p.wallet for p in g.players], [5] * 8)
        self.assertEqual(g.mission.pot.total, 0)
        self.assertEqual(g.accounting["income"], 0)

    def test_eight_rejections_pay_one_penalty_then_one_income(self):
        g = game()
        first_chairman = g.chairman
        for index in range(8):
            self.assertEqual(g.chairman, (first_chairman + index) % 8)
            proposal(g, approvals=0)
            self.assertEqual(g.accounting["income"], 0 if index < 7 else 8)
        self.assertEqual(g.phase, Phase.SELECT_CREW)
        self.assertEqual(g.crew, [])
        self.assertEqual(g.mission.pot, Tokens(red=5))
        self.assertEqual(g.accounting["penalty"], 5)
        self.assertIsNone(g.mission.winner)
        self.assertFalse(any(e["type"] == "reports_revealed" for e in g.events))
        self.assertEqual([p.wallet for p in g.players], [6] * 8)
        self.assertEqual(g.accounting["income"], 8)
        self.assertEqual(g.chairman, first_chairman)
        self.assertEqual(g.rejections, 0)
        self.assertEqual(g.attempt, 2)

    def test_rejection_penalty_can_complete_for_blue(self):
        g = game(threshold=10, threshold_max=10)
        resolve(g, {"p0": tokens(blue=5)})
        reports(g)
        for _ in range(8):
            proposal(g, approvals=0)
        self.assertEqual(g.resolutions[-1]["mission"]["pot"], tokens(blue=5, red=5))
        self.assertEqual(g.resolutions[-1]["mission"]["winner"], "blue")
        self.assertEqual(g.mission.number, 2)
        self.assertEqual(g.phase, Phase.SELECT_CREW)

    def test_terminal_penalty_skips_reports_and_income(self):
        for completed, expected in ((2, "FINISHED"), (0, "UNRESOLVED")):
            g = game(max_attempts=completed + 1)
            for index in range(completed):
                crew = (f"p{index * 2}", f"p{index * 2 + 1}")
                resolve(g, {pid: tokens(red=4) for pid in crew}, crew=crew)
                reports(g)
            income_before = g.accounting["income"]
            events_before = len(g.events)
            # A token-conserving fixture makes the next penalty complete.
            g.players[7].wallet -= 3
            g.mission.pot = Tokens(red=3)
            for _ in range(8):
                proposal(g, approvals=0)
            self.assertEqual(g.status, expected)
            self.assertEqual(g.phase, Phase.GAME_OVER)
            self.assertEqual(g.pending_requests(), {})
            self.assertEqual(g.accounting["income"], income_before)
            self.assertFalse(any(e["type"] == "reports_revealed" for e in g.events[events_before:]))

    def test_pledge_is_not_binding_or_escrow(self):
        g = game()
        proposal(g, pledges={"p0": tokens(blue=5), "p1": tokens(red=5)})
        self.assertEqual([p.wallet for p in g.players], [5] * 8)
        submit(g, "p0", {"type": "contribute", "tokens": tokens(red=1)})
        submit(g, "p1", {"type": "contribute", "tokens": tokens()})
        self.assertEqual(g.mission.pot, Tokens(red=1))
        self.assertEqual(g.resolutions[0]["original_contributions"]["p0"], tokens(red=1))

    def test_empty_wallet_remains_crew_eligible(self):
        g = game()
        # Token-conserving designer fixture, not a standard random deal.
        snapshot = g.snapshot()
        snapshot["players"][0]["wallet"] = 0
        snapshot["players"][7]["wallet"] = 10
        scenario = Game.from_snapshot(snapshot)
        proposal(scenario, pledges={"p0": tokens()})
        self.assertEqual(scenario.phase, Phase.CONTRIBUTE)
        submit(scenario, "p0", {"type": "contribute", "tokens": tokens()})


class SetupTests(unittest.TestCase):
    def test_setup_reproducible_and_seeds_private(self):
        one = Game(42, game_id="same")
        two = Game(42, game_id="same")
        self.assertEqual(one.snapshot(), two.snapshot())
        for seat in range(8):
            view = one.observe(f"p{seat}")
            self.assertNotIn("seed", view)
            self.assertNotIn("mission_rng", view)
        self.assertEqual(sum(p.team == "blue" for p in one.players), 5)

    def test_every_deal_has_five_blue_three_red_in_both_profiles(self):
        arrangements = set()
        for config in (GameConfig(), GameConfig.common_rules()):
            for seed in range(100):
                g = Game(seed, config)
                teams = tuple(p.team for p in g.players)
                self.assertEqual(teams.count("blue"), 5)
                self.assertEqual(teams.count("red"), 3)
                arrangements.add(teams)
                self.assertEqual(g.observe("p0")["public"]["rules"]["team_counts"], {"blue": 5, "red": 3})
        self.assertGreater(len(arrangements), 1)

    def test_snapshot_with_wrong_team_counts_is_rejected(self):
        data = Game(42).snapshot()
        next(p for p in data["players"] if p["team"] == "red")["team"] = "blue"
        with self.assertRaises(AssertionError):
            Game.from_snapshot(data)

    def test_full_rules_cannot_be_silently_enabled(self):
        for change in ({"abilities_enabled": True}, {"objective_mode": "unknown"},
                       {"mode": "prototype_v01"}, {"max_attempts": 0},
                       {"income": True}, {"blue_players": 6}, {"blue_players": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                GameConfig(**change)
