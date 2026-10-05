from __future__ import annotations

import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tarfile

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import TraceWriter, register_json_artifact, verify_optimization_traces, verify_trace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('finalize_level1_campaign', ROOT / 'scripts/finalize_level1_campaign.py')
finalize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalize)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def fixture_run(tmp_path, states=('build_failed', 'accuracy_failed', 'unstable', 'unattributed', 'gain')):
    run = tmp_path / 'campaign'
    dump(run / 'run-manifest.json', {'operators': ['exp'], 'validation_operators': [],
        'sentinel_case_ids': [1, 8, 14, 20], 'acceptance_case_ids': list(range(1, 21)),
        'budget': {'candidate_limit': 6, 'build_limit': 6, 'timing_limit': 6, 'full_profile_limit': 3}})
    task = run / 'tasks/exp'
    frozen = []
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        def snapshot(name):
            p = task / (name + '.tar')
            p.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(p, 'w') as archive:
                member = tarfile.TarInfo('source/op_kernel/kernel.asc')
                payload = name.encode()
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            return store.register_artifact(p)
        baseline = snapshot('baseline')
        stream = TraceWriter(task / 'trace_events.jsonl', run_id=run.name, task_id='exp', session_id='exp-campaign', store=store)
        for index, state in enumerate(states, 1):
            identifier, candidate_id = f'{index:03}', f'exp-{index:03}'
            directory = task / 'candidates' / identifier
            plan = {'candidate_id': candidate_id, 'mode': 'exploration', 'intent': 'Remove redundant vector work',
                'handler_id': 'vector.remove_redundant', 'handler_version': '1.0.0', 'parameters': {'tile': index},
                'expected_effects': ['Fewer vector instructions'], 'coverage_gap': 'Transformation is absent from graph.',
                'static_review': {'explanation': 'Preserves arithmetic order and dynamic shapes.'}}
            dump(directory / 'candidate_plan.json', plan)
            patch = register_json_artifact(store, {'patch': index})
            reg = {'candidate_id': candidate_id, 'mode': 'exploration', 'source_hashes': {'baseline': baseline, 'candidate': snapshot(candidate_id)},
                'patch_artifact_hash': patch, 'plan_hash': store.register_artifact(directory / 'candidate_plan.json')}
            dump(directory / 'registration.json', reg)
            frozen.append({**reg, 'frozen_plan_sha256': file_hash(directory / 'candidate_plan.json')})
            stream.append('candidate_proposed', {'mode': 'exploration', 'hypothesis': plan['intent'], 'source_parent_hash': baseline,
                'patch_hash': patch, 'handler_id': plan['handler_id'], 'handler_version': '1.0.0', 'parameters': plan['parameters'],
                'expected_effects': plan['expected_effects'], 'alternatives': [], 'coverage_gap': plan['coverage_gap']},
                candidate_id=candidate_id, attempt_id=candidate_id)
            log = register_json_artifact(store, {'build': state})
            stream.append('stage_completed', {'stage': 'build', 'status': 'failed' if state == 'build_failed' else 'passed',
                'reason': None, 'execution': None, 'artifact_refs': [log]},
                candidate_id=candidate_id, attempt_id=candidate_id)
            if state == 'build_failed':
                continue
            count = 3 if state == 'accuracy_failed' else 20
            dump(task / 'correctness' / identifier / 'correctness.json', {'status': 'failed' if count < 20 else 'passed',
                'case_ids': list(range(1, 21)), 'passed_count': count, 'case_count': 20,
                'cases': [{'case_id': i, 'kernel_exit_code': 0, 'status': 'passed' if i <= count else 'failed'} for i in range(1, min(count + 1, 20) + 1)]})
            if state == 'accuracy_failed':
                continue
            raw = {'unit': 'ns', 'source': 'acl_event', 'complete': True, 'case_ids': list(range(1, 21)), 'device': 0, 'records': []}
            for case in range(1, 21):
                for pair in range(30):
                    sample = lambda value: {'unit': 'ns', 'source': 'acl_event', 'elapsed_ns': value, 'device': 0}
                    candidate_ns = (40.0 if pair % 2 else 120.0) if state == 'unstable' else 80.0
                    raw['records'].append({'case_id': case, 'round': pair, 'order': ['candidate', 'baseline'] if pair % 2 else ['baseline', 'candidate'],
                        'baseline': sample(100.0), 'candidate': sample(candidate_ns)})
            base = task / 'timing/final' / identifier
            dump(base / 'raw_measurements.json', raw)
            dump(base / 'measurement_report.json', finalize.summarize_multicase(raw))
            if state == 'gain':
                profiles = []
                for label, value in (('baseline', 10), (identifier, 5)):
                    path = task / 'profiles' / label / 'case-01/counters.csv'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f'Kernel,vec_instructions\nexp_kernel,{value}\n')
                    digest = store.register_artifact(path)
                    profile = {'schema_version': '1.0.0', 'case_id': 1, 'kernel': 'exp_kernel',
                        'metrics': {'vec_instructions': {'value': value, 'unit': 'count', 'source_artifact_hash': digest,
                            'field': 'vec_instructions', 'aggregation': 'mean', 'samples': [value]}}}
                    dump(path.parent / 'normalized.json', profile)
                    profiles.append(register_json_artifact(store, profile))
                dump(directory / 'mechanism_report.json', {'schema_version': '1.0.0', 'candidate_id': candidate_id,
                    'hypothesis_basis': 'heuristic', 'metrics': [{'name': 'vec_instructions', 'baseline': 10, 'candidate': 5,
                        'unit': 'count', 'expected_direction': 'decrease', 'baseline_profile_hash': profiles[0], 'candidate_profile_hash': profiles[1]}]})
                dump(directory / 'gate_review.json', {key: {'status': 'passed', 'reason': 'Fixture review of dynamic source behavior.'} for key in ('scope', 'portability')})
        dump(task / 'frozen-roster.json', {'candidates': frozen, 'frozen_at': '2026-09-07T17:00:00Z'})
    return run


def test_all_attempts_failures_raw_evidence_gate_replay_and_idempotence(tmp_path):
    run = fixture_run(tmp_path)
    finalizer = finalize.Finalizer(run)
    result = finalizer.finalize_operator('exp')
    assert [item['verdict'] for item in result['attempts']] == ['build_failed', 'accuracy_failed', 'measurement_unstable', 'attribution_uncertain', 'production_safe_gain']
    assert [item['first_failed_stage'] for item in result['attempts'][:4]] == ['build', 'correctness', 'timing', 'mechanism_alignment']
    assert result['best_source']['candidate_id'] == 'exp-005'
    task = run / 'tasks/exp'
    assert (task / 'best_source/op_kernel/kernel.asc').read_text() == 'exp-005'
    before = (task / 'trace_events.jsonl').read_bytes()
    assert finalizer.finalize_operator('exp') == result
    assert (task / 'trace_events.jsonl').read_bytes() == before
    records = finalize.rows(task / 'optimization_traces.jsonl')
    assert records[2]['result']['speedup'] is None
    assert records[3]['result']['speedup'] == pytest.approx(1.25)
    assert records[3]['lesson']['status'] == 'inconclusive'
    assert records[4]['lesson']['status'] == 'supported'
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        assert store.connection.execute('SELECT count(*) FROM episodes').fetchone()[0] == 0
        for record in records:
            fragment = json.loads(store.verify_artifact(record['result']['attempt_evidence_hash']).read_text())
            assert not any(event['event_type'] == 'attempt_finished' for event in fragment['events'])
        assert verify_optimization_traces(task / 'optimization_traces.jsonl', store)['attempt_count'] == 5
        assert verify_trace(task / 'trace_events.jsonl', store)['valid']
    exported = finalizer.export()
    assert exported['attempt_count'] == 5
    assert (run / 'episodes.jsonl').read_bytes() == b''
    assert (run / 'train/episodes.jsonl').read_bytes() == b''
    assert (run / 'validation/episodes.jsonl').read_bytes() == b''
    assert finalizer.export() == exported


def test_no_verified_gain_delivers_baseline(tmp_path):
    run = fixture_run(tmp_path, ('unattributed',))
    result = finalize.Finalizer(run).finalize_operator('exp')
    assert result['best_source']['candidate_id'] is None
    assert (run / 'tasks/exp/best_source/op_kernel/kernel.asc').read_text() == 'baseline'


def test_pending_jobs_and_changed_roster_are_rejected_before_sealing(tmp_path):
    run = fixture_run(tmp_path, ('build_failed',))
    task = run / 'tasks/exp'
    dump(task / 'jobs/pending.json', {'output_dir': str(task / 'executions/pending')})
    with pytest.raises(StoreError, match='terminal'):
        finalize.Finalizer(run).finalize_operator('exp')
    assert not (task / 'exploration_request.json').exists()
    (task / 'jobs/pending.json').unlink()
    plan = task / 'candidates/001/candidate_plan.json'
    document = json.loads(plan.read_text())
    document['parameters']['tile'] = 777
    dump(plan, document)
    with pytest.raises(StoreError, match='changed after roster freeze'):
        finalize.Finalizer(run).finalize_operator('exp')


def test_forged_measurement_projection_rejected_before_summary(tmp_path):
    run = fixture_run(tmp_path, ('unattributed',))
    path = run / 'tasks/exp/timing/final/001/measurement_report.json'
    report = json.loads(path.read_text())
    report['gate_projection']['candidate_samples_ns'][0] = 1
    dump(path, report)
    with pytest.raises(StoreError, match='does not reproduce raw'):
        finalize.Finalizer(run).finalize_operator('exp')
    assert not (run / 'tasks/exp/optimization_traces.jsonl').exists()


def test_bound_profile_cell_tampering_is_not_an_attribution(tmp_path):
    run = fixture_run(tmp_path, ('gain',))
    path = run / 'tasks/exp/candidates/001/mechanism_report.json'
    report = json.loads(path.read_text())
    report['metrics'][0]['candidate'] = 1
    dump(path, report)
    with pytest.raises(Exception, match='values/units disagree'):
        finalize.Finalizer(run).finalize_operator('exp')


def test_benchmark_gain_can_be_delivered_with_explicit_scope_limit(tmp_path):
    run = fixture_run(tmp_path, ('gain',))
    (run / 'tasks/exp/candidates/001/gate_review.json').unlink()
    result = finalize.Finalizer(run).finalize_operator('exp')
    assert result['attempts'][0]['verdict'] == 'benchmark_specialized_gain'
    assert result['best_source']['candidate_id'] == 'exp-001'
    summary = finalize.rows(run / 'tasks/exp/optimization_traces.jsonl')[0]
    assert summary['lesson']['status'] == 'supported'
    assert any('qualified only for this benchmark' in reason for reason in summary['lesson']['limitations'])
    assert not summary['result']['graph_policy_eligible']


def test_delivered_source_tampering_is_rejected_on_verification(tmp_path):
    run = fixture_run(tmp_path, ('build_failed',))
    finalizer = finalize.Finalizer(run)
    finalizer.finalize_operator('exp')
    (run / 'tasks/exp/best_source/op_kernel/kernel.asc').write_text('unverified mutation')
    with pytest.raises(StoreError, match='best_source no longer matches'):
        finalizer.finalize_operator('exp')


def test_graph_candidate_without_real_store_episode_fails_closed(tmp_path):
    run = fixture_run(tmp_path, ('build_failed',))
    task = run / 'tasks/exp'
    path = task / 'candidates/001/candidate_plan.json'
    plan = finalize.read(path)
    plan['mode'] = 'graph'
    dump(path, plan)
    roster = finalize.read(task / 'frozen-roster.json')
    roster['candidates'][0]['frozen_plan_sha256'] = file_hash(path)
    dump(task / 'frozen-roster.json', roster)
    with pytest.raises(StoreError, match='independently finalized real episode'):
        finalize.Finalizer(run).finalize_operator('exp')
    assert not (task / 'optimization_traces.jsonl').exists()


def test_rich_frozen_plan_notes_are_lossless_strings(tmp_path):
    run = fixture_run(tmp_path, ('build_failed',))
    task = run / 'tasks/exp'
    plan_path = task / 'candidates/001/candidate_plan.json'
    plan = finalize.read(plan_path)
    plan['static_review'] = ['Bounds and arithmetic reviewed.']
    plan['alternatives'] = [{'intent': 'Keep baseline', 'reason_rejected': 'Experiment tests fewer instructions.'}]
    source = task / 'source-review.asc'
    source.write_text('reviewed kernel')
    anchor = {'path': str(source), 'lines': [2, 8], 'sha256': file_hash(source).removeprefix('sha256:')}
    plan['source_anchors'] = [anchor]
    dump(plan_path, plan)
    roster = finalize.read(task / 'frozen-roster.json')
    roster['candidates'][0]['frozen_plan_sha256'] = file_hash(plan_path)
    dump(task / 'frozen-roster.json', roster)
    finalize.Finalizer(run).finalize_operator('exp')
    summary = finalize.rows(task / 'optimization_traces.jsonl')[0]
    assert json.loads(summary['intervention']['alternatives'][0]) == plan['alternatives'][0]
    assert json.loads(summary['diagnosis']['source_anchors'][0]) == anchor


@pytest.mark.parametrize('candidate_value,expected_status', [(20, 'refuted'), (None, 'inconclusive'), (7, 'supported')])
def test_finalizer_preserves_unadmitted_mechanism_bindings(tmp_path, candidate_value, expected_status):
    import csv
    from bind_level1_mechanisms import MechanismBinder, SCALAR, normalize_profile
    run = fixture_run(tmp_path, ('unattributed',))
    task = run / 'tasks/exp'
    dump(task / 'prepared/case_01/metadata.json', {'case_id': 1, 'dtype': 'float32', 'numel': 64})
    def profile(label, value):
        base = task / 'profiles' / label / 'case-01'
        for invocation in range(5):
            path = base / 'raw/OPPROF_20260907_test/exp_kernel' / str(invocation) / f'PipeUtilization_20260907154719{invocation:03}.csv'
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, ['block_id', 'aiv_scalar_time(us)'])
                writer.writeheader()
                writer.writerow({'block_id': 0, 'aiv_scalar_time(us)': value})
        with EpisodeStore(run / 'train/episodes.sqlite') as store:
            normalize_profile(base / 'raw', base / 'normalized-current', 1, store)
    profile('baseline', 10)
    binder = MechanismBinder(run)
    binder.prepare('exp', '001', [1], {'kernel': 'exp_kernel', 'applicability': 'all',
        'metrics': [{'name': SCALAR, 'expected_direction': 'decrease'}], 'rationale': 'Predeclared scalar issue hypothesis.'})
    if candidate_value is not None:
        profile('001', candidate_value)
    binding = binder.bind('exp', '001')
    assert binding['status'] == expected_status
    result = finalize.Finalizer(run).finalize_operator('exp')
    assert result['attempts'][0]['verdict'] == ('benchmark_specialized_gain' if expected_status == 'supported' else 'attribution_uncertain')
    summary = finalize.rows(task / 'optimization_traces.jsonl')[0]
    assert summary['lesson']['status'] == expected_status
    assert any('Predeclared mechanism set is ' + expected_status in reason for reason in summary['lesson']['limitations'])
    assert any('No causal mechanism success' in reason for reason in summary['lesson']['limitations']) == (expected_status != 'supported')
    evidence = finalize.read(task / 'exploration_request.json')['evidence'][0]['artifacts']
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        for key in ('mechanism_plan', 'mechanism_binding'):
            assert evidence[key] in summary['lesson']['evidence_refs']
            assert store.verify_artifact(evidence[key]).read_bytes() == (task / 'candidates/001' / (key + '.json')).read_bytes()
    assert ('mechanism_report' in evidence) == (expected_status == 'supported')
    assert result['best_source']['candidate_id'] == ('exp-001' if expected_status == 'supported' else None)


def test_search_execution_failure_is_not_hidden_by_missing_final_timing(tmp_path):
    run = fixture_run(tmp_path, ('unattributed',))
    task = run / 'tasks/exp'
    import shutil
    shutil.rmtree(task / 'timing/final')
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        failure = register_json_artifact(store, {'stage': 'search_timing', 'exit_code': 2, 'error': 'Device timing execution failed.'})
        writer = TraceWriter(task / 'trace_events.jsonl', run_id=run.name, task_id='exp', session_id='exp-campaign', store=store)
        writer.append('stage_completed', {'stage': 'search_timing', 'status': 'failed',
            'reason': 'Timing command exited 2.', 'execution': None, 'artifact_refs': [failure]},
            candidate_id='exp-001', attempt_id='exp-001')
    result = finalize.Finalizer(run).finalize_operator('exp')
    assert result['attempts'][0]['first_failed_stage'] == 'timing'
    summary = finalize.rows(task / 'optimization_traces.jsonl')[0]
    assert summary['validation']['timing']['status'] == 'failed'
    assert failure in summary['validation']['timing']['artifact_refs']
    assert summary['result']['speedup'] is None
    assert summary['result']['verdict'] == 'artifacts_incomplete'
