#!/usr/bin/env python3
"""Install this release's runtime or expose its skills to a local host."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import venv

from release import verify


def install(root, target, with_remote=False):
    registry = verify(root)
    import json
    capabilities = json.loads((root / 'skillgraph/registry.json').read_text())
    rows = capabilities['capabilities']['core'] + capabilities['support_skills']
    if with_remote:
        rows += capabilities['capabilities']['optional_adapters']
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    for entry in rows:
        destination = target / entry['name']
        source = (root / entry['source']).resolve()
        if destination.is_symlink():
            if destination.resolve() == source:
                continue
            raise ValueError(f'another release owns {destination}; remove that link before switching')
        if destination.exists():
            raise ValueError(f'refusing to replace {destination}')
        destination.symlink_to(source, target_is_directory=True)
    return registry['release_id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, help='explicit host skills directory')
    parser.add_argument('--with-remote', action='store_true')
    parser.add_argument('--runtime', action='store_true', help='create .runtime-env and install declared dependencies')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    verify(root)
    if args.runtime:
        environment = root / '.runtime-env'
        if not environment.exists():
            venv.EnvBuilder(with_pip=True).create(environment)
        command = [str(environment / 'bin/python'), '-m', 'pip', 'install', str(root / 'runtime')]
        if args.with_remote:
            command[-1] += '[remote]'
        subprocess.run(command, check=True)
    if args.skills_dir:
        print(install(root, args.skills_dir, args.with_remote))
    if not args.runtime and not args.skills_dir:
        parser.error('choose --runtime and/or --skills-dir')


if __name__ == '__main__':
    main()
