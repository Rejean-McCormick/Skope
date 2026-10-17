"""The catalog discovers installed JSON dynamically, without any disk/data writes."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch

from skope import scope_profiles, api, massive, extraction


def simple(root='Q192154', **metadata):
    return {'title':'My user scope', 'target_slug':'kristal-botany', **metadata,
            'recipe': {'root':root, 'direction':'in', 'allowed_properties':['P171'],
                       'default_depth':7, 'max_entities':0,
                       'convergence':{'threshold_percent':14.6,'min_support':8,'extra_depth':0,'include':[]},
                       'geography': {'mode':'annotate','region_qid':'Q49','priority_qid':'Q16'}}}


class CatalogDropInTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        patcher=patch.object(scope_profiles,'CONFIG',self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def put(self, name, obj):
        (self.folder/name).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')

    def test_discovery_after_creation_rename_and_removal(self):
        self.assertEqual(scope_profiles.catalog()['profiles'], [])
        self.put('fougeres.json',simple())
        c=scope_profiles.catalog()
        self.assertEqual(c['count'],1)
        self.assertEqual(c['profiles'][0]['source_file'],'fougeres.json')
        self.assertEqual(c['profiles'][0]['passes'][0]['recipe']['default_depth'],7)
        (self.folder/'fougeres.json').rename(self.folder/'ferns.json')
        self.assertEqual(scope_profiles.catalog()['profiles'][0]['id'],'ferns')
        (self.folder/'ferns.json').unlink()
        self.assertEqual(scope_profiles.catalog()['count'],0)

    def test_campaign_and_simple_recipe_coexist(self):
        self.put('campaign.json',{'format':'skope.scope-campaign/1.0','id':'campaign',
                                 'title':'Two passes','target_slug':'kristal-botany',
                                 'passes':[{'id':'first','title':'First','intent':'Take QIDs',
                                            'risk':'May be big','recipe':simple()['recipe']},
                                           {'id':'second','title':'Second','intent':'Take more QIDs',
                                            'risk':'May be bigger','recipe':simple('Q42')['recipe']}]})
        self.put('quick.json',simple())
        c=scope_profiles.catalog()
        self.assertEqual((c['count'],c['pass_count']), (2,3))
        self.assertEqual(c['errors'],[])

    def test_raw_recipe_without_metadata_is_generic(self):
        self.put('general.json',simple()['recipe'])
        x=scope_profiles.catalog()['profiles'][0]
        self.assertIsNone(x['target_slug'])
        self.assertEqual(x['passes'][0]['recipe']['root'],'Q192154')
        self.assertEqual(x['source_kind'],'recipe')

    def test_invalid_json_is_reported_and_does_not_hide_good(self):
        self.put('valid.json',simple())
        (self.folder/'broken.json').write_text('{ "foo": ',encoding='utf-8')
        c=scope_profiles.catalog()
        self.assertEqual(c['count'],1)
        self.assertEqual(c['errors'][0]['file'],'broken.json')
        self.assertEqual([p['id'] for p in scope_profiles.all_profiles()],['valid'])
        self.assertEqual(c['scanned_files'],2)

    def test_duplicate_id_only_rejects_second(self):
        self.put('a.json',{'id':'identical',**simple()})
        self.put('b.json',{'id':'identical',**simple()})
        c=scope_profiles.catalog()
        self.assertEqual(c['count'],1)
        self.assertIn('Duplicate profile id',c['errors'][0]['error'])

    def test_invalid_rules_and_unsafe_actions_rejected(self):
        self.put('good.json',simple())
        for name, payload in {
            'write.json':{**simple(), 'safety':{'write_kristal_canon':True}},
            'execute.json':{**simple(), 'safety':{'auto_run':True}},
            'noqids.json':{**simple(), 'safety':{'collect_qid_only':False}},
            'both.json':{**simple(), 'recipe':{**simple()['recipe'],'direction':'both'}},
            'wildcard.json':{**simple(), 'recipe':{**simple()['recipe'],'allowed_properties':[]}},
            'documented.json':{**simple(), 'recipe':{**simple()['recipe'],'geography':{'mode':'documented_only', 'region_qid':'Q49','priority_qid':'Q16'}}},
            'convergence.json':{**simple(), 'recipe':{**simple()['recipe'],'convergence':{'include':['Q42']}}},
        }.items():
            self.put(name,payload)
        c=scope_profiles.catalog()
        self.assertEqual(c['count'],1)
        self.assertEqual(len(c['errors']),7)
        self.assertEqual(c['pass_count'],1)

    def test_symlink_not_followed_and_oversize_rejected(self):
        self.put('valid.json',simple())
        (self.folder/'large.json').write_text(' '*(scope_profiles.MAX_BYTES+1))
        self.assertEqual(scope_profiles.catalog()['count'],1)
        self.assertEqual(len(scope_profiles.catalog()['errors']),1)
        try:
            (self.folder/'shortcut.json').symlink_to(self.folder/'valid.json')
        except (OSError, NotImplementedError):
            return
        self.assertEqual(scope_profiles.catalog()['count'],1)
        self.assertEqual(len(scope_profiles.catalog()['errors']),2)

    def test_missing_dir_reports_error(self):
        with patch.object(scope_profiles,'CONFIG',self.folder/'missing'):
            c=scope_profiles.catalog()
            self.assertEqual(c['count'],0)
            self.assertEqual(len(c['errors']),1)

    def test_json_duplicates_and_nan_not_accepted(self):
        (self.folder/'duplicate.json').write_text('{"root":"Q1","root":"Q2","direction":"in","allowed_properties":["P171"]}')
        (self.folder/'nan.json').write_text('{"root":"Q1","direction":"in","allowed_properties":["P171"],"max_entities":NaN}')
        self.assertEqual(len(scope_profiles.catalog()['errors']),2)

    def test_http_refresh_without_restart_or_job_start(self):
        cls=type('CatalogTestApp',(api.App,),{'db_path':'/nonexistent/index.sqlite'})
        srv=ThreadingHTTPServer(('127.0.0.1',0),cls)
        t=threading.Thread(target=srv.serve_forever,daemon=True)
        t.start()
        self.addCleanup(t.join,3)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        url=f'http://127.0.0.1:{srv.server_port}/api/scope-profiles/catalog'
        with patch.object(massive,'start',side_effect=AssertionError('NO JOB')), \
             patch.object(extraction,'start',side_effect=AssertionError('NO EXTRACTION')):
            with urlopen(url) as r:
                self.assertEqual(json.load(r)['count'],0)
            self.put('later.json',simple())
            with urlopen(url) as r:
                result=json.load(r)
                self.assertEqual(result['count'],1)
                self.assertEqual(result['profiles'][0]['id'],'later')
            with urlopen(f'http://127.0.0.1:{srv.server_port}/api/scope-profiles') as r:
                self.assertEqual(len(json.load(r)),1)

    def test_ui_manual_and_automatic_refresh_no_job_start(self):
        js=(Path(api.__file__).parent/'static/app.js').read_text()
        html=(Path(api.__file__).parent/'static/index.html').read_text()
        self.assertIn("'/api/scope-profiles/catalog'",js)
        self.assertIn("el('scope-campaign-refresh').addEventListener('click'",js)
        self.assertIn('setInterval(()=>{if(!document.hidden)refreshScopeCampaigns();},30000)',js)
        self.assertIn('liveTargetSlug && profile.target_slug && profile.target_slug!==liveTargetSlug',js)
        self.assertIn('scope-campaign-errors',html)
        self.assertIn('scope-campaign-copy-folder',html)

if __name__=='__main__':
    unittest.main()
