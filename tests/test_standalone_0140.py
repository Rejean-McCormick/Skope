"""Standalone release acceptance tests: no EncyK Python checkout required."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from unittest.mock import patch

from skope import api, fastio, scope_common, scope_profiles, extraction
from test_integration import make_index

HOME = Path(__file__).resolve().parents[1]


def recipe(root='Q192154'):
    return {'root': root, 'default_depth': 4, 'direction': 'in',
            'allowed_properties': ['P171'], 'branches': {}, 'max_entities': 0,
            'convergence': {'threshold_percent': 12, 'min_support': 4,
                            'extra_depth': 0, 'include': []},
            'geography': {'mode': 'off'}}


class StandaloneAcceptance(unittest.TestCase):
    def test_code_ownership_is_standalone(self):
        self.assertEqual(api.SERVER_RELEASE, '0.14.4')
        self.assertEqual(extraction._module(), scope_common)
        self.assertIs(scope_common.fastio, fastio)
        self.assertEqual(scope_profiles.CONFIG, HOME / 'scopes')
        self.assertEqual(extraction.TOOL, HOME)
        self.assertFalse((HOME / '00_system').exists())
        self.assertFalse((HOME / 'legacy_fast.py').exists())
        self.assertTrue((HOME / 'Start_Skope.cmd').is_file())

    def test_builtin_profiles_are_available_and_do_not_need_active_kristal(self):
        c = scope_profiles.catalog()
        self.assertFalse(c['errors'], c['errors'])
        self.assertEqual(c['count'], 5)
        self.assertEqual({p['id'] for p in c['profiles']},
                         {'botany', 'economics', 'catho',
                          'catho-authors-persons', 'catho-recognised-authors'})

    def test_generic_multi_pass_catalog_accepts_no_target(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            profile = {'format': scope_profiles.FORMAT, 'id': 'science', 'title': 'Science',
                       'passes': [{'id': 'taxon', 'title': 'Plants', 'recipe': recipe()}]}
            (folder / 'science.json').write_text(json.dumps(profile), encoding='utf8')
            with patch.object(scope_profiles, 'CONFIG', folder):
                c = scope_profiles.catalog()
            self.assertEqual(c['count'], 1, c['errors'])
            self.assertIsNone(c['profiles'][0]['target_slug'])

    def test_rescan_good_and_bad_scope_without_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / 'bad.json').write_text('{bad json', encoding='utf8')
            (folder / 'ok.json').write_text(json.dumps({'title': 'Manual', 'recipe': recipe()}), encoding='utf8')
            with patch.object(scope_profiles, 'CONFIG', folder):
                first = scope_profiles.catalog()
                self.assertEqual(first['count'], 1)
                self.assertEqual(len(first['errors']), 1)
                (folder / 'new.json').write_text(json.dumps({'title': 'New', 'recipe': recipe('Q42')}), encoding='utf8')
                second = scope_profiles.catalog()
                self.assertEqual(second['count'], 2)
                self.assertEqual(len(second['errors']), 1)

    def test_block_dangerous_ai_recipe(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            payload = {'format': scope_profiles.FORMAT, 'id': 'unsafe', 'title': 'Unsafe',
                       'safety': {'auto_run': True},
                       'passes': [{'id': 'p', 'recipe': recipe()}]}
            (folder / 'unsafe.json').write_text(json.dumps(payload), encoding='utf8')
            with patch.object(scope_profiles, 'CONFIG', folder):
                c = scope_profiles.catalog()
            self.assertEqual(c['count'], 0)
            self.assertIn('Unsafe', c['errors'][0]['error'])

    def test_sidecar_probe_uses_original_data_volume_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            volume = Path(tmp)
            dump = volume / '10_sources/wikidata/dumps/current/wikidata.json.bz2'
            dump.parent.mkdir(parents=True)
            dump.write_bytes(b'fixture-no-read')
            sha1 = 'c'*40
            manifest = volume / '20_evidence/manifests/wikidata-dump-verified.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'sha1': sha1, 'verified': True,
                                            'file': dump.name}), encoding='utf8')
            fast = volume / '30_working/wikidata-fast' / ('sha1-' + sha1)
            fast.mkdir(parents=True)
            (fast / 'qid-locator.bin').write_bytes(b'locator')
            with patch.object(fastio, 'backend_capabilities', return_value={'backend': 'indexed_bzip2', 'random_access': True}):
                ok, info = scope_common.fast_access_status(volume, dump)
                self.assertTrue(ok)
                self.assertFalse(info['random_access_ready'])
                (fast / 'compression.bz2blocks.pkl').write_bytes(b'fixture')
                ok, info = scope_common.fast_access_status(volume, dump)
                self.assertTrue(info['random_access_ready'])
                self.assertEqual(info['locator_path'], str(fast / 'qid-locator.bin'))

    def test_sidecar_probe_never_treats_missing_reader_as_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            volume = Path(tmp)
            dump = volume / 'test.json.bz2'
            dump.write_bytes(b'fixture')
            with patch.object(fastio, 'backend_capabilities', return_value={'backend': 'bz2-stdlib', 'random_access': False}):
                _, info = scope_common.fast_access_status(volume, dump)
            self.assertFalse(info['random_access_ready'])

    def test_live_http_catalog_and_static_in_same_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / 'index.sqlite'
            make_index(index)
            app = type('StandaloneHTTPApp', (api.App,), {'db_path': str(index),
                       'starting_recipe': None, 'arketype_guidance': None,
                       'target_kristal': None, 'kristal_folder': None})
            srv = ThreadingHTTPServer(('127.0.0.1', 0), app)
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            try:
                url = 'http://127.0.0.1:' + str(srv.server_port)
                with urlopen(url + '/api/scope-profiles/catalog') as result:
                    cat = json.load(result)
                self.assertEqual(cat['count'], 5)
                with urlopen(url + '/api/config') as result:
                    config = json.load(result)
                self.assertIsNone(config['target_kristal'])
                self.assertEqual(config['scope_folder'], str(HOME / 'scopes'))
                with urlopen(url + '/density.js') as result:
                    self.assertIn(b'SkopeDensity', result.read())
                with urlopen(url + '/index.html') as result:
                    self.assertIn(b'scope-campaign-open-folder', result.read())
                payload = Request(url + '/api/scopes/open-folder', data=b'{}',
                                  headers={'Content-Type': 'application/json'}, method='POST')
                if __import__('os').name != 'nt':
                    with self.assertRaises(HTTPError) as err:
                        urlopen(payload)
                    self.assertEqual(err.exception.code, 400)
            finally:
                srv.shutdown()
                srv.server_close()
                thread.join(timeout=3)

    def test_cli_meta_runs_from_standalone_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / 'index.sqlite'
            make_index(index)
            result = subprocess.run([sys.executable, '-B', '-m', 'skope', 'meta', '--db', str(index)],
                                    cwd=HOME, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            details = json.loads(result.stdout)
            self.assertEqual(details['evidence_available'], 'false')

    def test_launcher_cannot_silently_use_python_314(self):
        source = (HOME / 'Start_Skope.cmd').read_text(encoding='utf8')
        self.assertIn('Python312', source)
        self.assertNotIn('pythonw', source)
        self.assertIn('%~dp0', source)
        self.assertIn('wikidata.compact.sqlite', source)


if __name__ == '__main__':
    unittest.main()
