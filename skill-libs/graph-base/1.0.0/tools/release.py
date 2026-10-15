#!/usr/bin/env python3
"""Verify a self-contained release without the development checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

IGNORED = {'__pycache__', '.runtime-env', '.pytest_cache', '.git', '.cursor', 'build', 'dist', '.eggs'}


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError(f'unsafe release path: {name}')
    path = root / relative
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'release symlink: {part}')
        if part == root:
            break
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'release path escapes package: {name}')
    return path


def inventory(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if (any(part in IGNORED or part.endswith('.egg-info') for part in rel.parts)
                or path.suffix in {'.pyc', '.pyo'} or rel.as_posix() == 'release.json'):
            continue
        local(root, rel)
        if path.is_file():
            result[rel.as_posix()] = sha(path)
    return result


def registry_errors(root):
    root = Path(root)
    registry = json.loads((root / 'skillgraph/registry.json').read_text())
    errors, names, sources = [], set(), set()
    entries = [e for rows in registry['capabilities'].values() for e in rows] + registry['support_skills']
    for entry in entries:
        name, source = entry['name'], entry['source']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or name in names:
            errors.append(f'invalid or duplicate capability: {name}')
        names.add(name)
        if source in sources:
            errors.append(f'duplicate capability source: {source}')
        sources.add(source)
        try:
            path = local(root, source)
            if path.parent not in (root / 'skills', root / 'adapters') or path.name != name:
                raise ValueError(f'capability must have its canonical directory: {source}')
            text = (path / 'SKILL.md').read_text()
            if not re.search(r'^name:\s*' + re.escape(name) + r'\s*$', text, re.M):
                errors.append(f'skill frontmatter name mismatch: {name}')
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    expected = {e['name'] for e in registry['capabilities']['core'] + registry['support_skills']}
    actual = {p.name for p in (root / 'skills').iterdir() if p.is_dir() and p.name not in IGNORED}
    if actual != expected:
        errors.append('skill inventory differs from registry')
    for entry in registry['cursor_agents']:
        if not local(root, entry['source']).is_file():
            errors.append(f'missing agent: {entry["source"]}')
    version = registry['library']['version']
    for host in ('.codex-plugin', '.claude-plugin'):
        manifest = json.loads((root / host / 'plugin.json').read_text())
        if manifest['name'] != registry['workflow_plugin']['name'] or manifest['version'] != version:
            errors.append(f'{host} identity differs from registry')
    return errors


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'release.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('status') != 'stable':
        raise ValueError('expected a sealed stable release')
    actual = inventory(root)
    if actual != manifest['files']:
        changed = sorted(k for k in actual.keys() | manifest['files'].keys()
                         if actual.get(k) != manifest['files'].get(k))
        raise ValueError('release bytes differ: ' + ', '.join(changed[:12]))
    errors = registry_errors(root)
    if errors:
        raise ValueError('; '.join(errors))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    release = verify(args.root)
    print(json.dumps({'valid': True, 'release_id': release['release_id'], 'files': len(release['files'])}))


if __name__ == '__main__':
    main()
