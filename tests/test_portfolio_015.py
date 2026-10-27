"""Skope native portfolio tests; no network and no Wikidata dump required."""
import csv
import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from skope import portfolio
from test_integration import make_index


def js(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True)


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'v11.zip'
        def dictionary(name, namespace, entries,language='fr'):
            return {'artifact_type':'kristal_curated_dictionary','namespace_id':namespace,
                    'language':language,'entries':[{'semantic_id':sid,'preferred_term':label} for sid,label in entries]}
        with zipfile.ZipFile(self.source,'w') as z:
            z.writestr('Kristal-Botany/.kristal/v11/dik.project.json','{}')
            z.writestr('Kristal-Other/.kristal/v11/dik.project.json','{}')
            z.writestr('Kristal-Botany/.kristal/v11/dictionaries/legacy-fr.json',js(dictionary('a','kristal:botany',[
                ('KQ100','Embryophyta'),('KQ101','MiniDemo 1')])))
            z.writestr('Kristal-Other/.kristal/v11/dictionaries/legacy-fr.json',js(dictionary('a','kristal:other',[
                ('KQ100','Embryophyta')])))
            z.writestr('Kristal-Botany/.kristal/v11/dictionaries/metadata-fr.json',js(dictionary('b','kristal:botany',[
                ('KP20','Meta field')])))
        self.work=self.root/'state'
        self.index=self.root/'index.sqlite'
        make_index(self.index)

    def _discover(self):
        portfolio.inventory(self.source,self.work)
        return portfolio.discover(self.work,self.index,max_queries=100,limit=8)

    def _approve(self):
        self._discover()
        csvpath=self.root/'review.csv'
        portfolio.export_review(self.work,csvpath)
        rows=list(csv.DictReader(csvpath.open(encoding='utf-8-sig',newline='')))
        for row in rows:
            if row['candidate_external_id']=='Q900000000':
                row.update(review_decision='confirm',reviewer='reviewer1',
                           documentary_evidence='document:an-independent-analysis',reason='Verified in domain')
        with csvpath.open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=portfolio.REVIEW_FIELDS)
            writer.writeheader();writer.writerows(rows)
        return portfolio.approve_review(self.work,csvpath)

    def test_real_native_inventory_and_idempotent_rerun(self):
        a=portfolio.inventory(self.source,self.work)
        self.assertEqual(a['projects'],2)
        self.assertEqual(a['lexemes'],3)
        self.assertEqual(portfolio.inventory(self.source,self.work),a)
        self.assertEqual(a['distinct_concepts'],3) # scoped namespace, not just the bare KQ
        self.assertEqual(a['approved_identity_proposals'],0)
        self.assertEqual(a['canonical_write_authorized'],False)

    def test_changed_source_cannot_mutate_existing_run(self):
        portfolio.inventory(self.source,self.work)
        with self.assertRaisesRegex(ValueError,'source/options changed'):
            portfolio.inventory(self.source,self.work,include_metadata=True)

    def test_bounded_discovery_and_resume(self):
        portfolio.inventory(self.source,self.work)
        first=portfolio.discover(self.work,self.index,max_queries=1)
        self.assertEqual(first['cached_queries'],1)
        second=portfolio.discover(self.work,self.index,max_queries=1)
        self.assertEqual(second['cached_queries'],2)
        third=portfolio.discover(self.work,self.index,max_queries=10)
        self.assertEqual(third['new_queries'],0)
        other=self.root/'copy.sqlite'
        other.write_bytes(self.index.read_bytes())
        with self.assertRaisesRegex(ValueError,'snapshot changed'):
            portfolio.discover(self.work,other,max_queries=1)

    def test_unverified_candidates_not_approved(self):
        self._discover()
        path=self.root/'review.csv'
        report=portfolio.export_review(self.work,path)
        self.assertGreater(report['rows'],0)
        self.assertEqual(portfolio.status(self.work)['approved_identity_proposals'],0)
        rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
        self.assertTrue(all(x['review_decision']=='unverified' for x in rows))

    def test_review_requires_reasons_and_listed_external_id(self):
        self._discover()
        p=self.root/'review.csv'
        portfolio.export_review(self.work,p)
        rows=list(csv.DictReader(p.open(encoding='utf-8-sig')))
        rows[0]['review_decision']='confirm'
        rows[0]['candidate_external_id']='Q123456789'
        rows[0]['reviewer']='x';rows[0]['documentary_evidence']='e';rows[0]['reason']='r'
        with p.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=portfolio.REVIEW_FIELDS);w.writeheader();w.writerows(rows)
        with self.assertRaisesRegex(ValueError,'Unlisted ID'):
            portfolio.approve_review(self.work,p)
        self.assertEqual(portfolio.status(self.work)['approved_identity_proposals'],0)

    def test_review_approves_scoped_mappings_and_emits_sorted_qid_inventory(self):
        report=self._approve()
        self.assertEqual(report['reviewed_mapping_proposals'],2)
        data=portfolio.export_seeds(self.work,self.root/'seeds')
        self.assertEqual(data['distinct_qids'],1)
        lines=(self.root/'seeds/portfolio-selected-qids.jsonl').read_text().splitlines()
        self.assertEqual([json.loads(x)['wikidata_qid'] for x in lines],['Q900000000'])
        mappings=[json.loads(x) for x in (self.root/'seeds/reviewed-mappings.jsonl').read_text().splitlines()]
        self.assertEqual({x['namespace'] for x in mappings},{'kristal:botany','kristal:other'})

    def test_wikidata_complete_claim_preserved_without_canon_writes(self):
        self._approve()
        entity={'id':'Q900000000','labels':{'fr':{'value':'Embryophyta'}},
                'claims':{'P527':[{'id':'Q900000000$X','rank':'preferred',
                                   'mainsnak':{'datavalue':{'type':'wikibase-entityid','value':{'id':'Q900000001'}}},
                                   'qualifiers':{'P580':[{'snaktype':'value','datavalue':{'value':'2026-01-01'}}]},
                                   'references':[{'hash':'s1','snaks':{'P854':[]}}]}]}}
        evidence=self.root/'evidence';evidence.mkdir()
        part=evidence/'part-000000.jsonl.gz'
        with gzip.open(part,'wt',encoding='utf-8') as f:f.write(js(entity)+'\n')
        manifest={'source_sha1':'a'*40,'parts':[{'file':part.name,
            'sha256':hashlib.sha256(part.read_bytes()).hexdigest(),'count':1}]}
        (evidence/'snapshot-manifest.json').write_text(js(manifest))
        output=self.root/'proposals.jsonl'
        result=portfolio.propose(self.work,evidence,output)
        self.assertEqual(result['review_proposals'],2)
        p=[json.loads(x) for x in output.read_text().splitlines()]
        self.assertEqual({x['namespace'] for x in p},{'kristal:botany','kristal:other'})
        self.assertEqual(p[0]['full_source_claim']['qualifiers'],entity['claims']['P527'][0]['qualifiers'])
        self.assertEqual(p[0]['full_source_claim']['references'],entity['claims']['P527'][0]['references'])
        self.assertIsNone(p[0]['semantic_property'])
        self.assertFalse(p[0]['publication_authorized'])
        related=[json.loads(x) for x in output.with_name('proposals.related-qids.jsonl').read_text().splitlines()]
        self.assertEqual(related[0]['wikidata_qid'],'Q900000001')
        # Mutate snapshot chunk: digest check must refuse.
        part.write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'checksum'):
            portfolio.propose(self.work,evidence,self.root/'bad.jsonl')

    def test_acquire_full_raw_source_resume(self):
        self._approve()
        source=json.loads((Path(__file__).parents[1]/'fixtures/demo.wikidata.jsonl').read_text().splitlines()[0]).copy()
        raw=(js(source)+'\n').encode()
        class Common:
            @staticmethod
            def fast_fetch_raw(root,dump,qids,threads):
                return {x:raw for x in qids}
        mock_profile={'extraction':{'workers':1}}
        dest=self.root/'acquired'
        with patch('skope.extraction.load_profile',return_value=mock_profile), \
             patch('skope.extraction._data_root',return_value=self.root), \
             patch('skope.extraction._check_source',return_value=({'dump':str(self.root/'dummy'),'sha1':'a'*40,'verified':True,'random_access_ready':True},[])), \
             patch('skope.extraction._module',return_value=Common):
            run=portfolio.acquire(self.work,self.index,'demo-profile',dest,batch_size=1,max_batches=1)
            self.assertEqual(run['state'],'completed')
            self.assertEqual(portfolio.acquire(self.work,self.index,'demo-profile',dest,batch_size=1)['new_batches'],0)
        result=portfolio.propose(self.work,dest,self.root/'acquired-proposals.jsonl')
        self.assertGreater(result['review_proposals'],0)

    def test_acquire_requires_review_and_reuses_skope_verified_path(self):
        portfolio.inventory(self.source,self.work)
        with self.assertRaisesRegex(ValueError,'No reviewed QID seeds'):
            portfolio.acquire(self.work,self.index,'any',self.root/'none')


if __name__=='__main__':unittest.main()

class DraftSuggestions(unittest.TestCase):
    def test_exact_name_only_and_no_a_kristal_auto_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'z.zip'
            def payload(namespace,entries):
                return json.dumps({'artifact_type':'kristal_curated_dictionary','namespace_id':namespace,
                                   'language':'fr','entries':[{'semantic_id':k,'preferred_term':v} for k,v in entries]},ensure_ascii=False)
            with zipfile.ZipFile(source,'w') as z:
                for project,ns in [('Kristal-Botany','ns1'),('A-Kristal-Precious','ns2')]:
                    z.writestr(project+'/.kristal/v11/dik.project.json','{}')
                    z.writestr(project+'/.kristal/v11/dictionaries/fr.json',payload(ns,[('KQ13','Embryophyta')]))
            idx=root/'idx.sqlite';make_index(idx)
            work=root/'work'
            portfolio.inventory(source,work)
            portfolio.discover(work,idx)
            result=portfolio.suggest_drafts(work)
            self.assertEqual(result['tentative_unverified'],1)
            self.assertEqual(result['a_kristals_auto_selected'],0)
            self.assertEqual(portfolio.status(work)['approved_identity_proposals'],0)
            reviewed=portfolio.export_seeds(work,root/'reviewed-only')
            self.assertEqual(reviewed['distinct_qids'],0)
            tentative=portfolio.export_seeds(work,root/'draft-seeds',include_draft=True)
            self.assertEqual(tentative['distinct_qids'],1)
            self.assertEqual(tentative['tentative_unverified_mappings'],1)
            with portfolio._open(work) as c:
                self.assertEqual(c.execute('SELECT external_id FROM tentative').fetchone()[0],'Q900000000')

    def test_unverified_draft_requires_explicit_opt_in_for_claim_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'z.zip'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr('Kristal-Draft/.kristal/v11/dik.project.json','{}')
                z.writestr('Kristal-Draft/.kristal/v11/dictionaries/fr.json',json.dumps({
                    'artifact_type':'kristal_curated_dictionary','namespace_id':'ns',
                    'language':'fr','entries':[{'semantic_id':'KQ100','preferred_term':'Embryophyta'}]}))
            idx=root/'idx.sqlite';make_index(idx)
            work=root/'work';portfolio.inventory(source,work);portfolio.discover(work,idx)
            portfolio.suggest_drafts(work)
            entity=json.loads((Path(__file__).parents[1]/'fixtures/demo.wikidata.jsonl').read_text().splitlines()[0])
            raw=root/'entity.jsonl';raw.write_text(json.dumps(entity)+'\n')
            none=portfolio.propose(work,raw,root/'none.jsonl')
            self.assertEqual(none['review_proposals'],0)
            draft=portfolio.propose(work,raw,root/'draft.jsonl',include_draft=True)
            self.assertGreater(draft['review_proposals'],0)
            record=json.loads((root/'draft.jsonl').read_text().splitlines()[0])
            self.assertEqual(record['identity_status'],'lexical_only_unverified')
            self.assertEqual(record['source_trust'],'unverified_standalone_fixture')
            self.assertFalse(record['publication_authorized'])
