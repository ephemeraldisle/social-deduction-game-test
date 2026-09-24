import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from mission_game.beliefs import SocialBeliefs, blue_prior
from mission_game.bot_memory import EvidenceMemory
from mission_game.policy import restore_policy
from mission_game.session import Session
from mission_game.social_policy import SocialPolicy, Traits, approval_probability
from tests.helpers import game, proposal, reports, resolve, set_teams, tokens
from tests.test_policy import observation


CALM = Traits(0, .3, 1)


def vote_view():
    view = observation("vote")
    view["public"].update(crew=["p1", "p2"], pledges={"p1": tokens(blue=4), "p2": tokens(blue=4)})
    return view


def analyze(g, viewer="p7"):
    view = g.observe(viewer)
    view["private"]["team"] = "blue"
    memory, beliefs = EvidenceMemory(), SocialBeliefs()
    memory.observe(view)
    beliefs.observe(view, memory)
    return beliefs, memory, view


class SocialBehaviorTests(unittest.TestCase):
    def test_personality_alone_does_not_veto_a_cooperative_crew(self):
        view = vote_view()
        calm = SocialPolicy(traits=CALM).choose_action(view)
        insistent = SocialPolicy(traits=Traits(1, .3, 1)).choose_action(view)
        self.assertTrue(calm["approve"])
        self.assertTrue(insistent["approve"])
        self.assertEqual(insistent["complaints"], [])

    def test_exclusion_protest_relaxes_under_rejection_pressure_or_imminent_win(self):
        view = vote_view()
        for change in ("pressure", "terminal"):
            modified = deepcopy(view)
            if change == "pressure":
                modified["public"]["rejections"] = 5
            else:
                modified["public"]["score"]["blue"] = 2
                modified["public"]["mission"]["pot"] = tokens(blue=3)
            action = SocialPolicy(traits=Traits(1, .3, 1)).choose_action(modified)
            self.assertTrue(action["approve"])
            self.assertFalse(action["complaints"])

    def test_observed_broken_promises_change_vote_and_crew_choice(self):
        g = game()
        initial_history = deepcopy(g.events)
        for _ in range(2):
            resolve(g, {"p0": tokens(red=2), "p1": tokens(red=2)},
                    pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
            reports(g)
        view = g.observe("p7")
        view["private"]["team"] = "blue"
        view["phase"], view["action_spec"] = "vote", {"type": "vote"}
        view["public"].update(crew=["p0", "p1"], pledges={"p0": tokens(blue=4), "p1": tokens(blue=4)}, votes=[])
        clean = deepcopy(view)
        clean["history"] = initial_history
        before, after = SocialPolicy(7, 7, traits=CALM), SocialPolicy(7, 7, traits=CALM)
        self.assertTrue(before.choose_action(clean)["approve"])
        action = after.choose_action(view)
        self.assertFalse(action["approve"])
        self.assertIn(action["complaints"][0]["modifier"], ("less", "exact"))
        self.assertIn(action["complaints"][0]["player_id"], ("p0", "p1"))
        self.assertLess(after.last_decision["details"]["approval_likelihood"],
                        before.last_decision["details"]["approval_likelihood"])
        # Equalize current wallets to isolate evidence in a new crew decision.
        view["phase"] = "select_crew"
        view["action_spec"] = {"type": "select_crew", "crew_size": 2, "players": [f"p{i}" for i in range(8)]}
        view["public"].update(crew=[], pledges={})
        for player in view["public"]["players"]:
            player["wallet"] = 5
        crew = after.choose_action(view)["crew"]
        self.assertTrue(set(crew).isdisjoint({"p0", "p1"}))

    def test_more_me_changes_future_vote_prediction_without_a_red_label(self):
        g = game()
        proposal(g, crew=("p0", "p1"), pledges={"p0": tokens(blue=4), "p1": tokens(blue=4)})
        view = g.observe("p7")
        view["private"]["team"] = "blue"
        before = SocialPolicy(7, 7, traits=CALM)
        before.memory.observe(view)
        before.beliefs.observe(view, before.memory)
        # A new, public inclusion protest in a later proposal, with no current vote yet.
        history = deepcopy(view["history"])
        event_id = history[-1]["id"] + 1
        history.append({"id": event_id, "type": "vote", "attempt": 1, "player_id": "p2", "approve": False,
                        "complaints": [{"modifier": "more", "player_id": "p2"}]})
        after = SocialPolicy.from_snapshot(before.snapshot())
        changed = deepcopy(view)
        changed["history"] = history
        after.memory.observe(changed)
        after.beliefs.observe(changed, after.memory)
        self.assertEqual(after.beliefs.estimate("p2")["blue_preference"], before.beliefs.estimate("p2")["blue_preference"])
        self.assertGreater(after.beliefs.estimate("p2")["inclusion_demand"], before.beliefs.estimate("p2")["inclusion_demand"])
        view["public"]["votes"] = []
        fixed_pot = tokens(blue=8)
        old = before.predict_votes(view, ["p0", "p1"], fixed_pot, tokens(), tokens())["p2"]
        new = after.predict_votes(view, ["p0", "p1"], fixed_pot, tokens(), tokens())["p2"]
        included = after.predict_votes(view, ["p0", "p2"], fixed_pot, tokens(), tokens())["p2"]
        self.assertLess(new, old)
        self.assertGreater(included, new)

    def test_vote_forecast_respects_votes_already_cast(self):
        view = vote_view()
        view["public"]["votes"] = [{"player_id": f"p{i}", "approve": True} for i in range(1, 6)]
        policy = SocialPolicy(traits=CALM)
        policy.choose_action(view)
        forecast = policy.last_decision["details"]
        self.assertEqual(forecast["approval_likelihood"], 1)
        self.assertTrue(all(forecast["vote_likelihoods"][f"p{i}"] == 1 for i in range(1, 6)))
        self.assertEqual(approval_probability([1, 1, 1, 1, 0, 0, 0, 0]), 0)
        self.assertAlmostEqual(approval_probability([.5] * 8), 93 / 256)


class EvidenceTests(unittest.TestCase):
    def test_blue_prior_accounts_for_own_team_and_remains_uncertain(self):
        for own, expected in (("blue", 4 / 7), ("red", 5 / 7)):
            view = observation("vote", team=own)
            self.assertAlmostEqual(blue_prior(view), expected)

    def test_ambiguous_discrepancy_does_not_identify_a_specific_liar(self):
        g = game()
        resolve(g, {"p0": tokens(blue=2), "p1": tokens(red=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        beliefs, _, _ = analyze(g)
        self.assertEqual(beliefs.last_resolution["known"], {})
        for pid in ("p0", "p1"):
            self.assertAlmostEqual(beliefs.estimate(pid)["pledge_reliability"], 3 / 4.25)
            self.assertIn("uncertain", beliefs.estimate(pid)["evidence"][-1]["text"])

    def test_matching_aggregate_does_not_certify_individual_colors(self):
        g = game()
        resolve(g, {"p0": tokens(red=2), "p1": tokens(blue=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(red=2)})
        beliefs, _, _ = analyze(g)
        self.assertEqual(beliefs.last_resolution["known"], {})
        self.assertLess(beliefs.estimate("p0")["pledge_reliability"], .8)

    def test_own_receipt_can_disambiguate_the_other_contribution(self):
        g = game()
        resolve(g, {"p0": tokens(blue=2), "p1": tokens(red=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        beliefs, _, _ = analyze(g, "p0")
        self.assertEqual(beliefs.last_resolution["known"]["p1"], tokens(red=2))
        self.assertGreater(beliefs.estimate("p0")["pledge_reliability"], beliefs.estimate("p1")["pledge_reliability"])

    def test_persistent_pot_and_penalty_are_not_new_paid_deposits(self):
        g = game(threshold=10, threshold_max=10)
        resolve(g, {"p0": tokens(blue=2), "p1": tokens(blue=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        reports(g)
        resolve(g, {"p0": tokens(blue=1), "p1": tokens(blue=1)},
                pledges={"p0": tokens(blue=1), "p1": tokens(blue=1)})
        reports(g)
        for _ in range(8):
            proposal(g, approvals=0)
        beliefs, memory, view = analyze(g)
        self.assertEqual(beliefs.paid, {"blue": 6, "red": 0})
        self.assertEqual(beliefs.last_resolution["crew"], [])
        before = deepcopy(beliefs.players)
        beliefs.observe(view, memory)
        self.assertEqual(beliefs.players, before)

    def test_report_credibility_changes_weight_of_unverified_accusation(self):
        g = game()
        resolve(g, {"p0": tokens(blue=2), "p1": tokens(red=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        initial, _, view = analyze(g)
        trusted, unreliable = SocialBeliefs.from_snapshot(initial.snapshot()), SocialBeliefs.from_snapshot(initial.snapshot())
        event = {"id": len(view["history"]) + 1, "type": "reports_revealed", "attempt": 1,
                 "reports": {"p1": [{"player_id": "p7", "verb": "took", "quantity": 0, "color": "blue"}]}}
        trusted.reports(event, .3)
        event["reports"]["p1"][0]["quantity"] = 99
        unreliable.reports(event, .3)
        allegation = {"id": event["id"] + 1, "type": "reports_revealed", "attempt": 1,
                      "reports": {"p1": [{"player_id": "p0", "verb": "gave", "quantity": 2, "color": "red"}]}}
        trusted.reports(allegation, .3)
        unreliable.reports(allegation, .3)
        self.assertLess(trusted.estimate("p0")["blue_preference"], unreliable.estimate("p0")["blue_preference"])
        self.assertNotIn("p0", trusted.last_resolution["known"])

    def test_association_is_weak_bounded_and_not_recursively_propagated(self):
        g = game()
        resolve(g, {"p0": tokens(red=2), "p1": tokens(red=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        beliefs, _, _ = analyze(g)
        beliefs.crew = ["p0", "p1"]
        before = beliefs.estimate("p2")["blue_preference"]
        for n in range(20):
            beliefs.associate("p2", {"id": 100 + n, "attempt": 2}, .2)
        self.assertLess(beliefs.estimate("p2")["blue_preference"], before)
        self.assertLess(before - beliefs.estimate("p2")["blue_preference"], .03)
        beliefs.crew = ["p2", "p3"]
        direct_before = beliefs.estimate("p4")["blue_preference"]
        beliefs.associate("p4", {"id": 200, "attempt": 3}, .2)
        self.assertEqual(beliefs.estimate("p4")["blue_preference"], direct_before)

    def test_truthful_behavior_can_recover_pledge_reliability(self):
        g = game()
        resolve(g, {"p0": tokens(red=2), "p1": tokens(red=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        old, _, _ = analyze(g)
        reports(g)
        resolve(g, {"p0": tokens(blue=2), "p1": tokens(blue=2)},
                pledges={"p0": tokens(blue=2), "p1": tokens(blue=2)})
        new, _, _ = analyze(g)
        self.assertGreater(new.estimate("p0")["pledge_reliability"], old.estimate("p0")["pledge_reliability"])


class ObjectiveAndPersistenceTests(unittest.TestCase):
    def terminal_view(self, objective, wallet, pledge=2, other=4):
        view = observation("contribute", objective=objective)
        view["private"]["objective"]["progress"] = {"value": 0}
        view["public"].update(score={"blue": 2, "red": 0}, crew=["p0", "p1"],
                              pledges={"p0": tokens(blue=pledge), "p1": tokens(blue=other)})
        view["public"]["mission"]["pot"] = tokens(blue=4)
        view["public"]["players"][0]["wallet"] = wallet
        return view

    def test_terminal_wallet_objectives_change_actual_spending(self):
        for objective, wallet, final in (("saver", 12, 10), ("exact_change", 9, 7), ("spendthrift", 5, 0)):
            with self.subTest(objective=objective):
                policy = SocialPolicy(4, traits=Traits(.5, .3, 0))
                action = policy.choose_action(self.terminal_view(objective, wallet))
                actual = wallet - sum(action["tokens"].values())
                self.assertGreaterEqual(actual, final) if objective == "saver" else self.assertEqual(actual, final)
                details = policy.last_decision["details"]
                self.assertAlmostEqual(details["condition_likelihood"], 1)
                self.assertEqual(details["outcome_likelihoods"]["personal_loss"], 0)
                if objective != "spendthrift":
                    # These two plans need the other member to pay: a kept
                    # promise can win, but zero payment leaves it unfinished.
                    self.assertGreater(details["outcome_likelihoods"]["personal_win"], 0)
                    self.assertLess(details["outcome_likelihoods"]["personal_win"], 1)
                    self.assertLess(details["expected_outcome_utility"], 100)

    def test_reliable_partner_keeps_qualifying_pledge_and_passenger_chooses_zero(self):
        reliable = self.terminal_view("reliable_partner", 5)
        reliable["private"]["objective"]["progress"]["value"] = 1
        self.assertEqual(SocialPolicy(traits=Traits(.5, .3, 0)).choose_action(reliable)["tokens"], tokens(blue=2))
        passenger = self.terminal_view("passenger", 5, other=5)
        self.assertEqual(SocialPolicy(traits=Traits(.5, .3, 0)).choose_action(passenger)["tokens"], tokens())

    def test_close_race_and_contrarian_change_tactical_preferences(self):
        view = observation("contribute", objective="contrarian")
        view["public"].update(crew=["p0", "p1"], pledges={"p0": tokens(red=3), "p1": tokens()})
        policy = SocialPolicy(traits=CALM)
        action = policy.choose_action(view)
        self.assertGreater(action["tokens"]["red"], action["tokens"]["blue"])
        view["private"]["objective"]["id"] = "close_race"
        view["public"]["score"] = {"blue": 2, "red": 0}
        policy.choose_action(view)
        self.assertEqual(policy.last_decision["details"]["tactical_side"], "red")
        view["public"]["score"]["red"] = 2
        policy.choose_action(view)
        self.assertEqual(policy.last_decision["details"]["tactical_side"], "blue")

    def test_opposition_patron_forecast_excludes_rejection_penalty(self):
        view = vote_view()
        view["private"]["objective"]["id"] = "opposition_patron"
        policy = SocialPolicy(traits=CALM)
        policy.choose_action(view)
        policy.beliefs.paid["red"] = 17
        pot = tokens(blue=10, red=3)
        self.assertTrue(policy.condition(view, pot, tokens(), [], tokens()))
        self.assertFalse(policy.condition(view, pot, tokens(), [], tokens(), penalty=True))

    def test_traits_are_seeded_independent_of_card_and_restore_with_beliefs(self):
        p = SocialPolicy(7, 2)
        self.assertEqual(p.traits, SocialPolicy(7, 2).traits)
        self.assertNotEqual(p.traits, SocialPolicy(7, 3).traits)
        view = observation("pledge", objective="contrarian")
        view["public"]["crew"] = ["p0", "p1"]
        original_traits = p.traits
        p.choose_action(view)
        self.assertEqual(p.traits, original_traits)
        restored = restore_policy(json.loads(json.dumps(p.snapshot())))
        self.assertEqual(p.snapshot(), restored.snapshot())
        self.assertEqual(p.choose_action(view), restored.choose_action(view))
        self.assertEqual(p.last_decision, restored.last_decision)

    def test_hidden_state_and_other_sealed_submissions_cannot_change_beliefs(self):
        g = game()
        proposal(g)
        before = g.observe("p1")
        from tests.helpers import submit
        set_teams(g, {"p0": "red" if g.players[0].team == "blue" else "blue", "p1": g.players[1].team})
        submit(g, "p0", {"type": "contribute", "tokens": tokens(red=4)})
        after = g.observe("p1")
        one, two = SocialPolicy(3, 1), SocialPolicy(3, 1)
        self.assertEqual(one.choose_action(before), two.choose_action(after))
        self.assertEqual(one.snapshot(), two.snapshot())
        self.assertNotIn("original_contributions", json.dumps(one.snapshot()))

    def test_custom_settings_are_validated_and_preserved_in_saved_sessions(self):
        for settings in ({"protest_threshold": 2}, {"funding_weight": float("nan")}, [], {"protest_relax_at": 2.5}):
            with self.subTest(settings=settings), self.assertRaises((ValueError, TypeError)):
                SocialPolicy(settings=settings)
        session = Session(3, policy_settings={"protest_threshold": .9})
        for _ in range(8):
            session.step_bot()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            session.save(path)
            restored = Session.load(path)
            self.assertTrue(all(p.settings.protest_threshold == .9 for p in restored.policies.values()))
            self.assertEqual(json.loads(json.dumps(session.snapshot())), json.loads(json.dumps(restored.snapshot())))
