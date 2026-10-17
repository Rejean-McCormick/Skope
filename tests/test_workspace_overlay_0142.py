"""Skope v0.14.2: one graph, its modal and the compact sidebar keep existing IDs."""
from pathlib import Path
from html.parser import HTMLParser
import unittest
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from skope import api

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'skope/static'

class Nesting(HTMLParser):
    def __init__(self):
        super().__init__();self.ancestors=[];self.seen={};self.unclosed=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:
            self.seen.setdefault(attrs['id'],[]).append((tag,tuple(self.ancestors)))
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.ancestors.append(tag)
    def handle_endtag(self, tag):
        if tag in self.ancestors:
            del self.ancestors[len(self.ancestors)-1-self.ancestors[::-1].index(tag):]

class WorkspaceOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(STATIC/'index.html').read_text(encoding='utf-8')
        cls.tree=Nesting();cls.tree.feed(cls.html)
    def test_graph_is_once_inside_modal(self):
        for ident in ('graph','density-controls','density-legend','density-lens','density-pick','pane-graph','pane-nodes','pane-candidates','pane-manifest'):
            self.assertEqual(len(self.tree.seen[ident]),1,ident)
            self.assertIn('dialog',self.tree.seen[ident][0][1],ident)
        self.assertEqual(self.tree.seen['scope-explorer-modal'][0][0],'dialog')
        self.assertEqual(self.tree.seen['graph'][0][0],'canvas')
        self.assertEqual(len(self.tree.seen),sum(len(i) for i in self.tree.seen.values()))
    def test_sidebar_configuration_preserves_controls(self):
        for ident in ('scope-config-panel','scope-acquisition-panel','author-roster-details','author-progress-details'):
            self.assertEqual(self.tree.seen[ident][0][0],'details')
        for ident in ('geo-mode-ui','depth','direction','props','threshold','minsupport','extra','large-start','extract-preflight','author-start'):
            self.assertEqual(len(self.tree.seen[ident]),1)
        self.assertIn('id="explorer-open"',self.html)
        self.assertIn('id="explorer-close"',self.html)
    def test_scripts_and_version_parity(self):
        self.assertIn('workspace-ui.css',self.html)
        self.assertIn('workspace-ui.js',self.html)
        self.assertIn("'/workspace-ui.js'",Path(api.__file__).read_text())
        self.assertIn("'/workspace-ui.css'",Path(api.__file__).read_text())
        self.assertEqual(api.SERVER_RELEASE,'0.14.4')
        self.assertIn("REQUIRED_RELEASE = '0.14.4'",(STATIC/'extraction.js').read_text())
    def test_http_serves_new_assets_without_broadening_file_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            App = type('WorkspaceUIApp', (api.App,), {'db_path':str(Path(tmp)/'wikidata.compact.sqlite')})
            srv=ThreadingHTTPServer(('127.0.0.1',0),App)
            worker=threading.Thread(target=srv.serve_forever,daemon=True)
            worker.start()
            try:
                base=f'http://127.0.0.1:{srv.server_port}'
                for resource,needle in [('/workspace-ui.js','explorer.showModal()'),('/workspace-ui.css','.scope-explorer-modal')]:
                    with urlopen(base+resource,timeout=4) as resp:
                        self.assertEqual(resp.status,200)
                        self.assertIn(needle,resp.read().decode())
                from urllib.error import HTTPError
                with self.assertRaises(HTTPError) as exc:
                    urlopen(base+'/random-file.txt',timeout=4)
                self.assertEqual(exc.exception.code,404)
            finally:
                srv.shutdown();srv.server_close()
    def test_modal_code_keeps_preview_explicit(self):
        js=(STATIC/'workspace-ui.js').read_text()
        self.assertIn('explorer.showModal()',js)
        self.assertIn('explorer.close()',js)
        self.assertIn("$('preview').click()",js)
        for prohibited in ('/api/extract/start','/api/large/start','/api/author-campaign/start'):
            self.assertNotIn(prohibited,js)

if __name__=='__main__':unittest.main()
