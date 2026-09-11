import json
import unittest
from collections import Counter
from copy import deepcopy

from mission_game import Game, GameConfig
from mission_game.config import DEFAULT_OBJECTIVE_DECK, OBJECTIVES_VERSION
from mission_game.cli import summarize
from mission_game.objectives import (
    deal, paid_deposits, passenger_attempts, private_card,
    reliable_attempts, wins,
)
from mission_game.replay import ReplayTimeline
from mission_game.rng import stream
from mission_game.session import Session
from mission_game.types import Objective, ObjectiveCard, Phase, Player
from tests.helpers import proposal, reports, resolve, set_teams, submit, tokens


def objective_game(**kwargs):
    return Game(42, GameConfig(threshold_min=8, threshold_max=8, crew_min=2, crew_max=2,
                               objective_deck=("loyalist",) * 8, **kwargs), game_id="objectives-test")


def assign(player, kind):
    player.objective = ObjectiveCard(player.objective.instance_id, kind)


def record(original=None, pledges=None, crew=("p0", "p1"), winner=None, penalty=False):
    return {"penalty": penalty, "crew": list(crew), "mission": {"number": 1, "winner": winner},
            "original_contributions": original or {}, "pledges": pledges or {}}


class ObjectivePredicateTests(unittest.TestCase):
    def player(self, kind, team="blue", wallet=5):
        return Player("p0", "Abby", team, wallet, ObjectiveCard("card", kind))

    def test_wallet_objectives_at_both_edges_and_for_both_teams(self):
        for kind, balances in {"saver": ((9, False), (10, True), (11, True)),
                               "spendthrift": ((0, True), (1, False)),
                               "exact_change": ((6, False), (7, True), (8, False))}.items():
            for team in ("blue", "red"):
                for wallet, expected in balances:
                    with self.subTest(kind=kind, team=team, wallet=wallet):
                        player = self.player(kind, team, wallet)
                        self.assertEqual(wins(player, {}, [], team), expected)
                        self.assertFalse(wins(player, {}, [], "red" if team == "blue" else "blue"))

    def test_loyalist_and_contrarian_desired_sides(self):
        for team in ("blue", "red"):
            for kind in ("loyalist", "contrarian"):
                player = self.player(kind, team)
                for winner in ("blue", "red"):
                    expected = winner == team if kind == "loyalist" else winner != team
                    self.assertEqual(wins(player, {}, [], winner), expected)
                self.assertEqual(player.team, team)
                self.assertEqual(private_card(player, {}, [])["desired_winner"],
                                 team if kind == "loyalist" else "red" if team == "blue" else "blue")

    def test_no_objective_wins_an_unresolved_game(self):
        for kind in Objective:
            self.assertFalse(wins(self.player(kind), {"blue": 2, "red": 2}, [], None))

    def test_close_race_requires_own_team_win_and_opponent_two(self):
        for team, other in (("blue", "red"), ("red", "blue")):
            player = self.player("close_race", team)
            for other_score in range(3):
                self.assertEqual(wins(player, {team: 3, other: other_score}, [], team), other_score == 2)
            self.assertFalse(wins(player, {team: 2, other: 3}, [], other))

    def test_patron_counts_original_paid_events_not_pots_or_modifiers(self):
        history = [record({"p0": tokens(red=2), "p1": tokens(red=17),
                           "p7": tokens(blue=50, green=100)})]
        player = self.player("opposition_patron")
        self.assertFalse(wins(player, {}, history, "blue"))
        # Off-crew paid action (future Stowaway) and a recovered token paid again.
        history.append(record({"p7": tokens(red=1)}, crew=("p1", "p2")))
        self.assertTrue(wins(player, {}, history, "blue"))
        history.append(record(penalty=True, crew=()))
        history[-1]["mission"]["pot"] = tokens(red=999)
        history[-1]["bonus"] = tokens(red=999)
        history[-1]["recolored"] = tokens(red=999)
        history[-1]["removed"] = tokens(red=20)
        self.assertEqual(paid_deposits(history, "red"), 20)
        history.append(record({"p7": tokens(red=1)}))
        self.assertEqual(paid_deposits(history, "red"), 21)
        self.assertEqual(paid_deposits(history, "red", "p0"), 2)
        self.assertFalse(wins(player, {}, history, "red"))
        self.assertTrue(wins(self.player("opposition_patron", "red"), {}, history, "red"))

    def test_reliable_requires_exact_colors_and_two_substantial_approved_attempts(self):
        player = self.player("reliable_partner")
        exact = record({"p0": tokens(blue=1, green=1)}, {"p0": tokens(blue=1, green=1)})
        history = [exact]
        self.assertFalse(wins(player, {}, history, "blue"))
        # Both records are on the same incomplete mission.
        history.append(deepcopy(exact))
        history[0]["modified_contributions"] = {"p0": tokens(red=2)}
        self.assertTrue(wins(player, {}, history, "blue"))
        self.assertFalse(wins(player, {}, history, "red"))
        nonqualifying = [record({"p0": tokens()}, {"p0": tokens()}),
                         record({"p0": tokens(blue=1)}, {"p0": tokens(blue=1)}),
                         record({"p0": tokens(blue=2)}, {"p0": tokens(red=2)}),
                         record({"p0": tokens(blue=2)}, {"p0": tokens(blue=2)}, crew=("p1", "p2")),
                         record(penalty=True, crew=())]
        self.assertEqual(reliable_attempts(nonqualifying, "p0"), 0)

    def test_passenger_qualifies_only_on_the_completing_approved_attempt(self):
        player = self.player("passenger")
        history = [record({"p0": tokens()}, winner=None),
                   record({"p0": tokens(blue=1)}, winner="blue"),
                   record({"p0": tokens()}, winner="blue", crew=("p1", "p2")),
                   record(penalty=True, winner="red", crew=())]
        self.assertEqual(passenger_attempts(history, "p0"), 0)
        self.assertFalse(wins(player, {}, history, "blue"))
        history.append(record({"p0": tokens()}, winner="red"))
        self.assertTrue(wins(player, {}, history, "blue"))
        self.assertFalse(wins(player, {}, history, "red"))


class ObjectiveIntegrationTests(unittest.TestCase):
    def test_default_deck_and_deterministic_deal_with_separate_random_streams(self):
        expected = Counter({"loyalist": 6, **{o.value: 1 for o in Objective if o not in ("loyalist", "contrarian")}})
        self.assertEqual(Counter(DEFAULT_OBJECTIVE_DECK), expected)
        seen = set()
        for seed in range(25):
            g = Game(seed, game_id="deal")
            self.assertEqual(g.snapshot(), Game(seed, game_id="deal").snapshot())
            self.assertEqual(len({p.objective.instance_id for p in g.players}), 8)
            self.assertLessEqual(Counter(p.objective.kind for p in g.players), expected)
            seen.update(p.objective.kind for p in g.players)
            old = Game(seed, GameConfig.common_rules(), game_id="deal")
            self.assertEqual([(p.team, p.wallet) for p in g.players], [(p.team, p.wallet) for p in old.players])
            self.assertEqual(g.chairman, old.chairman)
            self.assertEqual([g._draw_mission(i).to_dict() for i in range(1, 8)],
                             [old._draw_mission(i).to_dict() for i in range(1, 8)])
        self.assertEqual(seen, set(Objective) - {Objective.CONTRARIAN})

    def test_contrarian_deal_keeps_drawn_cards_and_only_changes_eligible_recipient(self):
        holders, present = set(), set()
        legacy_deck = DEFAULT_OBJECTIVE_DECK + ("contrarian",)
        for seed in range(100):
            g = Game(seed, GameConfig(objective_deck=legacy_deck))
            shuffled = [ObjectiveCard(f"objective-{i}", kind) for i, kind in enumerate(legacy_deck)]
            stream(seed, "objectives").shuffle(shuffled)
            self.assertEqual({p.objective.instance_id for p in g.players}, {c.instance_id for c in shuffled[:8]})
            contrarians = [p for p in g.players if p.objective.kind == "contrarian"]
            present.add(bool(contrarians))
            for player in contrarians:
                self.assertEqual(player.team, "blue")
                self.assertEqual(g.observe(player.id)["private"]["objective"]["desired_winner"], "red")
                holders.add(player.id)
            restored = Game.from_snapshot(json.loads(json.dumps(g.snapshot())))
            self.assertEqual(restored.snapshot(), g.snapshot())
        self.assertEqual(present, {False, True})
        self.assertEqual(holders, {f"p{i}" for i in range(8)})

    def test_forced_contrarian_deck_assigns_all_blue_seats_and_no_red_seats(self):
        teams = ["red", "blue", "red", "blue", "blue", "blue", "red", "blue"]
        recipients = set()
        for seed in range(100):
            cards = deal(("contrarian",) + ("loyalist",) * 7, stream(seed, "objectives"), teams)
            self.assertEqual(Counter(c.kind for c in cards), Counter(contrarian=1, loyalist=7))
            recipients.add(next(i for i, c in enumerate(cards) if c.kind == "contrarian"))
        self.assertEqual(recipients, {1, 3, 4, 5, 7})

    def test_contrarian_eligibility_is_public_but_presence_and_holder_are_private(self):
        g = objective_game()
        blue = next(p for p in g.players if p.team == "blue")
        viewer = next(p for p in g.players if p.id != blue.id)
        before = g.observe(viewer.id)
        assign(blue, "contrarian")
        g.assert_invariants()
        self.assertEqual(g.observe(viewer.id), before)
        self.assertEqual(before["public"]["rules"]["contrarian_team"], "blue")
        self.assertNotIn("contrarian_present", json.dumps(before))

    def test_snapshot_cannot_assign_contrarian_to_red(self):
        g = objective_game()
        assign(next(p for p in g.players if p.team == "red"), "contrarian")
        with self.assertRaises(AssertionError):
            Game.from_snapshot(g.snapshot())

    def test_diagnostics_split_games_by_presence_of_the_secret_fourth_red_goal(self):
        records = []
        for deck, present in ((("loyalist",) * 8, False), (("contrarian",) + ("loyalist",) * 7, True)):
            session = Session(8, GameConfig(objective_deck=deck), policy="random")
            session.run()
            session.replay()
            metrics = session.metrics()
            self.assertEqual(metrics["contrarian_present"], present)
            records.append(metrics)
        summary = summarize(records)
        self.assertEqual(set(summary["by_initial_blue_count"]), {"5"})
        for label in ("absent", "present"):
            counts = summary["by_contrarian"][label]
            self.assertEqual(counts["games"], 1)
            self.assertEqual(counts["blue_wins"] + counts["red_wins"], 1)

    def test_invalid_decks_and_mismatched_profiles_are_rejected(self):
        for deck in ([], ("loyalist",) * 7, ("wrong",) * 8,
                     ("contrarian",) * 2 + ("loyalist",) * 6):
            with self.subTest(deck=deck), self.assertRaises(ValueError):
                GameConfig(objective_deck=deck)
        g = objective_game()
        data = g.snapshot()
        data["schema_version"] = 1
        with self.assertRaises(ValueError):
            Game.from_snapshot(data)

    def test_original_history_updates_progress_and_stays_with_seat(self):
        g = objective_game()
        assign(g.players[0], "reliable_partner")
        for _ in range(2):
            resolve(g, {"p0": tokens(blue=2)}, pledges={"p0": tokens(blue=2)})
            reports(g)
        self.assertEqual(g.mission.number, 1)
        self.assertEqual(g.observe("p0")["private"]["objective"]["progress"]["value"], 2)
        # Designer-level swap verifies that counters belong to history, not cards.
        # There is no player swap action until abilities are implemented.
        g.players[0].objective, g.players[1].objective = g.players[1].objective, g.players[0].objective
        self.assertEqual(g.observe("p1")["private"]["objective"]["progress"]["value"], 0)
        assign(g.players[0], "reliable_partner")
        self.assertEqual(g.observe("p0")["private"]["objective"]["progress"]["value"], 2)

    def test_hidden_cards_and_patron_global_count_do_not_change_player_view(self):
        g = objective_game()
        assign(g.players[0], "opposition_patron")
        resolve(g, {"p0": tokens(red=1), "p1": tokens(red=3)})
        before = g.observe("p0")
        assign(next(p for p in g.players if p.team == "blue" and p.id != "p0"), "contrarian")
        g.resolutions[0]["original_contributions"]["p1"] = tokens(red=200)
        self.assertEqual(g.observe("p0"), before)
        progress = before["private"]["objective"]["progress"]
        self.assertIsNone(progress["value"])
        self.assertIsNone(progress["condition_met"])
        self.assertNotIn("instance_id", json.dumps(before))
        self.assertNotIn("objective_deck", json.dumps(before))
        before["private"]["objective"]["progress"]["own_paid"] = 500
        self.assertNotEqual(g.observe("p0"), before)

    def test_new_profile_sealed_deposit_does_not_change_progress_for_other_seat(self):
        g = objective_game()
        assign(g.players[1], "opposition_patron")
        proposal(g)
        before = g.observe("p1")
        submit(g, "p0", {"type": "contribute", "tokens": tokens(red=5)})
        self.assertEqual(g.observe("p1"), before)

    def test_freeze_uses_post_spend_wallet_and_closing_reports_cannot_change_results(self):
        g = objective_game()
        # Three legitimately funded Blue missions, using fresh crew wallets.
        for crew in (("p0", "p1"), ("p2", "p3")):
            resolve(g, {pid: tokens(blue=4) for pid in crew}, crew=crew)
            reports(g)
        assign(g.players[4], "spendthrift")
        assign(g.players[6], "exact_change")
        assign(g.players[7], "saver")
        set_teams(g, {"p0": "blue", "p4": "blue", "p6": "blue", "p7": "blue"})
        assign(g.players[0], "contrarian")
        resolve(g, {"p4": tokens(blue=7), "p5": tokens(blue=1)}, crew=("p4", "p5"))
        self.assertEqual(g.status, "CLOSING")
        frozen = deepcopy(g.frozen_result)
        self.assertTrue(frozen["players"]["p4"]["won"])
        self.assertTrue(frozen["players"]["p6"]["won"])
        self.assertFalse(frozen["players"]["p7"]["won"])
        self.assertFalse(frozen["players"]["p0"]["won"])
        self.assertEqual(frozen["players"]["p4"]["wallet"], 0)
        self.assertEqual(frozen["players"]["p6"]["wallet"], 7)
        self.assertNotIn("result", g.observe("p4")["private"])
        income = g.accounting["income"]
        reports(g)
        self.assertEqual(g.frozen_result, frozen)
        self.assertEqual(g.accounting["income"], income)
        self.assertIn("Your team won", g.observe("p0")["private"]["result"]["text"])
        self.assertIn("personal condition was not satisfied", g.observe("p7")["private"]["result"]["text"])
        self.assertEqual(set(g.observe("p0")["public"]["result"]), {"winner", "reason"})

    def test_terminal_attempt_itself_counts_for_passenger(self):
        g = objective_game()
        assign(g.players[0], "passenger")
        set_teams(g, {"p0": "blue"})
        for crew in (("p2", "p3"), ("p4", "p5")):
            resolve(g, {pid: tokens(blue=4) for pid in crew}, crew=crew)
            reports(g)
        # Let the crew build an incomplete final pot, then finish while p0 pays zero.
        resolve(g, {"p6": tokens(blue=4)}, crew=("p6", "p7"))
        reports(g)
        resolve(g, {"p1": tokens(blue=4)})
        self.assertEqual(g.observe("p0")["private"]["objective"]["progress"]["value"], 1)
        reports(g)
        self.assertTrue(g.frozen_result["players"]["p0"]["won"])

    def test_final_paid_deposit_crosses_patron_threshold_and_close_race_finishes_three_two(self):
        g = objective_game()
        assign(g.players[0], "opposition_patron")
        assign(g.players[2], "close_race")
        set_teams(g, {"p0": "blue", "p2": "blue"})
        for crew, color in ((("p0", "p1"), "red"), (("p2", "p3"), "red"),
                            (("p4", "p5"), "blue"), (("p6", "p7"), "blue")):
            resolve(g, {pid: tokens(**{color: 4}) for pid in crew}, crew=crew)
            reports(g)
        self.assertEqual(paid_deposits(g.resolutions, "red"), 16)
        resolve(g, {"p0": tokens(red=4), "p1": tokens(blue=4)})
        self.assertEqual(paid_deposits(g.resolutions, "red"), 20)
        self.assertEqual(g.score, {"blue": 3, "red": 2})
        self.assertTrue(g.frozen_result["players"]["p0"]["won"])
        self.assertTrue(g.frozen_result["players"]["p2"]["won"])

    def test_guard_does_not_award_contrarian_or_other_objectives(self):
        g = objective_game(max_attempts=1)
        set_teams(g, {"p0": "blue"})
        assign(g.players[0], "contrarian")
        resolve(g)
        reports(g)
        self.assertEqual(g.status, "UNRESOLVED")
        self.assertFalse(any(r["won"] for r in g.frozen_result["players"].values()))

    def test_cards_and_progress_replay_at_each_visible_step(self):
        session = Session(7, GameConfig(max_attempts=3), game_id="objective-replay")
        expected = [session.game.observe("p0")]
        while session.step_bot():
            observation = session.game.observe("p0")
            if observation != expected[-1]:
                expected.append(observation)
        replay = ReplayTimeline(session, "p0")
        self.assertEqual([frame["observation"] for frame in replay.frames], expected)
        restored = Game.from_snapshot(json.loads(json.dumps(session.game.snapshot())))
        self.assertEqual(restored.snapshot(), session.game.snapshot())
        self.assertEqual(restored.observe("p0"), expected[-1])
        designer = ReplayTimeline(session, "p0", True).frames[-1]["designer"]
        self.assertEqual([p["objective"] for p in designer["players"]],
                         [p.objective.kind for p in session.game.players])
        self.assertTrue(all("result" in p for p in designer["players"]))
        self.assertEqual(session.metrics()["rules_version"], OBJECTIVES_VERSION)

    def test_version_one_saves_keep_original_shape_and_loyalist_results(self):
        session = Session(7, GameConfig.common_rules(), game_id="old-save")
        initial = session.game.snapshot()
        self.assertEqual(initial["schema_version"], 1)
        self.assertNotIn("objective_deck", initial["config"])
        self.assertTrue(all("objective" not in p for p in initial["players"]))
        session.game = Game.from_snapshot(json.loads(json.dumps(initial)))
        self.assertEqual(session.game.snapshot(), initial)
        session.run()
        session.replay()
        for p in session.game.players:
            view = session.game.observe(p.id)
            self.assertEqual(set(view["private"]["objective"]), {"id", "text"})
            self.assertEqual(set(view["private"]["result"]), {"objective", "wallet", "won"})
            self.assertEqual(view["private"]["result"]["won"], p.team == session.game.frozen_result["winner"])
