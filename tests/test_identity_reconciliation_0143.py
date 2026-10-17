"""Skope 0.14.3: isolated read-only Catho reconciliation fixture tests."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import threading
import zipfile
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import pytest
from skope import api, reconciliation as r
from test_author_campaign_1322 import fake_index


def sample(tmp_path):
    index=fake_index(tmp_path)
    job='a'*32
    folder=tmp_path/'30_working/skope-large-scopes'/job
    folder.mkdir(parents=True)
    entries=[]
    for slug,name,category,status,candidates in [
       ('albert','Albert le Grand','docteur_eglise','ambiguous',['Q202','Q203']),
       ('alice','Historical Writer','commission_theologique_internationale','unmatched',[]),
       ('bob','A Ratzinger Laureate','laureat_prix_ratzinger','ambiguous',['Q101']),
    ]:
        entries.append({'kristal_person_id':'urn:kristal:catho:personne:'+slug,
            'name':name,'categories':[category],'match_status':status,'candidate_qids':candidates,
            'recognitions':[{'category':category,'source_url':'https://www.vatican.va/index','period':'historical'}]})
    raw=''.join(json.dumps(p)+'\n' for p in entries)
    (folder/'unresolved-people.jsonl').write_text(raw,encoding='utf-8')
    return index, job, folder, entries


def test_read_only_open_and_priority_order(tmp_path):
    db,job,folder,p=sample(tmp_path)
    before=hashlib.sha256((folder/'unresolved-people.jsonl').read_bytes()).hexdigest()
    result=r.list_people(db,job)
    assert result['counts']=={'total':3,'pending':3,'confirmed':0,'deferred':0,'no_reliable_match':0,
                              'ambiguous':2,'unmatched':1,'priority_pending':2}
    assert [x['name'] for x in result['people']][:2]==['Albert le Grand','A Ratzinger Laureate']
    assert not r._dbfile(folder).parent.exists()
    (folder/'matched-people.jsonl').write_text(json.dumps({'wikidata_qid':'Q202','name':'Another roster alias','kristal_person_id':'urn:kristal:catho:personne:alias'})+'\n')
    info=r.detail(db,job,p[0]['kristal_person_id'])
    assert len(info['candidates'])==2
    assert info['candidates'][0]['is_human']
    assert info['candidates'][0]['already_matched_in_campaign'][0]['name']=='Another roster alias'
    assert before==hashlib.sha256((folder/'unresolved-people.jsonl').read_bytes()).hexdigest()


def test_requires_human_review_and_documentary_evidence(tmp_path):
    db,job,folder,p=sample(tmp_path)
    person=p[0]['kristal_person_id']
    with pytest.raises(ValueError,match='Explicit human'):
        r.save(db,job,person,'confirmed','Q202','Clear documentary support','https://www.vatican.va/index',False,0)
    with pytest.raises(ValueError,match='justification'):
        r.save(db,job,person,'confirmed','Q202','short','https://www.vatican.va/index',True,0)
    with pytest.raises(ValueError,match='URL'):
        r.save(db,job,person,'confirmed','Q202','Long and reasoned identification','file:///tmp/a',True,0)
    with pytest.raises(ValueError,match='human'):
        r.save(db,job,person,'confirmed','Q300','Long and reasoned identification','https://www.vatican.va/index',True,0)
    assert not r._dbfile(folder).parent.exists()


def test_approval_revise_clear_audit_and_export(tmp_path):
    db,job,folder,p=sample(tmp_path)
    source=(folder/'unresolved-people.jsonl').read_bytes()
    person=p[0]['kristal_person_id']
    approved=r.save(db,job,person,'confirmed','Q202','Detailed documentary identification of this person',
                    'https://www.vatican.va/index',True,0)
    assert approved['revision']==1
    assert r.list_people(db,job)['counts']['confirmed']==1
    with pytest.raises(ValueError,match='Refresh'):
        r.save(db,job,person,'deferred',None,'Need additional work',None,True,0)
    info=r.detail(db,job,person)
    assert info['decision']['qid']=='Q202'
    r.save(db,job,person,'clear',None,'Undo decision',None,True,1)
    assert r.detail(db,job,person)['review_revision']==2
    assert r.list_people(db,job)['counts']['pending']==3
    with pytest.raises(ValueError,match='Refresh'):
        r.save(db,job,person,'deferred',None,'Later',None,True,0)
    r.save(db,job,person,'deferred',None,'Later',None,True,2)
    report=zipfile.ZipFile(io.BytesIO(r.export(db,job)))
    assert sorted(report.namelist())==['audit.jsonl','decisions.jsonl','manifest.json']
    assert len(report.read('audit.jsonl').decode().splitlines())==3
    assert json.loads(report.read('manifest.json'))['summary']['deferred']==1
    assert (folder/'unresolved-people.jsonl').read_bytes()==source
    assert r._dbfile(folder).parent.parent.name=='skope-reconciliation'
    assert not (folder/'selected-qids.jsonl').exists()


def test_invalid_job_and_duplicate_qids(tmp_path):
    db,job,folder,p=sample(tmp_path)
    with pytest.raises(ValueError):r.list_people(db,'../../etc/passwd')
    person=p[0]['kristal_person_id']
    r.save(db,job,person,'confirmed','Q101','A valid explicit source and documentary reason',
                    'https://www.vatican.va/index',True,0)
    with pytest.raises(ValueError,match='already confirmed'):
        r.save(db,job,p[2]['kristal_person_id'],'confirmed','Q101','Other explicit sources too',
               'https://www.vatican.va/index',True,0)


def test_http_routes_are_same_origin_and_read_only_until_confirmed(tmp_path):
    db,job,folder,p=sample(tmp_path)
    App=type('IdentityTestApp',(api.App,),{'db_path':str(db)})
    server=ThreadingHTTPServer(('127.0.0.1',0),App)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/api/reconciliation/people?job='+job,timeout=4) as response:
            result=json.load(response)
        assert result['counts']['total']==3
        for resource in ('reconciliation.js','reconciliation.css'):
            with urlopen(base+'/'+resource,timeout=4) as response:
                assert response.status==200
        req=Request(base+'/api/reconciliation/decision',method='POST',
                    data=json.dumps({'job':job,'person_id':p[0]['kristal_person_id'],
                                     'decision':'confirmed','confirmed':False}).encode(),
                    headers={'Origin':'https://some-other-host.example','Content-Type':'application/json'})
        with pytest.raises(HTTPError) as err:urlopen(req,timeout=4)
        assert err.value.code==403
        good=Request(base+'/api/reconciliation/decision',method='POST',
                    data=json.dumps({'job':job,'person_id':p[0]['kristal_person_id'],
                                     'decision':'deferred','note':'Research required','confirmed':True,
                                     'expected_revision':0}).encode(),
                    headers={'Content-Type':'application/json'})
        with urlopen(good,timeout=4) as response:
            assert json.load(response)['saved'] is True
        with urlopen(base+'/api/reconciliation/people?job='+job,timeout=4) as response:
            assert json.load(response)['counts']['deferred']==1
        with urlopen(base+'/api/reconciliation/export.zip?job='+job,timeout=4) as response:
            assert response.headers['Content-Type']=='application/zip'
            assert zipfile.is_zipfile(io.BytesIO(response.read()))
        assert r._dbfile(folder).is_file()
    finally:
        server.shutdown();server.server_close()


def test_ui_graph_is_not_duplicated():
    html=(Path(__file__).resolve().parents[1]/'skope/static/index.html').read_text()
    assert html.count('id="graph"')==1
    assert 'id="reconciliation-modal"' in html
    assert html.count('id="reconcile-open"')==1
    assert '/reconciliation.js' in html
    js=(Path(__file__).resolve().parents[1]/'skope/static/reconciliation.js').read_text()
    assert '/api/author-campaign/start' not in js
    assert '/api/extract/start' not in js
