import json
import unittest
from copy import deepcopy

from mission_game.beliefs import SocialBeliefs
from mission_game.bot_memory import EvidenceMemory
from mission_game.social_policy import SocialPolicy, Traits
from tests.helpers import game, reports, resolve, submit, tokens
from tests.test_policy import observation

CALM = Traits(0, .3, .3)


def beliefs_for(view):
    memory, beliefs = EvidenceMemory(), SocialBeliefs()
    memory.observe(view)
    beliefs.observe(view, memory)
    return beliefs, memory


def trusted_history(rounds=1):
    g = game()
    for index in range(rounds):
        crew = (f'p{2*index}', f'p{2*index+1}')
        payments = {pid: tokens(blue=2) for pid in crew}
        resolve(g, payments, crew=crew, pledges=payments)
        for pid in list(g.pending_requests()):
            submit(g, pid, {'type': 'report', 'statements': [
                {'player_id': pid, 'verb': 'gave', 'quantity': 2, 'color': 'blue'}]})
    view = g.observe('p7')
    view['private']['team'] = 'blue'
    view['private']['objective'] = {'id': 'loyalist'}
    return view


def accusation_view(view, speaker='p0', target='p2', attempt=2):
    changed = deepcopy(view)
    last_id = changed['history'][-1]['id']
    changed['history'].append({'id': last_id + 1, 'type': 'vote', 'attempt': attempt,
                               'player_id': speaker, 'approve': False,
                               'complaints': [{'modifier': 'less', 'player_id': target}]})
    return changed


class RedDeceptionTests(unittest.TestCase):
    def test_blue_cover_pledge_and_private_red_plan_are_separate(self):
        view = observation('pledge', team='red')
        view['public']['score']['red'] = 2  # A decisive attack takes priority over building cover.
        view['public']['crew'] = ['p0', 'p1']
        policy = SocialPolicy(3, traits=CALM)
        pledge = policy.choose_action(view)['tokens']
        self.assertGreater(pledge['blue'], 0)
        self.assertEqual(pledge['red'] + pledge['green'], 0)
        details = policy.last_decision['details']
        self.assertGreater(details['planned_deposit']['red'], 0)
        self.assertGreater(details['advertised_pot']['blue'], details['forecast_pot']['blue'])
        # It can approve a Blue-looking crew when its own secret payment wins Red.
        view['public']['pledges'] = {'p0': pledge, 'p1': tokens(blue=4)}
        view['phase'], view['action_spec']['type'] = 'vote', 'vote'
        self.assertTrue(policy.choose_action(view)['approve'])
        view['phase'], view['action_spec']['type'] = 'contribute', 'contribute'
        deposit = policy.choose_action(view)['tokens']
        self.assertGreater(deposit['red'], deposit['blue'])
        self.assertLessEqual(sum(deposit.values()), 5)

    def test_red_rejects_blue_crew_without_automatically_accusing_a_cooperator(self):
        view = trusted_history()
        view['private']['team'] = 'red'
        view['public']['score']['blue'] = 2  # Never buy cover by conceding the game.
        view['phase'], view['action_spec'] = 'vote', {'type': 'vote'}
        view['public'].update(crew=['p0', 'p2'], pledges={'p0': tokens(blue=4), 'p2': tokens(blue=4)}, votes=[])
        policy = SocialPolicy(3, 7, traits=CALM)
        action = policy.choose_action(view)
        self.assertFalse(action['approve'])
        self.assertEqual(action['complaints'][0]['modifier'], 'more')
        self.assertEqual(action['complaints'][0]['color'], 'blue')
        self.assertIsNone(policy.last_decision['details']['accusation_target'])

    def test_both_sides_use_public_grounds_when_complaining_about_red_funding(self):
        for team in ('blue', 'red'):
            with self.subTest(team=team):
                view = observation('vote', team=team)
                view['public'].update(crew=['p1', 'p2'], pledges={'p1': tokens(red=3), 'p2': tokens()})
                policy = SocialPolicy(3, traits=CALM)
                policy.choose_action(view)
                complaint, reason = policy.complaint(view, policy.last_decision['details'], False)
                self.assertIn(complaint, [{'modifier': 'less', 'color': 'red'},
                                          {'modifier': 'more', 'player_id': 'p1', 'color': 'blue'},
                                          {'modifier': 'more', 'color': 'blue'},
                                          {'modifier': 'more', 'player_id': 'p2', 'color': 'blue'}])
                self.assertTrue(reason)

    def test_both_sides_can_request_access_for_an_unmet_objective(self):
        for team in ('blue', 'red'):
            view = observation('vote', team=team, objective='spendthrift')
            view['public'].update(crew=['p1', 'p2'], pledges={'p1': tokens(blue=4), 'p2': tokens(blue=4)})
            policy = SocialPolicy(3, traits=Traits(1, .3, .3))
            action = policy.choose_action(view)
            self.assertFalse(action['approve'])
            self.assertEqual(action['complaints'], [{'modifier': 'more', 'player_id': 'p0'}])
            self.assertTrue(policy.last_decision['details']['exclusion_protest'])

    def test_blue_rejects_observed_red_support_even_without_broken_promises(self):
        g = game()
        initial_history = deepcopy(g.events)
        resolve(g, {'p0': tokens(red=2), 'p1': tokens(red=2)},
                pledges={'p0': tokens(red=2), 'p1': tokens(red=2)})
        reports(g)
        view = g.observe('p7')
        view['private'].update(team='blue', objective={'id': 'loyalist'})
        view['phase'], view['action_spec'] = 'vote', {'type': 'vote'}
        view['public'].update(crew=['p0', 'p2'], pledges={'p0': tokens(blue=5), 'p2': tokens(blue=5)}, votes=[])
        view['public']['mission'].update(pot=tokens(), threshold=12)
        fresh = deepcopy(view)
        fresh['history'] = initial_history
        self.assertTrue(SocialPolicy(3, traits=CALM).choose_action(fresh)['approve'])
        policy = SocialPolicy(3, traits=CALM)
        action = policy.choose_action(view)
        self.assertFalse(action['approve'])
        complaint = action['complaints'][0]
        self.assertTrue(complaint == {'modifier': 'less', 'player_id': 'p0'} or
                        complaint.get('modifier') == 'more' and complaint.get('color') == 'blue')
        self.assertGreater(policy.beliefs.estimate('p0')['pledge_reliability'], .75)
        self.assertTrue(policy.last_decision['details']['suspected_red_block'])
        # A risk objection relaxes before repeated rejections hand Red a penalty.
        view['public']['rejections'] = 5
        self.assertTrue(policy.choose_action(view)['approve'])

    def test_blue_close_race_hides_temporary_red_goal_in_pledge_vote_and_report(self):
        view = observation('pledge', objective='close_race')
        view['public'].update(crew=['p0', 'p1'], score={'blue': 2, 'red': 0})
        policy = SocialPolicy(3, traits=CALM)
        pledge = policy.choose_action(view)['tokens']
        self.assertGreater(pledge['blue'], 0)
        self.assertEqual(pledge['red'], 0)
        self.assertGreater(policy.last_decision['details']['planned_deposit']['red'], 0)
        view['phase'], view['action_spec']['type'] = 'contribute', 'contribute'
        view['public']['pledges'] = {'p0': pledge, 'p1': tokens()}
        self.assertGreater(policy.choose_action(view)['tokens']['red'], 0)
        view['phase'], view['action_spec']['type'] = 'vote', 'vote'
        view['public'].update(crew=['p1', 'p2'], pledges={'p1': tokens(blue=4), 'p2': tokens(blue=4)})
        action = policy.choose_action(view)
        self.assertFalse(action['approve'])
        self.assertNotEqual(action['complaints'][0].get('color'), 'red')
        # Reporting must remember the secret payment even after Red reaches 2.
        view['phase'], view['action_spec']['type'] = 'report', 'report'
        view['public']['score']['red'] = 2
        view['private']['last_contribution'] = {'attempt': 1, 'tokens': tokens(red=3)}
        self.assertEqual(policy.choose_action(view)['statements'], [
            {'player_id': 'p0', 'verb': 'gave', 'quantity': 3, 'color': 'blue'}])
        view['phase'], view['action_spec']['type'] = 'pledge', 'pledge'
        view['public']['crew'] = ['p0', 'p1']
        self.assertEqual(policy.choose_action(view)['tokens']['red'], 0)
        self.assertFalse(policy.last_decision['details']['concealing_red_intent'])
        self.assertEqual(policy.last_decision['details']['tactical_side'], 'blue')

    def test_no_objective_announces_red_pledges_or_requests_more_red(self):
        objectives = ('loyalist', 'saver', 'spendthrift', 'exact_change', 'reliable_partner',
                      'passenger', 'close_race', 'opposition_patron', 'contrarian')
        for team in ('blue', 'red'):
            for objective in objectives:
                for score in ({'blue': 1, 'red': 0}, {'blue': 2, 'red': 2}):
                    with self.subTest(team=team, objective=objective, score=score):
                        view = observation('pledge', team=team, objective=objective)
                        view['public'].update(crew=['p0', 'p1'], score=score)
                        policy = SocialPolicy(3, traits=CALM)
                        self.assertEqual(policy.choose_action(view)['tokens']['red'], 0)
                        view['phase'], view['action_spec']['type'] = 'vote', 'vote'
                        view['public'].update(crew=['p1', 'p2'], pledges={'p1': tokens(blue=4), 'p2': tokens(blue=4)})
                        action = policy.choose_action(view)
                        self.assertTrue(all(c.get('color') != 'red' for c in action['complaints']))
                        self.assertNotIn({'modifier': 'less', 'color': 'blue'}, action['complaints'])

    def test_personal_win_condition_controls_concealment(self):
        for team, covert in (('blue', True), ('red', False)):
            view = observation('pledge', team=team, objective='contrarian')
            view['public']['crew'] = ['p0', 'p1']
            p = SocialPolicy(traits=CALM)
            action = p.choose_action(view)
            self.assertEqual(p.last_decision['details']['concealing_red_intent'], covert)
            self.assertEqual(action['tokens']['red'], 0)
        view = observation('pledge', team='red')
        view['public']['crew'] = ['p0', 'p1']
        view['public']['players'][0]['wallet'] = 0
        self.assertEqual(SocialPolicy(traits=CALM).choose_action(view)['tokens'], tokens())

    def test_blue_report_can_be_exposed_by_another_players_receipt(self):
        g = game()
        resolve(g, {'p0': tokens(red=2), 'p1': tokens(blue=2)},
                pledges={'p0': tokens(blue=2), 'p1': tokens(blue=2)})
        view = g.observe('p0')
        view['private'].update(team='red', objective={'id': 'loyalist'})
        policy = SocialPolicy(traits=CALM)
        claim = policy.choose_action(view)
        self.assertEqual(claim['statements'], [{'player_id': 'p0', 'verb': 'gave', 'quantity': 2, 'color': 'blue'}])
        submit(g, 'p0', claim)
        submit(g, 'p1', {'type': 'report', 'statements': [
            {'player_id': 'p1', 'verb': 'gave', 'quantity': 2, 'color': 'blue'}]})
        beliefs, _ = beliefs_for(g.observe('p1'))
        self.assertEqual(beliefs.last_resolution['known']['p0'], tokens(red=2))
        self.assertLess(beliefs.estimate('p0')['report_credibility'], 2/3)
        self.assertLess(beliefs.estimate('p0')['pledge_reliability'], .75)


class AccusationTests(unittest.TestCase):
    def test_unproven_accuser_is_not_penalized_for_a_grounded_objection(self):
        g = game()
        resolve(g, {'p0': tokens(red=2), 'p1': tokens(red=2)},
                pledges={'p0': tokens(blue=2), 'p1': tokens(blue=2)})
        view = g.observe('p7')
        view['private'].update(team='blue', objective={'id': 'loyalist'})
        before, memory = beliefs_for(view)
        changed = accusation_view(view, speaker='p2', target='p0')
        after = SocialBeliefs.from_snapshot(before.snapshot())
        memory.observe(changed)
        after.observe(changed, memory)
        accusation = after.accusations['2:p2:p0']
        self.assertTrue(accusation['grounded'])
        self.assertFalse(accusation['trusted'])
        self.assertEqual(accusation['backlash'], 0)
        self.assertEqual(before.estimate('p2')['blue_preference'], after.estimate('p2')['blue_preference'])
        self.assertEqual(before.last_resolution, after.last_resolution)

    def test_own_accusation_cannot_reinforce_private_beliefs(self):
        view = trusted_history()
        before, memory = beliefs_for(view)
        changed = accusation_view(view, speaker=view['viewer'], target='p0')
        memory.observe(changed)
        after = SocialBeliefs.from_snapshot(before.snapshot())
        after.observe(changed, memory)
        self.assertEqual(before.players, after.players)
        self.assertEqual(after.accusations, {})

    def test_earned_trust_changes_both_target_influence_and_accuser_backlash(self):
        trusted = trusted_history()
        fresh = deepcopy(trusted)
        fresh['history'] = fresh['history'][:2]
        results = []
        for view in (fresh, trusted):
            before, memory = beliefs_for(view)
            after = SocialBeliefs.from_snapshot(before.snapshot())
            changed = accusation_view(view)
            memory.observe(changed)
            after.observe(changed, memory)
            source_before, source_after = before.estimate('p0'), after.estimate('p0')
            target_before, target_after = before.estimate('p2'), after.estimate('p2')
            self.assertEqual(target_before['pledge_reliability'], target_after['pledge_reliability'])
            self.assertEqual(before.last_resolution, after.last_resolution)
            results.append((source_before, source_after, target_before['blue_preference'] - target_after['blue_preference']))
        self.assertLess(results[0][1]['blue_preference'], results[0][0]['blue_preference'])
        self.assertEqual(results[1][1]['blue_preference'], results[1][0]['blue_preference'])
        self.assertGreater(results[1][2], results[0][2])

    def test_repeated_accusations_are_deduplicated_and_cannot_become_proof(self):
        view = accusation_view(trusted_history())
        beliefs, memory = beliefs_for(view)
        before = deepcopy(beliefs.players)
        changed = accusation_view(view)
        memory.observe(changed)
        beliefs.observe(changed, memory)
        self.assertEqual(before, beliefs.players)
        for attempt in range(3, 30):
            changed = accusation_view(changed, attempt=attempt)
        memory.observe(changed)
        beliefs.observe(changed, memory)
        p = beliefs.players['p2']
        self.assertLessEqual(p['soft_blue'] + p['soft_red'], 2.0000001)
        self.assertNotIn('p2', beliefs.last_resolution['known'])
        restored = SocialBeliefs.from_snapshot(json.loads(json.dumps(beliefs.snapshot())))
        self.assertEqual(restored.snapshot(), beliefs.snapshot())

    def test_accused_players_subsequent_blame_has_less_influence(self):
        view = trusted_history()
        clean = accusation_view(view, speaker='p2', target='p3')
        disputed = accusation_view(accusation_view(view, speaker='p0', target='p2'), speaker='p2', target='p3')
        before, _ = beliefs_for(clean)
        after, _ = beliefs_for(disputed)
        self.assertLess(after.accusations['2:p2:p3']['influence'], before.accusations['2:p2:p3']['influence'])

    def test_accusation_changes_a_later_crew_choice(self):
        view = trusted_history(rounds=2)
        view['phase'] = 'select_crew'
        view['action_spec'] = {'type': 'select_crew', 'crew_size': 2, 'players': [f'p{i}' for i in range(8)]}
        view['public'].update(crew=[], pledges={}, votes=[])
        for player in view['public']['players']:
            player['wallet'] = 5
        before = SocialPolicy(7, 7, traits=CALM).choose_action(view)['crew']
        target = next(pid for pid in before if pid in ('p0', 'p1', 'p2', 'p3'))
        speaker = next(pid for pid in ('p0', 'p1', 'p2', 'p3') if pid != target)
        after = SocialPolicy(7, 7, traits=CALM).choose_action(accusation_view(view, speaker=speaker, target=target))['crew']
        self.assertNotIn(target, after)
        self.assertNotEqual(before, after)
