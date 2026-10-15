#!/usr/bin/env python3
"""Explicit post-task archive dispatch; never infer the task's release from a default."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--skill-lib', type=Path, help='package frozen into the generic task job')
    choice.add_argument('--legacy-v051', action='store_true', help='explicit historical 0.5.1 copy-only handler')
    args, remaining = parser.parse_known_args(argv)
    if args.legacy_v051:
        entry = Path(__file__).with_name('archive_local_evidence_v051.py')
    else:
        root = args.skill_lib.resolve(strict=True)
        entry = root/'tools/archive_local_evidence.py'
        if not entry.is_file() or not (root/'skillgraph/registry.json').is_file():
            parser.error('selected package has no version-bound archive handler; no fallback is allowed')
    return subprocess.run([sys.executable, '-B', str(entry), *remaining], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
