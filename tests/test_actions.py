import unittest

from mission_game import ActionError
from mission_game.types import MAX_QUANTITY
from tests.helpers import game, proposal, resolve, submit, tokens


class ActionTests(unittest.TestCase):
    def assert_rejected_without_mutation(self, g, pid, action):
        before = g.snapshot()
        with self.assertRaises(ActionError):
            submit(g, pid, action)
        self.assertEqual(g.snapshot(), before)

    def test_bad_crews_and_unknown_fields(self):
        g = game()
        pid = f"p{g.chairman}"
        for crew in ([], ["p0"], ["p0", "p0"], ["p0", "p9"], ["p0", {}], "p0 p1"):
            with self.subTest(crew=crew):
                self.assert_rejected_without_mutation(g, pid, {"type": "select_crew", "crew": crew})
        self.assert_rejected_without_mutation(g, pid, {"type": "select_crew", "crew": ["p0", "p1"], "message": "hello"})

    def test_invalid_pledges(self):
        g = game()
        submit(g, f"p{g.chairman}", {"type": "select_crew", "crew": ["p0", "p1"]})
        bad = [tokens(blue=-1), tokens(blue=True), tokens(blue=1.5), tokens(blue="2"),
               tokens(blue=6), {"blue": 1}, {**tokens(), "yellow": 0}, []]
        for vector in bad:
            with self.subTest(vector=vector):
                self.assert_rejected_without_mutation(g, "p0", {"type": "pledge", "tokens": vector})

    def test_contribution_budget_and_invalid_second_commit(self):
        g = game()
        proposal(g)
        submit(g, "p0", {"type": "contribute", "tokens": tokens(blue=5)})
        self.assert_rejected_without_mutation(g, "p1", {"type": "contribute", "tokens": tokens(red=6)})
        self.assertEqual(g.players[0].wallet, 5)
        self.assertEqual(g.mission.pot.total, 0)

    def test_noncrew_cannot_submit_deposit(self):
        g = game()
        proposal(g)
        self.assert_rejected_without_mutation(g, "p7", {"type": "contribute", "tokens": tokens(blue=1)})

    def test_vote_requires_boolean_and_complaint_grammar(self):
        g = game()
        submit(g, f"p{g.chairman}", {"type": "select_crew", "crew": ["p0", "p1"]})
        for pid in g.crew:
            submit(g, pid, {"type": "pledge", "tokens": tokens()})
        pid = next(iter(g.pending_requests()))
        self.assert_rejected_without_mutation(g, pid, {"type": "vote", "approve": 1})
        for complaints in ([{}], [{"modifier": "more"}], [{"color": "yellow"}],
                           [{"player_id": "p9"}], [{"color": "red", "quantity": 2}],
                           [], [{"color": "red"}] * 2, "less red"):
            with self.subTest(complaints=complaints):
                self.assert_rejected_without_mutation(g, pid, {"type": "vote", "approve": False, "complaints": complaints})
        self.assert_rejected_without_mutation(g, pid, {"type": "vote", "approve": False})
        self.assert_rejected_without_mutation(g, pid, {"type": "vote", "approve": True,
                                                      "complaints": [{"color": "red"}]})
        spec = g.observe(pid)["action_spec"]
        self.assertEqual(spec["max_complaints"], 1)
        self.assertTrue(spec["complaint_required_on_no"])
        submit(g, pid, {"type": "vote", "approve": False,
                        "complaints": [{"modifier": "less", "player_id": "p2"}]})
        self.assertEqual(g.votes[-1]["complaints"], [{"modifier": "less", "player_id": "p2"}])
        submit(g, next(iter(g.pending_requests())), {"type": "vote", "approve": True})

    def test_false_reports_are_accepted_and_sealed(self):
        g = game()
        resolve(g)
        false_claim = {"player_id": "p7", "verb": "took", "quantity": MAX_QUANTITY, "color": "red"}
        submit(g, "p0", {"type": "report", "statements": [false_claim]})
        self.assertEqual(g.pending["p0"]["statements"], [false_claim])

    def test_reports_validate_syntax_and_crew_requirement(self):
        g = game()
        resolve(g)
        self.assert_rejected_without_mutation(g, "p0", {"type": "report", "statements": []})
        claim = {"player_id": "p0", "verb": "gave", "quantity": 0, "color": "blue"}
        for changes in ({"quantity": -1}, {"quantity": True}, {"quantity": MAX_QUANTITY + 1},
                        {"verb": "lied"}, {"color": "yellow"}, {"player_id": "p8"}, {"source": "wallet"}):
            with self.subTest(changes=changes):
                self.assert_rejected_without_mutation(g, "p0", {"type": "report", "statements": [{**claim, **changes}]})
        self.assert_rejected_without_mutation(g, "p0", {"type": "report", "statements": [claim] * 4})
        for statements in ([], [claim]):
            self.assert_rejected_without_mutation(g, "p2", {"type": "report", "statements": statements})
        self.assertIsNone(g.observe("p2")["action_spec"])
        # Even a forged current request ID cannot make an off-crew reporter eligible.
        with self.assertRaises(ActionError):
            g.submit("p2", f"{g.game_id}:{g.revision}:p2", g.revision, {"type": "report", "statements": [claim]})
        self.assertEqual(set(g.pending_requests()), {"p0", "p1"})
        for pid in ("p0", "p1"):
            submit(g, pid, {"type": "report", "statements": [claim]})
        revealed = next(e for e in g.events if e["type"] == "reports_revealed")
        self.assertEqual(set(revealed["reports"]), {"p0", "p1"})

    def test_stale_and_other_seat_requests_are_rejected(self):
        g = game()
        chairman = f"p{g.chairman}"
        other = f"p{(g.chairman + 1) % 8}"
        request = g.observe(chairman)
        before = g.snapshot()
        for pid, revision in ((other, request["revision"]), (chairman, -1), (chairman, True)):
            with self.assertRaises(ActionError):
                g.submit(pid, request["request_id"], revision, {"type": "select_crew", "crew": ["p0", "p1"]})
            self.assertEqual(g.snapshot(), before)
