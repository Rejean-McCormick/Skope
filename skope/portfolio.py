"""Native Skope portfolio enrichment for draft Kristal Framework v11 snapshots.

A portfolio run is a *working* store, not a canonical Kristal publication.
Skope discovers candidates and collects full Wikidata evidence; a reviewed
crosswalk is required before per-Kristal claim proposals are generated.
The existing EncyK compact index remains read-only throughout.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import unicodedata
import zipfile

from . import db as encyk

FORMAT = 'skope.portfolio/0.15.0'
PROPOSAL = 'skope.portfolio-wikidata-claim-proposal/1.0'
QID = re.compile(r'^Q[1-9][0-9]*$')
PID = re.compile(r'^P[1-9][0-9]*$')
SEM = re.compile(r'^K[QP][1-9][0-9]*$')
FIELDS = ('project','namespace','semantic_id','kind','language','label','source')
REVIEW_FIELDS = ('project','namespace','semantic_id','kind','language','label','source',
                 'candidate_external_id','candidate_label','candidate_description',
                 'match_quality','review_decision','reviewer','documentary_evidence','reason')


def _j(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _sha_file(file):
    h = hashlib.sha256()
    with Path(file).open('rb') as stream:
        for block in iter(lambda: stream.read(2 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.part')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        f.write(content)
    os.replace(tmp, path)


def _norm(s):
    value = unicodedata.normalize('NFKD', str(s).casefold())
    return ' '.join(re.sub(r'[^\w]+', ' ', ''.join(c for c in value if not unicodedata.combining(c))).split())


def _source(source):
    """Yield (project, relative file, decoded dictionary); does not extract source."""
    source = Path(source)
    marker = '/.kristal/v11/dictionaries/'
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            names = sorted(n for n in z.namelist() if not n.endswith('/'))
            projects = sorted({n.split('/', 1)[0] for n in names if n.endswith('/.kristal/v11/dik.project.json')})
            for project in projects:
                yield project, '', None
            for name in names:
                if (marker not in name or not name.endswith('.json') or name.endswith('/catalog.json')):
                    continue
                pp = PurePosixPath(name)
                if pp.is_absolute() or '..' in pp.parts or len(pp.parts) < 5 or name.split('/', 1)[0] not in projects:
                    continue
                info = z.getinfo(name)
                if info.file_size > 12 * 1024 * 1024:
                    raise ValueError('Dictionary file too large: ' + name)
                yield name.split('/', 1)[0], name, json.loads(z.read(name))
    elif source.is_dir():
        roots = ([source] if (source / '.kristal/v11/dik.project.json').is_file()
                 else sorted(p for p in source.iterdir() if p.is_dir() and not p.is_symlink()
                             and (p / '.kristal/v11/dik.project.json').is_file()))
        for root in roots:
            yield root.name, '', None
            folder = root / '.kristal/v11/dictionaries'
            for p in sorted(folder.glob('*.json')):
                if p.name == 'catalog.json' or p.is_symlink():
                    continue
                if p.stat().st_size > 12 * 1024 * 1024:
                    raise ValueError('Dictionary file too large: ' + str(p))
                yield root.name, str(p.relative_to(root)), json.loads(p.read_text(encoding='utf-8'))
    else:
        raise ValueError('Input must be a v11 portfolio directory or ZIP')


def _digest_source(source):
    p = Path(source)
    if p.is_file():
        return _sha_file(p)
    h = hashlib.sha256()
    for file in sorted(p.rglob('*')):
        if file.is_file() and not file.is_symlink() and ('.kristal/v11/' in file.as_posix() or file.name == 'dik.project.json'):
            h.update(str(file.relative_to(p)).encode())
            h.update(_sha_file(file).encode())
    return h.hexdigest()


def _init(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS project (slug TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS lexeme (
            project TEXT NOT NULL, namespace TEXT NOT NULL, semantic_id TEXT NOT NULL,
            kind TEXT NOT NULL, language TEXT NOT NULL, label TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY(project,namespace,semantic_id,language,label));
        CREATE TABLE IF NOT EXISTS query_cache (
            language TEXT NOT NULL, normalized TEXT NOT NULL, kind TEXT NOT NULL,
            hits_json TEXT NOT NULL, PRIMARY KEY(language,normalized,kind));
        CREATE TABLE IF NOT EXISTS tentative (
            namespace TEXT NOT NULL, semantic_id TEXT NOT NULL, external_id TEXT NOT NULL,
            reason TEXT NOT NULL, PRIMARY KEY(namespace,semantic_id));
        CREATE TABLE IF NOT EXISTS approved (
            namespace TEXT NOT NULL, semantic_id TEXT NOT NULL, external_id TEXT NOT NULL,
            reviewer TEXT NOT NULL, documentary_evidence TEXT NOT NULL,
            reason TEXT NOT NULL, PRIMARY KEY(namespace,semantic_id));
    ''')


def _set(c, key, value):
    c.execute('INSERT OR REPLACE INTO setting VALUES (?,?)', (key, str(value)))


def _get(c, key):
    row = c.execute('SELECT value FROM setting WHERE key=?', (key,)).fetchone()
    return row[0] if row else None


def _open(work):
    path = Path(work) / 'portfolio.sqlite'
    if not path.is_file():
        raise ValueError('No portfolio state. Run: skope portfolio inventory ...')
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    if _get(c, 'format') != FORMAT:
        c.close()
        raise ValueError('Incompatible Skope portfolio format')
    return c


def status(work):
    with closing(_open(work)) as c:
        getnum = lambda sql: c.execute(sql).fetchone()[0]
        return {'format': FORMAT, 'source_sha256': _get(c, 'source_sha256'),
                'index_identity': _get(c, 'index_identity'),
                'projects': getnum('SELECT COUNT(*) FROM project'),
                'lexemes': getnum('SELECT COUNT(*) FROM lexeme'),
                'distinct_concepts': getnum('SELECT COUNT(*) FROM (SELECT DISTINCT namespace,semantic_id FROM lexeme)'),
                'cached_queries': getnum('SELECT COUNT(*) FROM query_cache'),
                'approved_identity_proposals': getnum('SELECT COUNT(*) FROM approved'),
                'tentative_unverified_mappings': getnum('SELECT COUNT(*) FROM tentative'),
                'canonical_write_authorized': False}


def inventory(source, work, include_metadata=False):
    """Initialize native Skope state from v11 ZIP or folders; unchanged input may rerun."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    digest = _digest_source(source)
    state = work / 'portfolio.sqlite'
    if state.exists():
        current = status(work)
        with closing(sqlite3.connect(state)) as check:
            with_metadata = bool(int(_get(check, 'include_metadata') or '0'))
        if current['source_sha256'] != digest or with_metadata != bool(include_metadata):
            raise ValueError('Portfolio source/options changed: use a NEW working folder')
        return current
    temporary = state.with_name(state.name + '.part')
    if temporary.exists():
        raise ValueError('Incomplete portfolio inventory staging file; move it aside before retry')
    try:
        with closing(sqlite3.connect(temporary)) as c:
            _init(c)
            _set(c, 'format', FORMAT)
            _set(c, 'source_sha256', digest)
            _set(c, 'include_metadata', int(include_metadata))
            for project, filename, data in _source(source):
                c.execute('INSERT OR IGNORE INTO project VALUES (?)', (project,))
                if not isinstance(data, dict):
                    continue
                if data.get('artifact_type') != 'kristal_curated_dictionary':
                    continue
                basename = PurePosixPath(filename).name
                if not include_metadata and basename.startswith('metadata-'):
                    continue
                locale = data.get('language')
                namespace = data.get('namespace_id')
                if locale not in ('fr','en') or not isinstance(namespace, str) or not namespace:
                    continue
                for entry in data.get('entries', []):
                    sid, term = entry.get('semantic_id'), entry.get('preferred_term')
                    if (not isinstance(sid, str) or not SEM.fullmatch(sid) or not isinstance(term, str)
                            or not 1 <= len(term.strip()) <= 120 or not _norm(term)):
                        continue
                    c.execute('INSERT OR IGNORE INTO lexeme VALUES (?,?,?,?,?,?,?)',
                              (project,namespace,sid,'entity' if sid.startswith('KQ') else 'property',
                               locale,term.strip(),filename))
            c.commit()
        os.replace(temporary, state)
    except Exception:
        if temporary.exists(): temporary.unlink()
        raise
    summary = status(work)
    _write(work / 'inventory.json', _j(summary) + '\n')
    return summary


def _check_index(c, index_meta, index_path):
    digest = str(index_meta.get('source_snapshot_digest') or '')
    identity = _j({'index_path':str(Path(index_path).resolve()), 'source_snapshot_digest':digest,
                   'processed_entities':str(index_meta.get('processed_entities',''))})
    previous = _get(c, 'index_identity')
    if previous and previous != identity:
        raise ValueError('Index/source snapshot changed: start a NEW portfolio working folder')
    if not previous:
        _set(c, 'index_identity', identity)
    return identity


def discover(work, index, max_queries=1000, limit=8):
    """Bounded/restartable search against Skope EncyK compact index, NEVER autoapprove."""
    if not 1 <= max_queries <= 500_000 or not 1 <= limit <= 30:
        raise ValueError('Invalid query budget')
    with closing(_open(work)) as c, closing(encyk.connect(index)) as r:
        _check_index(c, encyk.meta(r), index)
        # SELECT DISTINCT avoids duplicate index lookups for the same label across Kristals.
        rows = c.execute('''SELECT DISTINCT language,label,kind FROM lexeme
            ORDER BY language,kind,label''')
        seen = set()
        done = 0
        for x in rows:
            language, label, kind = x
            key = (language, _norm(label), kind)
            if key in seen:
                continue
            seen.add(key)
            if c.execute('SELECT 1 FROM query_cache WHERE language=? AND normalized=? AND kind=?',key).fetchone():
                continue
            if done >= max_queries:
                break
            prefix = 'Q' if kind == 'entity' else 'P'
            found = [item for item in encyk.find(r, label, limit=limit) if item['id'].startswith(prefix)]
            c.execute('INSERT INTO query_cache VALUES (?,?,?,?)',(*key,_j(found)))
            done += 1
            if done % 100 == 0:
                c.commit()
        c.commit()
    result = status(work)
    result['new_queries'] = done
    result['match_policy'] = 'unverified_candidates_only'
    return result



def suggest_drafts(work):
    """Optional draft-only bounded exact-label candidate selection, NEVER exactMatch.

    No A-Kristal receives an automated mapping, even with this option.
    Ambiguous names and collisions within the same namespace are skipped.
    """
    with closing(_open(work)) as c:
        groups=defaultdict(list)
        for row in c.execute('SELECT * FROM lexeme ORDER BY namespace,semantic_id,language'):
            r=dict(row)
            if r['project'].casefold().startswith('a-kristal'):
                continue
            groups[(r['namespace'],r['semantic_id'])].append(r)
        selected={}
        ambiguous=0;incomplete=0
        for key,lexemes in groups.items():
            if c.execute('SELECT 1 FROM approved WHERE namespace=? AND semantic_id=?',key).fetchone():
                continue
            ids=set();viable=0
            for entry in lexemes:
                normal=_norm(entry['label'])
                if len(normal)<4 or not any(x.isalpha() for x in normal):
                    continue
                matched=c.execute('SELECT hits_json FROM query_cache WHERE language=? AND normalized=? AND kind=?',
                                  (entry['language'],normal,entry['kind'])).fetchone()
                if not matched:
                    continue
                viable+=1
                ids.update(hit['id'] for hit in json.loads(matched[0]) if _norm(hit.get('label',''))==normal
                           and hit['id'].startswith('Q' if entry['kind']=='entity' else 'P'))
            if not viable:
                incomplete+=1
            elif len(ids)!=1:
                ambiguous+=1
            else:
                selected[key]=next(iter(ids))
        # A single external ID inside a namespace cannot silently merge two KQ or KP.
        reverse=defaultdict(set)
        for (ns,sid),external in selected.items():
            reverse[(ns,external)].add(sid)
        candidates={key:value for key,value in selected.items() if len(reverse[(key[0],value)])==1}
        removed_collisions=len(selected)-len(candidates)
        c.execute('DELETE FROM tentative')
        for (ns,sid),external in candidates.items():
            c.execute('INSERT INTO tentative VALUES (?,?,?,?)',
                      (ns,sid,external,'Single normalized preferred-label hit among bounded search candidates; NOT a verified Wikidata identity'))
        c.commit()
    return {'format':'skope.portfolio-draft-suggestions/1.0',
            'tentative_unverified':len(candidates),'ambiguous_or_no_unique_exact_match':ambiguous,
            'unqueried_or_no_search_index':incomplete,'collisions_excluded':removed_collisions,
            'a_kristals_auto_selected':0,'exact_match_approved':0,
            'warning':'Draft proposals can drive evidence retrieval only with explicit --include-draft; never publish as exactMatch.'}


def _mappings(c, include_draft):
    result={}
    for row in c.execute('SELECT * FROM approved'):
        r=dict(row);r['identity_status']='review_attested';result[(r['namespace'],r['semantic_id'])]=r
    if include_draft:
        for row in c.execute('SELECT * FROM tentative'):
            r=dict(row);r['identity_status']='lexical_only_unverified'
            result.setdefault((r['namespace'],r['semantic_id']),r)
    return list(result.values())


def export_review(work, destination):
    """Human review CSV, one candidate per line. Never automatically confirms identity."""
    with closing(_open(work)) as c:
        rows = c.execute('''SELECT project,namespace,semantic_id,kind,language,label,source
            FROM lexeme ORDER BY project,namespace,semantic_id,language,label''')
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.part')
        total = 0
        with temp.open('w',encoding='utf-8-sig',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            for x in rows:
                row = dict(x)
                key = (x['language'],_norm(x['label']),x['kind'])
                match = c.execute('SELECT hits_json FROM query_cache WHERE language=? AND normalized=? AND kind=?',key).fetchone()
                hits = json.loads(match[0]) if match else []
                for hit in (hits or [{}]):
                    hit_label=hit.get('label','')
                    writer.writerow({**row,'candidate_external_id':hit.get('id',''),
                        'candidate_label':hit_label,'candidate_description':hit.get('description',''),
                        'match_quality':('exact_name_only' if _norm(hit_label)==_norm(row['label']) else 'other_candidate') if hit else 'no_candidate',
                        'review_decision':'unverified','reviewer':'','documentary_evidence':'','reason':''})
                    total += 1
        os.replace(temp,path)
    return {'review_file':str(path), 'rows':total, 'all_candidates_unverified':True}


def approve_review(work, review_csv):
    """Import independently documented decisions; do not modify diK crosswalks."""
    decisions = {}
    with Path(review_csv).open('r',encoding='utf-8-sig',newline='') as stream, closing(_open(work)) as c:
        for row in csv.DictReader(stream):
            if row.get('review_decision') != 'confirm':
                continue
            key = (row.get('namespace',''),row.get('semantic_id',''))
            external = row.get('candidate_external_id','')
            if (not SEM.fullmatch(key[1]) or not key[0] or not
                ((key[1].startswith('KQ') and QID.fullmatch(external)) or
                 (key[1].startswith('KP') and PID.fullmatch(external)))):
                raise ValueError('Invalid confirmed external mapping: ' + str(key))
            if not all(row.get(x,'').strip() for x in ('reviewer','documentary_evidence','reason')):
                raise ValueError('Confirmed identity requires reviewer, evidence and reason')
            lex = c.execute('''SELECT language,label,kind FROM lexeme
              WHERE namespace=? AND semantic_id=?''',key).fetchall()
            if not lex:
                raise ValueError('Confirmed identity not in this portfolio: '+str(key))
            candidates = set()
            for entry in lex:
                found = c.execute('SELECT hits_json FROM query_cache WHERE language=? AND normalized=? AND kind=?',
                                  (entry['language'],_norm(entry['label']),entry['kind'])).fetchone()
                if found:
                    candidates.update(x['id'] for x in json.loads(found[0]))
            if external not in candidates:
                raise ValueError('Unlisted ID: independent manual IDs need an explicit future review import, not a search approval')
            content = (key[0],key[1],external,row['reviewer'].strip(),row['documentary_evidence'].strip(),row['reason'].strip())
            if key in decisions and decisions[key][2] != external:
                raise ValueError('Conflicting approvals for same scoped Kristal identity')
            decisions[key] = content
        for record in decisions.values():
            old = c.execute('SELECT external_id FROM approved WHERE namespace=? AND semantic_id=?',record[:2]).fetchone()
            if old and old['external_id'] != record[2]:
                raise ValueError('Approved mapping already exists with different external ID')
        for record in decisions.values():
            c.execute('INSERT OR REPLACE INTO approved VALUES (?,?,?,?,?,?)',record)
        c.commit()
    return {'reviewed_mapping_proposals':len(decisions),'canonical_changed':False,
            'crosswalk_changed':False,'next':'skope portfolio export-seeds'}


def export_seeds(work, destination, include_draft=False):
    """Exact sorted QID inventory for Skope full-record acquisition; NOT a fake completed job."""
    with closing(_open(work)) as c:
        mappings=sorted(_mappings(c,include_draft),key=lambda x:(x['namespace'],x['semantic_id']))
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    _write(dest / 'reviewed-mappings.jsonl', ''.join(_j(x)+'\n' for x in mappings))
    qids = sorted({m['external_id'] for m in mappings if m['external_id'].startswith('Q')},key=lambda x:int(x[1:]))
    _write(dest / 'portfolio-selected-qids.jsonl', ''.join(_j({'wikidata_qid':x})+'\n' for x in qids))
    manifest={'format':'skope.portfolio-extraction-intent/1.0','source_portfolio':status(work)['source_sha256'],
              'reviewed_mappings':sum(x['identity_status']=='review_attested' for x in mappings),
              'tentative_unverified_mappings':sum(x['identity_status']=='lexical_only_unverified' for x in mappings),
              'distinct_qids':len(qids),
              'qid_inventory_sha256':_sha_file(dest/'portfolio-selected-qids.jsonl'),
              'source_index_identity':status(work)['index_identity'],
              'claim':'Reviewed and/or explicitly tentative QID seeds; raw Wikidata not yet extracted',
              'canonical_write_authorized':False}
    _write(dest/'extraction-intent.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


def _evidence_files(source):
    """Accept an immutable Skope extraction snapshot, or a standalone development JSONL.

    Production evidence snapshot chunks are SHA-256 checked before use.
    """
    p=Path(source)
    if p.is_dir():
        manifest_file=p/'snapshot-manifest.json'
        if not manifest_file.is_file():
            raise ValueError('Expected completed Skope extraction snapshot with snapshot-manifest.json')
        manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
        if not isinstance(manifest.get('parts'),list) or not manifest.get('source_sha1'):
            raise ValueError('Incomplete Skope evidence snapshot manifest')
        for part in manifest['parts']:
            name=part['file']
            if Path(name).name != name or not name.endswith('.jsonl.gz'):
                raise ValueError('Unsafe evidence part')
            file=p/name
            if not file.is_file() or _sha_file(file) != part['sha256']:
                raise ValueError('Evidence checksum mismatch: '+name)
            yield file, 'skope_manifest_chunks_checked_source_declared', str(manifest['source_sha1'])
    elif p.is_file() and (p.name.endswith('.jsonl.gz') or p.name.endswith('.jsonl')):
        yield p, 'unverified_standalone_fixture', ''
    else:
        raise ValueError('Expected Skope evidence snapshot or JSONL/JSONL.GZ fixture')


def propose(work, evidence, destination, max_claims=1_000_000, include_draft=False):
    """Project entire raw Wikidata statements into *proposals*, without inventing KP or writing a canon."""
    if max_claims < 1:
        raise ValueError('max_claims must be positive')
    with closing(_open(work)) as c:
        rows=_mappings(c,include_draft)
        subjects=defaultdict(list)
        properties={}
        for row in rows:
            r=dict(row)
            if r['semantic_id'].startswith('KQ'):
                subjects[r['external_id']].append(r)
            else:
                properties[(r['namespace'],r['external_id'])]=r['semantic_id']
    target=Path(destination)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_name(target.name + '.part')
    count=0;entities=0;relations=set();byproject=Counter();found_qids=set()
    try:
        with tmp.open('w',encoding='utf-8') as out:
            for file,trust,source_sha1 in _evidence_files(evidence):
                opener=gzip.open if file.name.endswith('.gz') else open
                with opener(file,'rt',encoding='utf-8') as stream:
                    for line in stream:
                        if not line.strip():
                            continue
                        entity=json.loads(line)
                        qid=entity.get('id')
                        if not QID.fullmatch(str(qid)):
                            raise ValueError('Raw evidence requires valid Wikidata entity QID')
                        if qid not in subjects:
                            continue
                        entities+=1;found_qids.add(qid)
                        raw_claims=entity.get('claims') or {}
                        if not isinstance(raw_claims,dict):
                            raise ValueError('Invalid Wikidata claims structure for '+qid)
                        for p,claims in sorted(raw_claims.items()):
                            if not PID.fullmatch(p) or not isinstance(claims,list):
                                raise ValueError('Invalid Wikidata property claims for '+qid)
                            for claim in claims:
                                if not isinstance(claim,dict):
                                    raise ValueError('Invalid statement object')
                                for subject in subjects[qid]:
                                    if count >= max_claims:
                                        raise ValueError('Maximum proposal budget reached; rerun with a higher bound')
                                    namespace=subject['namespace']
                                    # This is the exact source statement, not an approximate EncyK edge.
                                    proposal={'format':PROPOSAL,
                                        'namespace':namespace,'semantic_subject':subject['semantic_id'],
                                        'wikidata_subject':qid,'wikidata_property':p,
                                        'semantic_property':properties.get((namespace,p)),
                                        'wikidata_statement_id':claim.get('id'),
                                        'rank':claim.get('rank','normal'),
                                        'identity_status':subject['identity_status'],
                                        'full_source_claim':claim,
                                        'normalized_entity_sha256':hashlib.sha256(_j(entity).encode('utf8')).hexdigest(),
                                        'source_sha1':source_sha1,'source_trust':trust,
                                        'action':'review_wikidata_evidence_not_canonical_assertion',
                                        'publication_authorized':False}
                                    out.write(_j(proposal)+'\n')
                                    count+=1;byproject[namespace]+=1
                                val=((claim.get('mainsnak') or {}).get('datavalue') or {}).get('value')
                                target_q=val.get('id') if isinstance(val,dict) else None
                                if isinstance(target_q,str) and QID.fullmatch(target_q):
                                    relations.add(target_q)
        os.replace(tmp,target)
    finally:
        if tmp.exists():
            tmp.unlink()
    related=sorted(relations - found_qids,key=lambda x:int(x[1:]))
    _write(target.with_name(target.stem+'.related-qids.jsonl'),
           ''.join(_j({'wikidata_qid':x,'status':'discovery_seed_not_approved'})+'\n' for x in related))
    report={'format':'skope.portfolio-proposal-report/1.0','review_proposals':count,
            'raw_subject_entities':entities,'related_unapproved_qids':len(related),
            'proposals_by_namespace':dict(byproject),'canonical_changed':False,
            'full_claims_included':True,'note':'Full statements are evidence proposals, not Framework v11 KA assertions. Review and diK/Authoring Kit publication remain separate.'}
    _write(target.with_name(target.stem+'.report.json'),json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report


def acquire(work, index, profile_id, destination, batch_size=200, max_batches=None, include_draft=False):
    """Acquire full raw Wikidata for approved KQ->Q via Skope's VERIFIED fast locator.

    Uses source verification and random-access backend from existing Skope
    extraction, but takes a portfolio-native reviewed QID inventory. Results
    are immutable-style chunked Skope evidence, resumed at verified chunks.
    Does NOT start a Skope massive-scope campaign or scan an entire dump.
    """
    from . import extraction
    if not 1 <= batch_size <= 2000 or (max_batches is not None and max_batches < 1):
        raise ValueError('Invalid batch controls')
    with closing(_open(work)) as c:
        qids = sorted({r['external_id'] for r in _mappings(c,include_draft) if r['semantic_id'].startswith('KQ')},
                      key=lambda x: int(x[1:]))
    if not qids:
        raise ValueError('No reviewed QID seeds; import reviewed identity decisions first')
    # Existing production Skope source profile checks are reused in full.
    profile = extraction.load_profile(profile_id)
    root = extraction._data_root(index)
    source, blockers = extraction._check_source(profile, root)
    if blockers or not source.get('verified') or not source.get('random_access_ready'):
        raise ValueError('Verified Skope random-access source not ready: ' + '; '.join(blockers))
    state_key = _j({'source_sha1':source['sha1'], 'qids':qids, 'batch_size':batch_size,
                    'profile':profile_id,'include_draft':include_draft,'profile_sha256':hashlib.sha256(_j(profile).encode()).hexdigest()})
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    config = dest / 'portfolio-extraction-state.json'
    if config.is_file():
        saved = json.loads(config.read_text(encoding='utf-8'))
        if saved.get('config') != state_key:
            raise ValueError('Cannot reuse evidence directory with a different source/selection/batch size')
    elif any(dest.iterdir()):
        raise ValueError('Evidence directory has unrelated files; choose a new output directory')
    else:
        _write(config, _j({'format':'skope.portfolio-acquisition/1.0','config':state_key,
                          'selected_qids':len(qids)})+'\n')
    common = extraction._module()
    dump = Path(source['dump'])
    parts=[];new_batches=0
    for offset in range(0,len(qids),batch_size):
        index_batch=offset//batch_size
        chunk=qids[offset:offset+batch_size]
        name=f'part-{index_batch:06d}.jsonl.gz'
        piece=dest/name
        manifest_path=dest/f'part-{index_batch:06d}.manifest.json'
        if piece.is_file() and manifest_path.is_file():
            meta=json.loads(manifest_path.read_text(encoding='utf-8'))
            if meta.get('qids')!=chunk or meta.get('sha256')!=_sha_file(piece) or meta.get('source_sha1')!=source['sha1']:
                raise ValueError('Corrupted resumed Wikidata evidence chunk: '+name)
        elif piece.exists() or manifest_path.exists():
            raise ValueError('Incomplete evidence chunk: '+name)
        else:
            if max_batches is not None and new_batches>=max_batches:
                break
            values=common.fast_fetch_raw(root,dump,chunk,threads=min(8, int(profile['extraction'].get('workers',1))))
            missing=[q for q in chunk if q not in values]
            if missing:
                raise ValueError('Verified source does not contain '+str(len(missing))+' QIDs; no scan fallback')
            temp=dest/(name+'.part')
            try:
                records=[]
                with temp.open('wb') as file:
                    with gzip.GzipFile(fileobj=file,filename='',mode='wb',mtime=0,compresslevel=6) as stream:
                        for qid in chunk:
                            raw=values[qid]
                            entity=json.loads(raw)
                            if entity.get('id')!=qid:
                                raise ValueError('Raw full-entity ID mismatch: '+qid)
                            stream.write(raw.rstrip(b'\n')+b'\n')
                            records.append({'wikidata_qid':qid,'sha256':hashlib.sha256(raw).hexdigest()})
                os.replace(temp,piece)
            finally:
                if temp.exists():temp.unlink()
            meta={'file':name,'qids':chunk,'count':len(chunk),'sha256':_sha_file(piece),
                  'source_sha1':source['sha1'],'records':records}
            _write(manifest_path,_j(meta)+'\n')
            new_batches+=1
        parts.append({'file':name,'sha256':meta['sha256'],'count':len(chunk),
                      'manifest_file':manifest_path.name})
    complete=sum(x['count'] for x in parts)==len(qids)
    if complete:
        manifest={'format':'skope.portfolio-full-evidence/1.0',
                  'source_sha1':source['sha1'],'profile_id':profile_id,
                  'inventory_sha256':hashlib.sha256(''.join(q+'\n' for q in qids).encode()).hexdigest(),
                  'record_count':len(qids),'parts':parts,
                  'full_original_wikidata_json':True,'canonical_write_authorized':False}
        published=dest/'snapshot-manifest.json'
        if published.is_file():
            if json.loads(published.read_text(encoding='utf-8'))!=manifest:
                raise ValueError('Completed evidence manifest has changed')
        else:
            _write(published,json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return {'format':'skope.portfolio-acquisition-status/1.0','state':'completed' if complete else 'paused',
            'qids_total':len(qids),'qids_acquired':sum(x['count'] for x in parts),
            'new_batches':new_batches,'output':str(dest),'raw_source_verified_by_skope':True,'includes_unverified_draft_seeds':include_draft,
            'canonical_changed':False}
