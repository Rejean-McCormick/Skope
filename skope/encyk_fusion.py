"""Skope 1.0 candidate bridge for EncyK 0.14.0.

Reads local code and calls original, checked EncyK Skope bridge at user request.
Never turns selection inventories into canonical source records.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re

JOB = re.compile(r"^[0-9a-f]{32}$")


def _root():
    return Path(__file__).resolve().parents[1] / 'encyk'


def _bridge_file():
    return _root() / '00_system' / 'integrations' / 'skope_bridge.py'


def _load_bridge():
    path = _bridge_file()
    if not path.is_file():
        raise RuntimeError('EncyK bridge is not installed in this Skope candidate')
    spec = importlib.util.spec_from_file_location('skope_unified_encyk_bridge', str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def status():
    """Bounded existence checks. No inspection or traversal of D: data."""
    root = _root()
    data_root = Path(os.environ.get('ENCYK_DATA_ROOT', 'D:/EncyKlopedia'))
    return {
        'candidate': 'skope-1.0.0-rc.1',
        'engine_present': (root / '00_system' / 'tools' / 'scope-builder' / 'scripts' / 'run_scope_pipeline.py').is_file(),
        'bridge_present': _bridge_file().is_file(),
        'source_handoff_contract_present': (root / '00_system' / 'contracts' / 'source-evidence-handoff' / '2.0.0' / 'schema.json').is_file(),
        'data_root_present': data_root.is_dir(),
        'wikidata_index_present': (data_root / '30_working' / 'wikidata' / 'wikidata.compact.sqlite').is_file(),
        'data_root_migrated': False,
        'canonical_writes_enabled': False,
        'default_operation': 'read_only',
    }


def pull_completed_job(job: str, *, confirmed: bool = False, port: int = 8767):
    """Explicitly import a completed Skope job as NONCANONICAL EncyK intake.

    Original EncyK bridge validates the ZIP, QID ordering, completed job,
    checksums and existing receipts. No pipeline, handoff or canon write runs.
    """
    if confirmed is not True:
        raise ValueError('Explicit confirmation required before evidence intake')
    if not isinstance(job, str) or not JOB.fullmatch(job):
        raise ValueError('Invalid Skope 32-character lowercase hexadecimal job ID')
    if not isinstance(port, int) or not (1024 <= port <= 65535):
        raise ValueError('Invalid local Skope port')
    bridge = _load_bridge()
    client = bridge.SkopeClient('http://127.0.0.1:' + str(port))
    data_root = os.environ.get('ENCYK_DATA_ROOT', 'D:/EncyKlopedia')
    return bridge.pull(client, job, data_root)
