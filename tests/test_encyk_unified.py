"""Skope/EncyK integration smoke tests; no D: dataset needed."""
import json, threading, urllib.request, urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest import TestCase
from unittest.mock import patch
from skope import api, encyk_fusion

class UnifiedTests(TestCase):
    def test_canonical_boundaries(self):
        state=encyk_fusion.status()
        self.assertTrue(state['bridge_present'])
        self.assertTrue(state['engine_present'])
        self.assertTrue(state['source_handoff_contract_present'])
        self.assertFalse(state['canonical_writes_enabled'])
        self.assertEqual(state['candidate'],'skope-1.0.0-rc.1')

    def test_explicit_confirmation_and_qid_format(self):
        with self.assertRaises(ValueError): encyk_fusion.pull_completed_job('a'*32)
        with self.assertRaises(ValueError): encyk_fusion.pull_completed_job('Q42',confirmed=True)

    def test_local_get_status_and_refusal_of_unconfirmed_post(self):
        handler=type('TestSkope',(api.App,),{'db_path': '/missing.index.sqlite'})
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        url=f'http://127.0.0.1:{server.server_port}'
        with urllib.request.urlopen(url+'/api/encyk/status',timeout=5) as stream:
            data=json.load(stream)
        self.assertTrue(data['engine_present'])
        req=urllib.request.Request(url+'/api/encyk/pull',data=json.dumps({'job':'a'*32,'confirmed':False}).encode(),headers={'Content-Type':'application/json','Origin':url},method='POST')
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req,timeout=5)
        self.assertEqual(e.exception.code,400)
        self.assertEqual(json.load(e.exception)['error'],'explicit_confirmation_required')
        req2=urllib.request.Request(url+'/api/encyk/pull',data=json.dumps({'job':'a'*32,'confirmed':True}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with self.assertRaises(urllib.error.HTTPError) as e2:
            urllib.request.urlopen(req2,timeout=5)
        self.assertEqual(e2.exception.code,403)
        for route in ('/encyk-intake.js','/encyk-intake.css'):
            with urllib.request.urlopen(url+route,timeout=5) as stream:
                self.assertEqual(stream.status,200)
                self.assertTrue(stream.read())
