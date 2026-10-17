"""Bounded, resumable-in-practice evidence triage for existing Skope reconciliation jobs.

Analysis is read-only against the source campaign and the compact Wikidata index.
It writes a separate report under the Skope reconciliation working directory.
Heuristic ranking is NEVER an authenticated identity or a canonical decision.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import re
import threading
from pathlib import Path
import sqlite3
import unicodedata
import zipfile

from . import reconciliation as r
from .db import connect, find

POLICY = 'skope.reconciliation-batch/1.0'
MAX_CANDIDATES = 45
_LOCK = threading.RLock()
_ACTIVE = set()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '').casefold())
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).replace('-', ' ').replace("'", ' ').split())


def _paths(folder):
    directory = r._dbfile(folder).parent
    return directory / 'batch-analysis.json', directory / 'batch-progress.json'


def _digest(folder):
    return hashlib.sha256((folder / 'unresolved-people.jsonl').read_bytes()).hexdigest()


def _safe_read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _write(path, payload):
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('Unsafe batch report destination')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    if tmp.is_symlink():
        raise ValueError('Unsafe batch temporary file')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def _rank(person, candidate, known):
    qid = candidate['qid']
    reasons = []
    if not candidate['is_human']:
        return {'qid': qid, 'label': candidate.get('label', qid), 'score': 0,
                'reasons': ['Not verified as a human (P31=Q5)'], 'human': False, 'collision': False}
    label = _norm(candidate.get('label', ''))
    name = _norm(person.get('name', ''))
    aliases = candidate.get('aliases', {})
    variants = {_norm(x) for arr in aliases.values() for x in arr[:40]}
    score = 0
    if name and label == name:
        score += 45
        reasons.append('Exact display-name match')
    elif name and name in variants:
        score += 45
        reasons.append('Exact listed-alias match')
    elif name and (name in label or label in name) and min(len(name), len(label)) >= 7:
        score += 14
        reasons.append('Partial name overlap only')
    description = _norm(candidate.get('description', ''))
    occupations = ' '.join(_norm(x.get('label')) for x in candidate.get('occupations_and_positions', []))
    context = description + ' ' + occupations
    cats = person.get('categories') or []
    if 'docteur_eglise' in cats and any(x in context for x in ('theologien','theologian','doctor of the church','docteur de l eglise')):
        score += 14
        reasons.append('Theological context compatible with roster')
    elif any(x in cats for x in ('commission_theologique_internationale','academie_pontificale_saint_thomas')) and any(x in context for x in ('theologien','theologian','theology','theologie','philosoph','professor')):
        score += 8
        reasons.append('Profession context compatible; not a membership proof')
    if 'laureat_prix_ratzinger' in cats and any(x in context for x in ('ratzinger','theologien','theologian')):
        score += 8
        reasons.append('Prize/theology context compatible; not proof of award')
    collision = qid in known and person['kristal_person_id'] not in known[qid]
    if collision:
        score = max(0, score - 35)
        reasons.append('QID already belongs to another matched roster entry')
    return {'qid': qid, 'label': candidate.get('label') or qid,
            'description': candidate.get('description', ''), 'score': min(score, 100),
            'reasons': reasons or ['Candidate only; no corroborating context'],
            'human': True, 'collision': collision}


def _known(folder):
    path = folder / 'matched-people.jsonl'
    known = {}
    if path.is_file() and not path.is_symlink() and path.stat().st_size <= r.MAX_SOURCE_BYTES:
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                p = json.loads(line)
                qid = p.get('wikidata_qid')
                if isinstance(qid, str) and r.QID.fullmatch(qid):
                    known.setdefault(qid, set()).add(p.get('kristal_person_id'))
    return known


def _analyze(index, folder, update=None):
    people = r._source(folder)
    known = _known(folder)
    results = []
    digest = _digest(folder)
    with closing(connect(index)) as db:
        for i, person in enumerate(people):
            qids = list(dict.fromkeys(person.get('candidate_qids') or []))
            # Bounded secondary discovery is restricted to names already present in the roster;
            # candidate QIDs are never conjured from resemblance alone.
            if not qids:
                for result in find(db, person.get('name', ''), limit=6):
                    qid = result.get('id')
                    if qid and r.QID.fullmatch(qid) and qid not in qids:
                        qids.append(qid)
            if len(qids) > MAX_CANDIDATES:
                qids = qids[:MAX_CANDIDATES]
            ranked = sorted((_rank(person, r._candidate(db, qid), known) for qid in qids
                             if r.QID.fullmatch(qid)), key=lambda c: (-c['score'], c['qid']))
            eligible = [c for c in ranked if c['human'] and not c['collision']]
            top = eligible[0] if eligible else None
            runner = eligible[1] if len(eligible) > 1 else None
            # Only a review suggestion. Never described as evidence-backed or confirmed.
            confident = bool(top and top['score'] >= 52 and (runner is None or top['score']-runner['score'] >= 20))
            bucket = 'suggested' if confident else ('needs_review' if eligible else 'no_viable_candidate')
            results.append({'person_id': person['kristal_person_id'], 'name': person.get('name'),
                            'categories': person.get('categories', []), 'original_status': person.get('match_status'),
                            'bucket': bucket, 'suggested_qid': top['qid'] if confident else None,
                            'candidates': ranked,
                            'source_urls': sorted({a.get('source_url') for a in person.get('recognitions', []) if a.get('source_url')}),
                            'warning': 'Heuristic suggestion only; roster references prove recognition, not a QID identity.'})
            if update and (i % 5 == 0 or i + 1 == len(people)):
                update(i + 1, len(people))
    counts = {k: sum(row['bucket'] == k for row in results) for k in ('suggested','needs_review','no_viable_candidate')}
    return {'schema': POLICY, 'job': folder.name, 'generated_at': _now(), 'source_roster_sha256': digest,
            'policy': 'Offline context ranking; never confirms identities or checks online documentary sources.',
            'counts': {'total': len(people), **counts}, 'rows': results}


def status(index, job=None):
    folder = r._job(index, job)
    report, progress = _paths(folder)
    current = _safe_read(progress)
    completed = _safe_read(report)
    digest = _digest(folder)
    if completed and completed.get('source_roster_sha256') == digest and completed.get('schema') == POLICY:
        summary = {'state': 'completed', 'job': folder.name, 'counts': completed['counts'],
                   'generated_at': completed['generated_at'], 'read_only': True}
    else:
        summary = {'state': 'not_started', 'job': folder.name, 'read_only': True}
    if current and current.get('job') == folder.name and current.get('state') in ('running','failed'):
        if current['state'] == 'running':
            with _LOCK:
                active = str(report) in _ACTIVE
            if not active:
                current = {**current, 'state':'interrupted', 'message':'Server restarted; restart analysis to resume safely.'}
        if summary['state'] != 'completed' or current.get('state') == 'running':
            summary.update(current)
    return summary


def start(index, job=None, force=False):
    folder = r._job(index, job)
    report, progress = _paths(folder)
    with _LOCK:
        if str(report) in _ACTIVE:
            return status(index, folder.name)
        if status(index, folder.name)['state'] == 'completed' and not force:
            return status(index, folder.name)
        _ACTIVE.add(str(report))
        _write(progress, {'job':folder.name, 'state':'running', 'processed':0,
                          'total':len(r._source(folder)), 'started_at':_now()})
    thread = threading.Thread(target=_worker, args=(str(index), folder, report, progress), daemon=True)
    thread.start()
    return {'job':folder.name, 'state':'running', 'processed':0, 'total':len(r._source(folder))}


def _worker(index, folder, report, progress):
    try:
        def update(done, total):
            _write(progress, {'job':folder.name, 'state':'running', 'processed':done, 'total':total})
        data = _analyze(index, folder, update)
        _write(report, data)
        _write(progress, {'job':folder.name,'state':'completed','processed':len(data['rows']),
                          'total':len(data['rows'])})
    except Exception as exc:
        _write(progress, {'job':folder.name, 'state':'failed', 'message':f'{type(exc).__name__}: {exc}'})
    finally:
        with _LOCK:
            _ACTIVE.discard(str(report))


def results(index, job=None, bucket='all', offset=0, limit=100):
    folder = r._job(index, job)
    report, _ = _paths(folder)
    data = _safe_read(report)
    if not data or data.get('source_roster_sha256') != _digest(folder) or data.get('schema') != POLICY:
        raise ValueError('No current batch analysis. Run analysis first.')
    if bucket not in ('all','suggested','needs_review','no_viable_candidate'):
        raise ValueError('Invalid batch filter')
    offset, limit = int(offset), int(limit)
    if offset < 0 or not 1 <= limit <= 200 or offset > 20000:
        raise ValueError('Invalid batch pagination')
    rows = [p for p in data['rows'] if bucket == 'all' or p['bucket'] == bucket]
    return {'job':folder.name,'counts':data['counts'], 'total_filtered':len(rows),
            'rows':rows[offset:offset+limit], 'offset':offset, 'limit':limit,
            'policy':data['policy'], 'source_roster_sha256':data['source_roster_sha256']}


def _validate_stage(folder, data, selections):
    if not isinstance(selections,list) or not 1 <= len(selections) <= 200:
        raise ValueError('Choose 1–200 suggested identities for the batch')
    rows = {x['person_id']:x for x in data['rows']}
    existing = r._read_decisions(folder)
    known = _known(folder)
    choices = []
    qids = set()
    ids = set()
    for sel in selections:
        if not isinstance(sel,dict):
            raise ValueError('Invalid batch selection')
        pid, qid = sel.get('person_id'), sel.get('qid')
        row = rows.get(pid)
        if not row or row['bucket'] != 'suggested' or row['suggested_qid'] != qid:
            raise ValueError('Selected QID is not a current high-ranked suggestion')
        if pid in ids or qid in qids:
            raise ValueError('Duplicate QID or person in the same batch')
        if qid in known:
            raise ValueError('Selected QID already assigned to another roster entry')
        if pid in existing and existing[pid]['decision'] == 'confirmed':
            raise ValueError('Existing confirmed decision must not be overwritten')
        ids.add(pid); qids.add(qid); choices.append((pid,qid,row['name']))
    return choices


def stage(index, job, selections, digest, confirmed=False):
    folder=r._job(index,job)
    report,_=_paths(folder)
    data=_safe_read(report)
    if not data or data.get('source_roster_sha256') != _digest(folder) or digest != data['source_roster_sha256']:
        raise ValueError('Batch report changed; refresh and analyze again')
    if confirmed is not True:
        raise ValueError('Explicit bulk staging approval is required')
    choices=_validate_stage(folder,data,selections)
    dbpath=r._dbfile(folder)
    with r.AUDIT_LOCK:
        dbpath.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(dbpath,timeout=15)) as db:
            with db:
                r._init_store(db)
                db.execute('''CREATE TABLE IF NOT EXISTS batch_proposals(
                    person_id TEXT PRIMARY KEY, qid TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    roster_sha256 TEXT NOT NULL, staged_at TEXT NOT NULL)''')
                db.execute('''CREATE TABLE IF NOT EXISTS batch_audit(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,person_id TEXT NOT NULL,
                    qid TEXT NOT NULL,action TEXT NOT NULL,occurred_at TEXT NOT NULL)''')
                for pid,qid,name in choices:
                    conflict=db.execute('SELECT person_id FROM batch_proposals WHERE qid=? AND person_id<>?',(qid,pid)).fetchone()
                    if conflict:raise ValueError('QID already staged for another person')
                    db.execute('''INSERT INTO batch_proposals VALUES(?,?,?,?,?)
                        ON CONFLICT(person_id) DO UPDATE SET qid=excluded.qid,name=excluded.name,
                        roster_sha256=excluded.roster_sha256,staged_at=excluded.staged_at''',
                        (pid,qid,name,digest,_now()))
                    db.execute('INSERT INTO batch_audit(person_id,qid,action,occurred_at) VALUES(?,?,?,?)',
                               (pid,qid,'stage_unverified_proposal',_now()))
    return {'staged':len(choices),'status':'proposed_not_confirmed',
            'canon_written':False,'source_written':False,'extraction_started':False}


def export_zip(index,job=None):
    folder=r._job(index,job)
    report,_=_paths(folder)
    data=_safe_read(report)
    if not data or data.get('source_roster_sha256') != _digest(folder):
        raise ValueError('Run batch analysis before export')
    staged=[]
    dbpath=r._dbfile(folder)
    if dbpath.is_file():
        with closing(sqlite3.connect(f'{dbpath.as_uri()}?mode=ro',uri=True)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='batch_proposals'").fetchone():
                staged=[{'person_id':p,'qid':q,'name':n,'staged_at':ts} for p,q,n,sha,ts in
                        db.execute('SELECT person_id,qid,name,roster_sha256,staged_at FROM batch_proposals')
                        if sha == data['source_roster_sha256']]
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps({'schema':POLICY,'job':folder.name,
                   'source_roster_sha256':data['source_roster_sha256'],'counts':data['counts'],
                   'identity_verified':False,'canonical_changes':False,
                   'advice':'Heuristic ranking only. Obtain independent identity evidence before confirming QIDs.'},indent=2))
        z.writestr('triage.json',json.dumps(data,ensure_ascii=False,indent=2))
        z.writestr('staged-proposals.jsonl',''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in staged))
        csv_buffer=io.StringIO(newline='')
        writer=csv.writer(csv_buffer)
        writer.writerow(['person_id','name','bucket','suggested_qid','score','recognition_urls','review_decision','documentary_identity_url','reason_for_confirmation','expected_revision'])
        review_revisions=[(pid,rev) for pid,rev in _audit_revisions(dbpath)]
        for p in data['rows']:
            q=next((x for x in p['candidates'] if x['qid']==p['suggested_qid']),None)
            writer.writerow([p['person_id'],p['name'],p['bucket'],p['suggested_qid'] or '',
                             q['score'] if q else '', ' ; '.join(p['source_urls']), '', '', '',
                             next((revision for person_id,revision in review_revisions if person_id==p['person_id']),0)])
        z.writestr('human-review-template.csv',csv_buffer.getvalue().encode('utf-8-sig'))
    return output.getvalue()


def _csv_rows(text):
    if not isinstance(text,str) or not 1 <= len(text.encode('utf-8')) <= 55000:
        raise ValueError('Upload a reviewed CSV under 55 KB')
    source=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required={'person_id','suggested_qid','review_decision','documentary_identity_url','reason_for_confirmation','expected_revision'}
    if not required.issubset(set(source.fieldnames or [])):
        raise ValueError('Reviewed CSV must contain person_id, suggested_qid, review_decision, documentary_identity_url, reason_for_confirmation, expected_revision')
    rows=[]
    for row in source:
        choice=(row.get('review_decision') or '').strip().casefold()
        if choice not in ('','confirm'):
            raise ValueError('review_decision must be blank or confirm')
        if choice=='confirm':
            rows.append(row)
        if len(rows)>200:
            raise ValueError('Maximum 200 documented confirmations per batch')
    if not rows:
        raise ValueError('No rows marked confirm. Document evidence and set review_decision=confirm first.')
    return rows


def _validate_documented_rows(index,folder,text):
    from urllib.parse import urlparse
    rows=_csv_rows(text)
    people={p['kristal_person_id']:p for p in r._source(folder)}
    decisions=r._read_decisions(folder)
    known=_known(folder)
    ids=set();qids=set();prepared=[]
    with closing(connect(index)) as db:
        for row in rows:
            pid=(row['person_id'] or '').strip()
            qid=(row['suggested_qid'] or '').strip()
            note=(row['reason_for_confirmation'] or '').strip()
            url=(row['documentary_identity_url'] or '').strip()
            if pid not in people or not r.QID.fullmatch(qid):
                raise ValueError('Unknown roster person or invalid QID in documented CSV')
            if pid in ids or qid in qids or (qid in known and pid not in known[qid]):
                raise ValueError('Duplicate person/QID or conflict with already matched roster')
            ids.add(pid);qids.add(qid)
            if len(note)<15 or len(note)>3000:
                raise ValueError(f'Documentary justification for {pid} must be 15–3000 characters')
            parsed=urlparse(url)
            if len(url)>1500 or parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError(f'Explicit documentary HTTP(S) identity source missing for {pid}')
            if not r._candidate(db,qid)['is_human']:
                raise ValueError(f'{qid} is not verified as human P31=Q5')
            try:expected=int((row['expected_revision'] or '').strip())
            except ValueError:raise ValueError('Missing reviewed revision; download a current template')
            if expected<0:raise ValueError('Invalid negative revision')
            dec=decisions.get(pid)
            if dec and dec['decision']=='confirmed' and dec.get('qid')!=qid:
                raise ValueError('Already confirmed identity has a different QID; clear it individually first')
            prepared.append((pid,qid,note,url,expected))
    return prepared


def _audit_revisions(dbpath):
    if not dbpath.is_file():return []
    with closing(sqlite3.connect(f'{dbpath.as_uri()}?mode=ro',uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='audit'").fetchone():return []
        return [(pid,int(rev or 0)) for pid,rev in db.execute('SELECT person_id,MAX(revision) FROM audit GROUP BY person_id')]


def reviewed_csv_template(index,folder,report):
    # CSV exported by export_zip includes current per-person revision to prevent stale bulk writes.
    decisions=r._read_decisions(folder)
    history={}
    path=r._dbfile(folder)
    if path.is_file():
        with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)) as db:
            for pid,rev in db.execute('SELECT person_id,MAX(revision) FROM audit GROUP BY person_id'):
                history[pid]=int(rev or 0)
    return [(*row, history.get(row[0],0)) for row in report]


def validate_reviewed_csv(index,job,text):
    folder=r._job(index,job)
    rows=_validate_documented_rows(index,folder,text)
    return {'ready':True,'reviewed_count':len(rows),'csv_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'requires_explicit_attestation':True,
            'note':'Offline structural validation only. Source URL contents have NOT been checked by Skope.'}


def confirm_reviewed_csv(index,job,text,digest,confirmed=False):
    folder=r._job(index,job)
    if not confirmed:
        raise ValueError('Explicit reviewer attestation required to confirm documented identities')
    if digest!=hashlib.sha256(text.encode('utf-8')).hexdigest():
        raise ValueError('Reviewed CSV changed after validation; validate again')
    with r.AUDIT_LOCK:
        prepared=_validate_documented_rows(index,folder,text)
        dbpath=r._dbfile(folder)
        dbpath.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(dbpath,timeout=15)) as db:
            r._init_store(db)
            with db:
                for pid,qid,note,url,expected in prepared:
                    last=db.execute('SELECT MAX(revision) FROM audit WHERE person_id=?',(pid,)).fetchone()[0]
                    if int(last or 0)!=expected:
                        raise ValueError('Review revision changed; validate and export updated CSV first')
                    existing=db.execute('SELECT person_id FROM decisions WHERE qid=? AND decision=? AND person_id<>?',
                                        (qid,'confirmed',pid)).fetchone()
                    if existing:
                        raise ValueError('One QID already confirmed for another roster entry')
                now=_now()
                for pid,qid,note,url,expected in prepared:
                    old=db.execute('SELECT decision FROM decisions WHERE person_id=?',(pid,)).fetchone()
                    newrev=expected+1
                    db.execute('''INSERT INTO decisions VALUES(?,?,?,?,?,?,?) ON CONFLICT(person_id)
                        DO UPDATE SET decision=excluded.decision,qid=excluded.qid,note=excluded.note,
                        evidence_url=excluded.evidence_url,updated_at=excluded.updated_at,revision=excluded.revision''',
                        (pid,'confirmed',qid,note,url,now,newrev))
                    db.execute('''INSERT INTO audit(person_id,old_decision,new_decision,qid,note,evidence_url,occurred_at,revision)
                        VALUES(?,?,?,?,?,?,?,?)''',(pid,old[0] if old else None,'confirmed',qid,note,url,now,newrev))
    return {'confirmed':len(prepared),'decision_kind':'reviewer_attested_documentary_identity',
            'source_urls_checked_online':False,'canon_written':False,'source_written':False,'extraction_started':False}
