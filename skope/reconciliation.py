"""Review-only identity reconciliation for completed Catho author campaigns.

Source files and compact Wikidata index are read-only. Human decisions and the
append-only audit are stored in a separate SQLite file within the existing job.
No confirmation mutates the roster, extracted JSON or campaign QID inventory.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import threading
from urllib.parse import urlparse
import zipfile

from . import author_campaign, massive
from .db import connect, node

QID = re.compile(r'^Q[1-9][0-9]*$')
PERSON_ID = re.compile(r'^urn:kristal:catho:personne:[a-zA-Z0-9._-]{1,160}$')
MAX_SOURCE_BYTES = 8 * 1024 * 1024
AUDIT_LOCK = threading.RLock()
PRIORITY = ('docteur_eglise', 'laureat_prix_ratzinger', 'prix_ratzinger_annonce_non_remis')
STATE = {'confirmed', 'deferred', 'no_reliable_match'}


def _job(index, job):
    if not job:
        record = author_campaign.latest(index)
        job = record.get('job') if record else None
    if not job:
        raise ValueError('No author campaign found. Select a completed Catho campaign.')
    folder = massive._path(index, job)  # Strict 32-hex job ID, same D: root.
    if not (folder / 'unresolved-people.jsonl').is_file():
        raise ValueError('This job has no unresolved author roster.')
    return folder


def _source(folder):
    path = folder / 'unresolved-people.jsonl'
    if path.is_symlink() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError('Unsafe or oversized unresolved roster')
    entries = []
    ids = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row.get('kristal_person_id')
        if not isinstance(key, str) or not PERSON_ID.fullmatch(key) or key in ids:
            raise ValueError('Invalid or duplicated person ID in job evidence')
        ids.add(key)
        entries.append(row)
        if len(entries) > 20000:
            raise ValueError('Unresolved roster exceeds review safety limit')
    return entries


def _dbfile(folder):
    # Isolated Skope-owned working area, never inside the completed campaign folder.
    directory = folder.parent.parent / 'skope-reconciliation' / folder.name
    if directory.parent.is_symlink() or directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError('Unsafe reconciliation directory')
    path = directory / 'decisions.sqlite'
    if path.is_symlink():
        raise ValueError('Unsafe reconciliation database')
    return path


def _read_decisions(folder):
    path = _dbfile(folder)
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as db:
        return {row[0]: {'decision': row[1], 'qid': row[2], 'note': row[3],
                         'evidence_url': row[4], 'updated_at': row[5], 'revision': row[6]}
                for row in db.execute('SELECT person_id,decision,qid,note,evidence_url,updated_at,revision FROM decisions')}


def _priority(person):
    tags = person.get('categories') or []
    for i, cat in enumerate(PRIORITY):
        if cat in tags:
            return i
    return len(PRIORITY)


def list_people(index, job=None, query='', filter='all', offset=0, limit=40):
    folder = _job(index, job)
    people = _source(folder)
    decisions = _read_decisions(folder)
    counts = {'total': len(people), 'pending': 0, 'confirmed': 0, 'deferred': 0,
              'no_reliable_match': 0, 'ambiguous': 0, 'unmatched': 0, 'priority_pending': 0}
    for person in people:
        decision = decisions.get(person['kristal_person_id'], {}).get('decision', 'pending')
        counts[decision] += 1
        source_kind = person.get('match_status')
        if source_kind in counts:
            counts[source_kind] += 1
        if decision == 'pending' and _priority(person) < len(PRIORITY):
            counts['priority_pending'] += 1
    if not isinstance(query, str) or len(query) > 160 or filter not in ('all','pending','confirmed','deferred','no_reliable_match','priority'):
        raise ValueError('Invalid reconciliation filter')
    subset = []
    needle = query.casefold().strip()
    for person in people:
        dec = decisions.get(person['kristal_person_id'], {})
        status = dec.get('decision', 'pending')
        if filter == 'priority' and not (_priority(person) < len(PRIORITY) and status == 'pending'):
            continue
        if filter not in ('all','priority') and status != filter:
            continue
        if needle and not any(needle in str(val).casefold() for val in
                              (person.get('name',''),person['kristal_person_id'],*person.get('candidate_qids',[]))):
            continue
        subset.append({'person_id':person['kristal_person_id'], 'name':person.get('name'),
                       'categories':person.get('categories',[]), 'match_status':person.get('match_status'),
                       'candidates':person.get('candidate_qids',[]), 'decision':status,
                       'confirmed_qid':dec.get('qid'), 'priority':_priority(person)})
    subset.sort(key=lambda p:(p['decision'] != 'pending',p['priority'],str(p['name']).casefold()))
    try:
        offset,limit = int(offset),int(limit)
    except (TypeError,ValueError):
        raise ValueError('Invalid pagination')
    if not 0 <= offset <= 20000 or not 1 <= limit <= 100:
        raise ValueError('Pagination out of bounds')
    return {'job':folder.name,'counts':counts,'total_filtered':len(subset), 'offset':offset,
            'limit':limit,'people':subset[offset:offset+limit],
            'decision_store':str(_dbfile(folder)),
            'disclaimer':'Human-reviewed mapping only; no Kristal or original Wikidata changes.'}


def _person(folder, person_id):
    if not isinstance(person_id, str) or not PERSON_ID.fullmatch(person_id):
        raise ValueError('Invalid person identifier')
    return next((p for p in _source(folder) if p['kristal_person_id']==person_id),None)


def _candidate(db, qid):
    if not isinstance(qid,str) or not QID.fullmatch(qid):
        raise ValueError('Expected a Wikidata QID (Q...)')
    n = node(db, qid, lang='fr')
    if not n:
        return {'qid':qid,'exists':False,'is_human':False}
    human = db.execute('SELECT 1 FROM entity_edge WHERE subject_id=? AND property_id=31 AND target_id=5 LIMIT 1',(int(qid[1:]),)).fetchone() is not None
    # These links are contextual hints from an aggregated index, not proof of personal identity.
    occupations = []
    for row in db.execute('SELECT target_id FROM entity_edge WHERE subject_id=? AND property_id IN (106,39) LIMIT 15',(int(qid[1:]),)):
        other = node(db, 'Q'+str(int(row[0])))
        if other:
            occupations.append({'qid':other['id'],'label':other['label']})
    return {'qid':qid,'exists':True,'is_human':human,'label':n['label'],
            'description':n.get('description',''), 'aliases':n.get('aliases',{}),
            'occupations_and_positions':occupations[:12],
            'wikidata_url':'https://www.wikidata.org/wiki/'+qid}


def detail(index, job, person_id, lookup_qid=None):
    folder = _job(index, job)
    person = _person(folder, person_id)
    if person is None:
        raise ValueError('Person not found in unresolved campaign evidence')
    existing = _read_decisions(folder).get(person_id)
    requested = list(dict.fromkeys([*person.get('candidate_qids',[]), *([lookup_qid] if lookup_qid else []),
                                    *([existing['qid']] if existing and existing.get('qid') else [])]))
    if len(requested)>80:
        raise ValueError('Too many candidates; request a single QID')
    revision=existing['revision'] if existing else 0
    if existing is None:
        dbpath=_dbfile(folder)
        if dbpath.is_file():
            with closing(sqlite3.connect(f'{dbpath.as_uri()}?mode=ro',uri=True)) as local:
                row=local.execute('SELECT MAX(revision) FROM audit WHERE person_id=?',(person_id,)).fetchone()
                revision=int(row[0] or 0)
    already_matched={}
    matched_path=folder/'matched-people.jsonl'
    if matched_path.is_file() and not matched_path.is_symlink() and matched_path.stat().st_size <= MAX_SOURCE_BYTES:
        for line in matched_path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row=json.loads(line)
                qid=row.get('wikidata_qid')
                if qid in requested:
                    already_matched.setdefault(qid,[]).append({'person_id':row.get('kristal_person_id'),
                                                                  'name':row.get('name')})
    with closing(connect(index)) as db:
        candidates = [_candidate(db, q) for q in requested]
    for c in candidates:
        c['already_matched_in_campaign']=already_matched.get(c['qid'],[])
    return {'job':folder.name,'person':person,'decision':existing,'review_revision':revision,'candidates':candidates,
            'caution':'Candidate QIDs, human status, labels and occupations are discovery hints only. Confirm with external documentary evidence.'}


def _init_store(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS decisions(person_id TEXT PRIMARY KEY, decision TEXT NOT NULL,
      qid TEXT,note TEXT NOT NULL,evidence_url TEXT,updated_at TEXT NOT NULL,revision INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(event_id INTEGER PRIMARY KEY AUTOINCREMENT,
      person_id TEXT NOT NULL, old_decision TEXT,new_decision TEXT NOT NULL,qid TEXT,
      note TEXT NOT NULL,evidence_url TEXT,occurred_at TEXT NOT NULL,revision INTEGER NOT NULL);
    ''')


def save(index, job, person_id, action, qid=None, note='', evidence_url=None, confirmed=False, expected_revision=None):
    folder = _job(index, job)
    person = _person(folder, person_id)
    if person is None:
        raise ValueError('Person not present in unresolved campaign')
    if action not in (STATE | {'clear'}):
        raise ValueError('Unknown review decision')
    if confirmed is not True:
        raise ValueError('Explicit human review confirmation is required')
    if not isinstance(note,str) or len(note)>3000 or not isinstance(evidence_url,(str,type(None))):
        raise ValueError('Invalid decision note or evidence URL')
    note=note.strip();evidence_url=(evidence_url or '').strip()
    if len(evidence_url)>1500:
        raise ValueError('Evidence URL too long')
    if action=='confirmed':
        if not isinstance(qid,str) or not QID.fullmatch(qid):
            raise ValueError('Confirmed identity requires an explicit valid QID')
        if len(note)<15:
            raise ValueError('Provide a documentary justification (15+ characters)')
        uri=urlparse(evidence_url)
        if uri.scheme not in ('https','http') or not uri.hostname or uri.username or uri.password:
            raise ValueError('Provide an HTTP(S) documentary evidence URL')
        with closing(connect(index)) as db:
            if not _candidate(db,qid)['is_human']:
                raise ValueError('QID is not documented as a human (P31=Q5) in the compact index')
    else:
        qid=None
        evidence_url=None
        if action=='no_reliable_match' and len(note)<8:
            raise ValueError('State why no reliable match can currently be confirmed')
    try:
        revision=int(expected_revision)
    except (TypeError,ValueError):
        raise ValueError('Refresh the review before saving (missing revision)')
    if revision<0:
        raise ValueError('Invalid revision')
    path=_dbfile(folder)
    with AUDIT_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=15)) as db:
            _init_store(db)
            with db:
                old=db.execute('SELECT decision,revision FROM decisions WHERE person_id=?',(person_id,)).fetchone()
                # Persist monotonic revisions even across clear/re-review operations.
                last=db.execute('SELECT MAX(revision) FROM audit WHERE person_id=?',(person_id,)).fetchone()[0]
                current_rev=int(last or 0)
                if current_rev != revision:
                    raise ValueError('Review changed since loading. Refresh before saving.')
                if action=='confirmed':
                    conflict=db.execute('SELECT person_id FROM decisions WHERE qid=? AND decision=? AND person_id<>? LIMIT 1',
                                        (qid,'confirmed',person_id)).fetchone()
                    if conflict:
                        raise ValueError('This QID was already confirmed for another person; investigate duplicate roster identities before saving.')
                new_revision=current_rev+1
                now=datetime.now(timezone.utc).isoformat()
                if action=='clear':
                    db.execute('DELETE FROM decisions WHERE person_id=?',(person_id,))
                else:
                    db.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,?) ON CONFLICT(person_id) DO UPDATE SET decision=excluded.decision,qid=excluded.qid,note=excluded.note,evidence_url=excluded.evidence_url,updated_at=excluded.updated_at,revision=excluded.revision',
                               (person_id, action, qid, note, evidence_url or None, now, new_revision))
                db.execute('INSERT INTO audit(person_id,old_decision,new_decision,qid,note,evidence_url,occurred_at,revision) VALUES (?,?,?,?,?,?,?,?)',
                           (person_id,old[0] if old else None,action,qid,note,evidence_url or None,now,new_revision))
    return {'saved':True,'person_id':person_id,'decision':action,'qid':qid,
            'revision':new_revision,'job':folder.name,'canon_written':False,
            'wikidata_source_written':False}


def export(index, job):
    folder=_job(index,job)
    people=_source(folder)
    decisions=_read_decisions(folder)
    path=_dbfile(folder)
    audit=[]
    if path.is_file():
        with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)) as db:
            audit=[{'event_id':r[0],'person_id':r[1],'old_decision':r[2],
                    'new_decision':r[3],'qid':r[4],'note':r[5], 'evidence_url':r[6],
                    'occurred_at':r[7],'revision':r[8]} for r in db.execute(
                    'SELECT event_id,person_id,old_decision,new_decision,qid,note,evidence_url,occurred_at,revision FROM audit ORDER BY event_id')]
    summary=list_people(index,folder.name,limit=1)['counts']
    roster_file=folder/'unresolved-people.jsonl'
    manifest={'format':'skope.identity-reconciliation/1.0','job':folder.name,
              'source_roster_sha256':hashlib.sha256(roster_file.read_bytes()).hexdigest(),
              'exported_at':datetime.now(timezone.utc).isoformat(), 'summary':summary,
              'review_policy':'Explicit human confirmation, human P31 Q5 required; documentary URL/note; no inferred attribution',
              'writes_to_canon':False,'changes_source_json':False,
              'next_step':'Decisions are proposals; new person/work extraction requires a separate explicit workflow.'}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('decisions.jsonl',''.join(json.dumps({'person_id':p['kristal_person_id'],'name':p.get('name'),
                      'categories':p.get('categories'),'original_candidates':p.get('candidate_qids'),
                      **decisions[p['kristal_person_id']]},ensure_ascii=False)+'\n' for p in people
                      if p['kristal_person_id'] in decisions))
        z.writestr('audit.jsonl',''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in audit))
    return output.getvalue()
