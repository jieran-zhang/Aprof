"""The cancelled local-storage attempt stays incomplete under fresh replay."""
import json
from pathlib import Path

import pytest

import replay_task_local_cancellation as replay
from replay_timing_diagnosis import Evidence, digest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {'path': str(path), 'sha256': digest(path)}


def test_snapshot_normalizes_without_mutation_and_rechecks_bytes(tmp_path):
    root = tmp_path / 'raw'; root.mkdir(); original = root / 'data'; original.write_bytes(b'raw')
    inventory = {'root': str(root), 'files': {'data': {'sha256': digest(original), 'size_bytes': 3,
                  'mode': original.stat().st_mode & 0o7777}}, 'file_count': 1, 'total_regular_file_bytes': 3}
    before = json.dumps(inventory)
    view = replay.snapshot_view(inventory)
    replay.verify_snapshot(Evidence(), view)
    assert json.dumps(inventory) == before
    original.write_bytes(b'bad')
    with pytest.raises(ValueError, match='changed evidence'):
        replay.verify_snapshot(Evidence(), view)


@pytest.mark.parametrize('path', ['../escaped', '/absolute', 'a/../escaped'])
def test_snapshot_rejects_path_escape(tmp_path, path):
    with pytest.raises(ValueError, match='relative path'):
        replay.snapshot_view({'root': str(tmp_path), 'files': {path: {}}})


def test_filtered_index_cannot_replace_workload_or_documents():
    source = str(replay.RUNTIME / 'aprof_runtime/store.py')
    document = str(replay.REPO / 'skill-libs/graph-base/0.5.1/README.md')
    workload = '/external/validation/source/main.cpp'
    full = {'schema_version': 1, 'not_a_release': True,
            'files': {name: {'path': '/archive/file', 'sha256': 'sha256:abc'}
                      for name in (source, document, workload)}}
    reference = {'path': '/archive/index.json', 'sha256': 'sha256:def'}
    result = replay.producer_index(reference, full)
    assert list(result['files']) == [source]
    assert result['source_archive_ref'] == reference


@pytest.mark.parametrize('field', ['complete', 'eligible_for_publication', 'full_admission_replay_performed'])
def test_audit_rejects_promoted_or_relabelled_claim(field):
    audit = {'schema_version': 1, 'purpose': 'preserve_actual_evidence_not_admission',
             'complete': False, 'eligible_for_publication': False, 'not_actual_timeout': True,
             'full_admission_replay_performed': False, 'cancellation_reason': replay.REASON}
    replay.validate_audit(audit)
    audit[field] = True
    with pytest.raises(ValueError, match='cannot confer admission'):
        replay.validate_audit(audit)


def test_controls_keep_original_local_drift_threshold():
    controls = {phase: {'baseline_cv': .005, 'candidate_cv': .005, 'role_bias': .001}
                for phase in ('aa_before', 'formal', 'aa_after')}
    controls['drift'] = {'baseline': .02, 'candidate': .02}
    assert replay.controls_pass(controls)
    controls['drift']['baseline'] = .022915742461891098
    assert not replay.controls_pass(controls)
    controls['drift']['baseline'] = float('nan')
    assert not replay.controls_pass(controls)


def test_missing_parent_terminal_cannot_be_backfilled(tmp_path):
    campaign = tmp_path / 'campaign'
    exp = campaign / 'exp-confirmation'
    started = write(exp / 'started.json', {})
    execution = write(exp / 'job/execution.json', {})
    prior = write(exp / 'terminal.json', {'status': 'failed', 'execution': execution, 'started': started})
    names = ['exp-confirmation', 'exp-observation-01', 'exp-observation-09',
             'sigmoid-confirmation', 'sigmoid-observation-01', 'sigmoid-observation-04']
    for name in names[1:3]:
        prior = write(campaign / name / 'terminal.json',
                      {'slot_id': name, 'status': 'not_run', 'prerequisite_ref': prior})
    roster = {'slots': [{'slot_id': name} for name in names]}
    replay.verify_missing_stages(tmp_path, roster, Evidence())
    write(campaign / 'sigmoid-confirmation/terminal.json', {'status': 'passed'})
    with pytest.raises(ValueError, match='invented completion'):
        replay.verify_missing_stages(tmp_path, roster, Evidence())


def test_failed_readonly_replay_is_preserved(tmp_path, monkeypatch):
    archive = write(tmp_path / 'archive.json', {'schema_version': 1, 'not_a_release': True, 'files': {}})
    audit = write(tmp_path / 'audit.json', {'source_archive_ref': archive})
    output = tmp_path / 'replay'
    monkeypatch.setattr(replay.sys, 'argv', ['replay', '--audit', audit['path'], '--output', str(output)])
    def fail(*args, **kwargs):
        raise ValueError('actual evidence does not replay')
    monkeypatch.setattr(replay, 'replay_task_local_cancellation', fail)
    with pytest.raises(SystemExit) as result:
        replay.main()
    assert result.value.code == 1
    saved = json.loads((output / 'replay.json').read_text())
    assert saved['valid'] is False and saved['complete'] is False and saved['eligible_for_publication'] is False
    assert saved['error']['message'] == 'actual evidence does not replay'
    assert saved['duration_seconds'] >= 0
