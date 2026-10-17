"""Tiny real SQLite and roster fixtures for Catho person -> P50 -> source extraction handoff.
No Wikidata dump or Kristal canon is changed in these tests.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from unittest.mock import patch
import pytest

from skope import author_campaign as a, massive, scope_profiles, extraction

PROFILE='catho-recognised-authors'


def fake_kristal(tmp_path):
    k=tmp_path/'A-Kristal-Catho'
    (k/'canon/domain').mkdir(parents=True)
    (k/'kristal.workspace.json').write_text(json.dumps({
        'format':'kristal.local-workspace/3.2.0','slug':'kristal-catho','title':'Catho'}))
    roster={'schema_version':'kristal.catho.personnes-reconnaissances/1.0','as_of':'2026-10-13',
        'sources':[{'id':'vatican','url':'https://www.vatican.va/example'}],
        'personnes':[
           {'id':'urn:kristal:catho:personne:a','nom':'Scholar Unique','variantes_de_nom':[],
            'categories':['docteur_eglise'], 'reconnaissances':[{'categorie':'docteur_eglise','source_id':'vatican'}]},
           {'id':'urn:kristal:catho:personne:b','nom':'Ambiguous Fellow','variantes_de_nom':[],
            'categories':['laureat_prix_ratzinger'],'reconnaissances':[{'categorie':'laureat_prix_ratzinger','source_id':'vatican'}]},
           {'id':'urn:kristal:catho:personne:c','nom':'Never Indexed','variantes_de_nom':[],
            'categories':['commission_theologique_internationale'],'reconnaissances':[{'categorie':'commission_theologique_internationale','source_id':'vatican'}]},
           {'id':'urn:kristal:catho:personne:d','nom':'Pope Only','variantes_de_nom':[],
            'categories':['pape'],'reconnaissances':[{'categorie':'pape','source_id':'vatican'}]},
        ]}
    p=k/'canon/domain/personnes-reconnaissances.json'
    p.write_text(json.dumps(roster,ensure_ascii=False),encoding='utf-8')
    return k,p


def fake_index(tmp_path):
    root=tmp_path/'30_working'/'wikidata';root.mkdir(parents=True)
    path=root/'index.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript('''
          CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
          INSERT INTO meta VALUES('complete','1');
          CREATE TABLE entity(id INTEGER PRIMARY KEY,wid TEXT,label_fr TEXT,label_en TEXT,label_mul TEXT,description_fr TEXT,description_en TEXT);
          CREATE TABLE name(entity_id INTEGER,lang TEXT,value TEXT,name_kind INT,norm TEXT);
          CREATE INDEX idx_name_norm ON name(norm);
          CREATE TABLE entity_edge(subject_id INTEGER,target_id INTEGER,property_id INTEGER,statement_count INTEGER DEFAULT 1,best_rank INTEGER DEFAULT 1);
          CREATE INDEX idx_edge_target ON entity_edge(target_id,property_id);
        ''')
        for n,label in [(5,'human'),(101,'Scholar Unique'),(202,'Ambiguous Fellow'),(203,'Ambiguous Fellow'),(300,'A recognised book')]:
            db.execute('INSERT INTO entity VALUES(?,?,?,?,?,?,?)',(n,'Q'+str(n),label,label,label,'',''))
            db.execute('INSERT INTO name VALUES(?,?,?,?,?)',(n,'en',label,0,a._norm(label)))
        for n in (101,202,203):db.execute('INSERT INTO entity_edge(subject_id,target_id,property_id) VALUES(?,?,31)',(n,5))
        db.execute('INSERT INTO entity_edge(subject_id,target_id,property_id) VALUES(300,101,50)')
    return path


def test_catalog_author_profile_valid():
    profile=a._profile(PROFILE)
    assert profile['target_slug']=='kristal-catho'
    assert profile['source_kind']=='author-works'
    assert profile['orchestration']['work_property']=='P50'
    assert 'pape' not in profile['orchestration']['include_categories']


def test_canonical_roster_preview(tmp_path):
    k,p=fake_kristal(tmp_path)
    before=hashlib.sha256(p.read_bytes()).hexdigest()
    stats=a.preview(k,PROFILE)
    assert stats['people']==3
    assert stats['categories']['docteur_eglise']==1
    assert 'pape' not in stats['categories']
    assert before==hashlib.sha256(p.read_bytes()).hexdigest()


def test_exact_human_not_homonym_or_nonhuman(tmp_path):
    path=fake_index(tmp_path)
    with sqlite3.connect(path) as db:
        assert a._match(db,{'nom':'Scholar Unique'})==('matched_exact_human','Q101',[])
        status,qid,candidates=a._match(db,{'nom':'Ambiguous Fellow'})
        assert (status,qid,candidates)==('ambiguous',None,['Q202','Q203'])
        assert a._match(db,{'nom':'Never Indexed'})==('unmatched',None,[])
        assert a._match(db,{'nom':'A recognised book'})==('unmatched',None,[])


def test_one_click_checkpoint_handoff_provenance_and_resume(tmp_path):
    k,roster=fake_kristal(tmp_path)
    before=hashlib.sha256(roster.read_bytes()).hexdigest()
    index=fake_index(tmp_path)
    import shutil
    usage=shutil.disk_usage(tmp_path)
    fake_usage=type(usage)(usage.total,usage.used,50*1024**3)
    started=[]
    def fake_ext_start(idx,prof,source_job,resume=None,confirmed=False):
        started.append((prof,source_job,confirmed))
        return {'job':'1'*32,'state':'queued'}
    source={'verified':True,'fast_backend':'indexed_bzip2'}
    with patch.object(a.extraction,'_check_source',return_value=(source,[])), \
         patch.object(a.shutil,'disk_usage',return_value=fake_usage), \
         patch.object(a.extraction,'preflight',return_value={'ready':True,'blockers':[]}), \
         patch.object(a.extraction,'start',side_effect=fake_ext_start), \
         patch.object(a.extraction,'status',return_value={'job':'1'*32,'state':'running','processed':0,'total':2,'chunks':0,'message':'running','evidence_ready':False}):
        result=a.start(index,k,PROFILE,True)
        deadline=time.time()+15
        while time.time()<deadline:
            s=a.status(index,result['job'])
            if s.get('extraction_job') or s['state'] in ('failed','blocked'):
                break
            time.sleep(.05)
        assert s['state']=='extracting',s
        assert started==[('catho-recognised-authors-full-wikidata',result['job'],True)]
        summary=massive.status(index,result['job'])
        assert summary['state']=='completed'
        assert summary['selected']==2
        folder=massive._path(index,result['job'])
        assert [json.loads(x)['wikidata_qid'] for x in (folder/'selected-qids.jsonl').read_text().splitlines()]==['Q101','Q300']
        matched=[json.loads(x) for x in (folder/'matched-people.jsonl').read_text().splitlines()]
        unresolved=[json.loads(x) for x in (folder/'unresolved-people.jsonl').read_text().splitlines()]
        assert len(matched)==1 and matched[0]['recognitions'][0]['source_url']=='https://www.vatican.va/example'
        assert len(unresolved)==2 and any(r['match_status']=='ambiguous' for r in unresolved)
        assert json.loads((folder/'provenance-manifest.json').read_text())['works_linked']==1
        result_zip=massive.prepare_result_zip(index,result['job'])
        import zipfile
        with zipfile.ZipFile(result_zip) as z:
            assert 'unresolved-people.jsonl' in z.namelist()
            assert 'author-work-links.jsonl' in z.namelist()
            assert 'provenance-manifest.json' in z.namelist()
        assert hashlib.sha256(roster.read_bytes()).hexdigest()==before


def test_explicit_consent_is_required(tmp_path):
    k,_=fake_kristal(tmp_path); idx=fake_index(tmp_path)
    with pytest.raises(ValueError,match='Explicit confirmation'):
        a.start(idx,k,PROFILE,False)


def test_catalog_rejects_profile_path_escape():
    from skope.scope_profiles import _parse_profile
    raw={'format':a.SCOPE_FORMAT,'id':'bad','title':'Bad','target_slug':'kristal-catho',
         'orchestration':{'kind':'recognised_persons_to_authored_works','include_categories':['docteur_eglise'],
             'person_roster':'../../escape.json','work_property':'P50',
             'extraction_profile':'catho-recognised-authors-full-wikidata','auto_full_records':True}}
    with pytest.raises(ValueError,match='read-only Catho roster'):
        _parse_profile(raw,Path('bad.json'))


def test_loopback_http_preview_static_js_and_explicit_start_consent(tmp_path):
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.request import urlopen,Request
    from urllib.error import HTTPError
    from skope import api
    k,_ = fake_kristal(tmp_path)
    idx = fake_index(tmp_path)
    cls=type('CathoTestApp',(api.App,),{'db_path':str(idx),'kristal_folder':str(k)})
    server=ThreadingHTTPServer(('127.0.0.1',0),cls)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url='http://127.0.0.1:'+str(server.server_port)
    try:
        with urlopen(url+'/api/author-campaign/preview?profile='+PROFILE,timeout=5) as res:
            data=json.load(res)
        assert data['people']==3
        with urlopen(url+'/author-campaign.js',timeout=5) as res:
            assert b'Run complete' not in res.read() or res.status==200
        req=Request(url+'/api/author-campaign/start',data=json.dumps({'profile':PROFILE,'confirmed':False}).encode(),
                    headers={'Content-Type':'application/json'},method='POST')
        with pytest.raises(HTTPError) as caught:
            urlopen(req,timeout=5)
        assert caught.value.code == 400
        assert not (tmp_path/'30_working/skope-large-scopes').exists()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
