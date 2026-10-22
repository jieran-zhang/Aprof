#!/usr/bin/env python3
"""Install this release's runtime or expose its skills to a local host."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import venv

from release import verify, verify_unsealed, registry_path


def install(root, target, allow_unsealed=False):
    root = Path(root).resolve()
    registry = verify_unsealed(root) if allow_unsealed else verify(root)
    import json
    capabilities = json.loads(registry_path(root).read_text())
    rows = capabilities['capabilities']['core'] + capabilities['support_skills']
    target = Path(target).resolve()
    if target.is_relative_to(root):
        raise ValueError('host skills directory must be outside the complete source package')
    links = []
    for entry in rows:
        destination = target / entry['name']
        source = (root / entry['source']).resolve()
        if destination.is_symlink():
            if destination.resolve() == source:
                continue
            raise ValueError(f'another release owns {destination}; remove that link before switching')
        if destination.exists():
            raise ValueError(f'refusing to replace {destination}')
        links.append((destination, source))
    target.mkdir(parents=True, exist_ok=True)
    for destination, source in links:
        destination.symlink_to(source, target_is_directory=True)
    return registry['release_id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, help='explicit host skills directory')
    parser.add_argument('--runtime', action='store_true', help='create .runtime-env and install declared dependencies')
    parser.add_argument('--allow-unsealed', action='store_true',
                        help='explicitly install a development package after structural checks only')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # Bootstrap declared parser dependencies before importing the knowledge runtime.
    verifier = verify_unsealed if args.allow_unsealed else verify
    checked = verifier(root, check_knowledge=not args.runtime)
    if args.runtime:
        environment = root / '.runtime-env'
        if not environment.exists():
            venv.EnvBuilder(with_pip=True).create(environment)
        command = [str(environment / 'bin/python'), '-m', 'pip', 'install', str(root / 'runtime')]
        subprocess.run(command, check=True)
        if args.skills_dir:
            command = [str(environment / 'bin/python'), str(root / 'tools/install.py'), '--skills-dir', str(args.skills_dir)]
        else:
            command = [str(environment / 'bin/python'), str(root / 'tools/release.py')]
        if args.allow_unsealed:
            command.append('--allow-unsealed')
        subprocess.run(command, check=True)
        return
    if args.skills_dir:
        print(install(root, args.skills_dir, allow_unsealed=args.allow_unsealed))
        print(f'Keep the complete source package at {root}; installed skills are symbolic links.')
    if not args.runtime and not args.skills_dir:
        parser.error('choose --runtime and/or --skills-dir')
    if checked['status'] == 'unsealed':
        print('Unsealed development package installed; publication and default selection are unchanged.')


if __name__ == '__main__':
    main()
