"""Skope 0.14.4: 161-identity batch ranking is NOT identity confirmation."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import time
import zipfile
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import pytest
from skope import api, reconciliation as r, reconciliation_batch as b
from test_identity_reconciliation_0143 import sample


def done(index,job):
    b.start(index,job)
    limit=time.monotonic()+12
    while time.monotonic()<limit:
        s=b.status(index,job)
        if s['state'] in ('completed','failed'):
            assert s['state']=='completed',s
            return b.results(index,job)
        time.sleep(.03)
    raise AssertionError('Batch analysis timed out')


def test_analysis_no_changes_to_original_evidence_and_no_decisions(tmp_path):
    index,job,folder,people=sample(tmp_path)
    digest=hashlib.sha256((folder/'unresolved-people.jsonl').read_bytes()).hexdigest()
    assert b.status(index,job)['state']=='not_started'
    assert not r._dbfile(folder).parent.exists()
    result=done(index,job)
    assert result['counts']['total']==3
    assert result['counts']['no_viable_candidate']>=1
    assert all(p['bucket'] in ('suggested','needs_review','no_viable_candidate') for p in result['rows'])
    assert r.list_people(index,job)['counts']['confirmed']==0
    assert not r._dbfile(folder).is_file()
    assert digest==hashlib.sha256((folder/'unresolved-people.jsonl').read_bytes()).hexdigest()
    assert b.start(index,job)['state']=='completed'  # rerun safely reuses completed evidence
    assert b.status(index,job)['read_only'] is True


def test_batch_staging_gated_and_separate_from_confirmed_decisions(tmp_path):
    index,job,folder,people=sample(tmp_path)
    with sqlite3.connect(index) as db:
        db.execute("UPDATE entity SET label_fr='Albert le Grand',description_fr='Catholic theologian doctor of the Church' WHERE id=202")
        db.execute("UPDATE entity SET label_fr='Different person',description_fr='hagiographer' WHERE id=203")
    result=done(index,job)
    proposal=next((row for row in result['rows'] if row['person_id']==people[0]['kristal_person_id']),None)
    assert proposal['bucket']=='suggested',proposal
    selections=[{'person_id':proposal['person_id'],'qid':proposal['suggested_qid']}]
    digest=result['source_roster_sha256']
    with pytest.raises(ValueError,match='Explicit'):b.stage(index,job,selections,digest,False)
    with pytest.raises(ValueError,match='changed'):b.stage(index,job,selections,'bad',True)
    with pytest.raises(ValueError,match='not a current'):b.stage(index,job,[{'person_id':proposal['person_id'],'qid':'Q203'}],digest,True)
    staged=b.stage(index,job,selections,digest,True)
    assert staged['status']=='proposed_not_confirmed' and staged['staged']==1
    assert r.list_people(index,job)['counts']['confirmed']==0
    assert r.list_people(index,job)['counts']['pending']==3
    export=zipfile.ZipFile(io.BytesIO(b.export_zip(index,job)))
    assert 'human-review-template.csv' in export.namelist()
    assert json.loads(export.read('manifest.json'))['identity_verified'] is False
    assert b'stage_unverified_proposal' not in export.read('staged-proposals.jsonl')
    assert len(export.read('staged-proposals.jsonl').splitlines())==1
    assert (folder/'unresolved-people.jsonl').is_file()


def test_already_matched_author_is_a_collision_never_staged(tmp_path):
    index,job,folder,people=sample(tmp_path)
    (folder/'matched-people.jsonl').write_text(json.dumps({'wikidata_qid':'Q202','kristal_person_id':'urn:kristal:catho:personne:different'})+'\n')
    with sqlite3.connect(index) as db:
        db.execute("UPDATE entity SET label_fr='Albert le Grand',description_fr='Theologian' WHERE id=202")
    result=done(index,job)
    p=next(x for x in result['rows'] if x['person_id']==people[0]['kristal_person_id'])
    assert next(c for c in p['candidates'] if c['qid']=='Q202')['collision'] is True
    with pytest.raises(ValueError,match='current high-ranked'):
        b.stage(index,job,[{'person_id':p['person_id'],'qid':'Q202'}],result['source_roster_sha256'],True)


def test_http_batch_routes_guards_and_bundle(tmp_path):
    index,job,folder,people=sample(tmp_path)
    cls=type('BatchAPI',(api.App,),{'db_path':str(index)})
    server=ThreadingHTTPServer(('127.0.0.1',0),cls)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    url='http://127.0.0.1:'+str(server.server_port)
    try:
        with urlopen(url+'/api/reconciliation/batch/status?job='+job) as resp:
            assert json.load(resp)['state']=='not_started'
        request=Request(url+'/api/reconciliation/batch/start',method='POST',data=json.dumps({'job':job}).encode(),headers={'Content-Type':'application/json','Origin':'https://external-site.example'})
        with pytest.raises(HTTPError) as exc:urlopen(request)
        assert exc.value.code==403
        request=Request(url+'/api/reconciliation/batch/start',method='POST',data=json.dumps({'job':job}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(request) as resp:assert json.load(resp)['state']=='running'
        limit=time.monotonic()+10
        while time.monotonic()<limit:
            with urlopen(url+'/api/reconciliation/batch/status?job='+job) as resp:s=json.load(resp)
            if s['state']=='completed':break
            time.sleep(.05)
        assert s['state']=='completed'
        with urlopen(url+'/api/reconciliation/batch/results?job='+job) as resp:
            assert json.load(resp)['counts']['total']==3
        with urlopen(url+'/api/reconciliation/batch/export.zip?job='+job) as resp:
            assert zipfile.is_zipfile(io.BytesIO(resp.read()))
    finally:
        server.shutdown();server.server_close()


def test_ui_intentions_no_duplicate_graph_and_no_auto_collection():
    static=Path(__file__).resolve().parents[1]/'skope/static'
    html=(static/'index.html').read_text()
    assert html.count('id="graph"')==1
    for ident in ('nav-scopes','nav-identities','nav-explorer','reconcile-batch-workspace','reconcile-batch-stage','reconcile-batch-export'):
        assert html.count('id="'+ident+'"')==1
    scripts=(static/'reconciliation-batch.js').read_text()
    assert '/api/author-campaign/start' not in scripts
    assert '/api/extract/start' not in scripts
    assert '/api/reconciliation/batch/start' in scripts
    assert "identity_verified':False" in (Path(__file__).resolve().parents[1]/'skope/reconciliation_batch.py').read_text()


def _reviewed_csv(person_id,qid='Q202',reason='Cross-checked identity using independent biographical authority',url='https://example.org/biography',revision=0):
    import csv
    from io import StringIO
    out=StringIO(newline='')
    writer=csv.writer(out)
    writer.writerow(['person_id','suggested_qid','review_decision','documentary_identity_url','reason_for_confirmation','expected_revision'])
    writer.writerow([person_id,qid,'confirm',url,reason,revision])
    return out.getvalue()


def test_documented_bulk_dry_run_then_atomic_confirmation(tmp_path):
    index,job,folder,people=sample(tmp_path)
    raw=(folder/'unresolved-people.jsonl').read_bytes()
    csvtext=_reviewed_csv(people[0]['kristal_person_id'])
    assert not r._dbfile(folder).parent.exists()
    preview=b.validate_reviewed_csv(index,job,csvtext)
    assert preview['reviewed_count']==1 and preview['ready']
    assert not r._dbfile(folder).parent.exists()
    with pytest.raises(ValueError,match='attestation'):
        b.confirm_reviewed_csv(index,job,csvtext,preview['csv_sha256'],False)
    with pytest.raises(ValueError,match='changed'):
        b.confirm_reviewed_csv(index,job,csvtext,'wrong',True)
    result=b.confirm_reviewed_csv(index,job,csvtext,preview['csv_sha256'],True)
    assert result['confirmed']==1 and result['source_urls_checked_online'] is False
    assert r.list_people(index,job)['counts']['confirmed']==1
    assert (folder/'unresolved-people.jsonl').read_bytes()==raw
    with pytest.raises(ValueError,match='revision changed'):
        b.confirm_reviewed_csv(index,job,csvtext,preview['csv_sha256'],True)


def test_bulk_csv_all_or_nothing_on_conflict(tmp_path):
    import csv
    from io import StringIO
    index,job,folder,people=sample(tmp_path)
    out=StringIO(newline=''); writer=csv.writer(out)
    writer.writerow(['person_id','suggested_qid','review_decision','documentary_identity_url','reason_for_confirmation','expected_revision'])
    writer.writerow([people[0]['kristal_person_id'],'Q202','confirm','https://www.wikidata.org/wiki/Q202','Independent identity reference included',0])
    writer.writerow([people[2]['kristal_person_id'],'Q300','confirm','https://www.wikidata.org/wiki/Q300','Incorrect non-human identity reference',0])
    with pytest.raises(ValueError,match='human'):
        b.validate_reviewed_csv(index,job,out.getvalue())
    assert not r._dbfile(folder).is_file()


def test_csv_does_not_treat_recognition_page_as_verified_automatically(tmp_path):
    index,job,folder,people=sample(tmp_path)
    zipdata=zipfile.ZipFile(io.BytesIO(b.export_zip(index,job))) if False else None
    csvtext=_reviewed_csv(people[0]['kristal_person_id'],url='')
    with pytest.raises(ValueError,match='documentary'):
        b.validate_reviewed_csv(index,job,csvtext)


def test_http_serves_all_refactor_assets_and_rejects_arbitrary_paths(tmp_path):
    index,job,folder,people=sample(tmp_path)
    cls=type('BatchStatic',(api.App,),{'db_path':str(index)})
    server=ThreadingHTTPServer(('127.0.0.1',0),cls)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        origin='http://127.0.0.1:'+str(server.server_port)
        for name in ('reconciliation-batch.js','reconciliation-batch.css','research-ui.js','research-ui.css'):
            with urlopen(origin+'/'+name,timeout=4) as resp:
                assert resp.status==200 and len(resp.read())>50
        with pytest.raises(HTTPError) as exc:urlopen(origin+'/../README.md',timeout=4)
        assert exc.value.code==404
    finally:
        server.shutdown();server.server_close()


def test_documented_csv_http_dryrun_requires_attestation_and_does_not_start_extraction(tmp_path):
    index,job,folder,people=sample(tmp_path)
    cls=type('BatchCSVAPI',(api.App,),{'db_path':str(index)})
    server=ThreadingHTTPServer(('127.0.0.1',0),cls)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    root='http://127.0.0.1:'+str(server.server_port)
    def post(route,payload):
        req=Request(root+route,method='POST',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=5) as resp:return json.load(resp)
    try:
        csvtext=_reviewed_csv(people[0]['kristal_person_id'])
        before=(folder/'unresolved-people.jsonl').read_bytes()
        test=post('/api/reconciliation/batch/validate-reviewed',{'job':job,'csv':csvtext})
        assert test['ready'] and test['reviewed_count']==1
        assert not r._dbfile(folder).is_file()
        try:
            post('/api/reconciliation/batch/confirm-reviewed',{'job':job,'csv':csvtext,'csv_sha256':test['csv_sha256'],'confirmed':False})
            assert False,'Must deny unconfirmed requests'
        except HTTPError as e: assert e.code==400
        result=post('/api/reconciliation/batch/confirm-reviewed',{'job':job,'csv':csvtext,'csv_sha256':test['csv_sha256'],'confirmed':True})
        assert result['confirmed']==1 and result['extraction_started'] is False
        assert (folder/'unresolved-people.jsonl').read_bytes()==before
    finally:
        server.shutdown();server.server_close()
