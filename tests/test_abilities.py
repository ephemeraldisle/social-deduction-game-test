import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from mission_game import ActionError, Game, GameConfig
from mission_game import abilities
from mission_game.beliefs import SocialBeliefs
from mission_game.bot_memory import EvidenceMemory
from mission_game.policy import RandomLegalPolicy
from mission_game.replay import ReplayTimeline
from mission_game.session import Session
from mission_game.terminal import choose_action
from mission_game.types import ObjectiveCard, Phase, Tokens
from tests.helpers import proposal, reports, submit, tokens


def ability_game(mapping=None, **kwargs):
    g = Game(42, GameConfig(rules_version="0.1-abilities-dev.1", mode="development_abilities",
                                  abilities_enabled=True, crew_min=2, crew_max=2, threshold_min=8,
                                     threshold_max=8, objective_deck=("loyalist",) * 8, **kwargs), game_id="abilities")
    g.chairman = 0
    for p in g.players:
        p.ability = (mapping or {}).get(p.id, "echo")
    return g


def batch(g, actions=None, order=None):
    for pid in order or list(g.pending_requests()):
        action = {"type": g._action_type(), "ability": (actions or {}).get(pid)}
        if g.phase == Phase.CONTRIBUTE:
            action = {"type": "contribute", "tokens": tokens(), **(actions or {}).get(pid, {})}
        submit(g, pid, action)


def prepare(g, swaps=None, scouts=None):
    assert g.phase == Phase.PREPARE_SWAP
    batch(g, swaps)
    batch(g, scouts)


def start(g, pledges=None):
    prepare(g)
    proposal(g, pledges=pledges)


class AbilityRulesTests(unittest.TestCase):
    def test_new_sessions_enable_abilities_and_deal_no_contrarian(self):
        seen = set()
        for seed in range(40):
            g = Session(seed).game
            self.assertTrue(g.config.abilities_enabled)
            self.assertEqual(g.schema_version, 3)
            self.assertNotIn("contrarian", [p.objective.kind for p in g.players])
            self.assertEqual(g.snapshot(), Session(seed, game_id=g.game_id).game.snapshot())
            seen.update(p.ability for p in g.players)
            baseline = Game(seed)
            self.assertEqual([p.team for p in g.players], [p.team for p in baseline.players])
            self.assertEqual([p.objective for p in g.players], [p.objective for p in baseline.players])
            self.assertEqual(g.mission, baseline.mission)
            self.assertEqual(g.chairman, baseline.chairman)
        self.assertEqual(seen, set(abilities.KINDS))
        with self.assertRaises(ValueError):
            GameConfig.abilities(objective_deck=("contrarian",) + ("loyalist",) * 7)

    def test_echo_triggers_only_for_two_or_more_in_one_color(self):
        for paid, bonus in ((tokens(blue=2), tokens(blue=1)), (tokens(red=3), tokens(red=1)),
                            (tokens(green=2), tokens(green=1)), (tokens(blue=1), tokens()),
                            (tokens(blue=2, green=1), tokens()), (tokens(), tokens())):
            with self.subTest(paid=paid):
                g = ability_game()
                start(g, {"p0": paid})
                batch(g, {"p0": {"tokens": paid}})
                self.assertEqual(g.mission.pot, Tokens(**paid) + Tokens(**bonus))
                self.assertEqual(g.players[0].wallet, 5 - sum(paid.values()))
                self.assertEqual(g.resolutions[-1]["original_contributions"]["p0"], paid)
                self.assertEqual(g.accounting["bonus"], sum(bonus.values()))

    def test_deposits_echo_theft_recoloring_and_scoring_in_order(self):
        g = ability_game({"p2": "stowaway", "p3": "thief", "p4": "recolorer"})
        start(g)
        batch(g, {"p0": {"tokens": tokens(blue=3)}, "p1": {"tokens": tokens(blue=2)},
                  "p2": {"ability": {"color": "green"}},
                  "p3": {"ability": {"source": "mission", "tokens": tokens(blue=1, red=2)}},
                  "p4": {"ability": {"from": "blue", "to": "red"}}})
        # Eight deposited/created, then one removed: the threshold crossing did not lock a win.
        self.assertEqual(g.mission.pot, Tokens(blue=5, red=1, green=1))
        self.assertIsNone(g.mission.winner)
        self.assertEqual(g.players[2].wallet, 4)
        self.assertEqual(g.players[3].wallet, 6)
        self.assertEqual(g.resolutions[-1]["original_contributions"],
                         {"p0": tokens(blue=3), "p1": tokens(blue=2), "p2": tokens(green=1)})
        self.assertEqual(g.observe("p3")["private"]["receipts"][-1]["tokens"], tokens(blue=1))
        self.assertEqual(g.observe("p2")["private"]["last_contribution"]["tokens"], tokens(green=1))
        g.assert_invariants()

    def test_competing_thieves_clip_in_initiative_order_not_arrival_order(self):
        for chairman in (0, 3):
            g = ability_game({"p2": "thief", "p3": "thief"})
            g.chairman = chairman
            start(g)
            batch(g, {"p0": {"tokens": tokens(blue=3)},
                      "p2": {"ability": {"source": "mission", "tokens": tokens(blue=3)}},
                      "p3": {"ability": {"source": "mission", "tokens": tokens(blue=3)}}},
                  order=list(reversed(list(g.pending_requests()))))
            first, second = (2, 3) if chairman == 0 else (3, 2)
            self.assertEqual((g.players[first].wallet, g.players[second].wallet), (8, 6))
            self.assertEqual(g.mission.pot, Tokens())
            self.assertTrue(g.players[2].ability_used and g.players[3].ability_used)

    def test_wallet_theft_occurs_after_spending_and_empty_attempt_consumes_use(self):
        g = ability_game({"p0": "thief", "p2": "thief"})
        start(g)
        batch(g, {"p0": {"tokens": tokens(blue=5), "ability": {"source": "wallet", "target": "p1", "amount": 3}},
                  "p1": {"tokens": tokens(red=4)},
                  "p2": {"ability": {"source": "wallet", "target": "p1", "amount": 3}}})
        self.assertEqual([p.wallet for p in g.players[:3]], [1, 0, 5])
        self.assertEqual(g.private_receipts["p2"][-1]["amount"], 0)
        self.assertTrue(g.players[2].ability_used)
        batch(g)
        reports(g)
        prepare(g)
        proposal(g)
        self.assertIsNone(g.observe("p2")["action_spec"]["ability"])

    def test_recolorers_chain_in_initiative_order_and_can_unlock_all_green(self):
        g = ability_game({"p0": "recolorer", "p1": "recolorer"})
        start(g)
        batch(g, {"p0": {"tokens": tokens(green=4), "ability": {"from": "green", "to": "blue"}},
                  "p1": {"tokens": tokens(green=4), "ability": {"from": "blue", "to": "red"}}})
        self.assertEqual(g.mission.pot, Tokens(red=1, green=7))
        self.assertEqual(g.mission.winner, "red")
        self.assertEqual(g.players[0].wallet, 1)

    def test_stowaway_on_crew_cannot_make_an_extra_deposit(self):
        g = ability_game({"p0": "stowaway"})
        start(g)
        self.assertIsNone(g.observe("p0")["action_spec"]["ability"])
        before = g.snapshot()
        with self.assertRaises(ActionError):
            submit(g, "p0", {"type": "contribute", "tokens": tokens(), "ability": {"color": "blue"}})
        self.assertEqual(g.snapshot(), before)

    def test_penalty_allows_offcrew_effects_and_skips_audits_and_reports(self):
        g = ability_game({"p2": "stowaway", "p3": "thief", "p4": "recolorer", "p5": "auditor"}, max_attempts=1)
        for _ in range(8):
            prepare(g)
            proposal(g, approvals=0)
        self.assertEqual(g.phase, Phase.CONTRIBUTE)
        self.assertEqual(g.crew, [])
        self.assertEqual(g.mission.pot, Tokens())
        batch(g, {"p2": {"ability": {"color": "green"}},
                  "p3": {"ability": {"source": "mission", "tokens": tokens(red=1)}},
                  "p4": {"ability": {"from": "red", "to": "blue"}}})
        self.assertEqual(g.phase, Phase.GAME_OVER)
        self.assertEqual(g.mission.pot, Tokens(blue=1, red=3, green=1))
        self.assertEqual(g.accounting["bonus"], 0)
        self.assertEqual(g.accounting["income"], 0)
        self.assertFalse(any(e["type"] == "reports_revealed" for e in g.events))

    def test_swaps_resolve_against_current_cards_and_notify_only_final_assignment(self):
        g = ability_game({"p0": "switcher", "p1": "switcher"})
        for p, kind in zip(g.players, ("saver", "spendthrift", "exact_change")):
            p.objective = ObjectiveCard(p.objective.instance_id, kind)
        before = deepcopy([(p.team, p.wallet, p.ability) for p in g.players])
        cards = [p.objective for p in g.players]
        batch(g, {"p0": {"target": "p2"}, "p1": {"target": "p2"}}, order=list(reversed(list(g.pending_requests()))))
        self.assertEqual([p.objective for p in g.players[:3]], [cards[2], cards[0], cards[1]])
        self.assertEqual([(p.team, p.wallet, p.ability) for p in g.players], before)
        for pid in ("p0", "p1", "p2"):
            receipt = g.private_receipts[pid]
            self.assertEqual(len(receipt), 1)
            self.assertEqual(receipt[0]["objective"]["id"], g._player(pid).objective.kind)
            self.assertNotIn("target", receipt[0])
            self.assertNotIn("actor", receipt[0])
        self.assertTrue(g.players[0].ability_used)
        self.assertTrue(g.players[1].ability_used)
        self.assertFalse(g.players[2].ability_used)
        self.assertEqual(g.phase, Phase.PREPARE_SCOUT)

    def test_scout_is_private_and_public_targets_still_consume_use(self):
        g = ability_game({"p0": "scout", "p1": "standard_bearer"})
        batch(g)
        batch(g, {"p0": {"target": "p1"}})
        self.assertEqual(g.private_receipts["p0"][-1]["team"], g.players[1].team)
        self.assertTrue(g.players[0].ability_used)
        self.assertEqual(g.private_receipts["p1"], [])
        self.assertEqual(g.observe("p7")["public"]["public_badges"], {"p1": g.players[1].team})

    def test_audit_returns_original_deposit_after_modifications_and_before_reports(self):
        g = ability_game({"p2": "auditor", "p3": "thief", "p4": "recolorer"}, max_attempts=1)
        start(g)
        batch(g, {"p0": {"tokens": tokens(blue=2)},
                  "p3": {"ability": {"source": "mission", "tokens": tokens(blue=1)}},
                  "p4": {"ability": {"from": "blue", "to": "red"}}})
        self.assertEqual(g.phase, Phase.AUDIT)
        self.assertEqual(g.mission.pot, Tokens(blue=1, red=1))
        self.assertEqual(g.observe("p2")["action_spec"]["ability"]["targets"], ["p0", "p1"])
        batch(g, {"p2": {"target": "p0"}})
        self.assertEqual(g.phase, Phase.REPORT)
        self.assertEqual(g.private_receipts["p2"][-1]["tokens"], tokens(blue=2))
        self.assertEqual(g.accounting["income"], 0)
        reports(g)
        self.assertEqual(g.phase, Phase.GAME_OVER)

    def test_terminal_wallets_frozen_after_theft_before_closing_audit(self):
        g = ability_game({"p2": "thief", "p3": "auditor"})
        # Two fully played missions put Blue one point from victory.
        for _ in range(2):
            start(g)
            batch(g, {"p0": {"tokens": tokens(blue=3)}, "p1": {"tokens": tokens(blue=3)}})
            batch(g)
            reports(g)
        prepare(g)
        proposal(g, crew=("p4", "p5"))
        batch(g, {"p4": {"tokens": tokens(blue=3)}, "p5": {"tokens": tokens(blue=3)},
                  "p2": {"ability": {"source": "wallet", "target": "p4", "amount": 3}}})
        self.assertEqual(g.status, "CLOSING")
        self.assertEqual(g.frozen_result["players"]["p2"]["wallet"], 10)
        frozen = deepcopy(g.frozen_result)
        income = g.accounting["income"]
        batch(g, {"p3": {"target": "p4"}})
        self.assertEqual(g.private_receipts["p3"][-1]["tokens"], tokens(blue=3))
        reports(g)
        self.assertEqual(g.status, "FINISHED")
        self.assertEqual(g.frozen_result, frozen)
        self.assertEqual(g.accounting["income"], income)


class AbilityPrivacyAndIntegrationTests(unittest.TestCase):
    def test_sealed_preparation_hidden_actions_and_audit_do_not_leak_arrivals(self):
        g = ability_game({"p0": "switcher", "p1": "scout", "p2": "thief", "p3": "auditor"})
        for phase, actor, choice in ((Phase.PREPARE_SWAP, "p0", {"target": "p4"}),
                                     (Phase.PREPARE_SCOUT, "p1", {"target": "p5"})):
            self.assertEqual(g.phase, phase)
            before = g.observe("p7")
            submit(g, actor, {"type": "prepare", "ability": choice})
            self.assertEqual(g.observe("p7"), before)
            batch(g)
        proposal(g)
        before = g.observe("p7")
        submit(g, "p2", {"type": "contribute", "tokens": tokens(),
                          "ability": {"source": "wallet", "target": "p4", "amount": 3}})
        self.assertEqual(g.observe("p7"), before)
        batch(g)
        before = g.observe("p7")
        submit(g, "p3", {"type": "audit", "ability": {"target": "p0"}})
        self.assertEqual(g.observe("p7"), before)
        batch(g)
        view = g.observe("p7")
        self.assertEqual(view["private"]["receipts"], [])
        for key in ("effects", "original_contributions", "private_receipts", "ability_used"):
            self.assertNotIn(key, json.dumps(view))

    def test_role_catalogue_and_remaining_uses_do_not_change_other_seat_view(self):
        g = ability_game({"p0": "thief"})
        before = g.observe("p7")
        g.players[0].ability = "scout"
        g.players[0].ability_used = True
        self.assertEqual(g.observe("p7"), before)
        self.assertNotIn("scout", json.dumps(before))
        self.assertNotIn("thief", json.dumps(before))
        self.assertEqual(before["phase"], "preparation")

    def test_invalid_choices_leave_state_untouched(self):
        cases = [
            ("scout", Phase.PREPARE_SCOUT, {"target": "p0"}),
            ("switcher", Phase.PREPARE_SWAP, {"target": "missing"}),
            ("thief", Phase.CONTRIBUTE, {"source": "wallet", "target": "p1", "amount": True}),
            ("thief", Phase.CONTRIBUTE, {"source": "wallet", "target": "p0", "amount": 1}),
            ("thief", Phase.CONTRIBUTE, {"source": "mission", "tokens": tokens(blue=4)}),
            ("thief", Phase.CONTRIBUTE, {"source": "mission", "tokens": tokens()}),
            ("recolorer", Phase.CONTRIBUTE, {"from": "blue", "to": "blue"}),
            ("auditor", Phase.AUDIT, {"target": "p7"}),
        ]
        for kind, phase, choice in cases:
            with self.subTest(kind=kind, choice=choice):
                g = ability_game({"p0": kind})
                if phase == Phase.PREPARE_SCOUT:
                    batch(g)
                elif phase in (Phase.CONTRIBUTE, Phase.AUDIT):
                    start(g)
                    if phase == Phase.AUDIT:
                        batch(g)
                before = g.snapshot()
                action = {"type": g._action_type(), "ability": choice}
                if phase == Phase.CONTRIBUTE:
                    action["tokens"] = tokens()
                with self.assertRaises(ActionError):
                    submit(g, "p0", action)
                self.assertEqual(g.snapshot(), before)

    def test_every_partial_batch_restores_retries_and_replays(self):
        s = Session(11, GameConfig.abilities(max_attempts=2), policy="random", game_id="persist-abilities")
        phases = set()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            while s.game.phase != Phase.GAME_OVER:
                phases.add(s.game.phase)
                s.step_bot()
                record = s.game.action_log[-1]
                before = s.game.snapshot()
                s.game.submit(**record)
                self.assertEqual(s.game.snapshot(), before)
                s.save(path)
                restored = Session.load(path)
                self.assertEqual(json.loads(json.dumps(s.snapshot())), json.loads(json.dumps(restored.snapshot())))
                self.assertEqual(restored.replay().snapshot(), before)
        self.assertTrue({Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT, Phase.CONTRIBUTE, Phase.AUDIT} <= phases)
        timeline = ReplayTimeline(s, "p0")
        self.assertTrue(timeline.at(len(timeline.frames) - 1)["verified"])

    def test_all_policies_finish_with_abilities_and_replay(self):
        for policy in ("random", "straightforward", "social"):
            for seed in (1, 11, 29):
                with self.subTest(policy=policy, seed=seed):
                    s = Session(seed, policy=policy)
                    s.run()
                    self.assertIn(s.game.status, ("FINISHED", "UNRESOLVED"))
                    s.replay()
                    s.game.assert_invariants()

    def test_public_modifications_do_not_prove_a_broken_pledge_but_audit_does(self):
        g = ability_game({"p2": "auditor", "p3": "recolorer"})
        start(g, {"p0": tokens(blue=2), "p1": tokens(blue=2)})
        memory, beliefs = EvidenceMemory(), SocialBeliefs()
        def observe():
            view = g.observe("p2")
            memory.observe(view)
            beliefs.observe(view, memory)
        observe()
        batch(g, {"p0": {"tokens": tokens(blue=2)}, "p1": {"tokens": tokens(blue=2)},
                  "p3": {"ability": {"from": "blue", "to": "red"}}})
        observe()
        self.assertEqual(beliefs.players["p0"]["broken"], 1)
        self.assertEqual(beliefs.last_resolution["bounds"], {})
        self.assertEqual(beliefs.paid, {"blue": 0, "red": 0})
        batch(g, {"p2": {"target": "p0"}})
        observe()
        self.assertEqual(beliefs.last_resolution["known"]["p0"], tokens(blue=2))
        self.assertEqual(beliefs.players["p0"]["kept"], 4.5)
        self.assertEqual(beliefs.paid, {"blue": 2, "red": 0})

    def test_terminal_builds_guided_actions_for_each_choice_shape(self):
        for kind, inputs, expected in (
            ("scout", ["yes", "1"], {"target": "p1"}),
            ("switcher", [""], None),
            ("auditor", ["yes", "p1"], {"target": "p1"}),
            ("thief", ["yes", "mission", "1 0 2"], {"source": "mission", "tokens": tokens(blue=1, green=2)}),
            ("thief", ["yes", "wallet", "1", "3"], {"source": "wallet", "target": "p1", "amount": 3}),
            ("recolorer", ["yes", "green", "red"], {"from": "green", "to": "red"}),
            ("stowaway", ["yes", "blue"], {"color": "blue"}),
        ):
            with self.subTest(kind=kind):
                phase = "prepare" if kind in ("scout", "switcher") else "audit" if kind == "auditor" else "contribute"
                view = {"action_spec": {"type": phase, "on_crew": False,
                                        "ability": {"id": kind, "targets": ["p1"]}}}
                with patch("builtins.input", side_effect=inputs):
                    self.assertEqual(choose_action(view)["ability"], expected)


if __name__ == "__main__":
    unittest.main()
