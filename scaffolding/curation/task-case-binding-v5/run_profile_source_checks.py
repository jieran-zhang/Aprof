#!/usr/bin/env python3
"""Test only the collector serialization patch against unchanged 0.5.1 runtime."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = REPO / 'skill-libs/graph-base/0.5.1'


def main():
    with tempfile.TemporaryDirectory(prefix='aprof-profile-source-canonical-') as directory:
        release = Path(directory)
        for relative in ('runtime/src', 'skills/ascendc-aprof-profiling/scripts',
                         'skills/ascendc-aprof-profiling/assets'):
            shutil.copytree(BASE / relative, release / relative,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(HERE / 'profile-source-canonical.patch')],
                       cwd=release, check=True)
        environment = dict(os.environ)
        environment.update(APROF_SKILL_LIB=str(release), PYTHONDONTWRITEBYTECODE='1',
            PYTHONPATH=os.pathsep.join(map(str, (
                release / 'runtime/src', release / 'skills/ascendc-aprof-profiling/scripts',
                REPO / 'scaffolding/tests', REPO / 'scaffolding/collection/scripts'))))
        return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                               str(HERE / 'test_profile_source_canonical.py')],
                              env=environment, cwd=release).returncode


if __name__ == '__main__':
    raise SystemExit(main())
