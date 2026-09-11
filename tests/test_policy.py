import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from mission_game.bot_memory import EvidenceMemory
from mission_game.cli import main, summarize
from mission_game.policy import (
    POLICY_VERSION, STRAIGHTFORWARD_VERSION, RandomLegalPolicy,
    StraightforwardPolicy, make_policy, restore_policy,
)
from mission_game.replay import ReplayTimeline
from mission_game.session import Session
from tests.helpers import game, proposal, resolve, set_teams, submit, tokens


def observation(kind, team="blue", objective="loyalist", wallet=5, pot=None, threshold=8, crew_size=2):
    """Public/own observation fixture; no engine state reaches the policy."""
    view = game().observe("p0")
    view["phase"] = kind
    view["action_spec"] = {"type": kind, "max_total": wallet, "crew_size": crew_size,
                           "players": [f"p{i}" for i in range(8)], "min_statements": 0}
    view["private"]["team"] = team
    view["private"]["objective"] = {"id": objective}
    view["public"]["mission"].update(pot=pot or tokens(), threshold=threshold, crew_size=crew_size)
    return view


class StraightforwardTests(unittest.TestCase):
    def test_crew_uses_largest_public_wallets_and_reproducible_ties(self):
        view = observation("select_crew", crew_size=3)
        for player, wallet in zip(view["public"]["players"], [0, 2, 9, 8, 9, 1, 3, 4]):
            player["wallet"] = wallet
        action = StraightforwardPolicy(3).choose_action(view)
        self.assertEqual(set(action["crew"]), {"p2", "p3", "p4"})
        self.assertEqual(action, StraightforwardPolicy(3).choose_action(view))
        tied = observation("select_crew")
        crews = {tuple(StraightforwardPolicy(seed).choose_action(tied)["crew"]) for seed in range(12)}
        self.assertGreater(len(crews), 1)

    def test_fair_share_pledges_round_up_and_respect_wallets(self):
        for wallet, expected in ((0, 0), (1, 1), (2, 2), (20, 3)):
            view = observation("pledge", wallet=wallet, pot=tokens(green=1), threshold=8, crew_size=3)
            self.assertEqual(StraightforwardPolicy().choose_action(view)["tokens"], tokens(blue=expected))

    def test_funded_all_green_pot_gets_one_competitive_token(self):
        for team in ("blue", "red"):
            for wallet in (0, 5):
                view = observation("pledge", team=team, wallet=wallet, pot=tokens(green=10))
                self.assertEqual(StraightforwardPolicy().choose_action(view)["tokens"],
                                 tokens(**{team: int(wallet > 0)}))
        view = observation("pledge", pot=tokens(blue=4, red=4))
        self.assertEqual(StraightforwardPolicy().choose_action(view)["tokens"], tokens())

    def test_contrarian_reverses_desired_side_and_recomputes_after_card_change(self):
        for team in ("blue", "red"):
            policy = StraightforwardPolicy()
            view = observation("pledge", team=team, objective="contrarian")
            other = "red" if team == "blue" else "blue"
            self.assertEqual(policy.choose_action(view)["tokens"], tokens(**{other: 4}))
            self.assertEqual(view["private"]["team"], team)
            view["private"]["objective"]["id"] = "saver"
            self.assertEqual(policy.choose_action(view)["tokens"], tokens(**{team: 4}))
            self.assertEqual(policy.memory.desired_side, team)

    def test_completed_vote_forecast_includes_existing_pot_and_blue_tie(self):
        for team, objective, expected in (("blue", "loyalist", True), ("red", "loyalist", False),
                                          ("blue", "contrarian", False), ("red", "contrarian", True)):
            view = observation("vote", team=team, objective=objective, pot=tokens(blue=4))
            view["public"]["pledges"] = {"p2": tokens(red=4)}
            policy = StraightforwardPolicy()
            self.assertEqual(policy.choose_action(view)["approve"], expected)
            self.assertEqual(policy.last_decision["details"]["forecast_winner"], "blue")
            self.assertEqual(policy.last_decision["details"]["forecast_pot"], tokens(blue=4, red=4))

    def test_incomplete_vote_forecasts_distinguish_useful_funding(self):
        cases = ((tokens(), False), (tokens(blue=2), True), (tokens(red=2), False),
                 (tokens(blue=1, red=1), True), (tokens(green=8), True))
        for pledge, expected in cases:
            with self.subTest(pledge=pledge):
                view = observation("vote")
                view["public"]["pledges"] = {"p0": pledge}
                self.assertEqual(StraightforwardPolicy().choose_action(view)["approve"], expected)

    def test_rejection_pressure_is_explicitly_an_unmodeled_limitation(self):
        view = observation("vote")
        view["public"]["rejections"] = 7
        policy = StraightforwardPolicy()
        self.assertFalse(policy.choose_action(view)["approve"])
        self.assertIn("rejection pressure", " ".join(policy.last_decision["limitations"]))
        self.assertEqual(policy.last_decision["details"]["rejections"], 7)

    def test_contribution_honors_vector_even_if_objective_now_prefers_other_side(self):
        view = observation("contribute", objective="contrarian")
        view["public"]["pledges"] = {"p0": tokens(blue=2, green=1)}
        self.assertEqual(StraightforwardPolicy().choose_action(view)["tokens"], tokens(blue=2, green=1))

    def test_reports_describe_own_original_deposit_or_pass(self):
        for vector in (None, tokens(), tokens(blue=2, red=1, green=1)):
            view = observation("report")
            if vector is not None:
                view["private"]["last_contribution"] = {"attempt": 1, "tokens": vector}
            statements = StraightforwardPolicy().choose_action(view)["statements"]
            if vector is None:
                self.assertEqual(statements, [])
            else:
                self.assertGreaterEqual(len(statements), 1)
                self.assertTrue(all(s["player_id"] == "p0" and s["verb"] == "gave" for s in statements))
                self.assertEqual(sum(s["quantity"] for s in statements), sum(vector.values()))

    def test_policy_does_not_mutate_observation_or_mission_randomness(self):
        g = game()
        view = g.observe(f"p{g.chairman}")
        before_view, before_game = deepcopy(view), g.snapshot()
        policy = StraightforwardPolicy(20)
        for _ in range(20):
            policy.choose_action(view)
        self.assertEqual(view, before_view)
        self.assertEqual(g.snapshot(), before_game)


class MemoryAndPersistenceTests(unittest.TestCase):
    def test_evidence_is_deduplicated_detached_and_reports_remain_claims(self):
        g = game()
        resolve(g, {"p0": tokens(blue=2)})
        submit(g, "p0", {"type": "report", "statements": [
            {"player_id": "p1", "verb": "took", "quantity": 999, "color": "red"}]})
        for pid in list(g.pending_requests()):
            submit(g, pid, {"type": "report", "statements": [
                {"player_id": pid, "verb": "gave", "quantity": 0, "color": "blue"}] if pid in g.crew else []})
        view = g.observe("p0")
        memory = EvidenceMemory()
        memory.observe(view)
        saved = memory.snapshot()
        memory.observe(view)
        self.assertEqual(memory.snapshot(), saved)
        report = next(e for e in memory.events if e["type"] == "reports_revealed")
        self.assertEqual(report["reports"]["p0"][0]["quantity"], 999)
        self.assertEqual(memory.own_deposits["1"]["tokens"], tokens(blue=2))
        self.assertNotIn("p1", memory.own_deposits)
        view["history"].clear()
        view["private"]["last_contribution"]["tokens"]["blue"] = 999
        self.assertEqual(memory.snapshot(), saved)

    def test_memory_rejects_reuse_by_another_seat_or_game(self):
        view = observation("vote")
        for field, value in (("viewer", "p1"), ("game_id", "other-game")):
            memory = EvidenceMemory()
            memory.observe(view)
            other = deepcopy(view)
            other[field] = value
            with self.assertRaises(ValueError):
                memory.observe(other)

    def test_other_hidden_cards_or_sealed_deposits_cannot_affect_decision_or_memory(self):
        g = game()
        proposal(g)
        original = g.observe("p1")
        one, two = StraightforwardPolicy(2, 1), StraightforwardPolicy(2, 1)
        set_teams(g, {"p0": "red" if g.players[0].team == "blue" else "blue", "p1": g.players[1].team})
        submit(g, "p0", {"type": "contribute", "tokens": tokens(red=5)})
        changed = g.observe("p1")
        self.assertEqual(original, changed)
        self.assertEqual(one.choose_action(original), two.choose_action(changed))
        self.assertEqual(one.snapshot(), two.snapshot())
        self.assertEqual(one.last_decision, two.last_decision)

    def test_rng_memory_and_next_decision_survive_json_restore(self):
        policy = StraightforwardPolicy(42)
        view = observation("select_crew")
        policy.choose_action(view)
        restored = restore_policy(json.loads(json.dumps(policy.snapshot())))
        self.assertEqual(policy.snapshot(), restored.snapshot())
        self.assertEqual(policy.choose_action(view), restored.choose_action(view))
        self.assertEqual(policy.last_decision, restored.last_decision)

    def test_version_dispatch_preserves_random_stream_and_rejects_unknown_versions(self):
        view = observation("select_crew")
        policy = RandomLegalPolicy(42)
        restored = restore_policy(json.loads(json.dumps(policy.snapshot())))
        self.assertEqual(policy.choose_action(view), restored.choose_action(view))
        self.assertIsInstance(make_policy("straightforward"), StraightforwardPolicy)
        with self.assertRaises(ValueError):
            restore_policy({"version": "future-policy"})
        with self.assertRaises(ValueError):
            make_policy("unknown")

    def test_version_one_session_restores_random_bots_and_serializes_unchanged(self):
        session = Session(42, policy="random", game_id="legacy-session")
        session.session_version = 1
        for _ in range(5):
            session.step_bot()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            session.save(path)
            data = json.loads(path.read_text())
            self.assertNotIn("bot_decisions", data)
            restored = Session.load(path)
            self.assertEqual(json.loads(json.dumps(restored.snapshot())), data)
            self.assertTrue(all(isinstance(p, RandomLegalPolicy) for p in restored.policies.values()))
            session.run()
            restored.run()
            self.assertEqual(json.loads(json.dumps(session.snapshot())),
                             json.loads(json.dumps(restored.snapshot())))
            restored.replay()


class PolicyIntegrationTests(unittest.TestCase):
    def test_decision_explanations_match_actions_and_only_appear_in_designer_replay(self):
        session = Session(7, game_id="explanations", policy="straightforward")
        session.run()
        self.assertEqual(len(session.bot_decisions), len(session.game.action_log))
        for entry in session.bot_decisions:
            record = session.game.action_log[entry["action_index"]]
            self.assertEqual(entry["request_id"], record["request_id"])
            self.assertEqual(entry["player_id"], record["player_id"])
            self.assertEqual(entry["policy_version"], STRAIGHTFORWARD_VERSION)
        with patch.object(StraightforwardPolicy, "choose_action", side_effect=AssertionError("must not rerun")):
            player = ReplayTimeline(session, "p0")
            designer = ReplayTimeline(session, "p0", True)
            session.replay()
        self.assertTrue(all(frame["designer"] is None for frame in player.frames))
        self.assertNotIn("bot_decisions", json.dumps(session.game.snapshot()))
        self.assertNotIn(STRAIGHTFORWARD_VERSION, json.dumps(player.frames))
        self.assertIsNone(designer.frames[0]["designer"]["bot_decision"])
        for entry, frame in zip(session.bot_decisions, designer.frames[1:]):
            self.assertEqual(frame["designer"]["bot_decision"], entry)

    def test_public_claims_can_be_recorded_without_omniscient_contributions(self):
        session = Session(11, policy="straightforward")
        session.run()
        for pid, policy in session.policies.items():
            memory = policy.memory.snapshot()
            self.assertEqual(memory["viewer"], pid)
            self.assertNotIn("original_contributions", json.dumps(memory))
            self.assertNotIn("objective_deck", json.dumps(memory))
            self.assertNotIn("condition_satisfied", json.dumps(memory))

    def test_metrics_report_actual_and_mixed_policy_versions(self):
        straightforward, random = Session(4, policy="straightforward"), Session(4, policy="random")
        for session in (straightforward, random):
            session.run()
        self.assertEqual(summarize([straightforward.metrics()])["policy_version"], STRAIGHTFORWARD_VERSION)
        self.assertEqual(summarize([random.metrics()])["policy_version"], POLICY_VERSION)
        combined = summarize([straightforward.metrics(), random.metrics()])
        self.assertEqual(combined["policy_version"], "mixed")
        self.assertEqual(set(combined["policy_versions"]), {POLICY_VERSION, STRAIGHTFORWARD_VERSION})
        old = random.metrics()
        old.pop("policy_versions")
        self.assertEqual(summarize([old])["policy_version"], POLICY_VERSION)

    def test_cli_can_explicitly_keep_random_policy_and_records_population(self):
        import io
        with tempfile.TemporaryDirectory() as directory, patch("sys.stdout", io.StringIO()):
            self.assertEqual(main(["simulate", "--games", "1", "--seed", "1",
                                   "--policy", "random", "--out", directory]), 0)
            config = json.loads((Path(directory) / "policies.json").read_text())
            self.assertEqual(config, {"name": "random", "version": POLICY_VERSION})
            session = Session.load(Path(directory) / "example-replay.json")
            self.assertEqual(session.metrics()["policy_versions"], [POLICY_VERSION])
