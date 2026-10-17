"""Local Kristal workspace selector for standalone Skope.

Discovery reads workspace manifests only. Selecting never modifies a Kristal,
starts a job, or changes an already-started campaign's captured workspace.
The optional local registry lives on C: beside Skope, not under the Kristals.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from . import project

STATE_FILE = project.TOOL / 'config' / 'kristals.local.json'
STATE_FORMAT = 'skope.local-kristals/1.0'


class KristalRegistry:
    def __init__(self, locals_root=None, state_file=None, initial_path=None):
        self.locals_root = Path(locals_root) if locals_root is not None else project.DEFAULT_LOCALS
        self.state_file = Path(state_file) if state_file is not None else STATE_FILE
        self.lock = threading.RLock()
        self.manual_paths = []
        self.active_path = None
        self._load()
        if initial_path is not None:
            path, _ = self._validate(initial_path)
            self.active_path = path

    @staticmethod
    def _validate(raw):
        if not isinstance(raw, (str, Path)) or not 1 <= len(str(raw)) <= 1024:
            raise ValueError('Enter an existing local Kristal workspace folder')
        path = Path(raw).expanduser()
        if path.is_symlink():
            raise ValueError('A symlinked Kristal folder is not accepted')
        try:
            path = path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError('Kristal folder not found') from None
        return path, project.read_kristal(path)

    @staticmethod
    def _key(path):
        # Stable opaque identifier; the browser selects a discovered entry.
        return hashlib.sha256(os.path.normcase(str(path)).encode('utf-8')).hexdigest()[:20]

    def _load(self):
        if not self.state_file.is_file() or self.state_file.is_symlink():
            return
        try:
            if self.state_file.stat().st_size > 65536:
                return
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
            if data.get('format') != STATE_FORMAT or not isinstance(data.get('paths'), list):
                return
            self.manual_paths = [str(p) for p in data['paths'][:64] if isinstance(p, str) and 0 < len(p) <= 1024]
            if isinstance(data.get('active_path'), str):
                self.active_path = data['active_path']
        except (OSError, ValueError, TypeError):
            return

    def _save(self):
        # Only on an explicit 'Select' or 'Add' action; never in GET or startup.
        if self.state_file.is_symlink():
            raise ValueError('Local Kristal settings file must not be a symlink')
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {'format': STATE_FORMAT, 'paths': self.manual_paths,
                   'active_path': str(self.active_path) if self.active_path else None}
        temp = self.state_file.with_suffix('.json.tmp')
        if temp.exists() and temp.is_symlink():
            raise ValueError('Local Kristal settings staging file must not be a symlink')
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.replace(temp, self.state_file)
        finally:
            if temp.exists():
                temp.unlink()

    def _list(self):
        found = {}
        for path, meta in project.find_kristals(self.locals_root):
            p = path.resolve()
            found[str(p)] = (p, meta)
        for raw in self.manual_paths:
            try:
                p, meta = self._validate(raw)
                found[str(p)] = (p, meta)
            except (OSError, ValueError, TypeError):
                continue  # Removed workspace: do not advertise as valid.
        if self.active_path:
            try:
                p, meta = self._validate(self.active_path)
                found[str(p)] = (p, meta)
            except (OSError, ValueError, TypeError):
                pass
        return list(found.values())

    def _active(self):
        if not self.active_path:
            return None, None
        try:
            return self._validate(self.active_path)
        except (OSError, ValueError, TypeError):
            return None, None

    def snapshot(self):
        with self.lock:
            path, meta = self._active()
            return (str(path) if path else None, project.safe_target(meta))

    def catalog(self):
        with self.lock:
            paths = self._list()
            entries = [{'id': self._key(path), 'slug': meta['slug'],
                        'title': meta['title'], 'path': str(path)} for path, meta in paths]
            entries.sort(key=lambda e: (e['title'].casefold(), e['path'].casefold()))
            path, meta = self._active()
            return {'format': 'skope.kristal-catalog/1.0',
                    'entries': entries,
                    'active_id': self._key(path) if path else None,
                    'active': project.safe_target(meta),
                    'active_path': str(path) if path else None,
                    'locals_root': str(self.locals_root)}

    def select(self, key):
        with self.lock:
            if key is None or key == '':
                self.active_path = None
            else:
                if not isinstance(key, str) or len(key) != 20:
                    raise ValueError('Select a Kristal from the discovered list')
                matches = [path for path, meta in self._list() if self._key(path) == key]
                if len(matches) != 1:
                    raise ValueError('Kristal was removed or selection is invalid; refresh the list')
                self.active_path = matches[0]
            self._save()
            return self.catalog()

    def add(self, raw):
        with self.lock:
            path, _ = self._validate(raw)
            if str(path) not in self.manual_paths and len(self.manual_paths) >= 64:
                raise ValueError('Maximum of 64 manually registered Kristals reached')
            if str(path) not in self.manual_paths:
                self.manual_paths.append(str(path))
            self.active_path = path
            self._save()
            return self.catalog()
