"""Current rules smoke checks. No historical replays or bot-behavior locks."""
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mission_game.config import GameConfig
from mission_game.engine import ActionError, Game
from mission_game.session import Session
from mission_game.types import ObjectiveCard, Phase, Player, Tokens, vote_tally


def submit(game, action):
    pid = next(iter(game.pending_requests()))
    view = game.observe(pid)
    game.submit(pid, view['request_id'], view['revision'], action)
    return pid


def propose(game):
    submit(game, {'type': 'select_crew', 'crew': ['p0', 'p1']})
    for _ in range(2):
        submit(game, {'type': 'pledge', 'quantity': 2})


def voting_view(good=True, wallet=40, early=False):
    view = Game(3, GameConfig.common_rules()).observe('p0')
    view.update(phase='vote', action_spec={'type': 'vote', 'max_influence': wallet, 'vote_bonus': 0})
    view['private'].update(wallet=wallet, team='blue', objective={'id': 'loyalist'}, ability={'id': 'disabled'})
    public = view['public']
    public.update(crew=['p1', 'p2'], pledges={'p1': 3, 'p2': 3}, score={'blue': 2, 'red': 2}, chairman='p1')
    public['mission'].update(pot=Tokens(blue=20 if good else 0, red=0 if good else 20).to_dict(), threshold=25, crew_size=2)
    public['votes'] = [] if early else [
        {'type': 'vote', 'player_id': f'p{i}', 'approve': i <= (3 if good else 4),
         'influence': 25 if i == 4 else 0, 'complaints': [] if i <= (3 if good else 4) else [{'color': 'blue'}]}
        for i in range(1, 8)]
    view['history'] = [{'type': 'mission_drawn', 'mission': public['mission']},
                       {'type': 'crew_selected', 'crew': public['crew']},
                       {'type': 'pledges_revealed', 'pledges': public['pledges']}, *public['votes']]
    for i, event in enumerate(view['history'], 1):
        event.update(id=i, attempt=1)
    return view


def accusation_view(viewer='p3'):
    """A small 6022F9-style dispute, with only the chosen seat's evidence."""
    view = Game(3, GameConfig.abilities()).observe(viewer)
    view.update(phase='select_crew', action_spec={'type': 'select_crew',
                'players': [f'p{i}' for i in range(8)], 'crew_size': 2})
    view['private'].update(team='blue', wallet=10, objective={'id': 'loyalist'},
                           ability={'id': 'disabled'}, receipts=[], last_contribution=None, submissions=[])
    public = view['public']
    public.update(attempt=2, crew=[], pledges={}, votes=[], public_badges={}, rejections=0,
                  score={'blue': 1, 'red': 1}, reserve=0)
    public['mission'].update(pot=Tokens().to_dict(), threshold=20, crew_size=2)
    view['history'] = [
        {'type': 'crew_selected', 'crew': ['p0', 'p2']},
        {'type': 'pledges_revealed', 'pledges': {'p0': 3, 'p2': 4}},
        {'type': 'attempt_resolved', 'penalty': False, 'previous_pot': Tokens().to_dict(),
         'mission': {**public['mission'], 'pot': Tokens(blue=3, red=5).to_dict(), 'winner': None}},
        {'type': 'reports_revealed', 'reports': {
            'p0': [{'player_id': 'p0', 'verb': 'gave', 'quantity': 3, 'color': 'blue'},
                   {'player_id': 'p2', 'verb': 'gave', 'quantity': 4, 'color': 'red'}],
            'p2': [{'player_id': 'p2', 'verb': 'gave', 'quantity': 4, 'color': 'blue'}]}}]
    for i, event in enumerate(view['history'], 1):
        event.update(id=i, attempt=1)
    return view


class GameSmoke(unittest.TestCase):
    def game(self):
        return Game(3, GameConfig.common_rules(crew_min=2, crew_max=2, threshold_min=12, threshold_max=12))

    def test_weighted_votes_pool_tokens_and_break_ties(self):
        def tally(yes, no):
            return vote_tally([{'approve': True, 'influence': n} for n in yes]
                              + [{'approve': False, 'influence': n} for n in no])
        self.assertTrue(tally([5, 3, 0, 0], [5, 1, 0, 0])['approved'])
        self.assertFalse(tally([5, 1, 0, 0], [5, 3, 0, 0])['approved'])
        self.assertFalse(tally([2, 0, 0, 0], [2, 0, 0, 0])['approved'])
        result = tally([6, 7, 0, 0], [0, 0, 0, 0])
        self.assertEqual(result['yes'], {'ballots': 4, 'votes': 5, 'tokens': 3, 'spent': 13, 'bonus': 0})
        self.assertTrue(tally([30, 0, 0], [0, 0, 0, 0, 0])['approved'])

    def test_spending_private_balances_and_reserve_resolution(self):
        game = self.game()
        propose(game)
        yes = {'p0', 'p1', 'p2', 'p3'}
        spending = {'p0': 5, 'p1': 3, 'p4': 5, 'p5': 1}
        for _ in range(8):
            pid = next(iter(game.pending_requests()))
            approve = pid in yes
            submit(game, {'type': 'vote', 'approve': approve, 'influence': spending.get(pid, 0),
                          'complaints': [] if approve else [{'modifier': 'more', 'player_id': pid}]})
        self.assertEqual(game.phase, Phase.CONTRIBUTE)
        self.assertEqual((game.reserve, game.reserve_credit), (1, 4))
        self.assertEqual(game.mission.pot.total, 0)
        self.assertEqual(game.players[0].wallet, 0)
        for _ in range(2):
            pid = next(iter(game.pending_requests()))
            submit(game, {'type': 'contribute', 'tokens': Tokens(blue=game._player(pid).wallet).to_dict()})
        self.assertEqual(game.mission.pot, Tokens(blue=2, green=1))
        self.assertEqual(game.reserve, 0)
        event = game.events[-1]
        self.assertEqual(event['reserve_added'], 1)
        self.assertEqual(event['previous_pot'], Tokens().to_dict())
        view = game.observe('p0')
        self.assertIsNone(view['public']['result'])
        self.assertEqual(view['private']['wallet'], 0)
        self.assertTrue(all('wallet' not in p for p in view['public']['players']))
        self.assertTrue(all('wallets' not in e for e in view['history']))
        self.assertEqual(Game.from_snapshot(game.snapshot()).snapshot(), game.snapshot())

    def test_vote_validation_has_no_side_effects_and_retry_spends_once(self):
        game = self.game()
        propose(game)
        pid = next(iter(game.pending_requests()))
        view = game.observe(pid)
        before = game.snapshot()
        for amount in (-1, 1.5, True, '1', 6):
            with self.assertRaises(ActionError):
                game.submit(pid, view['request_id'], view['revision'], {'type': 'vote', 'approve': True, 'influence': amount})
            self.assertEqual(game.snapshot(), before)
        action = {'type': 'vote', 'approve': True, 'influence': 3}
        for _ in range(2):
            game.submit(pid, view['request_id'], view['revision'], action)
        self.assertEqual(game._player(pid).wallet, 2)
        self.assertEqual(game.accounting['vote_spent'], 3)
        self.assertEqual(game.observe(pid)['private']['submissions'][-1]['action'], action)

    def test_rejected_proposals_keep_reserves_until_penalty(self):
        game = self.game()
        for proposal in range(8):
            propose(game)
            for index in range(8):
                spend = int(index in (proposal, (proposal + 1) % 8))
                submit(game, {'type': 'vote', 'approve': False, 'influence': spend,
                              'complaints': [{'color': 'blue'}]})
            if proposal < 7:
                self.assertEqual(game.mission.pot.total, 0)
                self.assertEqual(game.reserve, ((proposal + 1) * 2) // 10)
        self.assertEqual(game.mission.pot, Tokens(red=5, green=1))
        self.assertEqual((game.reserve, game.reserve_credit), (0, 6))
        self.assertEqual(game.attempt, 2)

    def test_numeric_pledges_and_old_save_rejection(self):
        game = self.game()
        submit(game, {'type': 'select_crew', 'crew': ['p0', 'p1']})
        view = game.observe('p0')
        for action in ({'type': 'pledge', 'tokens': Tokens(blue=2).to_dict()},
                       {'type': 'pledge', 'quantity': True}, {'type': 'pledge', 'quantity': 6}):
            with self.assertRaises(ActionError):
                game.submit('p0', view['request_id'], view['revision'], action)
        for n in (0, 2):
            submit(game, {'type': 'pledge', 'quantity': n})
        self.assertEqual(game.pledges, {'p0': 0, 'p1': 2})
        old = game.snapshot()
        old['schema_version'] = 4
        with self.assertRaisesRegex(ValueError, 'outdated'):
            Game.from_snapshot(old)

    def test_each_bot_can_finish_and_current_session_can_resume(self):
        config = GameConfig.load(Path(__file__).parents[1] / 'configs/development_abilities.json')
        with tempfile.TemporaryDirectory() as directory:
            for policy in ('random', 'straightforward', 'social'):
                with self.subTest(policy=policy):
                    session = Session(17, config=config, policy=policy)
                    for _ in range(20):
                        session.step_bot()
                    path = Path(directory) / 'session.json'
                    session.save(path)
                    session = Session.load(path)
                    self.assertEqual(session.run(), 'FINISHED')
                    session.game.assert_invariants()
                    session.replay()
                    self.assertNotIn(session.game.action_log[-1]['action']['type'], ('report', 'audit'))
                    self.assertEqual([e['type'] for e in session.game.events[-2:]],
                                     ['attempt_resolved', 'game_over'])
                    self.assertEqual(session.game.pending_requests(), {})
                    for pid in ('p0', 'p7'):
                        view = session.game.observe(pid)
                        self.assertIsNone(view['action_spec'])
                        self.assertEqual(view['public']['result']['players'], {
                            pid: {'won': result['won']}
                            for pid, result in session.game.frozen_result['players'].items()})
                        self.assertTrue(all('wallet' not in p for p in view['public']['players']))
                        self.assertNotIn('wallets', json.dumps(view['history']))

    def test_attempt_limit_also_ends_at_resolution_without_reports(self):
        game = Game(3, GameConfig.common_rules(crew_min=2, crew_max=2,
                    threshold_min=12, threshold_max=12, max_attempts=1))
        propose(game)
        for _ in range(8):
            submit(game, {'type': 'vote', 'approve': True})
        for _ in range(2):
            submit(game, {'type': 'contribute', 'tokens': Tokens(blue=2).to_dict()})
        self.assertEqual(game.phase, Phase.GAME_OVER)
        self.assertEqual(game.status, 'UNRESOLVED')
        self.assertEqual([e['type'] for e in game.events[-2:]], ['attempt_resolved', 'game_over'])
        self.assertEqual(game.accounting['income'], 0)
        self.assertEqual(game.observe('p0')['public']['result']['players'],
                         {f'p{i}': {'won': False} for i in range(8)})

    def test_auditor_chooses_after_reports_and_before_next_attempt(self):
        for inspect in (True, False):
            with self.subTest(inspect=inspect):
                game = Game(17, GameConfig.abilities(crew_min=2, crew_max=2,
                            threshold_min=12, threshold_max=12))
                auditor = next(p.id for p in game.players if p.ability == 'auditor')
                while game.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT):
                    submit(game, {'type': 'prepare', 'ability': None})
                propose(game)
                for _ in range(8):
                    submit(game, {'type': 'vote', 'approve': True})
                for _ in range(8):
                    pid = next(iter(game.pending_requests()))
                    submit(game, {'type': 'contribute', 'tokens': Tokens(blue=2 if pid in game.crew else 0).to_dict()})
                self.assertEqual(game.phase, Phase.REPORT)
                self.assertFalse(any(r['type'] == 'audit' for r in game.private_receipts[auditor]))
                wallets = [p.wallet for p in game.players]
                for _ in range(2):
                    pid = next(iter(game.pending_requests()))
                    submit(game, {'type': 'report', 'statements': [
                        {'player_id': pid, 'verb': 'gave', 'quantity': 9, 'color': 'blue'}]})
                view = game.observe(auditor)
                self.assertEqual(game.phase, Phase.AUDIT)
                self.assertEqual(view['history'][-1]['type'], 'reports_revealed')
                self.assertEqual(view['history'][-1]['reports']['p0'][0]['quantity'], 9)
                self.assertEqual(view['action_spec']['ability']['targets'], ['p0', 'p1'])
                self.assertEqual(game.attempt, 1)
                self.assertEqual([p.wallet for p in game.players], wallets)
                for _ in range(8):
                    pid = next(iter(game.pending_requests()))
                    submit(game, {'type': 'audit', 'ability': {'target': 'p0'} if pid == auditor and inspect else None})
                self.assertEqual(game.attempt, 2)
                self.assertEqual([p.wallet for p in game.players], [w + 1 for w in wallets])
                receipts = [r for r in game.private_receipts[auditor] if r['type'] == 'audit']
                self.assertEqual(len(receipts), int(inspect))
                if inspect:
                    self.assertEqual(receipts[0]['tokens'], Tokens(blue=2).to_dict())
                    self.assertEqual(receipts[0]['attempt'], 1)
                self.assertFalse(any(r['type'] == 'audit' for pid, receipts in game.private_receipts.items()
                                     if pid != auditor for r in receipts))

    def test_green_machine_counts_all_green_sources_and_bots_pursue_it(self):
        from mission_game import objectives
        from mission_game.policy import StraightforwardPolicy
        from mission_game.social_policy import SocialPolicy

        player = Player('p0', 'Machine', 'blue', objective=ObjectiveCard('green', 'green_machine'))
        history = [{'original_contributions': {'p0': Tokens(green=4).to_dict(), 'p1': Tokens(green=12).to_dict()},
                    'mission': {'pot': Tokens(green=100).to_dict()}, 'reserve_added': 1,
                    'effects': [{'type': 'echo', 'color': 'green'},
                                {'type': 'recolorer', 'to': 'green', 'changed': True},
                                {'type': 'recolorer', 'to': 'green', 'changed': False},
                                {'type': 'recolorer', 'to': 'red', 'changed': True},
                                {'type': 'thief', 'tokens': Tokens(green=3).to_dict()}]}]
        score = {'blue': 4, 'red': 2}
        self.assertEqual(objectives.green_added(history), 19)
        self.assertFalse(objectives.wins(player, score, history, 'blue', 4))
        history[0]['reserve_added'] = 2
        self.assertEqual(objectives.green_added(history), 20)
        self.assertTrue(objectives.wins(player, score, history, 'blue', 4))
        self.assertFalse(objectives.wins(player, score, history, 'red', 4))
        self.assertFalse(objectives.wins(player, score, history, None, 4))
        card = objectives.private_card(player, score, history, 4)
        self.assertEqual(card['progress']['own_paid'], 4)
        self.assertEqual(card['progress']['value'], 20)
        self.assertTrue(card['progress']['condition_met'])
        self.assertEqual(card['progress']['visibility'], 'public')
        self.assertIn('green_machine', GameConfig.load(Path(__file__).parents[1] / 'configs/development_abilities.json').objective_deck)

        view = self.game().observe('p0')
        view.update(phase='contribute', action_spec={'type': 'contribute', 'max_total': 10})
        history[0]['reserve_added'] = 1
        view['private'].update(wallet=10, team='blue', objective=objectives.private_card(player, score, history, 4))
        view['public'].update(crew=['p0', 'p1'], pledges={'p0': 10, 'p1': 5})
        view['public']['mission']['pot'] = Tokens(blue=2).to_dict()
        for policy in (StraightforwardPolicy(3, 0), SocialPolicy(3, 0)):
            action = policy.choose_action(view)
            self.assertGreater(action['tokens']['green'], 0)
            self.assertLessEqual(sum(action['tokens'].values()), 10)

    def test_green_machine_resolution_counts_reserve_echo_recolor_and_stowaway_despite_theft(self):
        from mission_game.objectives import green_added

        game = Game(17, GameConfig.abilities(crew_min=2, crew_max=2, threshold_min=30, threshold_max=30))
        seats = {p.ability: p.id for p in game.players}
        while game.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT):
            submit(game, {'type': 'prepare', 'ability': None})
        submit(game, {'type': 'select_crew', 'crew': [seats['echo'], seats['standard_bearer']]})
        for _ in range(2):
            submit(game, {'type': 'pledge', 'quantity': 2})
        for _ in range(8):
            pid = next(iter(game.pending_requests()))
            submit(game, {'type': 'vote', 'approve': True,
                          'influence': 5 if pid in (seats['green_thumb'], seats['switcher']) else 0})
        self.assertEqual(game.reserve, 1)
        for _ in range(8):
            pid = next(iter(game.pending_requests()))
            paid = Tokens(green=2) if pid == seats['echo'] else Tokens(blue=1) if pid == seats['standard_bearer'] else Tokens()
            choice = {'color': 'green'} if pid == seats['stowaway'] else {'from': 'blue', 'to': 'green'} if pid == seats['recolorer'] else {'source': 'mission', 'tokens': Tokens(green=3).to_dict()} if pid == seats['thief'] else None
            submit(game, {'type': 'contribute', 'tokens': paid.to_dict(), 'ability': choice})
        self.assertEqual(game.resolutions[-1]['reserve_added'], 1)
        self.assertEqual(green_added(game.resolutions), 6)
        self.assertEqual(game.mission.pot.green, 3)
        totals = game.observe('p0')['public']['token_totals']
        self.assertEqual(totals['green_added'], 6)
        self.assertEqual(totals['paid']['green'], 3)
        self.assertEqual(game.events[-1]['token_totals'], totals)

    def test_green_thumb_boosts_yes_and_no_without_spending_or_making_reserves(self):
        for approve in (True, False):
            for spend in (0, 5):
                with self.subTest(approve=approve, spend=spend):
                    game = Game(3, GameConfig.abilities(crew_min=2, crew_max=2,
                                threshold_min=12, threshold_max=12))
                    self.assertEqual(len({p.ability for p in game.players}), 8)
                    thumb = next(p.id for p in game.players if p.ability == 'green_thumb')
                    while game.phase in (Phase.PREPARE_SWAP, Phase.PREPARE_SCOUT):
                        submit(game, {'type': 'prepare', 'ability': None})
                    propose(game)
                    allies = {thumb, *[p.id for p in game.players if p.id != thumb][:3]}
                    for _ in range(8):
                        pid = next(iter(game.pending_requests()))
                        choice = approve if pid in allies else not approve
                        self.assertEqual(game.observe(pid)['action_spec']['vote_bonus'], 5 if pid == thumb else 0)
                        action = {'type': 'vote', 'approve': choice, 'influence': spend if pid == thumb else 0,
                                  'complaints': [] if choice else [{'color': 'blue'}]}
                        if pid == thumb:
                            view = game.observe(pid)
                            with self.assertRaises(ActionError):
                                game.submit(pid, view['request_id'], view['revision'], {**action, 'bonus': 50})
                        submit(game, action)
                    votes = [e for e in game.events if e['type'] == 'vote']
                    tally = vote_tally(votes)
                    boosted = tally['yes' if approve else 'no']
                    self.assertEqual(boosted['bonus'], 5)
                    self.assertEqual(boosted['spent'], spend)
                    self.assertEqual((boosted['votes'], boosted['tokens']), (4 + (spend + 5) // 10, (spend + 5) % 10))
                    self.assertEqual(tally['approved'], approve)
                    self.assertEqual((game.reserve, game.reserve_credit), (0, spend))
                    self.assertEqual(game.accounting['vote_spent'], spend)
                    self.assertEqual(game._player(thumb).wallet, 6 - spend)
                    self.assertEqual(game.phase == Phase.CONTRIBUTE, approve)

    def test_bots_bid_early_and_secure_decisive_votes_beyond_ten_tokens(self):
        from mission_game.policy import StraightforwardPolicy
        from mission_game.social_policy import SocialPolicy

        for kind in (StraightforwardPolicy, SocialPolicy):
            for good, cost in ((True, 26), (False, 25)):
                for bonus in (0, 5):
                    with self.subTest(policy=kind.__name__, good=good, bonus=bonus):
                        view = voting_view(good)
                        view['action_spec']['vote_bonus'] = bonus
                        policy = kind(3, 0)
                        action = policy.choose_action(view)
                        self.assertEqual(action['approve'], good)
                        self.assertEqual(action['influence'], cost - bonus)
                        self.assertEqual(vote_tally([*view['public']['votes'], {**action, 'bonus': bonus}])['approved'], good)
                        self.assertEqual(policy.last_decision['details']['vote_plan']['success_after'], 1)
            early = kind(3, 0)
            action = early.choose_action(voting_view(early=True))
            self.assertGreater(action['influence'], 0)
            self.assertLessEqual(action['influence'], 40)
            plan = early.last_decision['details']['vote_plan']
            self.assertEqual(plan['remaining_voters'], 7)
            self.assertGreater(plan['success_after'], plan['success_before'])
            # A last-seat bid too small to change anything should not be wasted.
            self.assertEqual(kind(3, 0).choose_action(voting_view(wallet=15))['influence'], 0)

    def test_vote_spending_preserves_the_payment_that_makes_a_good_mission_work(self):
        from mission_game.social_policy import SocialPolicy

        view = voting_view(wallet=10)
        public = view['public']
        public['mission'].update(pot=Tokens().to_dict(), threshold=12)
        public['crew'][:] = ['p0', 'p1']
        public['pledges'].clear()
        public['pledges'].update(p0=10, p1=2)
        for vote in public['votes']:
            vote['influence'] = 0
        policy = SocialPolicy(3, 0)
        action = policy.choose_action(view)
        self.assertTrue(action['approve'])
        self.assertEqual(action['influence'], 0)
        self.assertEqual(policy.last_decision['details']['vote_plan']['spending_limit'], 0)

    def test_paid_votes_change_opinions_and_are_reassessed_against_results(self):
        from mission_game.social_policy import SocialPolicy
        from mission_game.vote_strategy import voting_evidence

        def record(paid, bonus=0, result=False):
            view = voting_view(early=True)
            view['public']['mission'].update(pot=Tokens().to_dict(), threshold=8)
            view['public']['pledges'].update(p1=4, p2=4)
            view['history'].append({'id': 4, 'attempt': 1, 'type': 'vote', 'player_id': 'p3',
                                    'approve': True, 'influence': paid, 'bonus': bonus, 'complaints': []})
            if result:
                view['history'].append({'id': 5, 'attempt': 1, 'type': 'attempt_resolved', 'penalty': False,
                    'previous_pot': Tokens().to_dict(),
                    'mission': {**view['public']['mission'], 'pot': Tokens(red=8).to_dict(), 'winner': 'red'}})
            return view

        cheap = voting_evidence(record(0))
        costly = voting_evidence(record(20))
        bonus = voting_evidence(record(0, bonus=5))
        self.assertGreater(costly['beliefs']['p3'], cheap['beliefs']['p3'])
        self.assertEqual(bonus['beliefs']['p3'], cheap['beliefs']['p3'])
        reassessed = voting_evidence(record(20, result=True))
        self.assertLess(reassessed['beliefs']['p3'], voting_evidence(record(0, result=True))['beliefs']['p3'])
        self.assertTrue(any('later gave Red' in e['text'] for e in reassessed['evidence']['p3']))
        # A later result must not get attached to an earlier rejected proposal.
        rejected = record(20)
        rejected['history'].extend([
            {'id': 5, 'attempt': 1, 'type': 'proposal_rejected'},
            {'id': 6, 'attempt': 1, 'type': 'crew_selected', 'crew': ['p1', 'p2']},
            {**record(20, result=True)['history'][-1], 'id': 7}])
        self.assertEqual(voting_evidence(rejected)['beliefs']['p3'], costly['beliefs']['p3'])
        # The actual policy exposes the evidence and reconstructs it on resume.
        view = record(20, result=True)
        policy = SocialPolicy(3, 0)
        policy.choose_action(view)
        before = deepcopy(policy.last_decision['details']['beliefs'])
        policy = SocialPolicy.from_snapshot(policy.snapshot())
        policy.choose_action(view)
        self.assertEqual(policy.last_decision['details']['beliefs'], before)
        self.assertTrue(before['p3']['evidence'])

    def test_cover_reports_fit_this_attempt_without_clamping_truthful_deposits(self):
        from mission_game.social_policy import SocialPolicy

        for pledge, before, after, audited, audit_attempt, paid, expected in (
            (7, 5, 13, 7, 1, Tokens(red=19), 1),  # Gray's situation.
            (7, 5, 13, 7, 0, Tokens(red=19), 7),  # Old audit is irrelevant.
            (19, 5, 13, 0, 1, Tokens(red=19), 8),  # Net increase, not total pot.
            (7, 5, 5, 0, 1, Tokens(red=19), 0),
            (7, 5, 3, 7, 1, Tokens(red=19), 0),
            (0, 5, 13, 0, 1, Tokens(red=19), 0),
            (19, 5, 13, 0, 1, Tokens(blue=19), 19),  # Truth survives hidden effects.
        ):
            with self.subTest(pledge=pledge, before=before, after=after, paid=paid):
                view = self.game().observe('p0')
                view.update(phase='report', action_spec={'type': 'report', 'min_statements': 1})
                view['public'].update(crew=['p0', 'p1'], pledges={'p0': pledge, 'p1': 7})
                view['public']['mission']['pot'] = Tokens(blue=after, red=19).to_dict()
                view['private'].update(last_contribution={'attempt': 1, 'tokens': paid.to_dict()},
                                       receipts=[{'type': 'audit', 'attempt': audit_attempt, 'target': 'p1',
                                                  'tokens': Tokens(blue=audited).to_dict()}])
                view['history'].append({'id': 3, 'type': 'attempt_resolved', 'attempt': 1,
                                        'previous_pot': Tokens(blue=before).to_dict(),
                                        'mission': view['public']['mission'], 'penalty': False})
                action = SocialPolicy(3, 0).choose_action(view)
                self.assertEqual(action['statements'], [
                    {'player_id': 'p0', 'verb': 'gave', 'quantity': expected, 'color': 'blue'}])

    def test_scout_team_certainty_survives_cooperative_or_hostile_behavior(self):
        from mission_game.vote_strategy import voting_evidence

        view = accusation_view('p7')
        for team, expected in (('red', 0.), ('blue', 1.)):
            with self.subTest(team=team):
                view['private']['receipts'] = [{'type': 'scout', 'target': 'p0', 'team': team}]
                for color in ('blue', 'red'):
                    view['history'][2]['mission']['pot'] = Tokens(**{color: 20}).to_dict()
                    view['history'][2]['mission']['winner'] = color
                    result = voting_evidence(view)
                    self.assertEqual(result['known_teams']['p0'], team)
                    self.assertEqual(result['beliefs']['p0'], expected)
                    if color != team:
                        self.assertNotEqual(result['behavior']['p0'], expected)

    def test_audit_exposes_a_false_cover_and_survives_resume_without_recounting(self):
        from mission_game.social_policy import SocialPolicy

        view = accusation_view()
        policy = SocialPolicy(3, 3)
        policy.choose_action(view)
        unverified = policy.last_decision['details']['beliefs']['p0']
        view['private']['receipts'] = [{'type': 'audit', 'attempt': 1, 'target': 'p0',
                                       'tokens': Tokens(red=4).to_dict()}]
        policy.choose_action(view)
        audited = deepcopy(policy.last_decision['details']['beliefs'])
        self.assertLess(audited['p0']['blue_preference'], .3)
        self.assertLess(audited['p0']['report_credibility'], unverified['report_credibility'])
        self.assertTrue(any('contradicts my private receipt' in e['text'] for e in audited['p0']['evidence']))
        self.assertFalse(any('Pressure on' in e['text'] and 'contradicted private payment' in e['text']
                             for e in audited['p0']['evidence']))
        self.assertNotIn('p0', policy.choose_action(view)['crew'])
        restored = SocialPolicy.from_snapshot(policy.snapshot())
        restored.choose_action(view)
        self.assertEqual(restored.last_decision['details']['beliefs'], audited)
        # No other seat receives this private fact merely because Drew has it.
        other = accusation_view('p5')
        restored = SocialPolicy(3, 5)
        restored.choose_action(other)
        self.assertGreater(restored.last_decision['details']['beliefs']['p0']['blue_preference'], .45)

    def test_framed_player_uses_own_payment_memory_and_does_not_verify_theft_claims(self):
        from mission_game.social_policy import SocialPolicy

        view = accusation_view('p2')
        view['private']['last_contribution'] = {'attempt': 1, 'tokens': Tokens(blue=4).to_dict()}
        policy = SocialPolicy(3, 2)
        policy.choose_action(view)
        beliefs = policy.last_decision['details']['beliefs']
        self.assertLess(beliefs['p0']['report_credibility'], .4)
        # The next payment must not erase knowledge that an earlier allegation
        # was false. This includes a save/resume between attempts.
        view['private']['last_contribution'] = {'attempt': 2, 'tokens': Tokens(blue=1).to_dict()}
        policy = SocialPolicy.from_snapshot(policy.snapshot())
        policy.choose_action(view)
        self.assertEqual(policy.last_decision['details']['beliefs']['p0']['report_credibility'],
                         beliefs['p0']['report_credibility'])
        view['history'][-1]['reports']['p0'] = [
            {'player_id': 'p2', 'verb': 'took', 'quantity': 4, 'color': 'blue'}]
        policy.choose_action(view)
        self.assertFalse(any('contradicts my private receipt' in e['text']
                             for e in policy.last_decision['details']['beliefs']['p0']['evidence']))

    def test_reports_are_weak_claims_and_repetition_cannot_manufacture_proof(self):
        from mission_game.vote_strategy import voting_evidence

        view = accusation_view()
        base = voting_evidence(view)
        # More original Blue than the net pot is possible after hidden effects.
        self.assertFalse(any('contradict' in e['text'] for e in base['evidence']['p2']))
        view['history'][-1]['reports']['p0'] *= 3
        duplicate = voting_evidence(view)
        self.assertEqual(base['beliefs'], duplicate['beliefs'])
        self.assertEqual(base['claims']['credibility'], duplicate['claims']['credibility'])
        for attempt in range(2, 30):
            view['history'].append({'id': attempt + 4, 'type': 'reports_revealed', 'attempt': attempt,
                'reports': {'p0': [{'player_id': 'p2', 'verb': 'gave', 'quantity': 4, 'color': 'red'}]}})
        repeated = voting_evidence(view)
        self.assertAlmostEqual(base['beliefs']['p2'], repeated['beliefs']['p2'])
        # An honest partial Blue claim does not deny other colors. Audit learns
        # the Red payment but must not invent a contradiction with that claim.
        view = accusation_view()
        view['history'][-1]['reports']['p0'] = [
            {'player_id': 'p0', 'verb': 'gave', 'quantity': 3, 'color': 'blue'}]
        view['private']['receipts'] = [{'type': 'audit', 'attempt': 1, 'target': 'p0',
                                       'tokens': Tokens(blue=3, red=2).to_dict()}]
        result = voting_evidence(view)
        self.assertGreater(result['claims']['credibility']['p0'], .66)

    def test_harper_pushes_back_on_known_red_accuser_without_inventing_payments(self):
        from mission_game.social_policy import SocialPolicy

        view = accusation_view('p7')
        view['private']['receipts'] = [{'type': 'scout', 'target': 'p0', 'team': 'red'}]
        view['history'].append({'id': 5, 'attempt': 2, 'type': 'vote', 'player_id': 'p0',
            'approve': False, 'influence': 0, 'complaints': [{'modifier': 'less', 'player_id': 'p2'}]})
        policy = SocialPolicy(3, 7)
        self.assertNotIn('p0', policy.choose_action(view)['crew'])
        view.update(phase='vote', action_spec={'type': 'vote', 'max_influence': 10, 'vote_bonus': 0})
        view['public'].update(crew=['p0', 'p2'], pledges={'p0': 3, 'p2': 3})
        action = policy.choose_action(view)
        self.assertFalse(action['approve'])
        self.assertEqual(action['complaints'], [{'modifier': 'less', 'player_id': 'p0'}])
        belief = policy.last_decision['details']['beliefs']['p0']
        self.assertEqual(belief['blue_preference'], 0)
        self.assertTrue(any('possible framing' in e['text'] for e in belief['evidence']))
        # Known Red is not proof of a particular payment, nor a reason to
        # reject a mission already favorable even under an adverse forecast.
        view['public']['mission'].update(pot=Tokens(blue=20).to_dict(), threshold=25)
        self.assertTrue(policy.choose_action(view)['approve'])
        view.update(phase='report', action_spec={'type': 'report', 'min_statements': 1, 'max_statements': 3})
        view['private']['last_contribution'] = {'attempt': 2, 'tokens': Tokens(blue=2).to_dict()}
        self.assertEqual(policy.choose_action(view)['statements'], [
            {'player_id': 'p7', 'verb': 'gave', 'quantity': 2, 'color': 'blue'}])

    def test_auditor_investigates_disputed_payment_and_respects_receipt_attempt(self):
        from mission_game.social_policy import SocialPolicy
        from mission_game.vote_strategy import voting_evidence

        view = accusation_view()
        view.update(phase='audit', action_spec={'type': 'audit',
            'ability': {'id': 'auditor', 'targets': ['p0', 'p1', 'p2']}})
        view['private']['ability'] = {'id': 'auditor'}
        view['public']['attempt'] = 1
        self.assertEqual(SocialPolicy(3, 3).choose_action(view)['ability'], {'target': 'p2'})
        view['private']['receipts'] = [{'type': 'audit', 'attempt': 0, 'target': 'p2',
                                       'tokens': Tokens(blue=4).to_dict()}]
        self.assertFalse(any('contradicts' in e['text'] for e in voting_evidence(view)['evidence']['p0']))
        view['private']['receipts'][0]['attempt'] = 1
        result = voting_evidence(view)
        self.assertTrue(any('contradicts' in e['text'] for e in result['evidence']['p0']))
        self.assertGreater(result['beliefs']['p2'], .8)
        self.assertEqual(SocialPolicy(3, 3).choose_action(view)['ability'], {'target': 'p0'})


class ProposalIncomeAndTrackerSmoke(unittest.TestCase):
    def test_proposal_income_arrives_before_pledges_once_even_across_retries_and_resume(self):
        for approve in (False, True):
            with self.subTest(approve=approve):
                game = Game(17, GameConfig.abilities(crew_min=2, crew_max=2,
                            threshold_min=30, threshold_max=30))
                while game.phase != Phase.SELECT_CREW:
                    submit(game, {'type': 'prepare', 'ability': None})
                pid = next(iter(game.pending_requests()))
                view = game.observe(pid)
                self.assertEqual([p.wallet for p in game.players], [5] * 8)
                with self.assertRaises(ActionError):
                    game.submit(pid, view['request_id'], view['revision'], {'type': 'select_crew', 'crew': ['p0']})
                self.assertEqual(game.accounting['income'], 0)
                action = {'type': 'select_crew', 'crew': ['p0', 'p1']}
                for _ in range(2):
                    game.submit(pid, view['request_id'], view['revision'], action)
                self.assertEqual([p.wallet for p in game.players], [6] * 8)
                self.assertEqual(game.accounting['income'], 8)
                self.assertEqual(game.observe('p0')['action_spec']['max_total'], 6)
                submit(game, {'type': 'pledge', 'quantity': 6})
                game = Game.from_snapshot(game.snapshot())
                submit(game, {'type': 'pledge', 'quantity': 6})
                self.assertEqual(game.pledges, {'p0': 6, 'p1': 6})
                for index in range(8):
                    voter = next(iter(game.pending_requests()))
                    if index == 0:
                        spender = voter
                        self.assertEqual(game.observe(voter)['action_spec']['max_influence'], 6)
                    submit(game, {'type': 'vote', 'approve': approve, 'influence': 6 if index == 0 else 0,
                                  'complaints': [] if approve else [{'color': 'blue'}]})
                self.assertEqual(game._player(spender).wallet, 0)
                self.assertEqual(game.accounting['income'], 8)
                self.assertEqual(sum(e['type'] == 'proposal_income' for e in game.events), 1)
                self.assertFalse(any(e['type'] == 'vote_income' for e in game.events))
                if not approve:
                    while game.phase != Phase.SELECT_CREW:
                        submit(game, {'type': 'prepare', 'ability': None})
                    submit(game, action)
                    self.assertEqual(game._player(spender).wallet, 1)
                    self.assertEqual(game.accounting['income'], 16)
                game.assert_invariants()

    def test_global_trackers_publish_only_resolved_totals_and_ignore_claims(self):
        from mission_game.objectives import opposing
        game = Game(3, GameConfig.common_rules(crew_min=2, crew_max=2, threshold_min=12, threshold_max=12))
        player = game.players[0]
        player.objective = ObjectiveCard('tracker', 'opposition_patron')
        color = opposing(player.team)
        propose(game)
        for _ in range(8):
            submit(game, {'type': 'vote', 'approve': True})
        zero = {'paid': Tokens().to_dict(), 'green_added': 0}
        submit(game, {'type': 'contribute', 'tokens': Tokens(**{color: 2}).to_dict()})
        for pid in ('p0', 'p1', 'p7'):
            self.assertEqual(game.observe(pid)['public']['token_totals'], zero)
        submit(game, {'type': 'contribute', 'tokens': Tokens(**{color: 4}).to_dict()})
        totals = game.observe('p0')['public']['token_totals']
        self.assertEqual(totals['paid'][color], 6)
        self.assertEqual(game.events[-1]['token_totals'], totals)
        progress = game.observe('p0')['private']['objective']['progress']
        self.assertEqual((progress['value'], progress['own_paid'], progress['target']), (6, 2, 20))
        self.assertEqual(progress['visibility'], 'public')
        self.assertFalse(progress['condition_met'])
        for _ in range(2):
            pid = next(iter(game.pending_requests()))
            submit(game, {'type': 'report', 'statements': [
                {'player_id': pid, 'verb': 'gave', 'quantity': 999, 'color': color}]})
        self.assertEqual(game.observe('p0')['public']['token_totals'], totals)
        restored = Game.from_snapshot(game.snapshot())
        self.assertEqual(restored.observe('p0')['private']['objective']['progress']['value'], 6)

    def test_global_goals_use_everyones_payments_and_bots_stop_requesting_completed_green_goal(self):
        from mission_game.objectives import private_card
        from mission_game.ability_policy import remaining_green
        from mission_game.social_policy import SocialPolicy
        player = Player('p0', 'Patron', 'blue', objective=ObjectiveCard('goal', 'opposition_patron'))
        history = [{'original_contributions': {'p1': Tokens(red=20, green=20).to_dict()},
                    'reserve_added': 2, 'effects': [], 'mission': {'pot': Tokens().to_dict()}}]
        card = private_card(player, {'blue': 3, 'red': 1}, history, 4)
        self.assertEqual(card['progress']['value'], 20)
        self.assertEqual(card['progress']['own_paid'], 0)
        self.assertTrue(card['progress']['condition_met'])
        player.objective = ObjectiveCard('goal', 'green_machine')
        card = private_card(player, {'blue': 3, 'red': 1}, history, 4)
        self.assertEqual(card['progress']['value'], 22)
        view = voting_view(wallet=10)
        view['private']['objective'] = card
        self.assertEqual(remaining_green(view), 0)
        self.assertTrue(SocialPolicy(3, 0).choose_action(view)['approve'])


class BlindPlaytestBotSmoke(unittest.TestCase):
    def choose(self, view):
        from mission_game.social_policy import SocialPolicy
        policy = SocialPolicy(3, int(view['viewer'][1:]))
        action = policy.choose_action(view)
        return action, policy.last_decision['details']

    def threatened_vote(self, team='red'):
        view = voting_view(wallet=18, early=True)
        other = 'blue' if team == 'red' else 'red'
        view['private'].update(team=team, objective={'id': 'saver'})
        public = view['public']
        public.update(score={team: 0, other: 3}, crew=['p1', 'p2', 'p3'],
                      pledges={'p1': 1, 'p2': 2, 'p3': 2},
                      public_badges={pid: other for pid in ('p1', 'p2', 'p3')})
        public['rules']['proposal_income'] = 1
        public['rules']['missions_to_win'] = 4
        public['mission'].update(pot={team: 1, other: 8, 'green': 2}, threshold=17, crew_size=3)
        view['history'] = []
        return view

    def test_guard_against_terminal_payments_above_pledges_for_either_team(self):
        for team in ('blue', 'red'):
            for rejections in (0, 6):
                with self.subTest(team=team, rejections=rejections):
                    view = self.threatened_vote(team)
                    view['public']['rejections'] = rejections
                    action, details = self.choose(view)
                    self.assertLess(sum(details['forecast_pot'].values()), 17)
                    self.assertGreaterEqual(sum(details['higher_payment_forecast'].values()), 17)
                    self.assertFalse(action['approve'])
                    self.assertTrue(details['terminal_loss_risk'])
                    # A Saver can spend below ten to avoid an immediate loss.
                    self.assertEqual(details['vote_plan']['spending_limit'], 18)

    def test_red_can_keep_nonterminal_cover_without_buying_blue_progress(self):
        view = self.threatened_vote()
        view['public']['score'] = {'blue': 0, 'red': 0}
        action, details = self.choose(view)
        self.assertTrue(action['approve'])
        self.assertEqual(action['influence'], 0)
        self.assertTrue(details['cover_only'])
        self.assertFalse(details['terminal_loss_risk'])

    def test_support_recovery_in_stages_but_not_a_funded_opponent_win(self):
        view = voting_view(wallet=2, early=True)
        public = view['public']
        public.update(crew=['p0', 'p1', 'p2'], pledges={'p0': 1, 'p1': 1, 'p2': 1},
                      score={'blue': 2, 'red': 0}, reserve=2,
                      public_badges={'p1': 'blue', 'p2': 'blue'})
        public['rules']['proposal_income'] = 1
        public['mission'].update(pot=Tokens(red=8, green=4).to_dict(), threshold=24, crew_size=3)
        view['history'] = []
        action, details = self.choose(view)
        self.assertTrue(action['approve'])
        self.assertEqual(action['influence'], 0)
        self.assertTrue(details['recovery_proposal'])
        self.assertLess(details['forecast_pot']['blue'], details['forecast_pot']['red'])
        public['mission']['threshold'] = 17
        self.assertFalse(self.choose(view)[0]['approve'])

    def test_bot_does_not_count_proposal_income_twice_when_planning_a_payment(self):
        view = voting_view(wallet=0, early=True)
        view['public'].update(crew=['p0', 'p1'], pledges={'p0': 0, 'p1': 0})
        view['public']['rules']['proposal_income'] = 1
        view['public']['mission'].update(pot=Tokens().to_dict(), threshold=1)
        view['history'] = []
        action, details = self.choose(view)
        self.assertEqual(action['influence'], 0)
        self.assertEqual(details['planned_payment'], Tokens().to_dict())
        view.update(phase='pledge', action_spec={'type': 'pledge', 'max_total': 0})
        self.assertEqual(self.choose(view)[0]['quantity'], 0)

    def test_known_team_does_not_override_audited_payment_behavior(self):
        view = accusation_view()
        view.update(phase='vote', action_spec={'type': 'vote', 'max_influence': 10, 'vote_bonus': 0})
        view['public'].update(crew=['p0', 'p2'], pledges={'p0': 4, 'p2': 0})
        view['public']['mission']['pot'] = Tokens().to_dict()
        view['private']['receipts'] = [
            {'type': 'scout', 'target': 'p0', 'team': 'blue'},
            {'type': 'audit', 'attempt': 1, 'target': 'p0', 'tokens': Tokens(red=4).to_dict()}]
        _, details = self.choose(view)
        self.assertEqual(details['beliefs']['p0']['blue_preference'], 1)
        self.assertGreater(details['forecast_pot']['red'], details['forecast_pot']['blue'])

    def test_close_race_secures_own_match_point_before_helping_opponent(self):
        view = voting_view(wallet=5)
        view.update(phase='contribute', action_spec={'type': 'contribute', 'max_total': 5})
        view['private']['objective'] = {'id': 'close_race'}
        view['public'].update(crew=['p0', 'p1'], pledges={'p0': 5, 'p1': 0})
        view['public']['rules']['missions_to_win'] = 4
        view['public']['mission'].update(pot=Tokens().to_dict(), threshold=20)
        view['history'] = []
        for blue, red, color in ((1, 0, 'blue'), (2, 1, 'blue'), (3, 1, 'red'), (3, 3, 'blue'), (1, 3, 'blue')):
            with self.subTest(blue=blue, red=red):
                view['public']['score'] = {'blue': blue, 'red': red}
                self.assertGreater(self.choose(view)[0]['tokens'][color], 0)

    def test_do_not_buy_negligible_tail_risk_above_confidence_target(self):
        from mission_game.vote_strategy import influence_plan, voting_evidence
        view = voting_view(early=True)
        view['action_spec']['vote_bonus'] = 5
        view['public']['votes'] = [{'player_id': f'p{i}', 'approve': True, 'influence': 0}
                                   for i in (1, 2, 3)]
        view['public']['public_badges'] = {f'p{i}': 'blue' for i in (4, 5, 6, 7)}
        for urgent in (False, True):
            spend, plan = influence_plan(view, True, Tokens(blue=20).to_dict(), voting_evidence(view), 40, urgent)
            self.assertGreater(plan['success_before'], plan['target_confidence'])
            self.assertGreater(plan['success_at_limit'], plan['success_before'])
            self.assertEqual(spend, 0)

    def test_small_affordable_probability_gains_must_justify_token_cost(self):
        from mission_game.vote_strategy import influence_plan, voting_evidence
        view = voting_view(wallet=2, early=True)
        view['public']['votes'] = [{'player_id': 'p1', 'approve': True, 'influence': 1}]
        evidence = voting_evidence(view)
        evidence['spending'] = {pid: [2, 0] for pid in evidence['spending']}
        spend, plan = influence_plan(view, True, Tokens(blue=20, red=1).to_dict(), evidence, 2)
        self.assertLess(plan['success_before'], plan['target_confidence'])
        self.assertGreater(plan['success_at_limit'], plan['success_before'])
        self.assertEqual(spend, 0)


class ReplayAssessmentSmoke(unittest.TestCase):
    def test_selected_player_assessments_carry_forward_and_rewind_without_future_evidence(self):
        from mission_game.replay import ReplayTimeline
        session = Session(17, policy='social')
        for _ in range(24):
            session.step_bot()
        original = session.snapshot()
        # Replay must use the saved assessments, even if today's policy changes.
        with patch('mission_game.social_policy.SocialPolicy.choose_action', side_effect=AssertionError('Bot invoked during replay')):
            for seat in ('p0', 'p3'):
                timeline = ReplayTimeline(session, seat, designer=True)
                decisions = [d for d in session.bot_decisions if d['player_id'] == seat and d['details'].get('beliefs')]
                self.assertGreaterEqual(len(decisions), 2)
                # Seek backward as well as forward. The last actor often differs
                # from the seat being inspected, and may have newer evidence.
                for position in reversed(range(len(session.game.action_log) + 1)):
                    with self.subTest(seat=seat, position=position):
                        frame = timeline.at_position(position)
                        eligible = [d for d in decisions if d['action_index'] < position]
                        saved = frame['designer']['player_assessment']
                        if not eligible:
                            self.assertIsNone(saved)
                            continue
                        expected = eligible[-1]
                        self.assertEqual(saved['player_id'], seat)
                        self.assertEqual(saved['position'], expected['action_index'] + 1)
                        self.assertEqual(saved['details'], expected['details'])
                        self.assertEqual(set(saved['details']['beliefs']), {f'p{i}' for i in range(8)} - {seat})
                        # Mutating a response cannot alter cached frames or saves.
                        saved['details']['beliefs'].clear()
                        self.assertEqual(timeline.at_position(position)['designer']['player_assessment']['details'], expected['details'])
            self.assertTrue(all(f['designer'] is None for f in ReplayTimeline(session, 'p0').frames))
        self.assertEqual(session.snapshot(), original)

    def test_unfinished_table_cannot_reveal_bot_rankings(self):
        from mission_game.server import TableStore, WebError
        with tempfile.TemporaryDirectory() as directory:
            store = TableStore(directory)
            game_id = store.create(paced=True)['id']
            with self.assertRaises(WebError) as caught:
                store.replay(game_id, designer=True)
            self.assertEqual(caught.exception.status, 403)
            self.assertIsNone(store.replay(game_id)['designer'])


if __name__ == '__main__':
    unittest.main()
