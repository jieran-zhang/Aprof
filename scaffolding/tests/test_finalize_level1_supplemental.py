"""CPU-only checks for explicit exp006 qualification evidence retention."""
import json

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import TraceWriter, register_json_artifact
from test_finalize_level1_campaign import dump, finalize, fixture_run


def qualification(run, *, status='passed', manifest_candidate='exp-006'):
    task = run / 'tasks/exp'
    root = task / 'qualification/zero_affine'
    directory = root / 'attempts/001'
    manifest = {'schema_version': '1.0.0', 'kind': 'supplemental_correctness_execution_manifest',
        'candidate_id': manifest_candidate, 'attempt': '001', 'case_count': 9,
        'purpose': 'correctness_only_no_performance_feedback',
        'timing_environment_unset': ['APROF_TIMING', 'APROF_TIMING_INTERACTIVE', 'APROF_WARMUP', 'APROF_REPEAT', 'APROF_SAMPLES'],
        'sources': [], 'cases': [{'case_id': f'zero-affine-{dtype}-n{size}'}
            for dtype in ('float32', 'float16', 'bfloat16') for size in (17, 4097, 196673)]}
    dump(directory / 'execution_manifest.json', manifest)
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        manifest_ref = register_json_artifact(store, {**manifest, 'source_artifact_refs': []})
        body = {'schema_version': '1.0.0', 'kind': 'supplemental_correctness_validation',
            'candidate_id': 'exp-006', 'attempt': '001', 'status': status, 'case_count': 9,
            'attempted_count': 9 if status == 'passed' else 1, 'passed_count': 9 if status == 'passed' else 0,
            'purpose': manifest['purpose'], 'timing_environment_unset': manifest['timing_environment_unset'],
            'run_manifest_ref': manifest_ref, 'event_id': 'exp-006-special-values-001-completed'}
        summary_ref = register_json_artifact(store, body)
        report = {**body, 'summary_ref': summary_ref}
        dump(root / 'hardware_validation.json', report)
        dump(directory / 'hardware_validation.json', report)
        raw_ref = store.register_artifact(root / 'hardware_validation.json')
        dump(directory / 'binding.json', {'artifact_ref': raw_ref,
            'summary_ref': summary_ref, 'event_id': body['event_id']})
        writer = TraceWriter(task / 'trace_events.jsonl', run_id=run.name,
            task_id='exp', session_id='exp-campaign', store=store)
        writer.append('next_step_decided', {'action': 'record_supplemental_correctness_qualification',
            'reason': 'Recorded correctness-only qualification; existing mandatory failures remain authoritative.',
            'evidence_refs': [raw_ref, summary_ref, manifest_ref]},
            candidate_id='exp-006', attempt_id='exp-006', event_id=body['event_id'])
    return {'supplemental_correctness': raw_ref,
        'supplemental_correctness_manifest': manifest_ref,
        'supplemental_correctness_summary': summary_ref}


@pytest.mark.parametrize('state,status,semantic,expected', [
    ('unattributed', 'passed', None, 'attribution_uncertain'),
    ('build_failed', 'passed', None, 'build_failed'),
    ('gain', 'failed', 'failed', 'accuracy_failed'),
])
def test_supplemental_refs_reach_gate_lesson_and_sealed_evidence_without_overriding_gates(
        tmp_path, state, status, semantic, expected):
    run = fixture_run(tmp_path, ('build_failed',) * 5 + (state,))
    task = run / 'tasks/exp'
    expected_refs = qualification(run, status=status)
    if semantic:
        path = task / 'candidates/006/gate_review.json'
        review = finalize.read(path)
        review['semantic'] = {'status': semantic, 'reason': 'Supplemental special-value qualification failed.'}
        dump(path, review)
    result = finalize.Finalizer(run).finalize_operator('exp')
    assert result['attempts'][-1]['verdict'] == expected
    assert result['best_source']['candidate_id'] is None
    summary = finalize.rows(task / 'optimization_traces.jsonl')[-1]
    request = finalize.read(task / 'exploration_request.json')
    gate = request['evidence'][-1]
    assert all(key not in item['artifacts'] for item in request['evidence'][:-1] for key in expected_refs)
    assert {key: gate['artifacts'][key] for key in expected_refs} == expected_refs
    assert set(expected_refs.values()).issubset(summary['lesson']['evidence_refs'])
    assert gate['semantic'] == (semantic or ('not_run' if state == 'build_failed' else 'passed'))
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        assert store.verify_artifact(expected_refs['supplemental_correctness']).read_bytes() == (
            task / 'qualification/zero_affine/hardware_validation.json').read_bytes()
        manifest = finalize.read(store.verify_artifact(expected_refs['supplemental_correctness_manifest']))
        assert manifest['candidate_id'] == 'exp-006' and manifest['case_count'] == 9
        for role in ('supplemental_correctness_binding', 'supplemental_correctness_execution_manifest'):
            assert gate['artifacts'][role] in summary['lesson']['evidence_refs']
            store.verify_artifact(gate['artifacts'][role])
        fragment = finalize.read(store.verify_artifact(summary['result']['attempt_evidence_hash']))
        seal = next(event for event in fragment['events'] if event['event_id'] == 'exp-006-finalizer-seal')
        assert set(expected_refs.values()).issubset(seal['payload']['evidence_refs'])


@pytest.mark.parametrize('mutation,error', [
    ('report_identity', 'report identity'), ('summary', 'summary/binding'),
    ('manifest_identity', 'manifest identity'), ('manifest_bytes', 'manifest changed'),
    ('raw_bytes', 'bound artifact changed'),
])
def test_mismatched_supplemental_binding_rejected_before_finalization(tmp_path, mutation, error):
    run = fixture_run(tmp_path, ('build_failed',) * 6)
    root = run / 'tasks/exp/qualification/zero_affine'
    qualification(run, manifest_candidate='exp-005' if mutation == 'manifest_identity' else 'exp-006')
    report_path = root / 'hardware_validation.json'
    if mutation in ('report_identity', 'summary'):
        report = finalize.read(report_path)
        report['candidate_id' if mutation == 'report_identity' else 'passed_count'] = 'exp-005' if mutation == 'report_identity' else 8
        dump(report_path, report)
    elif mutation == 'manifest_bytes':
        path = root / 'attempts/001/execution_manifest.json'
        manifest = finalize.read(path)
        manifest['case_count'] = 8
        dump(path, manifest)
    elif mutation == 'raw_bytes':
        # Semantically equal JSON still must match the original raw CAS ref.
        report_path.write_text(json.dumps(finalize.read(report_path), indent=2))
    with pytest.raises(StoreError, match=error):
        finalize.Finalizer(run).finalize_operator('exp')
    assert not (run / 'tasks/exp/exploration_request.json').exists()
    assert not (run / 'tasks/exp/optimization_traces.jsonl').exists()
