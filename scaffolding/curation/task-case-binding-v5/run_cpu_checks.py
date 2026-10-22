#!/usr/bin/env python3
"""Apply only the proposed patch to temporary source files and run CPU checks."""
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
    with tempfile.TemporaryDirectory(prefix='aprof-case-binding-v5-test-') as directory:
        release = Path(directory)
        # Source-only test environment; no release payload, manifest or raw profile.
        for relative in ('runtime/src', 'skills/ascendc-aprof-profiling/scripts',
                         'skills/ascendc-aprof-profiling/assets'):
            shutil.copytree(BASE / relative, release / relative,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(HERE / 'case-binding.patch')],
                       cwd=release, check=True)
        environment = dict(os.environ)
        environment.update(APROF_CASE_BINDING_TEST_RELEASE=str(release),
            PYTHONDONTWRITEBYTECODE='1',
            PYTHONPATH=os.pathsep.join(map(str, (
                release / 'runtime/src', release / 'skills/ascendc-aprof-profiling/scripts',
                REPO / 'scaffolding/tests', REPO / 'scaffolding/collection/scripts'))))
        return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                               str(HERE / 'test_case_binding.py')],
                              env=environment, cwd=release).returncode


if __name__ == '__main__':
    raise SystemExit(main())
