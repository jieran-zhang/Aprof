"""Canonical releases expose one inventory; metadata cannot redirect ownership."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

from aprof_layout import skill_lib, release_module


def test_registry_and_host_metadata_agree():
    root = skill_lib()
    assert release_module(root).registry_errors(root) == []
    registry = json.loads((root / 'skillgraph/registry.json').read_text())
    assert set(registry['capabilities']) == {'core', 'optional_adapters'}
    names = {row['name'] for row in registry['capabilities']['core']}
    assert 'ascendc-kernel-direct-invoke' in names
    assert 'ascendc-aprof-inject-problems' not in names
    manifest = json.loads((root / '.codex-plugin/plugin.json').read_text())
    assert manifest['skills'] == './skills/'
    assert not {'dependencies', 'agents', 'hooks'} & set(manifest)
    repo = Path(__file__).resolve().parents[2]
    market = json.loads((repo / '.agents/plugins/marketplace.json').read_text())
    assert len(market['plugins']) == 1
    entry = market['plugins'][0]
    catalog = json.loads((repo / 'skill-libs/catalog.json').read_text())
    assert (repo / entry['source']['path']).resolve() == (
        repo / 'skill-libs' / catalog['default_release']).resolve()
    assert root.name in {Path(row['path']).name for row in catalog['releases']}
    assert entry['policy'] == {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}


@pytest.mark.parametrize('change', ['escape', 'absolute', 'duplicate_name', 'duplicate_source', 'missing', 'symlink'])
def test_invalid_capability_ownership_is_rejected(tmp_path, change):
    root = tmp_path / 'release'
    shutil.copytree(skill_lib(), root, ignore=shutil.ignore_patterns('__pycache__', '.runtime-env'))
    path = root / 'skillgraph/registry.json'
    registry = json.loads(path.read_text())
    first = registry['capabilities']['core'][0]
    if change == 'escape': first['source'] = '../outside'
    if change == 'absolute': first['source'] = str(tmp_path / 'outside')
    if change == 'duplicate_name': first['name'] = registry['capabilities']['core'][1]['name']
    if change == 'duplicate_source': first['source'] = registry['capabilities']['core'][1]['source']
    if change == 'missing': first['source'] = 'skills/missing'
    if change == 'symlink':
        source = root / first['source']; target = tmp_path / 'outside'
        source.rename(target); source.symlink_to(target, target_is_directory=True)
    path.write_text(json.dumps(registry))
    assert release_module(root).registry_errors(root)


def test_installation_is_explicit_and_refuses_unmanaged_files(tmp_path):
    root = skill_lib()
    target = tmp_path / 'skills'
    command = [sys.executable, str(root / 'tools/install.py'), '--skills-dir', str(target)]
    subprocess.run(command, check=True, capture_output=True)
    assert (target / 'ascendc-aprof-workflow').resolve() == root / 'skills/ascendc-aprof-workflow'
    assert not (target / 'ascendc-remote-kernel-deploy').exists()
    subprocess.run(command + ['--with-remote'], check=True, capture_output=True)
    assert (target / 'ascendc-remote-kernel-deploy').resolve() == root / 'adapters/ascendc-remote-kernel-deploy'
    entry = target / 'ascendc-aprof-workflow'
    entry.unlink(); entry.mkdir()
    (entry / 'user-data').write_text('keep')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0 and (entry / 'user-data').read_text() == 'keep'
