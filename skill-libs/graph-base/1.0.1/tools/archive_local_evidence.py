#!/usr/bin/env python3
"""Invoke this package's independent archive handler with explicit versions."""
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'runtime/src'))
from aprof_runtime import local_archive

if local_archive.PACKAGE != PACKAGE:
    raise RuntimeError('archive handler was imported from another package')

if __name__ == '__main__':
    raise SystemExit(local_archive.main())
