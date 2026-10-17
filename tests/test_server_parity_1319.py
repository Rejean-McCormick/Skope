"""Regression: stale server detection and introspection of loaded, real modules."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch
from skope import extraction,api

class ServerParityTests(unittest.TestCase):
    def test_in_process_route_matches_loaded_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            cls=type('ReaderApp',(api.App,),{'db_path':str(Path(tmp)/'30_working/wikidata/wikidata.compact.sqlite')})
            server=ThreadingHTTPServer(('127.0.0.1',0),cls)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            addr='http://127.0.0.1:'+str(server.server_port)
            with urlopen(addr+'/api/diagnostics/reader') as r:
                self.assertEqual(r.status,200)
                result=json.load(r)
            self.assertEqual(result['server_release'],'0.14.4')
            self.assertEqual(result['process_id'],os.getpid())
            self.assertTrue(result['server_api_source_unchanged'])
            self.assertTrue(result['server_api_module'].endswith('skope/api.py'))
            self.assertTrue(result['scope_common_matches_repo'])
            self.assertTrue(result['fastio_matches_repo'])
            self.assertEqual(result['python'],__import__('sys').executable)
            with urlopen(addr+'/extraction.js') as r:
                source=r.read().decode()
                self.assertIn("REQUIRED_RELEASE = '0.14.4'",source)
                self.assertIn('/api/diagnostics/reader',source)
                self.assertIn('OUTDATED SERVER',source)
    def test_import_cache_mismatch_is_observable_without_mutating_cache(self):
        common=extraction._module()
        with patch.object(common.fastio,'_INDEXED_BZIP2',None), \
             patch.object(extraction.importlib,'import_module',return_value=type('Reader',(),{'__file__':'C:/python/indexed_bzip2.pyd'})()):
            # Reader import succeeds but fastio cached an earlier failure.
            # Test real directory layout expectation, but leave absent dump as a no-op.
            with tempfile.TemporaryDirectory() as temp:
                d=Path(temp)/'30_working/wikidata';d.mkdir(parents=True)
                diag=extraction.runtime_reader_diagnosis(d/'wikidata.compact.sqlite')
                self.assertTrue(diag['reader_importable'])
                self.assertFalse(diag['reader_cached'])
                self.assertIsNone(common.fastio._INDEXED_BZIP2)
    def test_preflight_still_fails_closed_missing_evidence(self):
        # Endpoint must not itself bypass source verification.
        diag=extraction.runtime_reader_diagnosis(Path('/not-a-real-root/30_working/wikidata/missing.sqlite'))
        self.assertNotEqual(diag['fast_index_ready'],True)
    def test_origin_not_broadened(self):
        self.assertIn('/api/diagnostics/reader',Path(api.__file__).read_text())
        self.assertEqual(api.SERVER_RELEASE,'0.14.4')

if __name__=='__main__':unittest.main()
