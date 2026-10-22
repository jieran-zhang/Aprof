"""Collector-only bundle fix, using real CPU child processes and frozen runtime."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.jsonio import canonical_json, file_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.profile_evidence import compare_profiles, load_capture_manifest, normalize_profile
from aprof_runtime.traces import register_json_artifact
import device_shared_timing as task
from test_profiler_backend_v042 import collector, normalizer, project


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp('canonical-profile-cpu')
    config = project.__wrapped__(root)
    source = Path(config['source_dir'])
    (source / '说明.h').write_text('// 非 ASCII source identity\n', encoding='utf-8')
    results = {role: collector.capture(dict(config, role=role), root / role)
               for role in ('baseline', 'candidate')}
    local = LocalEvidence.from_index(results['baseline']['local_index'])
    for reference, path in json.loads(Path(results['candidate']['local_index']).read_text())['artifacts'].items():
        assert local.register_artifact(path) == reference
    # The actual Task producer uses this source_inventory + register_json_artifact.
    bundle = {'schema_version': '1.0.0', 'files': task.source_inventory(source, local)}
    task_ref = register_json_artifact(local, bundle)
    profiles, manifests, original_manifest_bytes = {}, {}, {}
    for role, result in results.items():
        original_manifest_bytes[role] = Path(result['manifest']).read_bytes()
        manifest = load_capture_manifest(local, result['manifest_hash'])
        manifests[role] = manifest
        spec = {'duration': {'unit': 'us', 'file': 'OpBasicInfo.csv', 'format': 'csv',
                             'field': 'Task Duration(us)'}}
        profiles[role] = normalize_profile(local, result['manifest_hash'], normalizer.expand_specs(manifest, spec))
    return root, config, results, local, bundle, task_ref, profiles, manifests, original_manifest_bytes


def test_complete_captures_match_task_source_hash_without_runtime_change(completed):
    root, config, results, local, bundle, task_ref, profiles, manifests, original_bytes = completed
    expected = canonical_json(bundle).encode('utf-8')
    assert not expected.endswith(b'\n')
    assert '说明.h' in bundle['files']
    assert all(not name.startswith('build/') for name in bundle['files'])
    assert local.verify_artifact(task_ref).read_bytes() == expected
    assert (Path(config['cwd']) / 'calls.txt').read_text().splitlines() == ['launch'] * 30
    for role, manifest in manifests.items():
        assert manifest['source_hash'] == task_ref
        assert (root / role / 'source-bundle.json').read_bytes() == expected
        assert len(manifest['warmup_runs']) == 10 and len(manifest['captures']) == 5
        for record in manifest['warmup_runs'] + manifest['captures']:
            receipt = json.loads(local.verify_artifact(record['log_hash']).read_text())
            execution = receipt.get('capture', receipt)
            assert execution['exit_code'] == 0
            assert execution['identity_checks']['before']['source_hash'] == task_ref
            assert execution['identity_checks']['after']['source_hash'] == task_ref
    assert compare_profiles(local, profiles['baseline'], profiles['candidate'], 'duration',
                            source_hashes={role: task_ref for role in manifests})
    for role, result in results.items():
        assert Path(result['manifest']).read_bytes() == original_bytes[role]
        assert file_hash(result['manifest']) == result['manifest_hash']
    assert not list(root.rglob('*.sqlite'))


@pytest.mark.parametrize('fault', ['altered', 'missing', 'extra'])
def test_frozen_runtime_rejects_changed_task_file_map(completed, fault):
    _, _, _, local, bundle, task_ref, profiles, _, _ = completed
    changed = deepcopy(bundle)
    if fault == 'altered':
        changed['files']['kernel.cpp'] = changed['files']['说明.h']
    elif fault == 'missing':
        changed['files'].pop('kernel.cpp')
    else:
        changed['files']['extra.cpp'] = changed['files']['kernel.cpp']
    expected = register_json_artifact(local, changed)
    with pytest.raises(ContractError, match='profile source role differs'):
        compare_profiles(local, profiles['baseline'], profiles['candidate'], 'duration',
                         source_hashes={'baseline': task_ref, 'candidate': expected})


def test_completed_capture_rejects_unindexed_nested_source(completed):
    _, _, results, _, bundle, _, _, _, _ = completed
    path = Path(results['baseline']['local_index'])
    original = path.read_bytes()
    value = json.loads(original)
    value['artifacts'].pop(bundle['files']['kernel.cpp'])
    alternate = path.with_name('unindexed-source-index.json')
    alternate.write_text(json.dumps(value))
    local = LocalEvidence.from_index(alternate)
    with pytest.raises(StoreError, match='not indexed'):
        load_capture_manifest(local, results['baseline']['manifest_hash'])
    assert path.read_bytes() == original


@pytest.mark.parametrize('fault', ['altered', 'missing', 'extra'])
def test_identity_checks_reject_source_change_before_any_launch(project, tmp_path, fault):
    local = LocalEvidence(tmp_path / 'records')
    output = tmp_path / 'bundle'; output.mkdir()
    reference = collector.source_bundle(project['source_dir'], output, local)
    binding = {'source_dir': project['source_dir'], 'binary': project['binary'], 'tool': project['tool_path']}
    binding['expected'] = collector.identity_state(binding)
    assert binding['expected']['source_hash'] == reference
    source = Path(project['source_dir'])
    if fault == 'altered':
        (source / 'kernel.cpp').write_text('changed kernel\n')
    elif fault == 'missing':
        (source / 'kernel.cpp').unlink()
    else:
        (source / 'extra.h').write_text('extra source\n')
    with pytest.raises(RuntimeError):
        collector.run(project['command'], project['cwd'], tmp_path / 'rejected', 5, local, binding)
    assert not (Path(project['cwd']) / 'calls.txt').exists()
    receipt = json.loads((tmp_path / 'rejected.execution.json').read_text())
    assert receipt['error'] is not None and receipt['exit_code'] == -1


def test_bundle_destination_remains_create_only(project, tmp_path):
    local = LocalEvidence(tmp_path / 'records')
    output = tmp_path / 'bundle'; output.mkdir()
    collector.source_bundle(project['source_dir'], output, local)
    original = (output / 'source-bundle.json').read_bytes()
    with pytest.raises(FileExistsError):
        collector.source_bundle(project['source_dir'], output, local)
    assert (output / 'source-bundle.json').read_bytes() == original
