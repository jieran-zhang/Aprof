#!/usr/bin/env python3
"""Check copied, already applied 1.0 sources without modifying production files."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = REPO / 'skill-libs/graph-base/1.0.0'


def main():
    with tempfile.TemporaryDirectory(prefix='aprof-runtime023-applied-cpu-') as directory:
        release = Path(directory)
        for relative in ('runtime/src', 'skills/ascendc-aprof-profiling/scripts',
                         'skills/ascendc-aprof-profiling/assets'):
            shutil.copytree(BASE / relative, release / relative,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(BASE / 'runtime/pyproject.toml', release / 'runtime/pyproject.toml')
        fixtures = release / 'cpu-fixtures'; fixtures.mkdir()
        # Existing synthetic wire fixtures have a release-version skip guard.
        # Only broaden that test guard in this temporary copy, never runtime identity.
        for name in ('test_shared_measurement_admission.py', 'test_task_window_timing.py'):
            text = (REPO / 'scaffolding/tests' / name).read_text()
            text = text.replace('if __version__ != "0.2.2":',
                                'if __version__ not in ("0.2.2", "0.2.3"):')
            text = text.replace("if __version__ != '0.2.2':",
                                "if __version__ not in ('0.2.2', '0.2.3'):")
            (fixtures / name).write_text(text)
        environment = dict(os.environ)
        environment.update(APROF_SKILL_LIB=str(release), APROF_CASE_BINDING_TEST_RELEASE=str(release),
            PYTHONDONTWRITEBYTECODE='1',
            PYTHONPATH=os.pathsep.join(map(str, (
                release / 'runtime/src', release / 'skills/ascendc-aprof-profiling/scripts',
                fixtures, REPO / 'scaffolding/tests', REPO / 'scaffolding/collection/scripts'))))
        return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            *(str(HERE / name) for name in ('test_case_binding.py', 'test_profile_source_canonical.py',
                                          'test_runtime_023.py'))], env=environment, cwd=release).returncode


if __name__ == '__main__':
    raise SystemExit(main())
