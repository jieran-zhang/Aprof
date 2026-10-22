"""Documented release checks use the package's own runtime and frozen graph."""
from pathlib import Path
import os
import subprocess
import sys
from aprof_layout import skill_lib


def test_documented_checks():
    repo = Path(__file__).resolve().parents[2]
    root = skill_lib()
    commands = [
        [sys.executable, str(root / 'tools/release.py')],
        [sys.executable, str(repo / 'scaffolding/tools/sync_aprof_registry.py'), 'check', '--skill-lib', str(root)],
        [sys.executable, str(repo / 'scaffolding/tools/compile_graph_v2.py'), '--skill-lib', str(root), '--check'],
    ]
    for command in commands:
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
