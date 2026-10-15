"""Unsealed installation is explicit, structural, and keeps whole-package links."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


PACKAGE = Path(__file__).resolve().parents[2] / 'skill-libs/graph-base/1.0.1'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / 'complete-package'
    shutil.copytree(PACKAGE, root, ignore=shutil.ignore_patterns(
        '__pycache__', '.runtime-env', '*.egg-info', 'build', 'dist'))
    release = load('candidate_release_test', root / 'tools/release.py')
    monkeypatch.setitem(sys.modules, 'release', release)
    installer = load('candidate_installer_test', root / 'tools/install.py')
    return root, release, installer


def test_unsealed_requires_explicit_opt_in_and_never_creates_manifest(package, tmp_path):
    root, release, installer = package
    with pytest.raises(FileNotFoundError):
        installer.install(root, tmp_path / 'default-host')
    result = release.verify_unsealed(root)
    assert result['status'] == 'unsealed' and result['verification'] == 'structure_only'
    assert result['publication_accepted'] is False
    assert result['release_id'] == 'graph-base/1.0.1'
    assert result['runtime_version'] == '0.2.4'
    assert not (root / 'release.json').exists()
    assert not (tmp_path / 'default-host').exists()


def test_unsealed_flag_cannot_bypass_a_present_invalid_manifest(package):
    root, release, _ = package
    (root / 'release.json').write_text('{"status":"stable","files":{}}')
    with pytest.raises(ValueError, match='requires no release.json'):
        release.verify_unsealed(root)


def test_unsealed_flag_rejects_dangling_manifest_link(package, tmp_path):
    root, release, _ = package
    (root / 'release.json').symlink_to(tmp_path / 'absent-manifest.json')
    with pytest.raises(ValueError, match='requires no release.json'):
        release.verify_unsealed(root)


@pytest.mark.parametrize('relative', [
    'runtime/src/aprof_runtime/cli.py', 'schemas/context.schema.json',
    'skills/ascendc-aprof-workflow/SKILL.md',
])
def test_incomplete_package_is_rejected(package, relative):
    root, release, _ = package
    (root / relative).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        release.verify_unsealed(root)


def test_graph_mutation_is_rejected(package):
    root, release, _ = package
    graph = root / 'skillgraph/versions/v0002/graph.json'
    graph.write_bytes(graph.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='graph bytes differ'):
        release.verify_unsealed(root)


def test_link_conflict_is_preflighted_without_partial_install(package, tmp_path):
    root, _, installer = package
    entries = json.loads((root / 'skillgraph/registry.json').read_text())
    rows = entries['capabilities']['core'] + entries['support_skills']
    host = tmp_path / 'host'; host.mkdir()
    conflict = host / rows[-1]['name']; conflict.mkdir()
    with pytest.raises(ValueError, match='refusing to replace'):
        installer.install(root, host, allow_unsealed=True)
    assert list(host.iterdir()) == [conflict]


def test_links_retain_complete_source_package_and_are_idempotent(package, tmp_path):
    root, release, installer = package
    before = release.inventory(root)
    host = tmp_path / 'host'
    assert installer.install(root, host, allow_unsealed=True) == 'graph-base/1.0.1'
    assert installer.install(root, host, allow_unsealed=True) == 'graph-base/1.0.1'
    workflow = host / 'ascendc-aprof-workflow'
    assert workflow.is_symlink()
    assert workflow.resolve() == root / 'skills/ascendc-aprof-workflow'
    package_root = workflow.resolve().parents[1]
    assert package_root == root
    for name in ('tools/aprofctl', 'runtime/pyproject.toml', 'wiki/index.json',
                 'skillgraph/versions/v0002/graph.json'):
        assert (package_root / name).is_file()
    assert release.inventory(root) == before
    assert not (root / 'release.json').exists()


def test_other_release_link_is_not_retargeted(package, tmp_path):
    root, _, installer = package
    host = tmp_path / 'host'; host.mkdir()
    elsewhere = tmp_path / 'other-release-skill'; elsewhere.mkdir()
    link = host / 'ascendc-aprof-workflow'; link.symlink_to(elsewhere)
    with pytest.raises(ValueError, match='another release owns'):
        installer.install(root, host, allow_unsealed=True)
    assert link.resolve() == elsewhere
    assert list(host.iterdir()) == [link]


def test_install_cannot_put_host_links_inside_source_package(package):
    root, _, installer = package
    target = root / 'host-links'
    with pytest.raises(ValueError, match='outside the complete source package'):
        installer.install(root, target, allow_unsealed=True)
    assert not target.exists()
