"""New controller-to-verifier integration, with synthetic collector artifacts."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cannbench_msprof_timing as producer
import msprof_exploration_execute as execute
import msprof_exploration_report as report
import run_msprof_exploration_stage as stage
from test_msprof_exploration_report import setup_inputs, make_session, put


def test_controller_collects_six_real_evidence_fixtures_then_replays(tmp_path, monkeypatch):
    task = tmp_path / 'campaign/train/tasks/exp'
    verifier = task / 'baseline/scripts/verify_result.py'
    verifier.parent.mkdir(parents=True)
    verifier.write_text('# never executed: CPU fixture oracle\n')
    request, build = setup_inputs(task, ids=(1, 8))
    for row in request['cases']:
        row['verifier'] = str(verifier)
    put(task / 'input-bindings.json', {'cases': [
        {'case_id': row['case_id'], 'metadata': execute.pointer(row['metadata']),
         'verifier': execute.pointer(row['verifier']),
         'inputs': {'input': execute.pointer(execute.load(row['metadata'])['input'])},
         'oracle_file': execute.pointer(execute.load(row['metadata'])['golden'])}
        for row in request['cases']]})
    monkeypatch.setattr(execute.socket, 'gethostname', lambda: 'fixture-host')
    plan = execute.cohort_plan(task, request['role_build'], request['runner_build'], [1, 8], 'aa', 'initial')
    assert report.validate_plan(plan) == plan
    calls = []

    def collect(request_path, out):
        actual = execute.load(request_path)
        directory = make_session(Path(out).parent, actual, build, number=len(calls), name=Path(out).name)
        calls.append(str(directory))

    monkeypatch.setattr(execute, 'execution_modules', lambda: (SimpleNamespace(collect=collect, summarize=producer.summarize), None, None))
    group = task / 'stages/aa-initial/cohort'
    result = execute.collect_cohort(plan, group)
    completed = execute.load(group / 'group-completion.json')
    assert len(calls) == 6
    assert completed['status'] == 'passed'
    assert completed['completed_sessions'] == calls
    assert execute.load(group / 'report.json') == result
    # Publication after collection must not change the verifier's input closure.
    assert report.analyze_task_cohort(calls, plan) == result
    old = execute.load(group / 'producer-summary.json')
    assert old['version'] == report.PRODUCER
    assert all('aa_within_half_percent' in row for row in old['results'])
    assert all('aa_within_half_percent' not in row for row in result['results'])
    costs = stage.actual_costs(group)
    assert costs['native_processes_started'] == costs['native_processes_completed'] == 6
    assert costs['role_samples'] == 6 * 2 * 2 * 30 * 2
    assert costs['timed_complete_calls'] == costs['role_samples'] * 10


def test_actual_combined_manifest_passes_new_verifier(tmp_path):
    control_request, control = setup_inputs(tmp_path / 'control')
    candidate_request, _ = setup_inputs(tmp_path / 'candidate', kind='ab')
    composed_path = tmp_path / 'comparison.json'
    composed = execute.comparison_manifest(control_request['role_build'], candidate_request['role_build'], composed_path)
    request = {**control_request, 'role_build': str(composed_path)}
    directory = make_session(tmp_path / 'measurement', request, composed)
    verified = report.verify_observation(directory, request)
    assert verified['source_hashes']['A'] == control['roles']['A']['source_sha256']
    assert verified['source_hashes']['A'] != verified['source_hashes']['B']
    assert composed['component_builds'][1]['path'] in verified['artifacts']


def test_cpu_runtime_assessment_does_not_claim_another_native_start(tmp_path):
    correctness = tmp_path / 'correctness'
    put(correctness / 'completion.json', {'status': 'passed', 'completed': [{'case_id': str(c)} for c in range(1, 21)]})
    for case in range(1, 21):
        put(correctness / f'case_{case:02d}/native.json', {'exit_code': 0, 'stream_destroyed': True,
                                                        'context_destroyed': True, 'finalized': True})
    out = tmp_path / 'runtime'; out.mkdir()
    assessed = stage.runtime_assessment(correctness, out / 'runtime.json')
    assert assessed['new_native_execution'] is False
    assert execute.native_started_in(out) is False
    assert stage.actual_costs(out)['native_processes_started'] == 0
