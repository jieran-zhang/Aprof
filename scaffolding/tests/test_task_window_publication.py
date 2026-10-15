"""Publication routing guards; these fixtures are not qualification evidence."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(os.environ.get('APROF_TEST_REPO_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'skill-libs/graph-base/0.5.1/runtime/src'))
sys.path.insert(0, str(ROOT / 'scaffolding/tools'))
SCRIPT = Path(__file__).resolve().parents[1] / 'tools/verify_task_window_publication.py'
spec = importlib.util.spec_from_file_location('window_publication_test', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('protocol', [
    'shared_buffer_acl_event_v2', 'shared_buffer_msprof_task_v1', 'shared_buffer_msprof_task_v2',
    'shared_buffer_msprof_task_window_v1', 'shared_buffer_msprof_task_window_v2',
    'shared_buffer_msprof_task_window_v3',
])
def test_old_protocol_cannot_enter_window_publication(tmp_path, protocol):
    value = {key: {} for key in ('history_ref', 'confirmations', 'observation_archive_refs',
             'attempt_roster_ref', 'install_receipt_ref', 'candidate_inventory_ref', 'old_release_baseline_ref')}
    value.update(schema_version=1, protocol=protocol, qualification_dir=str(tmp_path))
    report = tmp_path / 'report.json'
    report.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='only calibrated Task window'):
        module.verify_in_process(ROOT / 'skill-libs/graph-base/0.5.1', report)


def test_publication_requires_observation_archive_refs(tmp_path):
    report = tmp_path / 'report.json'
    report.write_text(json.dumps({'schema_version': 1, 'protocol': module.PROTOCOL,
        'qualification_dir': str(tmp_path), 'history_ref': {}, 'confirmations': {},
        'attempt_roster_ref': {}, 'install_receipt_ref': {}, 'candidate_inventory_ref': {},
        'old_release_baseline_ref': {}}))
    with pytest.raises(ValueError, match='invalid publication report schema'):
        module.verify_in_process(ROOT / 'skill-libs/graph-base/0.5.1', report)


def test_independent_install_runs_new_replay_entry(tmp_path, monkeypatch):
    common = module.common
    package = tmp_path / 'independent'
    interpreter = package / '.runtime-env/bin/python'
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text('synthetic interpreter, never executed')
    stdout, stderr = tmp_path / 'pip.stdout', tmp_path / 'pip.stderr'
    stdout.write_text('synthetic pip receipt'); stderr.write_text('')
    execution = tmp_path / 'pip-execution.json'
    execution.write_text(json.dumps({'argv': [str(interpreter), '-m', 'pip', 'install', str(package / 'runtime')],
        'exit_status': 0, 'started_at': 1, 'finished_at': 2,
        'stdout_ref': common.bound(stdout), 'stderr_ref': common.bound(stderr)}))
    receipt = tmp_path / 'install.json'
    receipt.write_text(json.dumps({'schema_version': 1, 'package_root': str(package),
                                  'pip_execution_ref': common.bound(execution)}))
    report = {'install_receipt_ref': common.bound(receipt), '_report_path': tmp_path / 'publication.json'}
    monkeypatch.setattr(common, 'release_tool', lambda _: SimpleNamespace(
        inventory=lambda _: {'payload': 'synthetic'}, registry_errors=lambda _: []))
    calls = []

    def isolated_probe(argv, **options):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({
            'runtime_module': str(package / '.runtime-env/task_window_measurement_admission.py'),
            'runtime_module_sha256': 'synthetic',
            'operators': {op: {'receipt': {'measurement_report_ref': op}} for op in module.OPERATORS}}))

    monkeypatch.setattr(common.subprocess, 'run', isolated_probe)
    common.independent_install(ROOT / 'skill-libs/graph-base/0.5.1', report, {'payload': 'synthetic'},
                               probe_script=SCRIPT)
    assert len(calls) == 1
    assert calls[0] == [str(interpreter), '-I', str(SCRIPT), '--root', str(package),
                        '--report', str(report['_report_path']), '--installed-probe']


def test_post_task_archive_requires_complete_cas_index_without_admission_authority(tmp_path):
    from aprof_runtime.store import EpisodeStore
    from aprof_runtime.traces import register_json_artifact
    online = tmp_path / 'local-task'; store_path = tmp_path / 'archive.sqlite'
    with EpisodeStore(store_path) as store:
        completion_ref = register_json_artifact(store, {'kind': 'local_measurement_completion',
            'protocol': module.PROTOCOL, 'status': 'passed', 'finished_at': 1})
        index_ref = register_json_artifact(store, {'schema_version': 1, 'kind': 'local_evidence_index',
            'directory': str(online / 'records'), 'artifacts': {completion_ref: str(online / 'local-result.json')}})
    receipt = {'schema_version': 1, 'owner': 'trace_collection', 'cost_scope': 'post_task_archive',
        'admission_authority': False,
        'local_index': {'path': str(online / 'local-evidence-index.json'), 'sha256': index_ref},
        'completion_ref': completion_ref, 'store': str(store_path), 'artifact_refs': [completion_ref],
        'started_at': 2, 'finished_at': 3, 'elapsed_seconds': 1}
    path = tmp_path / 'archive-receipt.json'; path.write_text(json.dumps(receipt))
    item = {'archive_receipt_ref': module.common.bound(path), 'receipt_ref': completion_ref,
            'store_path': str(store_path)}
    result, completion = module.archived_confirmation(item, online)
    assert result['admission_authority'] is False and completion['status'] == 'passed'
    receipt['artifact_refs'] = []
    path.write_text(json.dumps(receipt)); item['archive_receipt_ref'] = module.common.bound(path)
    with pytest.raises(ValueError, match='archived local index scope differs'):
        module.archived_confirmation(item, online)
    receipt['artifact_refs'] = [completion_ref]
    receipt['admission_authority'] = True
    path.write_text(json.dumps(receipt)); item['archive_receipt_ref'] = module.common.bound(path)
    with pytest.raises(ValueError, match='post-task confirmation archive differs'):
        module.archived_confirmation(item, online)
    receipt['admission_authority'] = False
    receipt['started_at'] = 0
    path.write_text(json.dumps(receipt)); item['archive_receipt_ref'] = module.common.bound(path)
    with pytest.raises(ValueError, match='archived completion'):
        module.archived_confirmation(item, online)


@pytest.mark.parametrize('change', [{'accepted': True}, {'eligible_for_publication': True},
                                    {'complete_method_qualification': True},
                                    {'measurement_admission_replayed': True}, {'valid': False}])
def test_prior_failure_cannot_be_promoted_by_publication(monkeypatch, change):
    value = {'valid': True, 'accepted': False, 'eligible_for_publication': False,
             'complete_method_qualification': False, 'measurement_admission_replayed': False}
    value.update(change)
    calls = []
    monkeypatch.setitem(sys.modules, 'replay_task_window_failure', SimpleNamespace(
        replay_task_window_failure=lambda ref: calls.append(ref) or value))
    with pytest.raises(ValueError, match='prior failed Task-window attempt'):
        module.failed_attempt_history({'path': '/frozen/leaf.json', 'sha256': 'sha256:frozen'})
    assert len(calls) == 1
