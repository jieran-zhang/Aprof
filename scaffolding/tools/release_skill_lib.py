#!/usr/bin/env python3
"""Seal a new version directory, or verify an existing immutable release."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
from aprof_layout import release_module


def seal(root, source_commit, source_version):
    root = Path(root).resolve()
    target = root / 'release.json'
    if target.exists():
        raise ValueError('release already sealed; create a new version directory')
    tool = release_module(root)
    errors = tool.registry_errors(root)
    if errors:
        raise ValueError('; '.join(errors))
    registry = json.loads((root / 'skillgraph/registry.json').read_text())
    version = registry['library']['version']
    if root.name != version:
        raise ValueError('version directory and registry differ')
    runtime = tomllib.loads((root / 'runtime/pyproject.toml').read_text())['project']['version']
    graphs = {}
    for path in sorted((root / 'skillgraph/versions').iterdir()):
        if not path.is_dir():
            continue
        subprocess.run([str(root / 'tools/aprofctl'), 'graph', 'validate', '--graph', str(path)], check=True,
                       stdout=subprocess.DEVNULL)
        graphs[path.name] = tool.sha(path / 'graph.json')
    value = {'schema_version': 1, 'status': 'stable', 'release_id': f'{root.parent.name}/{version}',
             'skill_version': version, 'runtime_version': runtime, 'default_graph': 'v0002',
             'source_commit': source_commit, 'source_skill_version': source_version,
             'graphs': graphs, 'files': tool.inventory(root)}
    with target.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('seal', 'check'))
    parser.add_argument('--skill-lib', required=True, type=Path)
    parser.add_argument('--source-commit')
    parser.add_argument('--source-version')
    args = parser.parse_args()
    if args.command == 'seal':
        if not args.source_commit or not args.source_version:
            parser.error('seal requires --source-commit and --source-version')
        value = seal(args.skill_lib, args.source_commit, args.source_version)
    else:
        value = release_module(args.skill_lib).verify(args.skill_lib)
    print(json.dumps({'valid': True, 'release_id': value['release_id'], 'files': len(value['files'])}))


if __name__ == '__main__':
    main()
