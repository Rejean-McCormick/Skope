"""Read-only drop-in scope catalog for standalone Skope.

A catalog refresh reads the directory, but never starts a job, imports code from
profiles, or writes to any Kristal/dump. Bad JSON files are isolated per file.
"""
import json
import re
from pathlib import Path
from .scope import validate_recipe

CONFIG = Path(__file__).resolve().parents[1] / 'scopes'
FORMAT = 'skope.scope-campaign/1.0'
AUTHOR_FORMAT = 'skope.author-works-campaign/1.0'
AUTHOR_CATEGORIES = frozenset({'docteur_eglise', 'laureat_prix_ratzinger', 'prix_ratzinger_annonce_non_remis', 'commission_theologique_internationale', 'academie_pontificale_saint_thomas', 'pape'})
MAX_FILES = 256
MAX_BYTES = 256 * 1024
MAX_PASSES = 32
_IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}\Z')
_TARGET = re.compile(r'kristal-[a-z0-9][a-z0-9-]*\Z')


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON field: ' + key)
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError('Invalid JSON numeric constant: ' + value)


def _identifier(value, label):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(label + ' must be a unique lowercase identifier (letters, digits, _ or -)')
    return value


def _text(value, label, max_length=500):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(label + ' must be a nonempty string (max ' + str(max_length) + ')')
    return value.strip()


def _target(value):
    if value is None:
        return None  # generic recipe, usable with any active Kristal
    if not isinstance(value, str) or not _TARGET.fullmatch(value):
        raise ValueError('target_slug must look like kristal-botany, or be omitted for generic scopes')
    return value


def _safe_recipe(raw):
    recipe = validate_recipe(raw)
    if recipe['direction'] == 'both' or not recipe['allowed_properties']:
        raise ValueError('Batch QID collection needs one direction and explicit PIDs')
    if recipe['geography']['mode'] == 'documented_only':
        raise ValueError('documented_only is not supported by the batch collector')
    if recipe['convergence']['include']:
        raise ValueError('Scope profiles cannot silently add convergence candidates')
    return recipe


def _check_safety(safety):
    if safety is None:
        return
    if not isinstance(safety, dict):
        raise ValueError('safety must be a JSON object')
    for forbidden in ('auto_run', 'write_kristal_canon', 'write_original_dump', 'new_fast_index'):
        if forbidden in safety and safety[forbidden] is not False:
            raise ValueError('Unsafe scope profile: ' + forbidden + ' must be false')
    if safety.get('collect_qid_only', True) is not True:
        raise ValueError('Scope profiles must use QID-only collection')


def _pass(entry, file, index):
    if not isinstance(entry, dict):
        raise ValueError('Pass ' + str(index) + ' must be an object')
    ident = _identifier(entry.get('id', 'pass-' + str(index)), 'pass id')
    title = _text(entry.get('title', ident), 'pass title', 180)
    recipe = _safe_recipe(entry.get('recipe'))
    return {
        'id': ident, 'title': title,
        'priority': str(entry.get('priority', 'custom'))[:40],
        'intent': _text(entry.get('intent', 'User-defined Wikidata QID traversal'), 'intent', 1000),
        'risk': _text(entry.get('risk', 'Review root, direction, depth and volume before running.'), 'risk', 1000),
        'recipe': recipe,
    }


def _parse_profile(raw, file):
    if not isinstance(raw, dict):
        raise ValueError('Top-level JSON must be an object')
    ident = _identifier(raw.get('id', file.stem.lower()), 'profile id')
    target = _target(raw.get('target_slug'))
    title = _text(raw.get('title', file.stem.replace('-', ' ').replace('_', ' ')), 'profile title', 180)
    _check_safety(raw.get('safety'))
    if raw.get('format') == AUTHOR_FORMAT:
        if target != 'kristal-catho':
            raise ValueError('Author-works campaign currently requires kristal-catho')
        orch = raw.get('orchestration')
        if not isinstance(orch, dict) or orch.get('kind') != 'recognised_persons_to_authored_works':
            raise ValueError('Invalid recognised author-work orchestration')
        categories = orch.get('include_categories')
        if not isinstance(categories, list) or not categories or len(categories) != len(set(categories)) or not set(categories) <= AUTHOR_CATEGORIES:
            raise ValueError('Invalid or duplicate recognition category')
        if orch.get('person_roster') != 'canon/domain/personnes-reconnaissances.json' or orch.get('work_property') != 'P50':
            raise ValueError('Only read-only Catho roster and P50 authored works are supported')
        if orch.get('extraction_profile') != 'catho-recognised-authors-full-wikidata':
            raise ValueError('Unsupported extraction profile')
        if orch.get('auto_full_records') is not True:
            raise ValueError('Single-click campaign must request the verified full-record extraction')
        kind = 'author-works'
        parsed = []
    elif raw.get('format') == FORMAT:
        passes = raw.get('passes')
        if not isinstance(passes, list) or not passes or len(passes) > MAX_PASSES:
            raise ValueError('Campaign passes must contain 1..' + str(MAX_PASSES) + ' entries')
        parsed = [_pass(x, file, i + 1) for i, x in enumerate(passes)]
        kind = 'campaign'
    elif 'format' in raw:
        raise ValueError('Unsupported profile format: ' + str(raw['format'])[:120])
    else:
        # Simple recipe, optionally inside {"recipe": {...}, "title": ..., "target_slug": ...}.
        # Without target_slug, it can be used in the currently running Kristal.
        simple = raw.get('recipe', raw)
        parsed = [_pass({'id': 'main', 'title': 'Scope settings', 'recipe': simple,
                         'intent': raw.get('intent', 'Standalone scope JSON: one traversal'),
                         'risk': raw.get('risk', 'Check the target Kristal and estimate volume before running.')}, file, 1)]
        kind = 'recipe'
    keys = [entry['id'] for entry in parsed]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate pass ids')
    return {
        'format': AUTHOR_FORMAT if kind == 'author-works' else FORMAT, 'id': ident, 'title': title, 'target_slug': target,
        'state_ref': raw.get('state_ref'),
        'scope_context': str(raw.get('scope_context') or 'User-supplied scope settings')[:800],
        'notes': raw.get('notes', []) if isinstance(raw.get('notes', []), list) else [],
        'source_file': file.name, 'source_kind': kind,
        'orchestration': {'kind': 'recognised_persons_to_authored_works',
                          'include_categories': categories, 'person_roster': orch['person_roster'],
                          'work_property': 'P50', 'extraction_profile': orch['extraction_profile']} if kind == 'author-works' else None,
        'safety': {'auto_run': False, 'write_kristal_canon': False,
                   'write_original_dump': False, 'new_fast_index': False,
                   'collect_qid_only': True},
        'passes': parsed,
    }


def catalog():
    """Rescan *.json on every request; never read symlinks or files outside CONFIG."""
    profiles, errors = [], []
    if not CONFIG.is_dir() or CONFIG.is_symlink():
        return {'profiles': [], 'errors': [{'file': 'scope-profiles', 'error': 'Missing or unsafe profile directory'}],
                'count': 0, 'pass_count': 0, 'scanned_files': 0,
                'directory': 'scopes/', 'folder': str(CONFIG)}
    files = sorted(CONFIG.glob('*.json'), key=lambda p: (p.name.casefold(), p.name))
    if len(files) > MAX_FILES:
        errors.append({'file': 'scope-profiles', 'error': f'Only the first {MAX_FILES} JSON files are scanned; remove extras'})
    seen = set()
    for file in files[:MAX_FILES]:
        try:
            if file.is_symlink() or not file.is_file():
                raise ValueError('Symlinks and non-regular files are not allowed')
            if file.stat().st_size > MAX_BYTES:
                raise ValueError(f'JSON file exceeds {MAX_BYTES} bytes')
            raw = json.loads(file.read_text(encoding='utf-8-sig'),
                             object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
            info = _parse_profile(raw, file)
            if info['id'] in seen:
                raise ValueError('Duplicate profile id: ' + info['id'])
            seen.add(info['id'])
            profiles.append(info)
        except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
            errors.append({'file': file.name, 'error': str(exc)[:350]})
    return {'profiles': profiles, 'errors': errors, 'count': len(profiles),
            'pass_count': sum(len(p['passes']) for p in profiles),
            'scanned_files': len(files), 'directory': 'scopes/', 'folder': str(CONFIG)}


def all_profiles():
    """Backward-compatible list endpoint; invalid profiles never hide valid ones."""
    return catalog()['profiles']
