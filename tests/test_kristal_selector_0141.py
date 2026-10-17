"""Kristal selector: standalone HTTP contract, persistence and non-destructive switch."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from skope import api, author_campaign
from skope.kristal_registry import KristalRegistry
from test_integration import make_index

HOME = Path(__file__).resolve().parents[1]


def workspace(root, folder, slug):
    path = root / folder
    path.mkdir()
    (path / 'kristal.workspace.json').write_text(json.dumps({
        'format': 'kristal.local-workspace/3.2.0',
        'slug': slug, 'title': folder,
        'state_ref': 'urn:kristal:state:' + slug,
        'state_scope': {'domain': slug},
    }), encoding='utf-8')
    return path


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.locals = self.root / 'locals'
        self.locals.mkdir()
        self.botany = workspace(self.locals, 'Kristal-Botany', 'kristal-botany')
        self.catho = workspace(self.locals, 'A-Kristal-Catho', 'kristal-catho')
        self.state = self.root / 'config' / 'kristals.local.json'
        self.registry = KristalRegistry(locals_root=self.locals, state_file=self.state)

    def test_discovery_does_not_write_anything(self):
        before = (self.botany / 'kristal.workspace.json').read_bytes()
        roster = self.registry.catalog()
        self.assertEqual({x['slug'] for x in roster['entries']}, {'kristal-botany', 'kristal-catho'})
        self.assertIsNone(roster['active'])
        self.assertFalse(self.state.exists())
        self.assertEqual((self.botany / 'kristal.workspace.json').read_bytes(), before)

    def test_switch_persists_without_touching_workspaces(self):
        entries = self.registry.catalog()['entries']
        id_by_slug = {item['slug']: item['id'] for item in entries}
        self.assertEqual(self.registry.select(id_by_slug['kristal-catho'])['active']['slug'], 'kristal-catho')
        self.assertEqual(self.registry.select(id_by_slug['kristal-botany'])['active']['slug'], 'kristal-botany')
        another = KristalRegistry(locals_root=self.locals, state_file=self.state)
        self.assertEqual(another.snapshot()[1]['slug'], 'kristal-botany')
        self.assertIsNone(another.select('')['active'])
        self.assertIsNone(KristalRegistry(locals_root=self.locals, state_file=self.state).snapshot()[1])

    def test_explicit_path_and_validation(self):
        external_root = self.root / 'elsewhere'
        external_root.mkdir()
        econ = workspace(external_root, 'Economics', 'kristal-economics')
        out = self.registry.add(str(econ))
        self.assertEqual(out['active']['slug'], 'kristal-economics')
        self.assertIn(str(econ), self.state.read_text(encoding='utf-8'))
        another = KristalRegistry(locals_root=self.locals, state_file=self.state)
        self.assertEqual(len(another.catalog()['entries']), 3)
        with self.assertRaisesRegex(ValueError, 'kristal.workspace.json'):
            self.registry.add(str(self.root))
        with self.assertRaisesRegex(ValueError, 'invalid|Invalid|Select'):
            self.registry.select('does-not-exist')

    def test_http_switch_in_running_server_and_no_automatic_campaign(self):
        index = self.root / 'test.sqlite'
        make_index(index)
        app = type('SelectorApp', (api.App,), {'db_path': str(index)})
        server = ThreadingHTTPServer(('127.0.0.1', 0), app)
        server.kristal_registry = self.registry
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'

        def get(endpoint):
            with urlopen(base + endpoint) as resp:
                return json.load(resp)

        def post(endpoint, payload, origin=None):
            data = json.dumps(payload).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            if origin: headers['Origin'] = origin
            with urlopen(Request(base + endpoint, data=data, headers=headers)) as resp:
                return json.load(resp)

        with patch.object(author_campaign, 'start', side_effect=AssertionError('unexpected campaign start')):
            first = get('/api/kristals')
            self.assertIsNone(first['active'])
            self.assertIsNone(get('/api/config')['target_kristal'])
            target = next(x for x in first['entries'] if x['slug'] == 'kristal-catho')
            new = post('/api/kristals/select', {'id': target['id']})
            self.assertEqual(new['active']['slug'], 'kristal-catho')
            self.assertEqual(get('/api/config')['target_kristal']['slug'], 'kristal-catho')
            with patch.object(author_campaign, 'preview', return_value={'workspace': 'ok'}) as preview:
                get('/api/author-campaign/preview?profile=catho-recognised-authors')
                self.assertEqual(preview.call_args.args[0], str(self.catho.resolve()))
            blank = post('/api/kristals/select', {'id': ''})
            self.assertIsNone(blank['active'])
            self.assertIsNone(get('/api/config')['target_kristal'])
            with self.assertRaises(HTTPError) as denied:
                post('/api/kristals/select', {'id': target['id']}, origin='http://attacker.example')
            self.assertEqual(denied.exception.code, 403)
            with self.assertRaises(HTTPError) as bad:
                post('/api/kristals/add', {'path': str(self.root)})
            self.assertEqual(bad.exception.code, 400)

    def test_static_ui_preserves_density_and_single_launcher(self):
        markup = (HOME / 'skope/static/index.html').read_text(encoding='utf-8')
        js = (HOME / 'skope/static/app.js').read_text(encoding='utf-8')
        for id_ in ('kristal-select', 'kristal-activate', 'kristal-refresh', 'kristal-add'):
            self.assertIn(f'id="{id_}"', markup)
            self.assertIn(f"el('{id_}')", js)
        self.assertTrue((HOME / 'skope/static/density.js').is_file())
        self.assertIn('density.js', markup)
        self.assertTrue((HOME / 'Start_Skope.cmd').exists())
        self.assertFalse((HOME / 'Start_Skope_Catho.cmd').exists())


if __name__ == '__main__':
    unittest.main()
