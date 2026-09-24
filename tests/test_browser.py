"""Small checks for the shared browser adapter and public site packaging."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from mission_game.browser import BrowserApp
from mission_game.session import Session
from mission_game.table_store import WebError
from scripts.build_site import ROOT, build, bundle_runtime


class BrowserSmoke(unittest.TestCase):
    def test_browser_commands_save_resume_and_validate_without_a_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            examples = root / 'examples'
            examples.mkdir()
            (examples / 'manifest.json').write_text('[]')
            app = BrowserApp(root / 'saves', examples)
            bootstrap = json.loads(app.request_json('/api/bootstrap', ''))
            self.assertEqual(bootstrap['status'], 200)
            self.assertEqual(bootstrap['data']['games'], [])
            created = json.loads(app.request_json('/api/games', '{"human_seat":0,"paced":true}'))
            game_id = created['data']['game']['id']
            path = f'/api/games/{game_id}'
            before = app.request(path + '/resume', True, {'paced': False})
            reloaded = BrowserApp(root / 'saves', examples)
            self.assertEqual(reloaded.request(path + '/state'), before)
            self.assertEqual(len(reloaded.catalog()), 1)
            self.assertEqual(json.loads(app.request_json('/api/games', 'null'))['status'], 400)
            self.assertEqual(json.loads(app.request_json(path + '/replay?designer=true', ''))['status'], 403)

    def test_featured_replays_are_explicit_completed_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            examples = root / 'examples'
            session = Session(17, game_id='featured-smoke')
            session.run()
            session.save(examples / '0/session.json')
            (examples / 'manifest.json').write_text(json.dumps([
                {'id': session.game.game_id, 'file': '0/session.json', 'title': 'Featured example', 'description': 'Review this game.'}]))
            (examples / 'model-outputs.jsonl').write_text('Unlisted run data must not ship')
            app = BrowserApp(root / 'saves', examples)
            self.assertEqual(app.catalog()[0]['title'], 'Featured example')
            self.assertTrue(app.catalog()[0]['bundled'])
            self.assertFalse(app.catalog()[0]['can_resume'])
            for operation, payload in [('resume', {}), ('advance', {'step_key': 'old'}), ('actions', {})]:
                with self.assertRaises(WebError):
                    app.request(f'/api/games/featured-smoke/{operation}', True, payload)
            replay = app.request('/api/games/featured-smoke/replay?designer=true&position=20&seat=p3')
            self.assertEqual(replay['game']['title'], 'Featured example')
            self.assertEqual(replay['position'], 20)
            self.assertEqual(replay['designer']['player_assessment']['player_id'], 'p3')
            (ROOT / 'dist').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT / 'dist') as destination, patch('scripts.build_site.bundle_runtime'):
                build(destination, examples_dir=examples)
                with ZipFile(Path(destination) / 'game.zip') as archive:
                    self.assertIn('examples/0/session.json', archive.namelist())
                    self.assertNotIn('examples/model-outputs.jsonl', archive.namelist())
                    self.assertEqual(json.loads(archive.read('examples/manifest.json'))[0]['id'], 'featured-smoke')

    def test_static_build_allowlist_and_subdirectory_assets(self):
        (ROOT / 'dist').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'dist') as destination, tempfile.TemporaryDirectory() as directory:
            examples = Path(directory)
            (examples / 'manifest.json').write_text('[]')
            with patch('scripts.build_site.bundle_runtime'):
                build(destination, examples_dir=examples)
            with ZipFile(Path(destination) / 'game.zip') as archive:
                names = archive.namelist()
                self.assertIn('mission_game/browser.py', names)
                self.assertIn('configs/development_abilities.json', names)
                self.assertEqual(json.loads(archive.read('examples/manifest.json')), [])
                self.assertTrue(all(n.startswith(('mission_game/', 'configs/', 'examples/')) for n in names))
                self.assertNotIn('mission_game/blind_runner.py', names)
                self.assertNotIn('mission_game/server.py', names)
            html = (Path(destination) / 'index.html').read_text()
            self.assertIn('src="./browser-client.js?v=', html)
            self.assertIn('src="./app.js?v=', html)
            self.assertIn('href="./style.css?v=', html)
            self.assertIn('Saved on this device', html)

    def test_build_refuses_unfinished_examples_and_unverified_runtime(self):
        (ROOT / 'dist').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'dist') as destination, tempfile.TemporaryDirectory() as directory:
            examples = Path(directory)
            Session(17).save(examples / 'unfinished.json')
            (examples / 'manifest.json').write_text('[{"file":"unfinished.json","title":"Unfinished"}]')
            with patch('scripts.build_site.bundle_runtime'), self.assertRaisesRegex(ValueError, 'completed'):
                build(destination, examples_dir=examples)
            (examples / 'pyodide.mjs').write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                bundle_runtime(Path(destination), examples)


if __name__ == '__main__':
    unittest.main()
