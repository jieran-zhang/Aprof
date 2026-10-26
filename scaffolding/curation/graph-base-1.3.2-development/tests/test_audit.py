"""开发审计不能因归档、空目录或安装检查拆分而丢失覆盖。"""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


ARCHIVE = Path(__file__).resolve().parents[1]
PACKAGE = ARCHIVE.parents[2] / 'skill-libs/graph-base/1.3.2'
sys.path.insert(0, str(PACKAGE / 'runtime/src'))
from aprof_runtime.errors import GraphError
spec = importlib.util.spec_from_file_location('skills_development_audit', ARCHIVE / 'audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.fixture
def archive(tmp_path):
    target = tmp_path / 'archive'
    shutil.copytree(ARCHIVE, target, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'generated'))
    return target


def test_all_original_audit_coverage_is_retained():
    result = audit.verify_archive(PACKAGE)
    assert result == {'valid': True, 'archived_files': 221, 'migration_files': 8,
                      'seed_records': 195, 'paper_cases': 4, 'proposals': 2}


@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_old_seed_cannot_disappear_or_change(archive, damage):
    manifest = audit.read(archive / 'relocation.json')
    entry = next(e for e in manifest['files'] if e['group'] == 'legacy-seed' and e['path'].endswith('.md'))
    path = archive / entry['path']
    if damage == 'missing':
        path.unlink()
    else:
        path.write_text(path.read_text() + '\nchanged\n')
    with pytest.raises(ValueError):
        audit.verify_archive(PACKAGE, archive)


def test_empty_case_directory_cannot_silently_skip_contract_checks(archive):
    for entry in audit.read(archive / 'relocation.json')['files']:
        if entry['group'] == 'paper-cases':
            (archive / entry['path']).unlink()
    with pytest.raises(ValueError, match='缺失'):
        audit.verify_archive(PACKAGE, archive)


def test_migration_partition_cannot_omit_a_record(archive):
    path = archive / 'migration-files.json'
    rows = audit.read(path)
    path.write_text(json.dumps(rows[:-1]))
    with pytest.raises(ValueError, match='无遗漏'):
        audit.verify_archive(PACKAGE, archive)


@pytest.mark.parametrize('group', ['paper-cases', 'proposals'])
def test_matching_hash_does_not_replace_case_or_proposal_validation(archive, group):
    manifest = audit.read(archive / 'relocation.json')
    entry = next(e for e in manifest['files'] if e['group'] == group and e['path'].endswith('.json'))
    path = archive / entry['path']
    value = audit.read(path)
    value['schema_version'] = 'unknown-schema'
    path.write_text(json.dumps(value))
    entry.update(sha256=audit.sha(path), original_sha256=audit.sha(path), bytes=path.stat().st_size)
    (archive / 'relocation.json').write_text(json.dumps(manifest))
    with pytest.raises(GraphError):
        audit.verify_archive(PACKAGE, archive)


def test_audit_path_boundary_rejects_escape_and_symlink(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    with pytest.raises(ValueError):
        audit.local(root, '../outside')
    (root / 'link').symlink_to(tmp_path / 'outside')
    with pytest.raises(ValueError):
        audit.local(root, 'link')


def test_installation_still_rejects_missing_runtime_provenance(tmp_path):
    root = tmp_path / 'package'
    shutil.copytree(PACKAGE, root, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    graph = audit.read(root / 'skills/ascendc-aprof-diagnosis/graph/versions/v0007/graph.json')
    name = next(s['path'] for r in graph['records'] for s in r['sources'] if '/history/provenance/' in s['path'])
    (root / name).unlink()
    spec = importlib.util.spec_from_file_location('install_boundary_release', root / 'tools/release.py')
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    with pytest.raises((ValueError, GraphError, OSError)):
        release.verify_unsealed(root)
