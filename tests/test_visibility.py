import unittest

from mission_game import ActionError
from tests.helpers import game, proposal, resolve, set_teams, submit, tokens


class VisibilityTests(unittest.TestCase):
    def test_other_team_is_not_observable(self):
        g = game()
        before = g.observe("p0")
        set_teams(g, {"p0": g.players[0].team, "p1": "red" if g.players[1].team == "blue" else "blue"})
        self.assertEqual(g.observe("p0"), before)
        self.assertEqual(set(before["public"]["players"][0]), {"id", "name", "wallet"})
        for forbidden in ("resolutions", "mission_rng", "accounting", "action_log", "pending", "config"):
            self.assertNotIn(forbidden, before)
            self.assertNotIn(forbidden, before["public"])

    def test_pledge_batch_leaks_neither_response_nor_revision(self):
        g = game()
        submit(g, f"p{g.chairman}", {"type": "select_crew", "crew": ["p0", "p1"]})
        before = {pid: g.observe(pid) for pid in ("p1", "p7")}
        submit(g, "p0", {"type": "pledge", "tokens": tokens(blue=4)})
        for pid, observation in before.items():
            self.assertEqual(g.observe(pid), observation)
        self.assertTrue(g.observe("p0")["own_submission_received"])
        self.assertEqual(g.observe("p0")["public"]["pledges"], {})
        submit(g, "p1", {"type": "pledge", "tokens": tokens(red=1)})
        self.assertEqual(g.observe("p7")["public"]["pledges"]["p0"], tokens(blue=4))

    def test_contribution_batch_does_not_reveal_wallets_or_colors(self):
        g = game()
        proposal(g)
        before = g.observe("p1")
        submit(g, "p0", {"type": "contribute", "tokens": tokens(red=4)})
        self.assertEqual(g.observe("p1"), before)
        submit(g, "p1", {"type": "contribute", "tokens": tokens(blue=1)})
        result = g.observe("p1")
        self.assertEqual(result["private"]["last_contribution"]["tokens"], tokens(blue=1))
        self.assertTrue(all(r["player_id"] == "p1" for r in result["private"]["submissions"]))
        official = [e for e in result["history"] if e["type"] == "attempt_resolved"][0]
        self.assertNotIn("original_contributions", official)
        self.assertNotIn("deposits", official)
        self.assertEqual(official["wallets"]["p0"], 1)

    def test_report_batch_is_sealed(self):
        g = game()
        resolve(g)
        before = g.observe("p1")
        submit(g, "p0", {"type": "report", "statements": [
            {"player_id": "p1", "verb": "gave", "quantity": 100, "color": "green"}]})
        self.assertEqual(g.observe("p1"), before)

    def test_revealed_order_does_not_disclose_arrival_order(self):
        one, two = game(), game()
        for g in (one, two):
            submit(g, f"p{g.chairman}", {"type": "select_crew", "crew": ["p0", "p1"]})
        for g, order in ((one, ("p0", "p1")), (two, ("p1", "p0"))):
            for pid in order:
                submit(g, pid, {"type": "pledge", "tokens": tokens(blue=2)})
        self.assertEqual(one.observe("p7"), two.observe("p7"))
        self.assertEqual(list(one.pledges), list(two.pledges))

    def test_observation_mutation_cannot_change_engine(self):
        g = game()
        before = g.snapshot()
        view = g.observe(f"p{g.chairman}")
        view["public"]["players"][0]["wallet"] = 999
        view["history"].clear()
        view["private"]["team"] = "green"
        view["action_spec"]["players"].clear()
        self.assertEqual(g.snapshot(), before)

    def test_foreign_request_errors_do_not_reveal_sealed_arrival(self):
        g = game()
        proposal(g)
        request = g.observe("p0")
        errors = []
        for commit in (False, True):
            if commit:
                submit(g, "p0", {"type": "contribute", "tokens": tokens(blue=1)})
            before = g.snapshot()
            with self.assertRaises(ActionError) as error:
                g.submit("p1", request["request_id"], request["revision"],
                         {"type": "contribute", "tokens": tokens(blue=1)})
            errors.append((error.exception.code, str(error.exception)))
            self.assertEqual(g.snapshot(), before)
        self.assertEqual(errors[0], errors[1])

    def test_only_own_final_result_is_visible(self):
        g = game(max_attempts=1)
        resolve(g)
        from tests.helpers import reports
        reports(g)
        view = g.observe("p0")
        self.assertEqual(set(view["public"]["result"]), {"winner", "reason"})
        self.assertEqual(set(view["private"]["result"]), {"objective", "wallet", "won"})
        self.assertNotIn("players", view["private"]["result"])
