"""CPU-only checks for predeclared evidence and independent performance conclusions."""
import pytest

from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.store import EpisodeStore
from test_finalize_level1_campaign import dump, finalize, fixture_run


@pytest.mark.parametrize('conditions', [[], [
    'Extra partial tasks may cost more than they save for small inputs.',
    {'condition': 'Scalar serialization may remain', 'scope': ['general-p', 'zero-p']},
]])
def test_predeclared_conditions_bind_original_plan_bytes_without_claiming_measurements(tmp_path, conditions):
    run = fixture_run(tmp_path, ('build_failed',))
    task = run / 'tasks/exp'
    directory = task / 'candidates/001'
    plan_path = directory / 'candidate_plan.json'
    plan = finalize.read(plan_path)
    plan['contradicting_evidence'] = conditions
    dump(plan_path, plan)
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        plan_ref = store.register_artifact(plan_path)
    registration = finalize.read(directory / 'registration.json')
    registration['plan_hash'] = plan_ref
    dump(directory / 'registration.json', registration)
    roster = finalize.read(task / 'frozen-roster.json')
    roster['candidates'][0] = {**registration, 'frozen_plan_sha256': file_hash(plan_path)}
    dump(task / 'frozen-roster.json', roster)

    finalizer = finalize.Finalizer(run)
    result = finalizer.finalize_operator('exp')
    summary = finalize.rows(task / 'optimization_traces.jsonl')[0]
    refs = summary['diagnosis']['contradicting_evidence']
    gate_artifacts = finalize.read(task / 'exploration_request.json')['evidence'][0]['artifacts']
    if not conditions:
        assert refs == []
        assert 'predeclared_contradicting_evidence' not in gate_artifacts
    else:
        assert refs == [gate_artifacts['predeclared_contradicting_evidence']]
        with EpisodeStore(run / 'train/episodes.sqlite') as store:
            artifact = finalize.read(store.verify_artifact(refs[0]))
            assert content_hash(artifact) == refs[0]
            assert artifact == {
                'schema_version': '1.0.0', 'kind': 'predeclared_diagnostic_conditions',
                'candidate_id': 'exp-001', 'candidate_plan_hash': plan_ref,
                'source_field': '$.contradicting_evidence', 'conditions': conditions,
                'classification': 'predeclared_hypothesis_or_limitation',
                'measured_counterexample': False, 'evidence_refs': [plan_ref],
            }
            assert store.verify_artifact(artifact['candidate_plan_hash']).read_bytes() == plan_path.read_bytes()
            assert refs[0] in summary['lesson']['evidence_refs']
            fragment = finalize.read(store.verify_artifact(summary['result']['attempt_evidence_hash']))
            seal = next(event for event in fragment['events'] if event['event_id'] == 'exp-001-finalizer-seal')
            assert refs[0] in seal['payload']['evidence_refs']
        assert summary['lesson']['counterexamples'] == []
        assert summary['lesson']['limitations'][-len(conditions):] == finalize.text_items(conditions)
    assert finalizer.finalize_operator('exp') == result


def lesson_inputs(failed_stage=None):
    validation = {name: finalize.stage('passed') for name in
        ('static_review', 'build', 'correctness', 'runtime', 'timing', 'profile')}
    validation['timing'] = finalize.stage('not_run', 'A/A calibration blocked timing.')
    if failed_stage:
        validation[failed_stage] = finalize.stage('failed', 'Recorded source validation failed.')
    outcome = {'verdict': {'build': 'build_failed', 'correctness': 'accuracy_failed'}.get(
        failed_stage, 'artifacts_incomplete'), 'reasons': ['No admitted timing.']}
    binding = {'status': 'refuted', 'reason': 'Scalar time increased despite a frozen decrease prediction.',
        'comparisons': [{'case_id': 1, 'kernel': 'exp_kernel', 'name': 'scalar_time',
            'baseline_value': 10, 'candidate_value': 20, 'unit': 'ns',
            'expected_direction': 'decrease', 'status': 'refuted', 'reason': 'Counter moved opposite to prediction.'}]}
    return outcome, validation, binding


@pytest.mark.parametrize('timing_blocked', [False, True])
@pytest.mark.parametrize('failed_stage', [None, 'build', 'correctness'])
def test_counter_refutation_is_distinct_from_blocked_performance_and_source_failure(timing_blocked, failed_stage):
    outcome, validation, binding = lesson_inputs(failed_stage)
    lesson = finalize.lesson_for(outcome, validation, None, None, [],
        mechanism_binding=binding, timing_blocked=timing_blocked)
    assert lesson['status'] == ('inconclusive' if timing_blocked and failed_stage is None else 'refuted')
    assert any('case 1 exp_kernel scalar_time' in text and 'refuted' in text
        for text in lesson['ineffective_conditions'])
    assert any('mechanism hypothesis is refuted' in text for text in lesson['ineffective_conditions'])
    assert any('Predeclared mechanism set is refuted' in text for text in lesson['limitations'])
    assert not any('mechanism attribution remains unknown' in text for text in lesson['limitations'])
    assert any('Timing is blocked' in text for text in lesson['limitations']) == timing_blocked
    assert lesson['effective_conditions'] == lesson['counterexamples'] == []


def test_absent_binding_still_reports_unknown_attribution():
    outcome, validation, _ = lesson_inputs()
    lesson = finalize.lesson_for(outcome, validation, None, None, [], timing_blocked=True)
    assert lesson['status'] == 'inconclusive'
    assert any('mechanism attribution remains unknown' in text for text in lesson['limitations'])


def test_calibration_attestation_reaches_lesson_without_erasing_correctness_failure(tmp_path, monkeypatch):
    run = fixture_run(tmp_path, ('accuracy_failed',))
    task = run / 'tasks/exp'
    dump(task / 'queue/calibration_block.json', {'measurement_status': 'blocked',
        'timing_qualification_claimed': False, 'reason': 'Same-binary A/A calibration did not qualify timing.'})
    called = []
    original_lesson = finalize.lesson_for

    def record_lesson(*args, **kwargs):
        called.append(kwargs['timing_blocked'])
        return original_lesson(*args, **kwargs)

    monkeypatch.setattr(finalize, 'lesson_for', record_lesson)
    result = finalize.Finalizer(run).finalize_operator('exp')
    assert called == [True]
    assert result['attempts'][0]['verdict'] == 'accuracy_failed'
    summary = finalize.rows(task / 'optimization_traces.jsonl')[0]
    assert summary['lesson']['status'] == 'refuted'
    assert summary['validation']['timing']['status'] == 'not_run'
    assert summary['result']['speedup'] is None
