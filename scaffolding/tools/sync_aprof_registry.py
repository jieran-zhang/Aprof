#!/usr/bin/env python3
"""Maintain installation metadata; skill directories are never generated/copied."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
from aprof_layout import release_module, skill_lib


def load_registry(root):
    return json.loads((Path(root) / 'skillgraph/registry.json').read_text())


def check_artifacts(root, registry=None):
    return release_module(root).registry_errors(root)


def write_artifacts(root, registry):
    root = Path(root)
    if (root / 'release.json').exists():
        raise ValueError('cannot update a sealed release; edit a new version')
    for host in ('.codex-plugin', '.claude-plugin'):
        path = root / host / 'plugin.json'
        value = json.loads(path.read_text())
        value.update(name=registry['workflow_plugin']['name'], version=registry['library']['version'])
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'write'))
    parser.add_argument('--skill-lib', type=Path)
    args = parser.parse_args()
    root = args.skill_lib or skill_lib()
    registry = load_registry(root)
    if args.command == 'write':
        write_artifacts(root, registry)
    errors = check_artifacts(root, registry)
    if errors:
        raise SystemExit('\n'.join(errors))
    print('registry and host metadata valid; canonical skills unchanged')


if __name__ == '__main__':
    main()
