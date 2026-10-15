"""Exercise a copied release without checkout, scaffolding or another version."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import pytest
from aprof_layout import skill_lib, release_module


@pytest.fixture
def isolated(tmp_path):
    root = tmp_path / 'standalone'
    shutil.copytree(skill_lib(), root, ignore=shutil.ignore_patterns('__pycache__', '.runtime-env', '*.egg-info', 'build'))
    return root


def run(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'APROF_SKILL_LIB', 'APROF_PYTHON')}
    return subprocess.run(args, cwd=root, env=env, check=True, capture_output=True, text=True)


def test_standalone_install_graph_contract_and_gate_episode(isolated, tmp_path):
    root = isolated
    run(root, sys.executable, 'tools/release.py')
    run(root, sys.executable, 'tools/install.py', '--skills-dir', str(tmp_path / 'host'))
    cli = str(root / 'tools/aprofctl')
    for graph in ('v0001', 'v0002'):
        result = run(root, cli, 'graph', 'validate', '--graph', str(root / 'skillgraph/versions' / graph))
        assert json.loads(result.stdout)['result']['valid']
    # Existing semantic fixture exercises a real route, gate and finalization.
    from test_schema_parity import _runtime_values
    values = _runtime_values()
    for kind in ('context', 'candidate_draft', 'gate_request'):
        path = tmp_path / (kind + '.json'); path.write_text(json.dumps(values[kind.replace("_", "-") + ".schema.json"]))
        run(root, cli, 'contract', 'validate', '--kind', kind, '--input', str(path))
    run(root, cli, 'graph', 'route', '--graph', str(root / 'skillgraph/versions/v0001'), '--context', str(tmp_path / 'context.json'))
    run(root, cli, 'candidate', 'gate', '--request', str(tmp_path / 'gate_request.json'))
    result = run(root, cli, 'episode', 'finalize', '--context', str(tmp_path / 'context.json'),
                 '--request', str(tmp_path / 'gate_request.json'), '--graph', str(root / 'skillgraph/versions/v0001'))
    assert json.loads(result.stdout)['result']['episodes']


def test_standalone_tools_and_internal_links(isolated):
    root = isolated
    for command in [
        ['bash', 'skills/ops-profiling/scripts/msprof_profile_run.sh', '--help'],
        [sys.executable, 'skills/ops-profiling/scripts/msprof_perf_summary.py', '--help'],
        [sys.executable, 'skills/ops-profiling/scripts/perf_summary.py', '--help'],
        [sys.executable, 'skills/ops-simulator/scripts/trace_bubble_analyzer.py', '--help'],
        [sys.executable, 'skills/ascendc-aprof-profiling/scripts/paired_timing.py', '--help'],
    ]:
        run(root, *command)
    for path in root.rglob('*.md'):
        if 'provenance' in path.parts: continue  # Retained historical bytes, located by a separate map.
        for target in re.findall(r'\]\(([^\s)]+)\)', path.read_text()):
            if '://' in target or target.startswith(('#', '<')): continue
            resolved = (path.parent / target.split('#', 1)[0]).resolve()
            assert resolved.is_relative_to(root) and resolved.is_file(), (path, target)
    for name in ('ops-profiling', 'ops-simulator'):
        assert (root / 'skills' / name / 'LICENSE').is_file()
        assert (root / 'skills' / name / 'NOTICE.md').is_file()


def test_changed_release_and_escaping_symlinks_are_rejected(isolated):
    module = release_module(isolated)
    path = isolated / 'skills/ascendc-aprof-workflow/SKILL.md'
    original = path.read_bytes(); path.write_bytes(original + b'\nchanged\n')
    with pytest.raises(ValueError, match='release bytes differ'): module.verify(isolated)
    path.write_bytes(original)
    path.unlink(); path.symlink_to('/etc/hosts')
    with pytest.raises(ValueError, match='symlink'): module.verify(isolated)
