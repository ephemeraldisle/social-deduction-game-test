"""Versioned vote revenue, four-point games, and bot forecasts for those rules."""
import json
import unittest
from dataclasses import replace
from mission_game.config import REVENUE_ABILITIES_VERSION
from mission_game import Game, GameConfig
from mission_game.types import ObjectiveCard, Phase
from mission_game.session import Session
from mission_game.policy import restore_policy
from mission_game.social_policy import SocialPolicy, Traits
from mission_game.beliefs import SocialBeliefs
from mission_game.bot_memory import EvidenceMemory
from tests.helpers import proposal, submit, tokens, reports
from tests.test_abilities import prepare, batch
from tests.test_ability_strategy import view, ready


def new_game(**kwargs):
    # Isolate revenue behavior with repeated Scouts under the earlier deal rules.
    config = replace(GameConfig.abilities(crew_min=2, crew_max=2, threshold_min=8,
                                         threshold_max=8, objective_deck=('loyalist',)*8, **kwargs),
                     rules_version=REVENUE_ABILITIES_VERSION)
    g = Game(42, config, game_id='revenue')
    g.chairman = 0
    for p in g.players: p.ability = 'scout'
    return g


class RevenueRulesTests(unittest.TestCase):
    def test_new_default_and_legacy_profile_are_distinct_and_restore(self):
        current = Session(1).game
        self.assertEqual((current.config.vote_income, current.config.missions_to_win), (1,4))
        self.assertEqual(current.observe('p0')['public']['rules']['missions_to_win'],4)
        old = Game(1, GameConfig(rules_version='0.1-abilities-dev.1', mode='development_abilities', abilities_enabled=True))
        self.assertNotIn('vote_income', old.snapshot()['config'])
        for g in (current,old):
            self.assertEqual(g.snapshot(),Game.from_snapshot(json.loads(json.dumps(g.snapshot()))).snapshot())
        for changes in ({'vote_income':True}, {'missions_to_win':3}, {'vote_income':0}):
            with self.assertRaises(ValueError): GameConfig.abilities(**changes)

    def test_everyone_receives_one_after_all_ballots_pass_or_fail_and_retry_is_safe(self):
        for approve in (True,False):
            g = new_game(); prepare(g)
            submit(g,'p0',{'type':'select_crew','crew':['p0','p1']})
            for pid in ('p0','p1'): submit(g,pid,{'type':'pledge','tokens':tokens(blue=1)})
            for i in range(8):
                self.assertEqual([p.wallet for p in g.players],[5]*8)
                o=g.observe(f'p{i}')
                action={'type':'vote','approve':approve,'complaints':[] if approve else [{'color':'blue'}]}
                submit(g,f'p{i}',action)
            self.assertEqual([p.wallet for p in g.players],[6]*8)
            self.assertEqual(g.accounting['income'],8)
            g.submit('p7',o['request_id'],o['revision'],action)
            self.assertEqual([p.wallet for p in g.players],[6]*8)
            self.assertEqual(len([e for e in g.events if e['type']=='vote_income']),1)
            self.assertEqual(g.phase,Phase.CONTRIBUTE if approve else Phase.PREPARE_SWAP)
            g.assert_invariants()

    def test_eight_rejections_pay_eight_revenues_then_attempt_income(self):
        g=new_game()
        for n in range(8):
            prepare(g); proposal(g,approvals=0)
            self.assertEqual([p.wallet for p in g.players],[6+n]*8)
        self.assertEqual(g.phase,Phase.CONTRIBUTE)
        batch(g)
        self.assertEqual(g.mission.pot.red,5)
        self.assertEqual([p.wallet for p in g.players],[14]*8)
        self.assertEqual(g.accounting['income'],72)
        self.assertEqual(len([e for e in g.events if e['type']=='income']),1)
        g.assert_invariants()

    def test_fourth_mission_finishes_with_close_race_four_three_and_frozen_wallets(self):
        g=new_game()
        holder=g.players[0]
        holder.objective=ObjectiveCard(holder.objective.instance_id,'close_race')
        own=holder.team; other='red' if own=='blue' else 'blue'
        for i,color in enumerate((own,other,own,other,own,other,own)):
            prepare(g)
            crew=[f'p{(2*i)%8}',f'p{(2*i+1)%8}']
            proposal(g,crew=crew)
            batch(g,{pid:{'tokens':tokens(**{color:4})} for pid in crew})
            self.assertEqual(g.score[color],i//2+1)
            if i<6: self.assertIsNone(g.frozen_result)
            else:
                self.assertEqual(g.frozen_result['reason'],'four_missions')
                self.assertTrue(g.frozen_result['players']['p0']['won'])
                wallets=[p.wallet for p in g.players]
            batch(g); reports(g)
        self.assertEqual(g.phase,Phase.GAME_OVER)
        self.assertEqual([p.wallet for p in g.players],wallets)
        self.assertEqual(g.score,{own:4,other:3})
        self.assertIn('4–3',g.observe('p0')['private']['objective']['text'])
        self.assertIn('four',g.observe('p1')['private']['objective']['text'])

    def test_vote_revenue_is_spendable_and_cannot_be_mistaken_for_a_deposit(self):
        g=new_game(); prepare(g); proposal(g,pledges={'p0':tokens(blue=5),'p1':tokens()})
        memory,beliefs=EvidenceMemory(),SocialBeliefs()
        o=g.observe('p0'); memory.observe(o); beliefs.observe(o,memory)
        self.assertEqual(beliefs.wallets['p0'],6)
        batch(g,{'p0':{'tokens':tokens(blue=6)}})
        o=g.observe('p0');memory.observe(o);beliefs.observe(o,memory)
        self.assertEqual(g.players[0].wallet,0)
        self.assertEqual(beliefs.paid['blue'],6)
        self.assertEqual(beliefs.last_resolution['bounds'],{})


class RevenuePlanningTests(unittest.TestCase):
    def modern_view(self,ability,**kwargs):
        o=view(ability,**kwargs)
        o['public']['rules'].update(vote_income=1,missions_to_win=4)
        return o

    def test_third_mission_continues_fourth_ends(self):
        for before in (2,3):
            o=self.modern_view('echo',wallet=2,pot=tokens(blue=5),score={'blue':before,'red':1})
            p=ready(o);p.choose_action(o)
            result=p.last_decision['details']['outcome_likelihoods']
            self.assertAlmostEqual(result['personal_win'],float(before==3))
            self.assertAlmostEqual(p.last_decision['details']['expected_income'],float(before==2))

    def test_zero_wallet_stowaway_can_plan_spending_vote_revenue(self):
        o=self.modern_view('stowaway',kind='vote',wallet=0,pot=tokens(blue=7),objective='spendthrift',crew=('p1','p2'),score={'blue':3,'red':0})
        p=ready(o);action=p.choose_action(o);d=p.last_decision['details']
        self.assertEqual(d['planned_ability'],{'color':'blue'})
        self.assertAlmostEqual(d['expected_wallet_after_effects'],0)
        self.assertTrue(action['approve'])
        # At commitment the income is already included in the wallet.
        o['phase']='contribute';o['action_spec']['type']='contribute';o['public']['players'][0]['wallet']=1
        p=ready(o);p.choose_action(o)
        self.assertAlmostEqual(p.last_decision['details']['expected_wallet_after_effects'],0)

    def test_vote_can_plan_new_revenue_but_pledge_cannot_spend_it_early(self):
        for phase in ('pledge','vote','contribute'):
            o=self.modern_view('scout',kind=phase,wallet=0,pot=tokens(blue=7),score={'blue':3,'red':0})
            p=ready(o);action=p.choose_action(o)
            self.assertEqual(p.last_decision['details']['planned_deposit']['blue'],int(phase=='vote'))
            if phase=='pledge': self.assertEqual(action['tokens'],tokens())

    def test_close_race_targets_three_opponent_wins_and_previous_policies_restore(self):
        o=self.modern_view('scout',objective='close_race',score={'blue':2,'red':2})
        p=ready(o);self.assertEqual(p.tactical_side(o),'red')
        o['public']['score']['red']=3;self.assertEqual(p.tactical_side(o),'blue')
        old=view('echo');p=ready(old);p.version='social.9';p.choose_action(old)
        restored=restore_policy(json.loads(json.dumps(p.snapshot())))
        self.assertEqual(restored.version,'social.9')
        self.assertEqual(p.choose_action(old),restored.choose_action(old))
        self.assertEqual(p.snapshot(),restored.snapshot())


if __name__=='__main__': unittest.main()
