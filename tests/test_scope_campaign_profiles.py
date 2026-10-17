"""Release 0.13.20: genuine campaign profiles, read-only HTTP, correct Kristal targets."""
import json
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch
from skope import scope_profiles, api, massive, extraction

class CampaignScopeProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaigns=scope_profiles.all_profiles()
        cls.by_id={c['id']:c for c in cls.campaigns}

    def test_three_baseline_kristals_present(self):
        self.assertTrue({'botany','economics','catho'}.issubset(self.by_id))
        self.assertEqual({c['target_slug'] for c in self.campaigns},
                         {'kristal-botany','kristal-economics','kristal-catho'})
        self.assertEqual(self.by_id['economics']['state_ref'],'urn:kristal:state:kristal-economics')
        self.assertEqual(self.by_id['botany']['state_ref'],'urn:kristal:state:botany')
        self.assertEqual(self.by_id['catho']['state_ref'],'urn:kristal:state:catho')

    def test_botany_follows_P171_and_preserves_canada_first(self):
        a=self.by_id['botany']['passes']
        self.assertEqual([x['recipe']['default_depth'] for x in a],[7,8])
        self.assertTrue(all(x['recipe']['root']=='Q192154' for x in a))
        self.assertTrue(all(x['recipe']['allowed_properties']==['P171'] for x in a))
        self.assertEqual(a[0]['recipe']['geography']['priority_qid'],'Q16')
        self.assertEqual(a[0]['recipe']['geography']['region_qid'],'Q49')
        self.assertEqual(a[0]['recipe']['geography']['mode'],'annotate')

    def test_economics_separates_concept_classes_from_people(self):
        a=self.by_id['economics']['passes']
        self.assertEqual([(x['recipe']['root'],x['recipe']['allowed_properties'][0]) for x in a],
                         [('Q8134','P279'),('Q188094','P106')])

    def test_catho_preserves_doctrine_institution_people_distinction(self):
        a=self.by_id['catho']['passes']
        self.assertEqual([(x['recipe']['root'],x['recipe']['allowed_properties'][0]) for x in a],
                         [('Q1841','P279'),('Q9592','P361'),('Q9592','P140')])
        self.assertEqual(a[-1]['recipe']['max_entities'],25000)
        self.assertTrue(all(x['recipe']['geography']['mode']=='off' for x in a))

    def test_all_seven_passes_batch_safe(self):
        self.assertGreaterEqual(sum(len(c['passes']) for c in self.campaigns),7)
        for campaign in self.campaigns:
            self.assertFalse(campaign['safety']['auto_run'])
            for entry in campaign['passes']:
                r=entry['recipe']
                self.assertIn(r['direction'],('in','out'))
                self.assertTrue(r['allowed_properties'])
                self.assertFalse(r['convergence']['include'])
                self.assertNotEqual(r['geography']['mode'],'documented_only')
                self.assertEqual(r['convergence']['extra_depth'],0)

    def test_reject_modified_invalid_profile(self):
        original=scope_profiles.CONFIG
        # No need to touch actual installed profile files.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)
            for p in original.glob('*.json'):
                (dest/p.name).write_bytes(p.read_bytes())
            data=json.loads((dest/'economics.json').read_text())
            data['passes'][0]['recipe']['direction']='both'
            (dest/'economics.json').write_text(json.dumps(data))
            with patch.object(scope_profiles,'CONFIG',dest):
                results=scope_profiles.catalog()
                self.assertEqual({c['id'] for c in results['profiles']}, set(self.by_id)-{'economics'})
                self.assertIn('Batch QID collection',results['errors'][0]['error'])

    def test_http_returns_validated_profiles_without_any_job_start(self):
        cls=type('ScopeTestServer',(api.App,),{'db_path':'/nonexistent/index.sqlite'})
        server=ThreadingHTTPServer(('127.0.0.1',0),cls)
        th=threading.Thread(target=server.serve_forever,daemon=True)
        th.start()
        try:
            with patch.object(massive,'start',side_effect=AssertionError('MUST NOT START')), \
                 patch.object(extraction,'start',side_effect=AssertionError('MUST NOT EXTRACT')):
                with urlopen('http://127.0.0.1:'+str(server.server_port)+'/api/scope-profiles') as response:
                    self.assertEqual(response.status,200)
                    got=json.load(response)
                    self.assertEqual({x['id'] for x in got},set(self.by_id))
        finally:
            server.shutdown();server.server_close();th.join(timeout=3)

    def test_ui_click_only_and_target_guard(self):
        app=(Path(api.__file__).parent/'static/app.js').read_text()
        html=(Path(api.__file__).parent/'static/index.html').read_text()
        self.assertIn("el('scope-campaign-apply').addEventListener('click',applyScopeCampaign)",app)
        self.assertIn('profile.target_slug!==liveTargetSlug',app)
        self.assertIn('loadedScopeCampaign.target_slug!==liveTargetSlug',app)
        self.assertIn('scope-campaign-select',html)
        self.assertIn('scope-campaign-pass',html)
        self.assertIn('skope-release-label',html)
        self.assertIn('activeLargeJob=null',app)

    def test_no_trusted_sources_or_canon_mutated(self):
        src=(Path(api.__file__).parent/'scope_profiles.py').read_text()
        self.assertNotIn('connect(',src)
        self.assertNotIn('subprocess',src)
        self.assertNotIn('write_text(',src)
        self.assertNotIn('shutil',src)

if __name__=='__main__':unittest.main()
