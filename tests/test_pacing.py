"""Live steps preserve sealed-action privacy and resumable engine decisions."""
import json
import tempfile
import unittest
from pathlib import Path
from mission_game.config import GameConfig
from mission_game.policy import RandomLegalPolicy
from mission_game.server import TableStore, WebError
from mission_game.session import Session


class PacingTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)

    def table(self,sub='paced'):
        root=self.root/sub;root.mkdir()
        s=Session(11,GameConfig.abilities(max_attempts=2),human_seat=2,game_id='paced-test')
        path=root/'session.json';s.save(path)
        return TableStore(root),s,path

    def next_human(self,store,data):
        for _ in range(400):
            if not data['can_advance']: return data
            before=data['observation']
            data=store.step('paced-test',{'step_key':data['step_key']})
            events=data['observation']['history'][len(before['history']):]
            self.assertLessEqual(sum(e['type']=='vote' for e in events),1)
        self.fail('Live pacing did not reach a player decision')

    def test_paced_and_instant_tables_make_identical_decisions_and_replay(self):
        paced,_,_=self.table('paced');fast,_,_=self.table('fast')
        p=self.next_human(paced,paced.resume('paced-test',paced=True))
        f=fast.resume('paced-test')
        player=RandomLegalPolicy(999,2)
        while p['observation']['phase']!='game_over':
            self.assertEqual(p['observation'],f['observation'])
            o=p['observation'];action=player.choose_action(o)
            payload={'request_id':o['request_id'],'revision':o['revision'],'action':action}
            p=paced.submit('paced-test',{**payload,'paced':True})
            p=self.next_human(paced,p)
            f=fast.submit('paced-test',payload)
        ps,_=paced.load('paced-test');fs,_=fast.load('paced-test')
        self.assertEqual(ps.snapshot(),fs.snapshot())
        self.assertEqual(ps.replay().snapshot(),ps.game.snapshot())

    def test_reload_does_not_advance_and_stale_step_cannot_advance_again(self):
        store,s,path=self.table()
        first=store.resume('paced-test',paced=True)
        self.assertEqual(json.loads(json.dumps(s.snapshot())),json.loads(json.dumps(Session.load(path).snapshot())))
        self.assertTrue(first['can_advance'])
        next_state=store.step('paced-test',{'step_key':first['step_key']})
        saved=path.read_bytes()
        self.assertEqual(TableStore(path.parent).state('paced-test')['observation'],next_state['observation'])
        with self.assertRaises(WebError): store.step('paced-test',{'step_key':first['step_key']})
        self.assertEqual(path.read_bytes(),saved)

    def test_waits_for_human_and_human_submission_does_not_run_other_seats(self):
        store,_,path=self.table()
        ready=self.next_human(store,store.state('paced-test'))
        before=Session.load(path)
        same=store.step('paced-test',{'step_key':ready['step_key']})
        self.assertEqual(same['observation'],ready['observation'])
        self.assertEqual(before.snapshot(),Session.load(path).snapshot())
        o=ready['observation'];action=RandomLegalPolicy(88,2).choose_action(o)
        response=store.submit('paced-test',{'request_id':o['request_id'],'revision':o['revision'],'action':action,'paced':True})
        after=Session.load(path)
        self.assertEqual(len(after.game.action_log),len(before.game.action_log)+1)
        self.assertEqual(before.bot_decisions,after.bot_decisions)
        self.assertEqual(response['observation'],after.game.observe('p2'))

    def test_bad_pacing_requests_do_not_change_game(self):
        store,_,path=self.table();before=path.read_bytes()
        for payload in ({},{'step_key':1},{'revision':0},{'step_key':'0','seat':'p1'}):
            with self.assertRaises(WebError):store.step('paced-test',payload)
        self.assertEqual(before,path.read_bytes())


if __name__=='__main__':unittest.main()
