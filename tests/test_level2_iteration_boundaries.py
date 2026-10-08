"""CPU-only coordinator recovery, lineage and semantic-guard regression checks."""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import level2_iteration as iteration
import level2_boundaries as boundaries
from msprof_exploration_execute import load, pointer, save, sha
from msprof_exploration_campaign import comparisons
from msprof_exploration_report import digest
from shared_context_build import source_hash


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def stage_fixture(tmp_path, monkeypatch):
    task = tmp_path / 'train/tasks/gcd'
    parent = task / 'candidates/gcd001'
    parent.mkdir(parents=True)
    (parent / 'source.tar').write_bytes(b'frozen-source')
    value = {'kind': 'build', 'candidate_id': 'gcd001', 'stage_id': 'gcd001-build',
             'status': 'passed', 'error': None}
    plan = {'case_ids': list(range(1, 21)), 'source_hash': sha(parent / 'source.tar')}
    result_path = parent / 'stages/build/result.json'
    save(result_path, value)
    save(result_path.parent / 'stage-plan.json', plan)
    row = {'kind': 'build', 'candidate_id': 'gcd001', 'plan': plan,
           'attempts': [{'outcome': 'success', 'evidence': {'result': pointer(result_path)}}]}
    ledger = SimpleNamespace(state={'tasks': {'gcd': {
        'candidates': {'gcd001': {'source_hash': sha(parent / 'source.tar')}},
        'stages': {'gcd001-build': row}}}}, config={})
    monkeypatch.setattr(iteration, 'Campaign', lambda path: ledger)
    monkeypatch.setattr(iteration, 'verify_source_snapshot', lambda *a: None)
    monkeypatch.setattr(iteration, 'run_stage', lambda *a, **k: pytest.fail('resumption must not rerun'))
    return tmp_path, parent, result_path, value, plan, row


@pytest.mark.parametrize('failed', [False, True])
def test_finished_stage_reuses_exact_outcome_without_rewriting(stage_fixture, failed):
    run, parent, path, value, plan, row = stage_fixture
    if failed:
        value.update(status='failed', error={'type': 'CompilerError', 'message': 'invalid API'})
        write(path, value)
        row['attempts'][0].update(outcome='build_failed', evidence={'result': pointer(path)})
    before = path.read_bytes()
    assert iteration.stage(run, 'gcd', 'gcd001', 'build', 'build') == value
    assert path.read_bytes() == before


@pytest.mark.parametrize('mutation,match', [
    ('cases', 'cases differ'), ('explicit_plan', 'requested stage plan'),
    ('result', 'result differs'), ('unfinished', 'incomplete stage ledger'),
    ('source', 'source archive differs'), ('identity', 'identity differs')])
def test_resume_rejects_changed_evidence(stage_fixture, mutation, match):
    run, parent, path, value, plan, row = stage_fixture
    kwargs = {}
    if mutation == 'cases': kwargs['cases'] = [1]
    elif mutation == 'explicit_plan':
        other = parent / 'other.json';save(other, {'case_ids': [1]});kwargs['plan_path'] = other
    elif mutation == 'result':
        value['error'] = {'message': 'tampered'};write(path, value)
    elif mutation == 'unfinished': row['attempts'][0]['outcome'] = None
    elif mutation == 'source': (parent / 'source.tar').write_bytes(b'changed')
    else:
        value['stage_id'] = 'another-build';write(path, value)
    with pytest.raises(ValueError, match=match):
        iteration.stage(run, 'gcd', 'gcd001', 'build', 'build', **kwargs)


def test_partial_stage_is_not_reexecuted(stage_fixture):
    run, parent, path, *_ = stage_fixture
    path.unlink()
    with pytest.raises(ValueError, match='incomplete stage requires explicit evidence recovery'):
        iteration.stage(run, 'gcd', 'gcd001', 'build', 'build')


def close_reports_fixture(task, parent, item):
    from run_msprof_exploration_stage import timing_report_bindings
    plan = load(parent / 'stages/search/stage-plan.json')
    reports = [load(parent / 'stages/search' / c['relation'] / 'report.json') for c in plan['cohorts']]
    binding = timing_report_bindings(parent / 'stages/search', plan['cohorts'], reports)
    result_path = parent / 'stages/search/result.json'
    write(result_path, {'kind': 'timing', 'candidate_id': item['candidate_id'],
        'stage_id': item['candidate_id'] + '-search', 'status': 'passed', 'report_bindings': binding})
    return SimpleNamespace(state={'tasks': {task.name: {'candidates': {item['candidate_id']: item},
        'stages': {item['candidate_id'] + '-search': {'kind': 'timing', 'candidate_id': item['candidate_id'],
            'plan': plan, 'attempts': [{'outcome': 'success', 'evidence': {
                'result': pointer(result_path), 'report_bindings': binding}}]}}}}})


@pytest.fixture
def reports_fixture(tmp_path, monkeypatch):
    task = tmp_path / 'train/tasks/gcd';parent = task / 'candidates/gcd002'
    for directory, content in [(task / 'baseline', 'original'), (task / 'candidates/gcd001/op', 'first'), (parent / 'op', 'second')]:
        (directory / 'op_kernel').mkdir(parents=True)
        (directory / 'op_kernel/kernel.asc').write_text(content)
    for directory, name, content in [(task, 'baseline-source.tar', b'base'), (task / 'candidates/gcd001', 'source.tar', b'first'), (parent, 'source.tar', b'second')]:
        (directory / name).write_bytes(content)
    baseline = sha(task / 'baseline-source.tar')
    item = {'candidate_id': 'gcd002', 'source_hash': sha(parent / 'source.tar'),
            'source_parent': {'candidate_id': 'gcd001', 'source_hash': sha(task / 'candidates/gcd001/source.tar')},
            'probes': [{'case_id': 3}, {'case_id': 5}]}
    cases = [1, 8, 14, 20, 3, 5]
    plan = {'purpose': 'search', 'case_ids': cases, 'comparisons': comparisons(item, baseline), 'cohorts': []}
    for relation, control_id, source in [('direct_parent', 'gcd001', task / 'candidates/gcd001/op'), ('original_baseline', 'baseline', task / 'baseline')]:
        build_path = parent / 'plans' / (relation + '-roles.json')
        hashes = {'A': source_hash(source), 'B': source_hash(parent / 'op')}
        save(build_path, {'operator': 'gcd', 'roles': {r: {'source_sha256': h} for r, h in hashes.items()}})
        frozen = {'case_ids': cases, 'identity_bindings': {'role_build': pointer(build_path)},
                  'calibration_scope': {'epoch': 'epoch-01'},
                  'schedule': [{'name': 'p'+str(i), 'request': {'version': 'msprof_kernel_time_study_v2',
                      'load_order': load_order, 'first_order': first_order, 'buffer_configs': configs}}
                      for i, (load_order, first_order, configs) in enumerate(__import__('msprof_exploration_report').DESIGN)]}
        frozen_path = parent / 'plans' / (relation + '-cohort.json');save(frozen_path, frozen)
        plan['cohorts'].append({'relation': relation, 'control_candidate_id': control_id, 'plan': pointer(frozen_path)})
        report = {'case_ids': [str(c) for c in cases], 'source_hashes': hashes, 'operator': 'gcd',
                  'comparison_kind': 'ab', 'evidence_status': 'verified_complete', 'plan_hash': digest(frozen),
                  'results': [{'case_id': str(c), 'buffer_config': config, 'speedup': 1.1, 'ci95': [1., 1.2],
                               'latency_change': -.1, 'cv_status': 'within_limit', 'calibration_status': 'applicable',
                               'coarse_observed_controls': 'limited', 'measurement_quality': 'complete_with_caution', 'limitations': []}
                              for c in cases for config in ('normal', 'swapped')],
                  'suite': {config: {'case_ids': [str(c) for c in cases]} for config in ('normal', 'swapped')}, 'limitations': []}
        out = parent / 'stages/search' / relation
        save(out / 'report.json', report);save(out / 'group-completion.json', {'status': 'passed'})
    save(parent / 'stages/search/stage-plan.json', plan)
    monkeypatch.setattr(iteration, 'verify_source_snapshot', lambda *args: None)
    ledger = close_reports_fixture(task, parent, item)
    monkeypatch.setattr(iteration, 'Campaign', lambda _: ledger)
    return task, parent, item, baseline, plan


def test_reports_bind_distinct_parent_and_original_without_hidden_cases(reports_fixture):
    task, parent, item, baseline, _ = reports_fixture
    reports = iteration.comparison_reports(task, parent, 'gcd', item, baseline, required=True)
    assert [r['control_candidate_id'] for r in reports] == ['gcd001', 'baseline']
    assert reports[0]['source_hashes']['A'] != reports[1]['source_hashes']['A']
    assert all(r['case_ids'] == ['1', '8', '14', '20', '3', '5'] for r in reports)


@pytest.mark.parametrize('mutation,match', [
    ('missing_parent', 'missing required direct_parent'), ('missing_original', 'missing required original_baseline'),
    ('wrong_source', 'source, plan or completion'), ('wrong_plan', 'source, plan or completion'),
    ('hidden_case', 'public scope'), ('failed_completion', 'source, plan or completion'),
    ('wrong_control', 'selected parent'), ('changed_cohort', 'cohort plan changed'),
    ('changed_role_build', 'role build changed')])
def test_mismatched_or_missing_comparison_cannot_be_measured(reports_fixture, mutation, match):
    task, parent, item, baseline, plan = reports_fixture
    path = parent / 'stages/search/direct_parent/report.json';report = load(path)
    if mutation == 'missing_parent': path.unlink()
    elif mutation == 'missing_original': (parent / 'stages/search/original_baseline/report.json').unlink()
    elif mutation == 'wrong_source': report['source_hashes']['A'] = 'bad';write(path, report)
    elif mutation == 'wrong_plan': report['plan_hash'] = 'bad';write(path, report)
    elif mutation == 'hidden_case': report['results'][0]['case_id'] = '2';write(path, report)
    elif mutation == 'failed_completion': write(path.parent / 'group-completion.json', {'status': 'failed'})
    elif mutation == 'wrong_control':
        plan['cohorts'][0]['control_candidate_id'] = 'baseline';write(parent / 'stages/search/stage-plan.json', plan)
    elif mutation == 'changed_cohort': write(Path(plan['cohorts'][0]['plan']['path']), {})
    else: write(parent / 'plans/direct_parent-roles.json', {})
    with pytest.raises(ValueError, match=match):
        iteration.comparison_reports(task, parent, 'gcd', item, baseline, required=True)


def test_first_round_reuses_one_comparison_for_identical_parent_and_original(reports_fixture, monkeypatch):
    task, parent, item, baseline, plan = reports_fixture
    item['source_parent'] = {'candidate_id': None, 'source_hash': baseline}
    original = plan['cohorts'][1];original['relation'] = 'direct_parent'
    plan.update(comparisons=comparisons(item, baseline), cohorts=[original])
    write(parent / 'stages/search/stage-plan.json', plan)
    for name in ('report.json', 'group-completion.json'):
        write(parent / 'stages/search/direct_parent' / name, load(parent / 'stages/search/original_baseline' / name))
    ledger = close_reports_fixture(task, parent, item)
    monkeypatch.setattr(iteration, 'Campaign', lambda _: ledger)
    reports = iteration.comparison_reports(task, parent, 'gcd', item, baseline, required=True)
    assert len(reports) == 1 and reports[0]['control_candidate_id'] == 'baseline'


@pytest.fixture
def boundary_fixture(tmp_path, monkeypatch):
    task = tmp_path / 'train/tasks/gcd';parent = task / 'candidates/gcd001'
    script = task / 'agent/boundary_guard.py';script.parent.mkdir(parents=True);script.write_text('# independent guard')
    binary = parent / 'build/gcd';binary.parent.mkdir(parents=True);binary.write_bytes(b'executable')
    save(parent / 'build/build_manifest.json', {'standalone': pointer(binary)})
    save(parent / 'dispatch_plan.json', {'entries': [{'tiling_key': 1, 'kernel_entry': 'gcd_linear_kernel'}],
         'fallback': {'tiling_key': 0, 'kernel_entry': 'gcd_kernel'}})
    control = {'key': 1, 'entry': 'gcd_linear_kernel', 'exit_status': 0, 'stderr': '', 'reject': False, 'verify_fail': False, 'timeout': False}
    calls = []
    def process(argv, cwd, out, **kwargs):
        argv = list(map(str, argv));calls.append(argv);out.mkdir(parents=True)
        if out.name == 'prepare':
            inputs = Path(argv[argv.index('--output') + 1])
            save(inputs / 'coordinator_commands.json', [{'name': 'minimum', 'argv': [], 'expected_key': 1,
                 'expected_exit': 'nonzero' if control['reject'] else 0,
                 'expected_error': 'index value out of' if control['reject'] else None}])
        elif out.name == 'verify':
            if control['verify_fail']: raise RuntimeError('precision mismatch')
        else:
            save(out / 'execution.json', {'exit_status': control['exit_status']})
            (out / 'stdout.log').write_text('APROF_DISPATCH_JSON:'+json.dumps({'tiling_key': control['key'], 'kernel_entry': control['entry']})+'\n')
            (out / 'stderr.log').write_text(control['stderr'])
            if control['timeout']:
                import subprocess
                raise subprocess.TimeoutExpired(argv, 1)
            if control['exit_status']: raise RuntimeError('nonzero process')
    monkeypatch.setattr(boundaries, 'run_process', process)
    monkeypatch.setattr(boundaries, 'exclusive_host', nullcontext)
    monkeypatch.setattr(boundaries, 'health', lambda p: None)
    return tmp_path, task, parent, control, calls


def test_guard_passes_actual_plan_to_both_phases_and_binds_entry(boundary_fixture):
    run, task, parent, control, calls = boundary_fixture
    result = boundaries.collect(run, 'gcd', 'gcd001')
    assert result['status'] == 'passed'
    for argv in (calls[0], calls[-1]):
        assert argv[argv.index('--plan') + 1] == str(parent / 'dispatch_plan.json')
    assert load(result['request']['path'])['dispatch_plan'] == pointer(parent / 'dispatch_plan.json')
    assert iteration.boundary_result(task, parent, 'gcd', 'gcd001') == result
    before = (parent / 'boundary-validation/completion.json').read_bytes()
    with pytest.raises(FileExistsError): boundaries.collect(run, 'gcd', 'gcd001')
    assert (parent / 'boundary-validation/completion.json').read_bytes() == before


@pytest.mark.parametrize('field,value', [('key', 0), ('key', True), ('entry', 'wrong_kernel'), ('verify_fail', True)])
def test_wrong_dispatch_or_failed_oracle_never_passes(boundary_fixture, field, value):
    run, task, parent, control, calls = boundary_fixture;control[field] = value
    assert boundaries.collect(run, 'gcd', 'gcd001')['status'] == 'failed'


def test_expected_rejection_is_distinct_from_timeout_or_signal(boundary_fixture):
    run, task, parent, control, _ = boundary_fixture
    control.update(reject=True, exit_status=1, stderr='index value out of range')
    assert boundaries.collect(run, 'gcd', 'gcd001', parent / 'expected-rejection')['status'] == 'passed'
    control.update(exit_status=-15, timeout=True)
    assert boundaries.collect(run, 'gcd', 'gcd001', parent / 'timed-out')['status'] == 'failed'


def test_guard_resume_rejects_plan_drift(boundary_fixture):
    run, task, parent, control, _ = boundary_fixture
    boundaries.collect(run, 'gcd', 'gcd001')
    write(parent / 'dispatch_plan.json', {'changed': True})
    with pytest.raises(ValueError, match='dispatch plan differs'):
        iteration.boundary_result(task, parent, 'gcd', 'gcd001')


def test_closed_failure_remains_failure_and_never_reexecutes(tmp_path, monkeypatch):
    task = tmp_path / 'train/tasks/gcd';parent = task / 'candidates/gcd001'
    item = {'source_hash': 'sha256:'+'a'*64, 'source_parent': {'candidate_id': None, 'source_hash': 'sha256:'+'b'*64},
            'feedback_closed': True, 'observation_ids': ['gcd001-feedback-01']}
    feedback = {'candidate_id': 'gcd001', 'operator': 'gcd', 'source_hash': item['source_hash'],
                'source_parent': item['source_parent'], 'status': 'infrastructure_blocked'}
    path = task / 'feedback/gcd001.json';save(path, feedback)
    ledger = SimpleNamespace(state={'tasks': {'gcd': {'candidates': {'gcd001': item}, 'observations': {
        'gcd001-feedback-01': {'report_ref': sha(path), 'feedback': feedback}}}}})
    monkeypatch.setattr(iteration, 'Campaign', lambda p: ledger)
    monkeypatch.setattr(iteration, 'stage', lambda *a, **kw: pytest.fail('closed feedback must not execute'))
    result = iteration.candidate(tmp_path, 'gcd', 'gcd001')
    assert result['status'] == 'infrastructure_blocked' and result['feedback_already_closed']
    write(path, dict(feedback, status='measured'))
    with pytest.raises(ValueError, match='immutable observation'):
        iteration.candidate(tmp_path, 'gcd', 'gcd001')


@pytest.mark.parametrize('failure,expected', [('none', 'measured'), ('missing_report', 'infrastructure_blocked'),
                                              ('timing', 'infrastructure_blocked'), ('build', 'infrastructure_blocked')])
def test_candidate_feedback_preserves_infrastructure_failures_without_closing_round(reports_fixture, monkeypatch, failure, expected):
    task, parent, item, baseline, plan = reports_fixture
    run = task.parents[2]
    item.update(feedback_closed=False, observation_ids=[])
    state = {'candidates': {'gcd002': item}, 'stages': {}, 'reserved_final_candidate_ids': []}
    observations, calls = [], []
    ledger = SimpleNamespace(state={'tasks': {'gcd': state}}, config={'tasks': {'gcd': {'baseline_source_hash': baseline}}},
                             observe=lambda **kwargs: observations.append(kwargs))
    monkeypatch.setattr(iteration, 'Campaign', lambda path: ledger)
    save(parent / 'proposal.json', {'optimization_stage': 'execution'})
    save(parent / 'plans/search/stage-plan.json', plan)
    if failure == 'missing_report': (parent / 'stages/search/original_baseline/report.json').unlink()
    def run_stage(run, operator, cid, kind, group, **kwargs):
        calls.append(kind)
        failed = kind == failure
        row = {'kind': kind, 'candidate_id': cid, 'stage_id': cid+'-'+group,
               'status': 'failed' if failed else 'passed', 'error': {'message': 'actual failure'} if failed else None}
        path = parent / 'stages' / group / 'result.json'
        if kind == 'timing' and not failed:
            row['report_bindings'] = load(path)['report_bindings']
        write(path, row)
        evidence = {'result': pointer(path)}
        if 'report_bindings' in row: evidence['report_bindings'] = row['report_bindings']
        state['stages'][row['stage_id']] = {'kind': kind, 'candidate_id': cid,
            'plan': plan if kind == 'timing' else {},
            'attempts': [{'outcome': 'failed' if failed else 'success', 'evidence': evidence}]}
        return row
    monkeypatch.setattr(iteration, 'stage', run_stage)
    result = iteration.candidate(run, 'gcd', 'gcd002', boundaries=False)
    assert result['status'] == expected
    assert len(observations) == 1 and observations[0]['close_feedback'] is (expected != 'infrastructure_blocked')
    feedback = observations[0]['feedback']
    assert feedback['source_parent'] == item['source_parent']
    assert feedback['source_hash'] == item['source_hash']
    assert observations[0]['quality']['complete_measurement'] == (expected == 'measured')
    assert set(observations[0]['stage_ids']) == set(state['stages'])
    if failure == 'build': assert calls == ['build']
    if failure == 'missing_report': assert feedback['measurement_error'] and not feedback['comparisons']


@pytest.mark.parametrize('kind', ['build', 'correctness'])
def test_unknown_infrastructure_failure_stays_open_and_reentry_is_idempotent(reports_fixture, monkeypatch, kind):
    task, parent, item, baseline, plan = reports_fixture
    run = task.parents[2]
    item.update(feedback_closed=False, observation_ids=[])
    state = {'candidates': {'gcd002': item}, 'stages': {}, 'observations': {}, 'reserved_final_candidate_ids': []}
    observations = []
    def observe(**value):
        observations.append(value)
        state['observations'][value['observation_id']] = value
        item['observation_ids'].append(value['observation_id'])
        item['feedback_closed'] = value['close_feedback']
    ledger = SimpleNamespace(state={'tasks': {'gcd': state}},
        config={'tasks': {'gcd': {'baseline_source_hash': baseline}}}, observe=observe)
    monkeypatch.setattr(iteration, 'Campaign', lambda *_: ledger)
    save(parent / 'proposal.json', {'optimization_stage': 'execution'})
    save(parent / 'plans/search/stage-plan.json', plan)
    def execute(run, operator, cid, actual, group, **kwargs):
        failed = actual == kind
        result = {'kind': actual, 'candidate_id': cid, 'stage_id': cid+'-'+group,
            'status': 'failed' if failed else 'passed', 'native_started': False,
            'error': {'type': 'ValueError', 'message': 'expected exactly one supported host, found []'} if failed else None}
        save(parent / 'stages' / group / 'result.json', result)
        state['stages'][result['stage_id']] = {'candidate_id': cid,
            'attempts': [{'outcome': 'failed' if failed else 'success'}]}
        return result
    monkeypatch.setattr(iteration, 'stage', execute)
    monkeypatch.setattr(iteration, 'reclaim_outputs', lambda *a: pytest.fail('no closed successful timing to reclaim'))
    first = iteration.candidate(run, 'gcd', 'gcd002', boundaries=False, deduplicate_outputs=True)
    assert first['status'] == 'infrastructure_blocked'
    assert item['feedback_closed'] is False and observations[0]['close_feedback'] is False
    feedback = load(first['feedback']['path'])
    assert feedback['failure_classification']['status'] == 'infrastructure_blocked'
    before = Path(first['feedback']['path']).read_bytes()
    monkeypatch.setattr(iteration, 'stage', lambda *a, **kw: pytest.fail('blocked reentry must not execute'))
    again = iteration.candidate(run, 'gcd', 'gcd002', boundaries=False, deduplicate_outputs=True)
    assert again['status'] == 'infrastructure_blocked' and again['feedback_already_recorded']
    assert again['feedback_already_closed'] is False and len(observations) == 1
    assert Path(first['feedback']['path']).read_bytes() == before


def test_positive_compiler_source_failure_closes_real_candidate_feedback(tmp_path, monkeypatch):
    from test_level2_failure_classification import compiler
    task, parent, failed_stage = compiler(tmp_path)
    cid = parent.name;run = task.parents[2]
    item = {'source_hash': 'sha256:'+'c'*64,
        'source_parent': {'candidate_id': None, 'source_hash': 'sha256:'+'b'*64},
        'feedback_closed': False, 'observation_ids': []}
    state = {'candidates': {cid: item}, 'stages': {failed_stage['stage_id']: {
        'candidate_id': cid, 'attempts': [{'outcome': 'build_failed'}]}}, 'reserved_final_candidate_ids': []}
    observations = []
    ledger = SimpleNamespace(state={'tasks': {'maximum': state}},
        config={'tasks': {'maximum': {'baseline_source_hash': 'sha256:'+'b'*64}}},
        observe=lambda **value: observations.append(value))
    monkeypatch.setattr(iteration, 'Campaign', lambda *_: ledger)
    calls = []
    def execute(*args, **kwargs):
        calls.append(args[3]);assert args[3] == 'build'
        return failed_stage
    monkeypatch.setattr(iteration, 'stage', execute)
    save(parent/'proposal.json', {'optimization_stage': 'execution'})
    result = iteration.candidate(run, 'maximum', cid)
    assert result['status'] == 'source_attempt_failed' and calls == ['build']
    assert observations[0]['close_feedback'] is True
    classification = observations[0]['feedback']['failure_classification']
    assert classification['rule'] == 'original_source_compiler_diagnostic'
    assert classification['status'] == 'source_attempt_failed' and classification['evidence']


def test_candidate_reclaims_outputs_only_after_completed_timing_stage(reports_fixture, monkeypatch):
    task,parent,item,baseline,plan = reports_fixture;run = task.parents[2]
    item.update(feedback_closed=False, observation_ids=[])
    state = {'candidates': {'gcd002': item}, 'stages': {}, 'reserved_final_candidate_ids': []}
    calls = []
    ledger = SimpleNamespace(state={'tasks': {'gcd': state}},
        config={'tasks': {'gcd': {'baseline_source_hash': baseline}}}, observe=lambda **_: None)
    monkeypatch.setattr(iteration,'Campaign',lambda *_: ledger)
    save(parent/'proposal.json',{'optimization_stage':'execution'})
    save(parent/'plans/search/stage-plan.json',plan)
    def execute(run,operator,cid,kind,group,**kwargs):
        result={'kind':kind,'candidate_id':cid,'stage_id':cid+'-'+group,'status':'passed','error':None}
        path = parent/'stages'/group/'result.json'
        if kind == 'timing': result['report_bindings'] = load(path)['report_bindings']
        write(path,result)
        evidence = {'result': pointer(path)}
        if 'report_bindings' in result: evidence['report_bindings'] = result['report_bindings']
        state['stages'][result['stage_id']]={'kind':kind,'candidate_id':cid,
            'plan':plan if kind == 'timing' else {},
            'attempts':[{'outcome':'success','evidence':evidence}]}
        calls.append('closed-'+kind)
        return result
    monkeypatch.setattr(iteration,'stage',execute)
    def reclaim(*args):
        assert calls == ['closed-build','closed-correctness','closed-runtime','closed-timing']
        assert args[-1]=='search';calls.append('dedup')
    monkeypatch.setattr(iteration,'reclaim_outputs',reclaim)
    assert iteration.candidate(run,'gcd','gcd002',boundaries=False,deduplicate_outputs=True)['status']=='measured'
    assert calls[-1]=='dedup'
