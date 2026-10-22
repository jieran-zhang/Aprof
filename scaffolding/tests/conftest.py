"""Tests explicitly select the release under test before loading its runtime."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RELEASE = Path(os.environ.get('APROF_SKILL_LIB', ROOT / 'skill-libs/graph-base/0.4.1')).resolve()
os.environ['APROF_SKILL_LIB'] = str(RELEASE)
for path in (RELEASE / 'runtime/src', ROOT / 'scaffolding/collection/scripts', ROOT / 'scaffolding/tools', Path(__file__).parent):
    sys.path.insert(0, str(path))
