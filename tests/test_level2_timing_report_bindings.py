"""No NPU: resumed feedback must use immutable finished report hashes or full replay."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import level2_iteration as iteration
import run_msprof_exploration_stage as stage
import msprof_exploration_report as analysis
from msprof_exploration_execute import load, pointer, save
from test_msprof_search_lite import lite_cohort
from test_msprof_exploration_report import make_cohort


def fixture(tmp_path, monkeypatch, *, bound=True, lite=True):
    task = tmp_path / 'run/train/tasks/maximum'
    parent = task / 'candidates/maximum001'; directory = parent / 'stages/search'
    cohort_dir = directory / 'direct_parent'
    sessions, frozen = lite_cohort(cohort_dir) if lite else make_cohort(cohort_dir, ids=(1, 8), kind='ab')
    report = analysis.analyze_task_cohort(sessions, frozen)
    save(cohort_dir / 'plan.json', frozen); save(cohort_dir / 'report.json', report)
    completion = {'status': 'passed', 'error': None, 'completed_sessions': list(map(str, sessions))}
    save(cohort_dir / 'group-completion.json', completion)
    frozen_path = parent / 'plans/search/direct_parent-cohort.json'; save(frozen_path, frozen)
    cohort = {'relation': 'direct_parent', 'control_candidate_id': 'baseline', 'plan': pointer(frozen_path)}
    plan = {'purpose': 'search', 'protocol': frozen['protocol'], 'cohorts': [cohort]}
    if not lite:
        # A real A/A fixture is not necessary to replay this historically
        # uncalibrated synthetic comparison; None is explicit reader input.
        calibration_path = task / 'stages/aa-initial/cohort/report.json'
        save(calibration_path, None)
    save(directory / 'stage-plan.json', plan)
    item = {'candidate_id': 'maximum001', 'source_hash': 'sha256:' + 'a' * 64,
            'source_parent': {'candidate_id': None, 'source_hash': 'sha256:' + 'b' * 64}}
    result = {'kind': 'timing', 'candidate_id': item['candidate_id'],
              'stage_id': 'maximum001-search', 'status': 'passed'}
    evidence = {}
    if bound:
        binding = stage.timing_report_bindings(directory, [cohort], [report])
        result['report_bindings'] = binding; evidence['report_bindings'] = copy.deepcopy(binding)
    save(directory / 'result.json', result); evidence['result'] = pointer(directory / 'result.json')
    row = {'kind': 'timing', 'candidate_id': item['candidate_id'], 'plan': plan,
           'attempts': [{'outcome': 'success', 'evidence': evidence}]}
    ledger = SimpleNamespace(state={'tasks': {'maximum': {
        'candidates': {item['candidate_id']: item}, 'stages': {'maximum001-search': row}}}})
    monkeypatch.setattr(iteration, 'Campaign', lambda _: ledger)
    def authenticate():
        observed = {'relation': 'direct_parent', 'cohort': cohort, 'frozen': frozen,
            'directory': cohort_dir, 'report': load(cohort_dir / 'report.json'),
            'completion': load(cohort_dir / 'group-completion.json')}
        return iteration.authenticate_timing_reports(task, parent, 'maximum', item, plan, [observed], required=True)
    return authenticate, cohort_dir, row, result, frozen


def test_fresh_and_resumed_bound_reports_do_not_reread_raw_payloads(tmp_path, monkeypatch):
    authenticate, *_ = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, 'analyze_task_cohort', lambda *a, **k: pytest.fail('bound feedback reread raw'))
    authenticate()
    authenticate()  # A new function invocation uses ledger hashes, not a cache object.


@pytest.mark.parametrize('mutation', ['report', 'completion', 'result', 'ledger_binding',
                                     'deleted_ledger_binding', 'wrong_path', 'failed_stage'])
def test_bound_feedback_rejects_tamper_without_running_raw_analysis(tmp_path, monkeypatch, mutation):
    authenticate, directory, row, result, _ = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis, 'analyze_task_cohort', lambda *a, **k: pytest.fail('tamper fell back to replay'))
    if mutation == 'report':
        value = load(directory / 'report.json'); value['results'][0]['speedup'] = 99
        (directory / 'report.json').write_text(json.dumps(value))
    elif mutation == 'completion':
        value = load(directory / 'group-completion.json'); value['ended_at'] = 'changed'
        (directory / 'group-completion.json').write_text(json.dumps(value))
    elif mutation == 'result':
        result['report_bindings']['cohorts'][0]['report']['sha256'] = 'sha256:' + '0' * 64
        (directory.parent / 'result.json').write_text(json.dumps(result))
    elif mutation == 'ledger_binding':
        row['attempts'][0]['evidence']['report_bindings']['cohorts'][0]['report']['sha256'] = 'sha256:' + '0' * 64
    elif mutation == 'deleted_ledger_binding':
        row['attempts'][0]['evidence'].pop('report_bindings')
    elif mutation == 'wrong_path':
        row['attempts'][0]['evidence']['result']['path'] = str(directory / 'result.json')
    else:
        row['attempts'][0]['outcome'] = 'failed'
    with pytest.raises(ValueError): authenticate()


@pytest.mark.parametrize('lite', [False, True])
@pytest.mark.parametrize('mutation', ['raw_output', 'report'])
def test_unbound_legacy_completion_replays_real_observations(tmp_path, monkeypatch, lite, mutation):
    authenticate, directory, _, _, frozen = fixture(tmp_path, monkeypatch, bound=False, lite=lite)
    original = analysis.analyze_task_cohort; calls = []
    def replay(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(analysis, 'analyze_task_cohort', replay)
    authenticate()
    assert len(calls) == 1 and len(calls[0][0][0]) == (2 if lite else 6)
    assert '_verified_sessions' not in calls[0][1]
    if mutation == 'raw_output':
        session = directory / frozen['schedule'][0]['name']
        (session / 'native/1_normal_A.bin').write_bytes(b'tampered raw output')
        match = 'output hash'
    else:
        value = load(directory / 'report.json'); value['results'][0]['speedup'] = 99
        (directory / 'report.json').write_text(json.dumps(value))
        match = 'saved report differs from verified observation analysis'
    with pytest.raises(ValueError, match=match): authenticate()


def test_collector_result_cannot_be_replaced_before_it_is_bound(tmp_path, monkeypatch):
    _, directory, _, _, _ = fixture(tmp_path, monkeypatch)
    verified = load(directory / 'report.json')
    changed = copy.deepcopy(verified); changed['results'][0]['speedup'] = 99
    (directory / 'report.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='differs from collector verification'):
        stage.timing_report_bindings(directory.parent, [{'relation': 'direct_parent'}], [verified])


@pytest.mark.parametrize('lite', [False, True])
def test_closed_legacy_feedback_uses_immutable_report_without_raw_replay(tmp_path, monkeypatch, lite):
    authenticate, directory, _, _, _ = fixture(tmp_path, monkeypatch, bound=False, lite=lite)
    task = directory.parents[4]
    state = iteration.Campaign(task.parents[1] / 'ledger').state['tasks']['maximum']
    item = state['candidates']['maximum001']
    feedback = {'candidate_id': 'maximum001', 'operator': 'maximum',
        'source_hash': item['source_hash'], 'source_parent': item['source_parent'],
        'comparisons': [{'relation': 'direct_parent', 'report': pointer(directory / 'report.json')}]}
    feedback_path = task / 'feedback/maximum001.json'; save(feedback_path, feedback)
    oid = 'maximum001-feedback-01'
    state['observations'] = {oid: {'close_feedback': True, 'stage_ids': ['maximum001-search'],
        'stage_attempts': {'maximum001-search': 1}, 'feedback': feedback,
        'report_ref': pointer(feedback_path)['sha256']}}
    item.update(feedback_closed=True, observation_ids=[oid])
    monkeypatch.setattr(analysis, 'analyze_task_cohort', lambda *a, **k: pytest.fail('closed round replayed raw'))
    authenticate()
    original = (directory / 'report.json').read_bytes()
    value = load(directory / 'report.json'); value['results'][0]['speedup'] = 99
    (directory / 'report.json').write_text(json.dumps(value))
    with pytest.raises(ValueError, match='closed feedback report changed'): authenticate()
    (directory / 'report.json').write_bytes(original)
    changed_feedback = dict(feedback, source_hash='sha256:' + 'c' * 64)
    feedback_path.write_text(json.dumps(changed_feedback))
    with pytest.raises(ValueError, match='immutable observation'): authenticate()


def test_timing_finish_binds_report_hashes_in_result_and_ledger(tmp_path, monkeypatch):
    recorded = []
    class Ledger:
        config = {'policy': {'protocol': stage.PROTOCOL}}
        def __init__(self, *_): pass
        def validate_start(self, **_): pass
        def start(self, **_): pass
        def finish(self, **value): recorded.append(value)
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    def collect(plan, out, calibration):
        verified = {'evidence_status': 'verified_complete', 'results': [{'speedup': 1.2}]}
        save(out / 'report.json', verified); save(out / 'group-completion.json', {'status': 'passed', 'error': None})
        return verified
    monkeypatch.setattr(stage, 'collect_cohort', collect)
    frozen = tmp_path / 'cohort.json'; save(frozen, {'scope': 'synthetic'})
    calibration = tmp_path / 'calibration.json'; save(calibration, None)
    plan_path = tmp_path / 'plan.json'
    save(plan_path, {'calibration_report': pointer(calibration),
                    'cohorts': [{'relation': 'direct_parent', 'plan': pointer(frozen)}]})
    result = stage.run_stage(tmp_path, 'exp', 'exp001', 'timing', 'search', plan_path=plan_path)
    assert result['status'] == 'passed'
    assert result['report_bindings'] == recorded[0]['evidence']['report_bindings']
    assert result['report_bindings']['version'] == 'level2_timing_report_bindings_v1'
    assert load(recorded[0]['evidence']['result']['path']) == result
