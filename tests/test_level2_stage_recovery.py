"""Explicit correctness recovery keeps failed evidence and binds runtime lineage."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import level2_iteration as iteration
import run_msprof_exploration_stage as stage
from msprof_exploration_execute import ALL_CASES, load, pointer, save, sha


def correctness_row(parent, group, candidate_id, source_hash, order, *, passed=True, evidence=True):
    sid = (candidate_id or 'baseline')+'-'+group
    directory = parent / 'stages' / group
    record = {'kind': 'correctness', 'stage_id': sid, 'candidate_id': candidate_id,
              'status': 'passed' if passed else 'failed', 'error': None if passed else {'message': 'pre-native detector failure'}}
    save(directory / 'result.json', record)
    plan = {'case_ids': ALL_CASES, 'source_hash': source_hash}
    save(directory / 'stage-plan.json', plan)
    attempt = {'outcome': 'success' if passed else 'failed', 'start_order': order,
               'native_started': passed, 'evidence': {'result': pointer(directory / 'result.json'),
                                                     'prepared_output_checked': passed}}
    if passed and evidence:
        save(directory / 'evidence/completion.json', {'status': 'passed', 'completed': [{'case_id': c} for c in ALL_CASES]})
        for c in ALL_CASES:
            save(directory / f'evidence/case_{c:02d}/native.json', {'exit_code': 0, 'stream_destroyed': True,
                 'context_destroyed': True, 'finalized': True})
        save(directory / 'standalone/completion.json', {'status': 'passed', 'passed_count': 20})
    return sid, {'stage_id': sid, 'kind': 'correctness', 'candidate_id': candidate_id, 'plan': plan, 'attempts': [attempt]}


@pytest.fixture
def recovery(tmp_path):
    parent = tmp_path / 'train/tasks/maximum';parent.mkdir(parents=True)
    archive = parent / 'baseline-source.tar';archive.write_bytes(b'original unchanged operator')
    source_hash = sha(archive)
    rows = dict([correctness_row(parent, 'correctness', None, source_hash, 1, passed=False),
                 correctness_row(parent, 'correctness-recovery-01', None, source_hash, 2)])
    ledger = SimpleNamespace(state={'tasks': {'maximum': {'stages': rows, 'candidates': {}}}},
                             config={'policy': {'protocol': stage.PROTOCOL}, 'tasks': {'maximum': {'baseline_source_hash': source_hash}}})
    return tmp_path, parent, source_hash, ledger


def test_selects_recent_success_of_same_source_and_candidate_only(recovery):
    run, parent, source_hash, ledger = recovery
    rows = ledger.state['tasks']['maximum']['stages']
    rows.update([correctness_row(parent, 'correctness-old-success', None, source_hash, 0)])
    other = parent / 'candidates/maximum001'
    rows.update([correctness_row(other, 'correctness', 'maximum001', source_hash, 20)])
    rows.update([correctness_row(parent, 'correctness-wrong-source', None, 'sha256:'+'f'*64, 30)])
    binding = stage.successful_correctness_binding(ledger, 'maximum', None, parent, source_hash)
    expected = parent / 'stages/correctness-recovery-01'
    assert binding == {'correctness_stage_id': 'baseline-correctness-recovery-01',
                       'correctness_result': pointer(expected / 'result.json'),
                       'correctness_directory': str(expected / 'evidence')}


@pytest.mark.parametrize('mutation,match', [('result', 'result differs'), ('coverage', 'coverage differs'),
                                            ('no_success', 'successful same-source'), ('unchecked', 'result differs')])
def test_runtime_binding_rejects_missing_or_changed_success(recovery, mutation, match):
    run, parent, source_hash, ledger = recovery
    rows = ledger.state['tasks']['maximum']['stages'];row = rows['baseline-correctness-recovery-01']
    if mutation == 'result': (parent / 'stages/correctness-recovery-01/result.json').write_text('{}')
    elif mutation == 'coverage': row['plan']['case_ids'] = [1]
    elif mutation == 'no_success': row['attempts'][0]['outcome'] = 'failed'
    else: row['attempts'][0]['evidence']['prepared_output_checked'] = False
    with pytest.raises(ValueError, match=match): stage.successful_correctness_binding(ledger, 'maximum', None, parent, source_hash)


def test_runtime_uses_recovered_evidence_and_standalone_without_touching_failed_stage(recovery, monkeypatch):
    run, parent, source_hash, ledger = recovery
    records = []
    ledger.validate_start = lambda **kwargs: records.append(('validate', kwargs))
    ledger.start = lambda **kwargs: records.append(('start', kwargs))
    ledger.finish = lambda **kwargs: records.append(('finish', kwargs))
    monkeypatch.setattr(stage, 'Campaign', lambda path: ledger)
    failed = parent / 'stages/correctness/result.json';before = failed.read_bytes()
    result = stage.run_stage(run, 'maximum', 'baseline', 'runtime', 'runtime')
    assert result['status'] == 'passed' and result['native_started'] is False
    plan = load(parent / 'stages/runtime/stage-plan.json')
    assert plan['depends_on'] == ['baseline-correctness-recovery-01']
    assert plan['correctness_result'] == pointer(parent / 'stages/correctness-recovery-01/result.json')
    runtime = load(parent / 'stages/runtime/runtime.json')
    assert runtime['correctness'] == pointer(parent / 'stages/correctness-recovery-01/evidence/completion.json')
    assert runtime['correctness_stage_result'] == plan['correctness_result']
    assert pointer(parent / 'stages/correctness-recovery-01/standalone/completion.json') in runtime['native_results']
    assert records[-1][1]['outcome'] == 'success'
    assert failed.read_bytes() == before
    assert ledger.state['tasks']['maximum']['stages']['baseline-correctness']['attempts'][0]['outcome'] == 'failed'


def test_runtime_rechecks_bound_correctness_result_before_assessing(recovery):
    run, parent, source_hash, ledger = recovery
    binding = stage.successful_correctness_binding(ledger, 'maximum', None, parent, source_hash)
    Path(binding['correctness_result']['path']).write_text('{}')
    output = parent / 'rejected-runtime.json'
    with pytest.raises(ValueError, match='bound correctness result changed'):
        stage.runtime_assessment(binding['correctness_directory'], output,
                                 correctness_result=binding['correctness_result'])
    assert not output.exists()


def test_explicit_baseline_recovery_group_does_not_retry_default(recovery, monkeypatch):
    run, parent, source_hash, ledger = recovery
    calls = []
    def execute(run, operator, candidate, kind, group, **kwargs):
        calls.append((kind, group))
        return {'status': 'failed' if group == 'correctness' else 'passed'}
    monkeypatch.setattr(iteration, 'stage', execute)
    failed = parent / 'stages/correctness/result.json';before = failed.read_bytes()
    assert iteration.baseline(run, 'maximum')['status'] == 'blocked'
    assert calls == [('correctness', 'correctness')]
    calls.clear()
    assert iteration.baseline(run, 'maximum', correctness_group='correctness-recovery-01')['status'] == 'baseline_validated_and_calibrated'
    assert calls == [('correctness', 'correctness-recovery-01'), ('runtime', 'runtime'), ('control', 'aa-initial')]
    assert failed.read_bytes() == before


@pytest.mark.parametrize('group', ['../correctness', 'runtime', 'correctness/child', 'correctness-', ''])
def test_recovery_group_cannot_escape_or_overwrite_another_stage(tmp_path, monkeypatch, group):
    monkeypatch.setattr(iteration, 'stage', lambda *a, **kw: pytest.fail('no stages should run'))
    with pytest.raises(ValueError, match='correctness group'):
        iteration.baseline(tmp_path, 'maximum', correctness_group=group)


def test_baseline_cli_passes_explicit_group_without_changing_candidate_flow(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(iteration, 'baseline', lambda *args, **kwargs: calls.append((args, kwargs)) or {'status': 'baseline_validated_and_calibrated'})
    monkeypatch.setattr(sys, 'argv', ['level2_iteration.py', 'baseline', '--run', str(tmp_path), '--operator', 'maximum',
                                    '--correctness-group', 'correctness-recovery-01', '--search-protocol', 'full'])
    assert iteration.main() == 0
    assert calls[0][1] == {'correctness_group': 'correctness-recovery-01',
                             'control_group': 'aa-initial', 'measurement': {}, 'deduplicate_outputs': False}
    monkeypatch.setattr(sys, 'argv', ['level2_iteration.py', 'candidate', '--run', str(tmp_path), '--operator', 'maximum',
                                    '--candidate', 'maximum001', '--correctness-group', 'correctness-recovery-01'])
    with pytest.raises(SystemExit) as exc: iteration.main()
    assert exc.value.code == 2


def test_existing_runtime_cannot_silently_rebind_to_new_correctness(recovery, monkeypatch):
    run, parent, source_hash, ledger = recovery
    binding = stage.successful_correctness_binding(ledger, 'maximum', None, parent, source_hash)
    plan = {'case_ids': ALL_CASES, 'source_hash': source_hash, **binding}
    result = {'kind': 'runtime', 'candidate_id': None, 'stage_id': 'baseline-runtime', 'status': 'passed', 'error': None}
    path = parent / 'stages/runtime/result.json';save(path, result);save(path.parent / 'stage-plan.json', plan)
    ledger.state['tasks']['maximum']['stages']['baseline-runtime'] = {
        'kind': 'runtime', 'candidate_id': None, 'plan': plan,
        'attempts': [{'outcome': 'success', 'start_order': 3, 'evidence': {'result': pointer(path)}}]}
    ledger.state['tasks']['maximum']['stages'].update([
        correctness_row(parent, 'correctness-recovery-02', None, source_hash, 4)])
    monkeypatch.setattr(iteration, 'Campaign', lambda path: ledger)
    monkeypatch.setattr(iteration, 'verify_source_snapshot', lambda *args: None)
    monkeypatch.setattr(iteration, 'run_stage', lambda *args, **kwargs: pytest.fail('must not rerun or rewrite'))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='runtime correctness binding differs'):
        iteration.stage(run, 'maximum', 'baseline', 'runtime', 'runtime')
    assert path.read_bytes() == before
