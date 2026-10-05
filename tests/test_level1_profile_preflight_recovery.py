from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import recover_level1_profile_preflight as recovery
import run_level1_blocked_diagnostics as diagnostic
from collect_level1_traces import Campaign
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.traces import register_json_artifact, utcnow, verify_trace
from test_level1_blocked_diagnostics import dump, rejected_calibration


@pytest.fixture
def failed_preflight(tmp_path):
    run = tmp_path / 'campaign'
    dump(run / 'run-manifest.json', {'operators': ['exp'], 'train_operators': ['exp'], 'validation_operators': [],
        'sentinel_case_ids': [1, 8, 14, 20], 'acceptance_case_ids': list(range(1, 21)),
        'budget': {'candidate_limit': 6, 'build_limit': 6, 'timing_limit': 6, 'full_profile_limit': 3}})
    rejected_calibration(run)
    c = Campaign(run)
    task = c.task('exp')
    (task / 'baseline').mkdir(parents=True)
    (task / 'baseline/kernel.asc').write_text('synthetic baseline\n')
    controller = diagnostic.HardwareQueue(c, 'exp', diagnostic.DIAGNOSTIC_SLOTS)
    mechanism_refs = {}
    for identifier in ('001', '002'):
        directory = task / 'candidates' / identifier
        shutil.copytree(task / 'baseline', directory / 'op')
        (directory / 'op/kernel.asc').write_text('synthetic candidate ' + identifier + '\n')
        dump(directory / 'candidate_plan.json', {'candidate_id': 'exp-' + identifier, 'mode': 'exploration',
            'intent': 'Reduce vector work', 'handler_id': 'fixture', 'parameters': {}, 'expected_effects': ['Fewer operations'],
            'coverage_gap': 'Synthetic transformation.', 'static_review': ['Fixture review.']})
        c.register_candidate('exp', identifier)
        dump(task / 'executions' / identifier / 'build/execution.json', {'status': 'passed', 'exit_code': 0})
        controller.event('stage_completed', {'stage': 'build', 'status': 'passed', 'execution': None, 'reason': None,
            'artifact_refs': []}, identifier=identifier)
        dump(c.accuracy_report('exp', identifier), {'status': 'passed', 'passed_count': 20, 'case_count': 20,
            'case_ids': list(range(1, 21)), 'cases': [{'case_id': case, 'status': 'passed', 'kernel_exit_code': 0} for case in range(1, 21)]})
        plan = {'candidate_id': 'exp-' + identifier, 'candidate_plan_hash': file_hash(directory / 'candidate_plan.json'), 'predictions': []}
        dump(directory / 'mechanism_plan.json', plan)
        mechanism_refs[identifier] = controller.artifact(plan)
        controller.event('next_step_decided', {'action': 'freeze_mechanism_plan', 'reason': 'Synthetic pre-profile declaration.',
            'evidence_refs': [mechanism_refs[identifier]]}, identifier=identifier, event_id='exp-' + identifier + '-mechanism-plan-frozen')
        dump(directory / 'mechanism_bindings/partial.json', {'status': 'inconclusive', 'reason': 'No candidate profile yet.'})
    frozen = c.freeze('exp')
    selection = {'candidate_ids': ['001', '002'], 'sentinel_case_ids': [1, 8, 14, 20], 'basis': 'lexical first two'}
    dump(task / 'profile_selection.json', selection)
    plan = {'frozen_roster_ref': controller.artifact(frozen), 'profile_selection_ref': controller.artifact(selection),
        'mechanism_plan_refs': mechanism_refs}
    dump(task / 'queue/diagnostic_plan.json', plan)
    for identifier in ('001', '002'):
        controller.block(identifier, {'item': identifier, 'phase': 'profiles', 'stage': 'profile', 'status': 'error',
            'error': recovery.KNOWN_FAILURE}, interrupted=True)
    controller.dispatch([(identifier, case) for identifier in ('001', '002') for case in (1, 8, 14, 20)],
        lambda *args: pytest.fail('preflight failure cannot launch hardware'), 'profiles')
    complete = {'candidate_ids': ['001', '002'], 'correctness_qualified': ['001', '002'], 'status': 'completed',
        'collection_mode': 'blocked_diagnostics', 'measurement_status': 'blocked',
        # The archived old controller mislabeled these as profiled.
        'profiled_candidate_ids': ['001', '002'], 'blocked_candidates': controller.blocked,
        'diagnostic_plan_ref': controller.artifact(plan)}
    dump(task / 'queue/hardware_complete.json', complete)
    controller.event('next_step_decided', {'action': 'hardware_collection_complete', 'reason': 'Synthetic old controller closure.',
        'evidence_refs': [controller.artifact(complete)]}, event_id='exp-diagnostic-hardware-complete')
    old_producer = tmp_path / 'reconstructed_old.py'
    old_producer.write_text(recovery.PRODUCER.read_text().replace(recovery.FIXED_EXPRESSION, recovery.BAD_EXPRESSION))
    return c, old_producer


def test_recovery_archives_history_and_resumes_only_profiles_without_correctness_or_source_changes(failed_preflight):
    c, old = failed_preflight
    task = c.task('exp')
    original_stream = (task / 'trace_events.jsonl').read_bytes()
    original_queue = {path.name: path.read_bytes() for path in (task / 'queue').glob('*.json')}
    original_partial = (task / 'candidates/001/mechanism_bindings/partial.json').read_bytes()
    result = recovery.prepare_recovery(c, 'exp', old)
    assert len(result['ignored_event_ids']) == 2
    assert not (task / 'queue/hardware_complete.json').exists()
    for name, payload in original_queue.items():
        assert (task / 'controller_recoveries' / recovery.RECOVERY_ID / 'queue' / name).read_bytes() == payload
    assert (task / 'trace_events.jsonl').read_bytes().startswith(original_stream)
    assert (task / 'candidates/001/mechanism_bindings/partial.json').read_bytes() == original_partial
    c.correctness = lambda *args, **kwargs: pytest.fail('existing 20/20 correctness must be reused')
    calls = []
    def profile(op, identifier, *, case, **kwargs):
        calls.append((identifier, case))
        report = {'status': 'passed', 'exit_code': 0, 'started_at': utcnow(), 'synthetic': True}
        dump(task / 'executions' / identifier / f'profile-{case:02d}/execution.json', report)
        with c.store(op) as store:
            ref = register_json_artifact(store, report)
            c.writer(op, store).append('stage_completed', {'stage': 'profile', 'status': 'passed', 'reason': None,
                'execution': None, 'artifact_refs': [ref]}, candidate_id=op + '-' + identifier, attempt_id=op + '-' + identifier)
        return report
    c.profile_case = profile
    complete = diagnostic.execute_operator('exp', campaign=c)
    assert set(calls) == {(identifier, case) for identifier in ('001', '002') for case in (1, 8, 14, 20)}
    assert complete['blocked_candidates'] == {}
    assert complete['selected_profile_candidate_ids'] == complete['profiled_candidate_ids'] == complete['full_profile_candidate_ids'] == ['001', '002']
    assert complete['controller_recovery_ref'] == result['manifest_ref']
    with c.store('exp') as store:
        assert recovery.load_verified_recovery(c, 'exp', store)['ignored_event_ids'] == result['ignored_event_ids']
        assert verify_trace(task / 'trace_events.jsonl', store)['valid']
        manifest = json.loads(store.verify_artifact(result['manifest_ref']).read_text())
        assert manifest['old_producer_provenance'] == 'reconstructed_from_known_single_line_patch'
        assert manifest['old_producer_ref'] != manifest['new_producer_ref']
    assert (task / 'candidates/001/mechanism_bindings/partial.json').read_bytes() == original_partial


@pytest.mark.parametrize('state', ['actual_job', 'raw_csv', 'execution', 'finalized', 'different_failure', 'source_changed', 'plan_changed'])
def test_recovery_rejects_actual_work_other_failures_and_changed_frozen_inputs(failed_preflight, state):
    c, old = failed_preflight
    task = c.task('exp')
    if state == 'actual_job':
        dump(task / 'jobs/001-profile-01.json', {'job_id': 'exp-001-profile-01', 'argv': ['msprof', 'op']})
    elif state == 'raw_csv':
        path = task / 'profiles/001/case-01/raw/counter.csv'
        path.parent.mkdir(parents=True)
        path.write_text('counter\n1\n')
    elif state == 'execution':
        dump(task / 'executions/001/profile-01/execution.json', {'status': 'failed', 'exit_code': 7})
    elif state == 'finalized':
        dump(task / 'finalization_report.json', {'status': 'completed'})
    elif state == 'different_failure':
        path = task / 'queue/hardware_complete.json'
        value = json.loads(path.read_text())
        value['blocked_candidates']['001']['reason'] = 'Actual hardware failure'
        dump(path, value)
    elif state == 'source_changed':
        (task / 'candidates/001/op/kernel.asc').write_text('changed source')
    else:
        dump(task / 'candidates/001/mechanism_plan.json', {'changed': True})
    with pytest.raises((StoreError, KeyError)):
        recovery.prepare_recovery(c, 'exp', old)
    assert (task / 'queue/hardware_complete.json').exists()
    assert not (task / 'profile_preflight_recovery.json').exists()


def test_loader_never_whitelists_a_later_real_failure_and_rejects_a_backdated_execution(failed_preflight):
    c, old = failed_preflight
    task = c.task('exp')
    recovered = recovery.prepare_recovery(c, 'exp', old)
    controller = diagnostic.HardwareQueue(c, 'exp', diagnostic.DIAGNOSTIC_SLOTS)
    controller.event('stage_completed', {'stage': 'profile', 'status': 'failed', 'reason': 'Synthetic actual profiler exit failure.',
        'execution': None, 'artifact_refs': []}, identifier='001', event_id='later-real-profile-failure')
    with c.store('exp') as store:
        value = recovery.load_verified_recovery(c, 'exp', store)
        assert value['ignored_event_ids'] == recovered['ignored_event_ids']
        assert 'later-real-profile-failure' not in value['ignored_event_ids']
        dump(task / 'executions/001/profile-01/execution.json', {'started_at': '2020-01-01T00:00:00Z'})
        with pytest.raises(StoreError, match='predates recovery qualification'):
            recovery.load_verified_recovery(c, 'exp', store)


def test_loader_rejects_archive_tampering(failed_preflight):
    c, old = failed_preflight
    recovery.prepare_recovery(c, 'exp', old)
    path = c.task('exp') / 'controller_recoveries' / recovery.RECOVERY_ID / 'queue/profiles.json'
    path.chmod(0o644)
    path.write_text('[]')
    with c.store('exp') as store:
        with pytest.raises(StoreError, match='archive changed'):
            recovery.load_verified_recovery(c, 'exp', store)
