"""One-click, evidence-preserving recognised-person -> authored-work campaign.

Kristal roster is read ONLY. Wikidata SQLite source is read ONLY. Job results and
checkpoints live exclusively under the existing EncyK data volume (30_working).
No entity identity, attribution or doctrinal endorsement is inferred from mere
appearance on a Vatican website.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
import uuid

from . import extraction, massive, scope_profiles
from .db import connect, _wid

LOCK = threading.RLock()
RUNNING = {}
KIND = 'skope.recognised-authors/1.0'
ROSTER = 'canon/domain/personnes-reconnaissances.json'
SCOPE_FORMAT = 'skope.author-works-campaign/1.0'
QID = re.compile(r'^Q[1-9][0-9]*$')
MAX_PEOPLE = 20000
MAX_HOMONYMS = 75
MAX_WORKS = 250000  # fail closed: no silently partial evidence inventory


def _compact(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write(path, obj):
    path = Path(path)
    tmp = path.with_name(path.name + '.part')
    tmp.write_text(_compact(obj) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def _target(folder):
    if not folder:
        raise ValueError('Start Skope with --kristal pointing to the Catho workspace')
    p = Path(folder).resolve(strict=True)
    if not p.is_dir() or p.is_symlink():
        raise ValueError('Kristal directory must be a regular directory')
    from .project import read_kristal
    meta = read_kristal(p)
    if meta['slug'].lower() != 'kristal-catho':
        raise ValueError('This author campaign requires the active kristal-catho workspace')
    return p


def _profile(profile_id):
    for profile in scope_profiles.all_profiles():
        if profile['id'] == profile_id and profile.get('source_kind') == 'author-works':
            return profile
    raise ValueError('Select an installed author-works campaign JSON')


def _roster(folder, profile):
    path = _target(folder) / ROSTER
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Kristal-Catho persons/recognitions roster is missing or too large')
    contents = path.read_bytes()
    src = json.loads(contents.decode('utf-8-sig'))
    if src.get('schema_version') != 'kristal.catho.personnes-reconnaissances/1.0':
        raise ValueError('Unsupported Kristal-Catho person-roster schema')
    people = src.get('personnes')
    if not isinstance(people, list) or len(people) > MAX_PEOPLE:
        raise ValueError('Invalid or oversized people list')
    active = set(profile['orchestration']['include_categories'])
    selected = []
    ids = set()
    for person in people:
        ident = person.get('id')
        categories = person.get('categories', [])
        if not isinstance(ident, str) or not ident.startswith('urn:kristal:catho:personne:') or not isinstance(categories, list):
            raise ValueError('Invalid person identifier or recognition tags in Catho roster')
        if ident in ids:
            raise ValueError('Duplicate person identifier: ' + ident)
        ids.add(ident)
        if active.intersection(categories):
            if not person.get('nom') or not isinstance(person.get('reconnaissances'), list):
                raise ValueError('Selected person lacks name or evidence')
            selected.append(person)
    if not selected:
        raise ValueError('No recognised persons match the selected profile categories')
    return selected, _sha(contents), src


def preview(kristal_folder, profile_id):
    p = _profile(profile_id)
    people, digest, source = _roster(kristal_folder, p)
    categories = {cat: sum(cat in x['categories'] for x in people) for cat in p['orchestration']['include_categories']}
    return {'profile': p['id'], 'title': p['title'], 'people': len(people),
            'categories': categories, 'roster_sha256': digest,
            'roster_as_of': source.get('as_of'), 'roster_schema': source.get('schema_version'),
            'source_count': len(source.get('sources', [])),
            'mode': 'one_click_inventory_then_full_records',
            'target': 'kristal-catho', 'automatic_identity_guessing': False,
            'work_property': 'P50', 'out_of_scope_categories': ['pape'] if 'pape' not in categories else [],
            'limitations': [
                'Only exact unambiguous Wikidata human matches are linked automatically; ambiguous/unmatched people are reported.',
                'P50 links are Wikidata discovery assertions, not independent historical authentication of authorship.',
                'The roster contains Vatican-listed persons, not only Catholic writers or doctrinally endorsed authors.',
                'Award announced but not yet presented remains a separate category.',
                'People without indexed P50 works can still be saved, but absence of P50 does not mean no works exist.',
                'No Kristal canon or dump write. The full JSON extractor runs only after verified source preflight.'
            ]}


def _jobfolder(index, job):
    return massive._path(index, job)


def _stat(folder):
    path = folder / 'campaign-state.json'
    if not path.is_file():
        raise ValueError('Not an author-evidence campaign')
    info = json.loads(path.read_text(encoding='utf-8'))
    if info['state'] in ('matching', 'works', 'preflight') and folder.name not in RUNNING:
        info['state'] = 'interrupted'
        info['message'] = 'Skope was stopped; resume the campaign to continue.'
    return info


def status(index, job):
    folder = _jobfolder(index, job)
    with LOCK:
        info = _stat(folder)
    if info.get('extraction_job'):
        try:
            e = extraction.status(index, info['extraction_job'])
            info['extraction'] = {k: e.get(k) for k in ('job', 'state', 'processed', 'total', 'chunks', 'message', 'evidence_ready', 'evidence_path')}
            if e['state'] == 'completed':
                info['state'] = 'completed'
                info['message'] = 'Full source JSON extraction completed; unmatched people remain in report.'
            elif e['state'] in ('paused', 'failed', 'interrupted', 'missing_source_records'):
                info['state'] = e['state']
                info['message'] = 'Extraction stage: ' + e.get('message', e['state'])
            else:
                info['state'] = 'extracting'
                info['message'] = 'Extracting full Wikidata source JSON records'
        except ValueError as exc:
            info['message'] = 'Extraction status unavailable: ' + str(exc)
    return info


def _init(folder, info):
    folder.mkdir(parents=True)
    _write(folder / 'campaign-state.json', info)
    _write(folder / 'recipe.json', {
        'kind': KIND, 'root': 'multi-person-roster', 'default_depth': 1, 'geography': {'mode': 'off'},
        'max_entities': 0, 'target_slug': 'kristal-catho',
        'profile_id': info['profile'], 'roster_sha256': info['roster_sha256'],
        'work_property': 'P50', 'selection_policy': 'unique_exact_human_name',
    })
    with sqlite3.connect(folder / 'state.sqlite') as db:
        db.executescript('''
          CREATE TABLE selected(id INTEGER PRIMARY KEY);
          CREATE TABLE status(state TEXT NOT NULL,selected INTEGER NOT NULL,expanded INTEGER NOT NULL,
             pending INTEGER NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,message TEXT NOT NULL);
          CREATE TABLE people(id TEXT PRIMARY KEY,name TEXT NOT NULL,result TEXT NOT NULL,qid TEXT,
             candidates TEXT NOT NULL,evidence TEXT NOT NULL, categories TEXT NOT NULL);
          CREATE TABLE works(author_qid TEXT NOT NULL,work_qid TEXT NOT NULL,PRIMARY KEY(author_qid,work_qid));
        ''')
        now = time.time()
        db.execute('INSERT INTO status VALUES (?,?,?,?,?,?,?)', ('queued', 0, 0, info['people_total'], now, now, 'Queued'))


def _norm(name):
    v = unicodedata.normalize('NFKD', name.strip()[:160])
    v = ''.join(c for c in v if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^\w]+', ' ', v.casefold()).split())


def _match(src, person):
    # Exact normalized name/explicit variants only, indexed lookup, capped ambiguity.
    names = [person['nom'], *person.get('variantes_de_nom', [])]
    candidates = set()
    overflow = False
    for name in names[:15]:
        if not isinstance(name, str):
            continue
        key = _norm(name)
        if len(key) < 4:
            continue
        rows = src.execute('SELECT entity_id FROM name INDEXED BY idx_name_norm WHERE norm=? LIMIT ?', (key, MAX_HOMONYMS + 1)).fetchall()
        if len(rows) > MAX_HOMONYMS:
            overflow = True
        for (eid,) in rows:
            # A homonym is not a match. P31=Q5 human is required.
            if src.execute('SELECT 1 FROM entity_edge WHERE subject_id=? AND property_id=31 AND target_id=5 LIMIT 1', (eid,)).fetchone():
                candidates.add(int(eid))
    if overflow or len(candidates) > 1:
        return ('ambiguous', None, [_wid(n) for n in sorted(candidates)[:MAX_HOMONYMS]])
    if not candidates:
        return ('unmatched', None, [])
    return ('matched_exact_human', _wid(next(iter(candidates))), [])


def _update_status(db, state, message, total):
    selected = db.execute('SELECT COUNT(*) FROM selected').fetchone()[0]
    matched = db.execute("SELECT COUNT(*) FROM people WHERE result='matched_exact_human'").fetchone()[0]
    pending = max(0, total - db.execute('SELECT COUNT(*) FROM people').fetchone()[0])
    db.execute('UPDATE status SET state=?, selected=?, expanded=?,pending=?,updated_at=?,message=?',
               (state, selected, matched, pending, time.time(), message[:350]))


def _save_state(folder, **kw):
    obj = json.loads((folder / 'campaign-state.json').read_text(encoding='utf-8'))
    obj.update(kw)
    obj['updated_at'] = time.time()
    _write(folder / 'campaign-state.json', obj)


def _export(index, folder, people, src):
    with sqlite3.connect(folder/'state.sqlite') as st:
        rows = st.execute('SELECT id,name,result,qid,candidates,evidence,categories FROM people ORDER BY id').fetchall()
        works = st.execute('SELECT author_qid,work_qid FROM works ORDER BY author_qid,work_qid').fetchall()
        qids = st.execute('SELECT id FROM selected ORDER BY id').fetchall()
    resolved = {r[0]:r for r in rows}
    roster_sources = {s['id']:s for s in src.get('sources', [])}
    matched, unresolved = [], []
    for person in people:
        row = resolved[person['id']]
        evidence = [{'category': x.get('categorie'), 'relation': x.get('relation'),
                     'period': x.get('periode'), 'source_id': x.get('source_id'),
                     'source_url': roster_sources.get(x.get('source_id'), {}).get('url')}
                    for x in person['reconnaissances']]
        entry = {'kristal_person_id': person['id'], 'name': person['nom'],
                 'categories': person['categories'], 'recognitions': evidence,
                 'match_status': row[2], 'wikidata_qid': row[3],
                 'candidate_qids': json.loads(row[4]),
                 'identity_policy': 'exact_normalised_name_plus_P31_Q5; no homonym guesses'}
        (matched if row[3] else unresolved).append(entry)
    def jsonl(file, collection):
        temp = folder / (file+'.part')
        with temp.open('w', encoding='utf-8', newline='\n') as output:
            for item in collection:
                output.write(_compact(item)+'\n')
        os.replace(temp, folder / file)
    jsonl('matched-people.jsonl', matched)
    jsonl('unresolved-people.jsonl', unresolved)
    jsonl('author-work-links.jsonl', ({'author_qid':a, 'work_qid':w, 'property':'P50',
              'evidence_type':'wikidata_aggregated_index_not_source_claim'} for a,w in works))
    jsonl('selected-qids.jsonl', ({'wikidata_qid':_wid(n)} for (n,) in qids))
    payload = {'format':KIND, 'profile': _stat(folder)['profile'],
        'roster_sha256':_stat(folder)['roster_sha256'], 'roster_as_of':src.get('as_of'),
        'people_selected':len(people), 'people_matched':len(matched), 'people_unresolved':len(unresolved),
        'works_linked':len(works), 'unique_qids':len(qids),
        'categories':_stat(folder)['categories'],
        'recognition_sources': list(roster_sources.values()),
        'identity_resolution':'Unique indexed exact normalized human match only; variants considered; ambiguities withheld',
        'work_resolution':'Incoming P50 in compact SQLite, not historically authenticated attribution',
        'warnings':['Ratzinger laureates may not be Catholic; honorary award is not doctrinal endorsement',
                    'Members of CTI/Academy may be historical rather than current',
                    'Announced 2026 Ratzinger award is distinct from awarded laureates',
                    'Missing P50 is not proof of absent literary works',
                    'No canon or source modification; verify source JSON before publication']}
    _write(folder/'provenance-manifest.json', payload)
    return payload


def _worker(index, folder, stop, kristal_folder, people, roster_src):
    try:
        with closing(connect(index)) as src, sqlite3.connect(folder/'state.sqlite', timeout=30) as db:
            names_index = src.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_name_norm'").fetchone()
            if not names_index:
                raise ValueError('Missing idx_name_norm on Wikidata index; do not rebuild within Skope')
            for i, person in enumerate(people,1):
                if stop.is_set():break
                if not db.execute('SELECT 1 FROM people WHERE id=?',(person['id'],)).fetchone():
                    match, qid, candidates = _match(src,person)
                    with db:
                        db.execute('INSERT INTO people VALUES (?,?,?,?,?,?,?)',
                          (person['id'],person['nom'],match,qid,_compact(candidates),
                           _compact(person['reconnaissances']),_compact(person['categories'])))
                        if qid:
                            db.execute('INSERT OR IGNORE INTO selected VALUES (?)',(int(qid[1:]),))
                        _update_status(db,'running','Resolving official roster identities',len(people))
                    _save_state(folder, state='matching', people_processed=i,
                                matched=db.execute("SELECT COUNT(*) FROM people WHERE qid IS NOT NULL").fetchone()[0])
            if stop.is_set():
                with db:_update_status(db,'paused','Paused after person identity match',len(people))
                _save_state(folder,state='paused',message='Paused. Resume to continue identity/works.');return
            persons = db.execute('SELECT DISTINCT qid FROM people WHERE qid IS NOT NULL ORDER BY qid').fetchall()
            for n, (author,) in enumerate(persons, 1):
                if stop.is_set():break
                if db.execute('SELECT 1 FROM works WHERE author_qid=? LIMIT 1',(author,)).fetchone():
                    pass  # idempotent, but an author with 0 works will be safely re-queried on resume
                count = db.execute('SELECT COUNT(*) FROM works').fetchone()[0]
                for (work,) in src.execute('SELECT subject_id FROM entity_edge WHERE target_id=? AND property_id=50', (int(author[1:]),)):
                    if work < 1 or work >= 1_000_000_000:continue
                    if src.execute('SELECT 1 FROM entity WHERE id=?', (work,)).fetchone() is None: continue
                    if count >= MAX_WORKS:
                        raise ValueError('Work safety limit reached; campaign refused to silently truncate P50 coverage')
                    with db:
                        db.execute('INSERT OR IGNORE INTO works VALUES (?,?)',(author,_wid(work)))
                        db.execute('INSERT OR IGNORE INTO selected VALUES (?)',(work,))
                    count += 1
                with db:_update_status(db,'running','Following incoming P50 for resolved authors',len(people))
                _save_state(folder, state='works', authors_processed=n, authors_total=len(persons))
            if stop.is_set():
                with db:_update_status(db,'paused','Paused before inventory finalization',len(people))
                _save_state(folder,state='paused',message='Paused. Resume to rebuild/finish works.');return
            if not db.execute('SELECT 1 FROM selected LIMIT 1').fetchone():
                raise ValueError('No persons could be matched unambiguously; no empty evidence extraction allowed')
            manifest=_export(index,folder,people,roster_src)
            with db:_update_status(db,'completed','Completed P50 author/work inventory',len(people))
            _save_state(folder, state='preflight', selected_qids=manifest['unique_qids'],
                        unresolved=manifest['people_unresolved'], works=manifest['works_linked'],
                        message='QID inventory complete; verifying Wikidata original source before extraction')
        # Single-button pipeline: check source and start full records after inventory has been committed.
        p = _stat(folder)
        check = extraction.preflight(index, p['extraction_profile'], folder.name)
        if not check['ready']:
            _save_state(folder,state='blocked',message='Full JSON preflight blocked: '+ '; '.join(check['blockers'])[:380]);return
        job = extraction.start(index,p['extraction_profile'],folder.name,confirmed=True)
        _save_state(folder,state='extracting',extraction_job=job['job'],
                    message='Original Wikidata JSON extraction running')
    except Exception as exc:
        _save_state(folder, state='failed', message=type(exc).__name__+': '+str(exc)[:350])
        try:
            with sqlite3.connect(folder / 'state.sqlite') as db:
                with db:_update_status(db,'failed',str(exc),len(people))
        except Exception:pass
    finally:
        with LOCK: RUNNING.pop(folder.name,None)


def start(index, kristal_folder, profile_id, confirmed=False):
    if confirmed is not True:
        raise ValueError('Explicit confirmation to collect QIDs AND extract full Wikidata JSON is required')
    p = _profile(profile_id)
    if p.get('target_slug') != 'kristal-catho':
        raise ValueError('Campaign target must be kristal-catho')
    people, digest, src = _roster(kristal_folder,p)
    spec = p['orchestration']
    ext_profile = spec['extraction_profile']
    ep = extraction.load_profile(ext_profile)
    if (ep.get('target') or {}).get('write_to_canon') is not False:
        raise ValueError('Cannot write to Kristal canon')
    root = extraction._data_root(index)
    checked, blockers = extraction._check_source(ep,root)
    if blockers:
        raise ValueError('Full source preflight failed: ' + '; '.join(blockers))
    free = shutil.disk_usage(root).free
    required = int((ep['safety'].get('minimum_free_space_gib') or 20) * 1024**3)
    if free < max(required,2 * 1024**3):
        raise ValueError('Insufficient space on D: for full source evidence extraction')
    with LOCK:
        if RUNNING:
            raise ValueError('An author/work campaign is already running')
        folder = massive._folder(index) / uuid.uuid4().hex
        info = {'job': folder.name,'profile':p['id'],'kind':KIND,
            'state':'queued','people_total':len(people),'people_processed':0,
            'matched':0,'works':0,'selected_qids':0,'authors_processed':0,'authors_total':0,
            'unresolved':0,'categories':{g:sum(g in x['categories'] for x in people) for g in spec['include_categories']},
            'roster_sha256':digest,'extraction_profile':ext_profile,
            'source_verified':checked['verified'],'reader_backend':checked.get('fast_backend'),
            'message':'Queued','created_at':time.time(),'updated_at':time.time(),'extraction_job':None}
        _init(folder,info)
        stop = threading.Event()
        RUNNING[folder.name] = stop
        threading.Thread(target=_worker,args=(str(index),folder,stop,kristal_folder,people,src),
                         daemon=True,name='skope-author-'+folder.name[:8]).start()
        return status(index,folder.name)


def pause(index, job):
    folder = _jobfolder(index,job)
    info = status(index,job)
    if info.get('extraction_job'):
        return extraction.pause(index, info['extraction_job'])
    with LOCK:
        flag = RUNNING.get(job)
        if not flag:
            raise ValueError('Campaign is not actively collecting; see its status')
        flag.set()
    return {'job':job,'state':'pausing','message':'Pause requested'}


def resume(index, kristal_folder, job, confirmed=False):
    if confirmed is not True:
        raise ValueError('Explicit confirmation is required to resume source extraction')
    folder = _jobfolder(index,job)
    info = status(index,job)
    if info.get('extraction_job'):
        if info['state'] not in ('paused','failed','interrupted','missing_source_records'):
            raise ValueError('Extraction cannot be resumed from this state')
        result = extraction.start(index,info['extraction_profile'],job,info['extraction_job'],confirmed=True)
        _save_state(folder,state='extracting',message='Resumed source JSON extraction')
        return status(index,job)
    if info['state'] not in ('paused','failed','interrupted','blocked'):
        raise ValueError('Campaign cannot be resumed from this state')
    p = _profile(info['profile'])
    people,digest,roster_src = _roster(kristal_folder,p)
    if digest != info['roster_sha256']:
        raise ValueError('Kristal roster changed: cannot resume under altered identity/provenance evidence')
    if info['state']=='blocked':
        checked = extraction.preflight(index,info['extraction_profile'],job)
        if not checked['ready']:
            raise ValueError('Full source still blocked: '+ '; '.join(checked['blockers']))
        result=extraction.start(index,info['extraction_profile'],job,confirmed=True)
        _save_state(folder,state='extracting',extraction_job=result['job'],message='Full extraction started')
        return status(index,job)
    with LOCK:
        if RUNNING:
            raise ValueError('Another author campaign is currently running')
        event=threading.Event();RUNNING[job]=event
        _save_state(folder,state='queued',message='Resuming author roster and work discovery')
        threading.Thread(target=_worker,args=(str(index),folder,event,kristal_folder,people,roster_src),
                         daemon=True,name='skope-author-resume-'+job[:8]).start()
    return status(index,job)


def latest(index):
    root=massive._folder(index)
    if not root.is_dir():return None
    candidates=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
                and re.fullmatch(r'[0-9a-f]{32}',p.name) and (p/'campaign-state.json').is_file()]
    if not candidates:return None
    return status(index,max(candidates,key=lambda p:p.stat().st_mtime).name)
