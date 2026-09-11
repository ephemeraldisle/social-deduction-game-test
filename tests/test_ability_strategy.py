"""Ability use must follow predicted consequences, not just produce legal actions."""

import json
import unittest
from copy import deepcopy

from mission_game.ability_forecasts import EffectEvidence, apply_own
from mission_game.policy import restore_policy
from mission_game.social_policy import SocialPolicy, Traits
from mission_game.social_baseline import SocialPolicy as PreviousSocialPolicy
from tests.helpers import tokens, reports
from tests.test_abilities import ability_game, start, batch, prepare

CALM = Traits(0, 0, 0)


def view(ability, kind="contribute", wallet=5, pot=None, objective="loyalist",
         crew=("p0", "p1"), score=None):
    g = ability_game({"p0": ability})
    start(g)
    o = g.observe("p0")
    o["phase"] = kind
    o["action_spec"].update(type=kind, max_total=wallet if "p0" in crew else 0, on_crew="p0" in crew)
    o["private"]["team"] = "blue"
    o["private"]["objective"] = {"id": objective, "progress": {"value": 0}}
    o["public"].update(crew=list(crew), pledges={pid: tokens() for pid in crew}, score=score or {"blue": 2, "red": 0})
    o["public"]["mission"]["pot"] = pot or tokens()
    o["public"]["players"][0]["wallet"] = wallet
    for player in o["public"]["players"][1:]:
        player["wallet"] = 0
    o["history"] = []
    return o


def ready(o):
    p = SocialPolicy(traits=CALM)
    p.memory.observe(o)
    p.beliefs.observe(o, p.memory)
    return p


class JointAbilityPlanningTests(unittest.TestCase):
    def test_own_ability_forecasts_match_engine_resolution(self):
        scenarios = [
            ("echo", "p0", tokens(blue=2), None),
            ("recolorer", "p0", tokens(red=2), {"from": "red", "to": "blue"}),
            ("thief", "p0", tokens(blue=2), {"source": "mission", "tokens": tokens(red=3)}),
            ("thief", "p0", tokens(blue=2), {"source": "wallet", "target": "p1", "amount": 3}),
            ("stowaway", "p2", tokens(), {"color": "green"}),
        ]
        for ability, me, own, choice in scenarios:
            with self.subTest(ability=ability, choice=choice):
                g = ability_game({f"p{i}": ability if f"p{i}" == me else "scout" for i in range(8)})
                start(g)
                o = g.observe(me)
                payments = {pid: tokens(red=4) if pid == "p1" else tokens(blue=2)
                            for pid in g.crew if pid != me}
                paid = {c: sum(v[c] for v in payments.values()) for c in tokens()}
                case = {"pot": {c: o["public"]["mission"]["pot"][c] + paid[c] for c in tokens()},
                        "paid": paid, "wallets": {p.id: p.wallet - sum(payments.get(p.id, {}).values()) for p in g.players},
                        "mass": 1.}
                forecast = apply_own(o, case, g.crew, own, choice)
                batch(g, {**{pid: {"tokens": payment} for pid, payment in payments.items()},
                          me: {"tokens": own, "ability": choice}})
                result = g.resolutions[-1]
                self.assertEqual(forecast["pot"], result["mission"]["pot"])
                self.assertEqual(forecast["wallet"], result["wallets_before_income"][me])
                self.assertEqual(forecast["paid"], {c: sum(v[c] for v in result["original_contributions"].values()) for c in tokens()})

    def test_echo_changes_funding_plan_and_vote_without_paid_history_credit(self):
        for phase in ("pledge", "vote", "contribute"):
            o = view("echo", phase, wallet=2, pot=tokens(blue=5))
            p = ready(o)
            action = p.choose_action(o)
            d = p.last_decision["details"]
            self.assertEqual(d["planned_deposit"], tokens(blue=2))
            self.assertAlmostEqual(d["forecast_pot"]["blue"], 8)
            self.assertAlmostEqual(d["expected_paid_deposits"]["blue"], 2)
            self.assertAlmostEqual(d["advertised_pot"]["blue"], 7 if phase == "pledge" else 5)
            if phase == "vote":
                self.assertTrue(action["approve"])
            else:
                self.assertEqual(action["tokens"], tokens(blue=2))

    def test_recolorer_can_approve_a_crew_it_can_turn_into_a_winning_tie(self):
        for phase in ("vote", "contribute"):
            o = view("recolorer", phase, wallet=0, pot=tokens(blue=3, red=5), crew=("p1", "p2"))
            p = ready(o)
            action = p.choose_action(o)
            d = p.last_decision["details"]
            self.assertEqual(d["planned_ability"], {"from": "red", "to": "blue"})
            self.assertAlmostEqual(d["outcome_likelihoods"]["personal_win"], 1)
            self.assertAlmostEqual(d["advertised_pot"]["blue"], 3)
            if phase == "vote": self.assertTrue(action["approve"])
            else: self.assertEqual(action["ability"], d["planned_ability"])

    def test_thief_takes_one_instead_of_three_to_preserve_completion(self):
        o = view("thief", wallet=0, pot=tokens(blue=4, red=5))
        p = ready(o)
        action = p.choose_action(o)
        self.assertEqual(action["ability"], {"source": "mission", "tokens": tokens(red=1)})
        self.assertAlmostEqual(p.last_decision["details"]["outcome_likelihoods"]["personal_win"], 1)
        self.assertAlmostEqual(p.last_decision["details"]["expected_wallet_after_effects"], 1)

    def test_thief_can_finish_saver_offcrew_and_votes_for_that_plan(self):
        for phase in ("vote", "contribute"):
            o = view("thief", phase, wallet=7, pot=tokens(blue=8), objective="saver", crew=("p1", "p2"))
            o["public"]["players"][3]["wallet"] = 5
            p = ready(o)
            action = p.choose_action(o)
            self.assertEqual(p.last_decision["details"]["planned_ability"], {"source": "wallet", "target": "p3", "amount": 3})
            self.assertAlmostEqual(p.last_decision["details"]["expected_wallet_after_effects"], 10)
            if phase == "vote": self.assertTrue(action["approve"])

    def test_exact_change_steals_only_the_missing_amount_and_passes_at_seven(self):
        for wallet, amount in ((6, 1), (7, 0)):
            o = view("thief", wallet=wallet, pot=tokens(blue=8), objective="exact_change", crew=("p1", "p2"))
            o["public"]["players"][3]["wallet"] = 5
            p = ready(o)
            action = p.choose_action(o)
            self.assertEqual(action["ability"], {"source": "wallet", "target": "p3", "amount": amount} if amount else None)
            self.assertAlmostEqual(p.last_decision["details"]["expected_wallet_after_effects"], 7)

    def test_no_pointless_theft_and_no_reuse_of_spent_ability(self):
        o = view("thief", wallet=0, pot=tokens(), score={"blue": 0, "red": 0})
        p = ready(o)
        self.assertIsNone(p.choose_action(o)["ability"])
        o["private"]["ability"]["uses_remaining"] = 0
        o["public"]["mission"]["pot"] = tokens(blue=4, red=5)
        p = ready(o)
        self.assertIsNone(p.choose_action(o)["ability"])
        self.assertAlmostEqual(p.last_decision["details"]["expected_transfer"], 0)

    def test_stowaway_finish_spendthrift_and_exact_change_without_demanding_a_seat(self):
        for objective, wallet, expected in (("spendthrift", 1, 0), ("exact_change", 8, 7)):
            for phase in ("vote", "contribute"):
                o = view("stowaway", phase, wallet=wallet, pot=tokens(blue=7), objective=objective, crew=("p1", "p2"))
                p = ready(o)
                action = p.choose_action(o)
                d = p.last_decision["details"]
                self.assertEqual(d["planned_ability"], {"color": "blue"})
                self.assertAlmostEqual(d["expected_wallet_after_effects"], expected)
                self.assertEqual(d["planned_deposit"], tokens())
                if phase == "vote": self.assertTrue(action["approve"])

    def test_stowaway_preserves_saver_and_cannot_earn_passenger_offcrew(self):
        o = view("stowaway", wallet=10, pot=tokens(blue=8), objective="saver", crew=("p1", "p2"))
        p = ready(o)
        self.assertIsNone(p.choose_action(o)["ability"])
        o = view("stowaway", wallet=1, pot=tokens(blue=7), objective="passenger", crew=("p1", "p2"))
        p = ready(o)
        _, d = p.evaluate(o, o["public"]["crew"], tokens(), {}, "contribute")
        self.assertAlmostEqual(d["condition_likelihood"], 0)

    def test_rejection_penalty_forecast_includes_offcrew_recoloring(self):
        o = view("recolorer", "vote", wallet=0, pot=tokens(blue=5, red=1), crew=("p1", "p2"), score={"blue": 2, "red": 2})
        o["public"]["rejections"] = 7
        for pid in (1, 2):
            o["public"]["players"][pid]["wallet"] = 4
            o["public"]["pledges"][f"p{pid}"] = tokens(red=4)
        p = ready(o)
        for pid in ("p1", "p2"):
            p.beliefs.players[pid]["kept"] = 1000
        action = p.choose_action(o)
        self.assertFalse(action["approve"])
        d = p.last_decision["details"]
        self.assertAlmostEqual(d["rejection_value"], 100)
        self.assertEqual(d["penalty_plan"]["planned_ability"], {"from": "red", "to": "blue"})

    def test_wallet_theft_scenarios_clip_after_target_spending(self):
        o = view("thief", wallet=5, pot=tokens(), score={"blue": 0, "red": 0})
        o["public"]["players"][1]["wallet"] = 3
        o["public"]["pledges"]["p1"] = tokens(blue=3)
        p = ready(o)
        raw, _ = p.raw_cases(o, ["p0", "p1"], tokens(), o["public"]["pledges"])
        choice = {"source": "wallet", "target": "p1", "amount": 3}
        for case in raw:
            applied = apply_own(o, case, ["p0", "p1"], tokens(), choice)
            self.assertEqual(applied["transferred"], 3 - sum(case["paid"].values()))
            self.assertEqual(applied["wallet"], 5 + applied["transferred"])
        with self.assertRaises(ValueError):
            apply_own(o, raw[0], ["p0", "p1"], tokens(blue=6), choice)

    def test_modified_colors_and_bonuses_do_not_fulfill_opposition_patron(self):
        for ability in ("echo", "recolorer", "thief"):
            o = view(ability, objective="opposition_patron")
            p = ready(o)
            p.beliefs.paid["red"] = 19
            self.assertFalse(p.condition(o, tokens(blue=5, red=8), tokens(), ["p0", "p1"], tokens(), wallet_after=5, paid=tokens(blue=5)))
            self.assertTrue(p.condition(o, tokens(blue=5), tokens(), ["p0", "p1"], tokens(), wallet_after=5, paid=tokens(red=1)))

    def test_original_pledge_matching_survives_echo_and_theft(self):
        o = view("echo", wallet=2, pot=tokens(blue=5), objective="reliable_partner")
        o["private"]["objective"]["progress"]["value"] = 1
        o["public"]["pledges"]["p0"] = tokens(blue=2)
        p = ready(o)
        p.choose_action(o)
        self.assertEqual(p.last_decision["details"]["planned_deposit"], tokens(blue=2))
        self.assertAlmostEqual(p.last_decision["details"]["condition_likelihood"], 1)


class InformationAbilityTests(unittest.TestCase):
    def test_scout_prefers_relevant_unknown_team_and_remembers_inspection(self):
        o = view("scout", "prepare")
        o["action_spec"]["ability"] = {"id": "scout", "targets": ["p1", "p2", "p3"]}
        o["public"]["public_badges"] = {"p1": "blue"}
        o["public"]["players"][2]["wallet"] = 8
        p = ready(o)
        self.assertEqual(p.choose_action(o)["ability"], {"target": "p2"})
        o["private"]["receipts"] = [{"type": "scout", "attempt": 1, "target": "p2", "team": "red"}]
        self.assertEqual(p.choose_action(o)["ability"], {"target": "p3"})
        self.assertEqual(p.beliefs.known_teams["p2"], "red")
        self.assertGreater(p.beliefs.estimate("p2")["blue_preference"], 0)

    def test_auditor_prefers_an_unverified_substantial_pledge_over_self(self):
        o = view("auditor", "audit", crew=("p0", "p1", "p2"))
        o["action_spec"]["ability"] = {"id": "auditor", "targets": ["p0", "p1", "p2"]}
        o["public"]["pledges"]["p1"] = tokens(blue=5)
        p = ready(o)
        self.assertEqual(p.choose_action(o)["ability"], {"target": "p1"})
        self.assertIn("unverified", p.last_decision["reason"])

    def test_switcher_keeps_a_met_condition_but_can_gamble_on_a_difficult_finish(self):
        o = view("switcher", "prepare", wallet=5, objective="saver")
        o["action_spec"]["ability"] = {"id": "switcher", "targets": ["p1"]}
        p = ready(o)
        self.assertEqual(p.choose_action(o)["ability"], {"target": "p1"})
        o["private"]["objective"]["progress"]["condition_met"] = True
        self.assertIsNone(p.choose_action(o)["ability"])
        o["private"]["objective"] = {"id": "loyalist"}
        self.assertIsNone(p.choose_action(o)["ability"])
        self.assertIn("unknown replacement", p.last_decision["reason"])

    def test_standard_bearer_badge_is_known_team_not_guaranteed_cooperation(self):
        o = view("standard_bearer")
        o["public"]["public_badges"] = {"p1": "red"}
        p = ready(o)
        self.assertEqual(p.beliefs.known_teams, {"p1": "red"})
        self.assertNotEqual(p.beliefs.estimate("p1")["blue_preference"], 0)
        self.assertIsNone(p.choose_action(o)["ability"])

    def test_audit_evidence_changes_later_trust_and_payment_forecasts(self):
        g = ability_game({"p0": "auditor"})
        start(g, {"p0": tokens(blue=2), "p1": tokens(blue=2)})
        p = SocialPolicy(traits=CALM)
        before = g.observe("p0")
        p.choose_action(before)
        prior = p.beliefs.estimate("p1")["pledge_reliability"]
        batch(g, {"p0": {"tokens": tokens(blue=2)}, "p1": {"tokens": tokens(red=2)}})
        batch(g, {"p0": {"target": "p1"}})
        p.choose_action(g.observe("p0"))
        self.assertLess(p.beliefs.estimate("p1")["pledge_reliability"], prior)
        self.assertEqual(p.beliefs.last_resolution["known"]["p1"], tokens(red=2))


class EffectLearningAndPersistenceTests(unittest.TestCase):
    def observed_effect(self):
        g = ability_game({"p0": "auditor"})
        model = EffectEvidence()
        for _ in range(2):
            start(g, {"p0": tokens(blue=2), "p1": tokens(blue=2)})
            model.observe(g.observe("p0"))
            batch(g, {"p0": {"tokens": tokens(blue=2)}, "p1": {"tokens": tokens(blue=2)}})
            model.observe(g.observe("p0"))
            batch(g, {"p0": {"target": "p1"}})
            model.observe(g.observe("p0"))
            reports(g)
            model.observe(g.observe("p0"))
        return g, model

    def test_repeat_effect_is_a_hypothesis_without_revealing_other_cards(self):
        g, model = self.observed_effect()
        hypotheses = model.hypotheses(["p0", "p1"])
        self.assertEqual(len(hypotheses), 1)
        self.assertEqual(hypotheses[0]["delta"], tokens(blue=1))
        self.assertLess(hypotheses[0]["confidence"], .5)
        self.assertEqual(model.hypotheses(["p0", "p2"]), [])
        self.assertNotIn("echo", json.dumps(model.snapshot()))
        state = model.snapshot()
        model.observe(g.observe("p0"))
        self.assertEqual(model.snapshot(), state)

    def test_learned_effect_changes_forecast_but_retains_no_effect_scenario(self):
        _, model = self.observed_effect()
        o = view("auditor", wallet=0, pot=tokens(blue=7))
        p = ready(o)
        _, before = p.evaluate(o, ["p0", "p1"], tokens(), o["public"]["pledges"], "contribute")
        p.effects = model
        _, after = p.evaluate(o, ["p0", "p1"], tokens(), o["public"]["pledges"], "contribute")
        self.assertAlmostEqual(before["outcome_likelihoods"]["blue"], 0)
        self.assertGreater(after["outcome_likelihoods"]["blue"], 0)
        self.assertGreater(after["outcome_likelihoods"]["incomplete"], .5)
        self.assertTrue(after["effect_hypotheses"])

    def test_reports_alone_cannot_teach_verified_effects(self):
        g, _ = self.observed_effect()
        o = g.observe("p0")
        o["private"]["receipts"] = []
        model = EffectEvidence()
        model.observe(o)
        self.assertEqual(model.hypotheses(["p0", "p1"]), [])

    def test_action_state_and_effect_learning_restore_deterministically(self):
        _, model = self.observed_effect()
        o = view("recolorer", "vote", wallet=0, pot=tokens(blue=3, red=5), crew=("p1", "p2"))
        p = ready(o)
        p.effects = model
        p.choose_action(o)
        saved = json.loads(json.dumps(p.snapshot()))
        restored = restore_policy(saved)
        self.assertEqual(p.choose_action(o), restored.choose_action(o))
        self.assertEqual(p.last_decision, restored.last_decision)
        self.assertEqual(p.snapshot(), restored.snapshot())

    def test_legacy_social_sessions_keep_the_previous_algorithm(self):
        for version in ("social.7", "social.8"):
            p = PreviousSocialPolicy(4, 0)
            p.version = version
            restored = restore_policy(json.loads(json.dumps(p.snapshot())))
            self.assertIsInstance(restored, PreviousSocialPolicy)
            self.assertNotIsInstance(restored, SocialPolicy)
            o = view("thief", wallet=0, pot=tokens(blue=4, red=5))
            self.assertEqual(p.choose_action(o), restored.choose_action(o))
            self.assertEqual(restored.version, version)

    def test_observation_and_hidden_arrival_cannot_change_other_bots_plan(self):
        from tests.helpers import submit
        g = ability_game({"p0": "thief"})
        start(g)
        before = g.observe("p0")
        submit(g, "p1", {"type": "contribute", "tokens": tokens(red=5)})
        after = g.observe("p0")
        one, two = SocialPolicy(3, traits=CALM), SocialPolicy(3, traits=CALM)
        untouched = deepcopy(before)
        self.assertEqual(one.choose_action(before), two.choose_action(after))
        self.assertEqual(one.snapshot(), two.snapshot())
        self.assertEqual(before, untouched)


if __name__ == '__main__':
    unittest.main()
