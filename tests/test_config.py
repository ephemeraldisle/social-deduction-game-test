"""Editable new-game settings, unique ability deals, and saved-rule isolation."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mission_game import Game, GameConfig
from mission_game.abilities import KINDS
from mission_game.cli import main
from mission_game.config import DEFAULT_CONFIG_PATH, REVENUE_ABILITIES_VERSION
from mission_game.server import TableStore
from mission_game.session import Session


class ConfigTests(unittest.TestCase):
    def test_current_profile_accepts_tuned_ranges_and_rejects_invalid_ranges(self):
        config = GameConfig.abilities(threshold_min=15, threshold_max=30, crew_max=5)
        self.assertEqual(GameConfig(**config.to_dict()), config)
        for changes in ({"threshold_min": 31, "threshold_max": 30}, {"threshold_min": 0},
                        {"threshold_max": True}, {"crew_max": 9}, {"crew_min": 1},
                        {"crew_min": 5, "crew_max": 4}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                GameConfig.abilities(**changes)
        with self.assertRaises(ValueError):
            replace(config, rules_version=REVENUE_ABILITIES_VERSION)

    def test_running_store_rereads_config_but_existing_tables_keep_their_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "settings.json"
            first = GameConfig.abilities(threshold_min=15, threshold_max=15, crew_min=5, crew_max=5)
            path.write_text(json.dumps(first.to_dict()))
            store = TableStore(root / "games", policy="random", config_path=path)
            one = store.create(paced=True)
            second = replace(first, threshold_min=30, threshold_max=30, crew_min=2, crew_max=2)
            path.write_text(json.dumps(second.to_dict()))
            two = store.create(paced=True)
            for entry, expected in ((one, first), (two, second)):
                session, _ = store.load(entry["id"])
                self.assertEqual(session.game.config, expected)
                self.assertEqual(session.game.mission.threshold, expected.threshold_min)
                self.assertEqual(session.game.mission.crew_size, expected.crew_min)
                session.replay()
            path.write_text('{"threshold_min":0}')
            with self.assertRaises(ValueError):
                store.create(paced=True)
            self.assertEqual(len(store.catalog()), 2)
            self.assertEqual(store.load(one["id"])[0].game.config, first)

    def test_default_web_table_uses_the_repository_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TableStore(directory, policy="random")
            entry = store.create(paced=True)
            self.assertEqual(store.load(entry["id"])[0].game.config, GameConfig.load(DEFAULT_CONFIG_PATH))

    def test_web_cli_passes_an_explicit_config_to_the_server(self):
        with patch("mission_game.server.serve") as serve:
            self.assertEqual(main(["web", "--port", "8766", "--config", "my-settings.json"]), 0)
        serve.assert_called_once_with("runs", 8766, "social", None, "my-settings.json")

    def test_terminal_cli_defaults_to_the_same_repository_profile(self):
        with patch("mission_game.cli.human_loop") as play:
            self.assertEqual(main(["play", "--seed", "7"]), 0)
        self.assertEqual(play.call_args.args[0].game.config, GameConfig.load(DEFAULT_CONFIG_PATH))

    def test_five_person_crews_and_larger_missions_play_and_replay(self):
        config = GameConfig.abilities(threshold_min=15, threshold_max=30,
                                      crew_min=5, crew_max=5, max_attempts=2)
        session = Session(7, config, policy="random")
        session.run()
        self.assertEqual(len(session.game.resolutions), 2)
        self.assertEqual(session.replay().snapshot(), session.game.snapshot())
        rules = session.game.observe("p0")["public"]["rules"]
        self.assertEqual(rules["threshold_range"], [15, 30])
        self.assertEqual(rules["crew_range"], [5, 5])


class UniqueAbilityTests(unittest.TestCase):
    def test_every_new_deal_has_one_of_each_ability_and_preserves_other_random_streams(self):
        orders = set()
        for seed in range(80):
            new = Game(seed, GameConfig.abilities(), game_id="same")
            old = Game(seed, replace(new.config, rules_version=REVENUE_ABILITIES_VERSION))
            order = tuple(p.ability for p in new.players)
            self.assertEqual(set(order), set(KINDS))
            orders.add(order)
            self.assertEqual([(p.team, p.objective) for p in new.players],
                             [(p.team, p.objective) for p in old.players])
            self.assertEqual(new.chairman, old.chairman)
            self.assertEqual(new.mission, old.mission)
            self.assertEqual(new.snapshot(), Game(seed, new.config, game_id="same").snapshot())
        self.assertGreater(len(orders), 1)

    def test_new_snapshots_reject_duplicates_but_old_deals_restore_unchanged(self):
        new = Game(42, GameConfig.abilities())
        bad = new.snapshot()
        bad["players"][1]["ability"] = bad["players"][0]["ability"]
        with self.assertRaisesRegex(AssertionError, "exactly once"):
            Game.from_snapshot(bad)
        old = Session(42, replace(new.config, rules_version=REVENUE_ABILITIES_VERSION, max_attempts=1), policy="random")
        self.assertLess(len({p.ability for p in old.game.players}), 8)
        old.run()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            old.save(path)
            restored = Session.load(path)
            self.assertEqual(json.loads(json.dumps(old.snapshot())), json.loads(json.dumps(restored.snapshot())))
            self.assertEqual(restored.replay().snapshot(), old.game.snapshot())


if __name__ == "__main__":
    unittest.main()
