from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import run_level1_blocked_diagnostics as diagnostic
from collect_level1_traces import Campaign
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import TraceWriter, register_json_artifact, verify_trace


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def rejected_calibration(run):
    root = run / 'calibration'
    reject = {'accepted': False, 'max_device_jobs': 0, 'reason': 'All predeclared rounds rejected.'}
    dump(root / 'selection-unpinned.json', reject)
    dump(root / 'selection.json', {**reject, 'protocol_ref': str(root / 'affinity-v1/protocol.json')})
    dump(root / 'affinity-v1/protocol.json', {'name': 'affinity-v1', 'widths': [8, 4, 2, 1]})
    for directory, widths in ((root, (32, 16, 8, 4, 2, 1)), (root / 'affinity-v1', (8, 4, 2, 1))):
        for width in widths:
            dump(directory / f'calibration-{width}.json', {'width': width, 'accepted': False,
                'outcomes': [{'passed': False} for _ in range(width)]})


class FakeCampaign:
    def __init__(self, run, identifiers=('001', '002', '003', '004'), *, failed=()):
        self.run = run
        self.manifest = {'operators': ['exp'], 'sentinel_case_ids': [1, 8, 14, 20], 'acceptance_case_ids': list(range(1, 21)),
            'budget': {'candidate_limit': 6, 'full_profile_limit': 3}}
        dump(run / 'run-manifest.json', self.manifest)
        rejected_calibration(run)
        self.calls, self.verified, self.failed = [], [], set(failed)
        self.lock = threading.Lock()
        self.on_profile = None
        for identifier in identifiers:
            directory = self.task('exp') / 'candidates' / identifier
            dump(directory / 'registration.json', {'candidate_id': 'exp-' + identifier})
            dump(directory / 'candidate_plan.json', {'candidate_id': 'exp-' + identifier})
            plan = {'candidate_id': 'exp-' + identifier, 'candidate_plan_hash': file_hash(directory / 'candidate_plan.json')}
            dump(directory / 'mechanism_plan.json', plan)
            dump(self.task('exp') / 'executions' / identifier / 'build/execution.json', {'status': 'passed', 'exit_code': 0})
            with self.store('exp') as store:
                ref = register_json_artifact(store, plan)
                self.writer('exp', store).append('next_step_decided', {'action': 'freeze_mechanism_plan',
                    'reason': 'Synthetic pre-profile prediction fixture.', 'evidence_refs': [ref]},
                    candidate_id='exp-' + identifier, attempt_id='exp-' + identifier,
                    event_id='exp-' + identifier + '-mechanism-plan-frozen')

    def task(self, op):
        return self.run / 'tasks' / op

    def store(self, op):
        return EpisodeStore(self.run / 'train/episodes.sqlite')

    def writer(self, op, store):
        return TraceWriter(self.task(op) / 'trace_events.jsonl', run_id=self.run.name, task_id=op,
            session_id=op + '-campaign', store=store)

    def verify_source_identity(self, op, identifier):
        self.verified.append(identifier)

    def freeze(self, op):
        value = {'candidates': [json.loads(path.read_text()) for path in sorted((self.task(op) / 'candidates').glob('*/registration.json'))]}
        dump(self.task(op) / 'frozen-roster.json', value)
        return value

    def accuracy_report(self, op, identifier):
        return self.task(op) / 'correctness' / identifier / 'correctness.json'

    def correctness(self, op, identifier, *, host, device):
        assert (host, device) in diagnostic.DIAGNOSTIC_SLOTS
        assert (self.task(op) / 'frozen-roster.json').exists()
        with self.lock:
            self.calls.append(('correctness', identifier, host, device))
        passed = identifier not in self.failed
        report = {'status': 'passed' if passed else 'failed', 'passed_count': 20 if passed else 0,
            'case_count': 20, 'case_ids': list(range(1, 21)), 'cases': []}
        dump(self.accuracy_report(op, identifier), report)
        return report

    def measure_case(self, *args, **kwargs):
        pytest.fail('blocked diagnostics must never call candidate timing')

    def profile_case(self, op, identifier, *, case, host, device):
        assert (host, device) in diagnostic.DIAGNOSTIC_SLOTS
        assert (self.task(op) / 'frozen-roster.json').exists()
        assert (self.task(op) / 'profile_selection.json').exists()
        assert (self.task(op) / 'queue/diagnostic_plan.json').exists()
        with self.lock:
            self.calls.append(('profile', identifier, case, host, device))
        if self.on_profile:
            return self.on_profile(identifier, case)
        return {'status': 'passed', 'exit_code': 0}

    aggregate = Campaign.aggregate


@pytest.mark.parametrize('state', ['old_selection', 'pending_round', 'accepted_unpinned', 'accepted_affinity', 'partial_round'])
def test_requires_both_complete_failed_ladders_before_any_mutation(tmp_path, state):
    campaign = FakeCampaign(tmp_path)
    root = tmp_path / 'calibration'
    if state == 'old_selection':
        dump(root / 'selection.json', json.loads((root / 'selection-unpinned.json').read_text()))
    elif state == 'pending_round':
        (root / 'affinity-v1/calibration-1.json').unlink()
    elif state.startswith('accepted'):
        dump(root / ('selection-unpinned.json' if state.endswith('unpinned') else 'selection.json'),
            {'accepted': True, 'max_device_jobs': 1, 'reason': 'Timing is qualified.'})
    else:
        dump(root / 'affinity-v1/calibration-2.json', {'accepted': False, 'width': 2, 'outcomes': [{'passed': False}]})
    before = {str(path): path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    with pytest.raises((StoreError, FileNotFoundError)):
        diagnostic.execute_operator('exp', campaign=campaign)
    assert campaign.calls == [] and campaign.verified == []
    assert {str(path): path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()} == before


def test_collects_twenty_case_correctness_and_lexical_three_sentinel_profiles_without_timing(tmp_path):
    campaign = FakeCampaign(tmp_path, failed=('001',))
    result = diagnostic.execute_operator('exp', campaign=campaign)
    assert result['status'] == 'completed' and result['measurement_status'] == 'blocked'
    assert result['timing_qualification_claimed'] is False
    assert result['profiled_candidate_ids'] == ['002', '003', '004']
    assert campaign.verified == ['001', '002', '003', '004']
    assert len([row for row in campaign.calls if row[0] == 'correctness']) == 4
    assert {(row[1], row[2]) for row in campaign.calls if row[0] == 'profile'} == {
        (identifier, case) for identifier in ('002', '003', '004') for case in (1, 8, 14, 20)}
    for identifier in ('001', '002', '003', '004'):
        for phase in ('search', 'final'):
            raw = json.loads((campaign.task('exp') / 'timing' / phase / identifier / 'raw_measurements.json').read_text())
            report = json.loads((campaign.task('exp') / 'timing' / phase / identifier / 'measurement_report.json').read_text())
            assert raw['records'] == [] and raw['complete'] is False
            assert report['gate_projection']['baseline_samples_ns'] == report['gate_projection']['candidate_samples_ns'] == []
    events = [json.loads(line) for line in (campaign.task('exp') / 'trace_events.jsonl').read_text().splitlines()]
    blocked = [row for row in events if row['payload'].get('action') == 'block_timing_after_calibration_failure']
    assert {row['candidate_id'] for row in blocked} == {'exp-' + identifier for identifier in ('001', '002', '003', '004')}
    assert not any(row['event_type'] == 'stage_completed' and 'timing' in row['payload'].get('stage', '') for row in events)
    with campaign.store('exp') as store:
        assert verify_trace(campaign.task('exp') / 'trace_events.jsonl', store)['valid']
        store.verify_artifact(result['calibration_block_ref'])
        for ref in result['calibration_refs']:
            store.verify_artifact(ref)
    calls = list(campaign.calls)
    assert diagnostic.execute_operator('exp', campaign=campaign) == result
    assert campaign.calls == calls


def test_existing_profile_selection_is_immutable_and_not_backfilled(tmp_path):
    campaign = FakeCampaign(tmp_path, failed=('002',))
    path = campaign.task('exp') / 'profile_selection.json'
    dump(path, {'candidate_ids': ['004', '002'], 'sentinel_case_ids': [1, 8, 14, 20], 'basis': 'Previously frozen choice.'})
    before = path.read_bytes()
    result = diagnostic.execute_operator('exp', campaign=campaign)
    assert result['selected_profile_candidate_ids'] == ['004', '002']
    assert result['profiled_candidate_ids'] == result['full_profile_candidate_ids'] == ['004']
    assert path.read_bytes() == before
    assert {row[1] for row in campaign.calls if row[0] == 'profile'} == {'004'}


def test_failed_correctness_is_never_retried_and_all_failed_roster_closes(tmp_path):
    campaign = FakeCampaign(tmp_path, identifiers=('001', '002'), failed=('001', '002'))
    for identifier in ('001', '002'):
        dump(campaign.accuracy_report('exp', identifier), {'status': 'failed', 'passed_count': 0})
    result = diagnostic.execute_operator('exp', campaign=campaign)
    assert campaign.calls == []
    assert result['status'] == 'completed' and result['correctness_qualified'] == []
    assert result['profiled_candidate_ids'] == []
    assert set(result['final_reports']) == {'001', '002'}


def test_missing_predeclared_mechanism_stops_profiles_and_still_closes(tmp_path):
    campaign = FakeCampaign(tmp_path, identifiers=('001',))
    (campaign.task('exp') / 'candidates/001/mechanism_plan.json').unlink()
    result = diagnostic.execute_operator('exp', campaign=campaign)
    assert not any(row[0] == 'profile' for row in campaign.calls)
    assert result['selected_profile_candidate_ids'] == ['001']
    assert result['profiled_candidate_ids'] == result['full_profile_candidate_ids'] == []
    assert result['blocked_candidates']['001']['stage'] == 'profile'
    events = [json.loads(line) for line in (campaign.task('exp') / 'trace_events.jsonl').read_text().splitlines()]
    assert any(row['event_type'] == 'execution_interrupted' and row['payload']['execution'] is None for row in events)


def test_profile_failure_stops_queued_cases_and_preserves_inflight_case(tmp_path):
    campaign = FakeCampaign(tmp_path, identifiers=('001',))
    second_started, failure_recorded = threading.Event(), threading.Event()
    original_writer = campaign.writer
    def writer(op, store):
        writer = original_writer(op, store)
        append = writer.append
        def record(kind, payload, **kwargs):
            result = append(kind, payload, **kwargs)
            if payload.get('action') == 'stop_candidate_after_execution_failure':
                failure_recorded.set()
            return result
        writer.append = record
        return writer
    campaign.writer = writer
    def profile(identifier, case):
        if case == 1:
            assert second_started.wait(5)
            return {'status': 'failed', 'exit_code': 7}
        if case == 8:
            second_started.set()
            assert failure_recorded.wait(5)
            return {'status': 'passed', 'exit_code': 0}
        pytest.fail('a queued case started after profile failure')
    campaign.on_profile = profile
    result = diagnostic.execute_operator('exp', campaign=campaign)
    rows = json.loads((campaign.task('exp') / 'queue/profiles.json').read_text())
    assert [row['status'] for row in rows] == ['failed', 'passed', 'skipped', 'skipped']
    assert result['status'] == 'completed' and result['measurement_status'] == 'blocked'


def test_existing_timing_cannot_be_overwritten_by_the_fallback(tmp_path):
    campaign = FakeCampaign(tmp_path)
    path = campaign.task('exp') / 'timing/search/001/case-01/raw_measurements.json'
    dump(path, {'records': [{'observed': 'existing evidence'}]})
    before = path.read_bytes()
    with pytest.raises(StoreError, match='cannot overwrite existing candidate timing'):
        diagnostic.execute_operator('exp', campaign=campaign)
    assert path.read_bytes() == before and campaign.calls == []


def test_prior_profile_controller_failure_is_terminal_even_without_execution_file(tmp_path):
    campaign = FakeCampaign(tmp_path, identifiers=('001',))
    with campaign.store('exp') as store:
        campaign.writer('exp', store).append('execution_interrupted', {'stage': 'profile',
            'reason': 'Previous profiler transport state is unknown.', 'execution': None},
            candidate_id='exp-001', attempt_id='exp-001')
    result = diagnostic.execute_operator('exp', campaign=campaign)
    assert not any(row[0] == 'profile' for row in campaign.calls)
    assert result['blocked_candidates']['001']['stage'] == 'profile'


def test_real_finalizer_and_read_only_verifier_preserve_blocked_timing_as_inconclusive(tmp_path):
    from finalize_level1_campaign import Finalizer
    from verify_level1_campaign import CampaignVerifier, ReadOnlyStore
    from aprof_runtime.traces import verify_optimization_traces
    run = tmp_path / 'campaign'
    dump(run / 'run-manifest.json', {'operators': ['exp'], 'train_operators': ['exp'], 'validation_operators': [],
        'sentinel_case_ids': [1, 8, 14, 20], 'acceptance_case_ids': list(range(1, 21)),
        'budget': {'candidate_limit': 6, 'build_limit': 6, 'timing_limit': 6, 'full_profile_limit': 3}})
    rejected_calibration(run)
    c = Campaign(run)
    task = c.task('exp')
    baseline = task / 'baseline'
    baseline.mkdir(parents=True)
    (baseline / 'kernel.asc').write_text('synthetic baseline\n')
    directory = task / 'candidates/001'
    shutil.copytree(baseline, directory / 'op')
    (directory / 'op/kernel.asc').write_text('synthetic candidate\n')
    dump(directory / 'candidate_plan.json', {'candidate_id': 'exp-001', 'mode': 'exploration',
        'intent': 'Reduce vector work', 'handler_id': 'exp.fixture', 'handler_version': '1.0.0', 'parameters': {},
        'static_review': ['Synthetic bounds review.'], 'expected_effects': ['Fewer operations'], 'coverage_gap': 'Fixture transformation.'})
    c.register_candidate('exp', '001')
    plan = {'candidate_id': 'exp-001', 'candidate_plan_hash': file_hash(directory / 'candidate_plan.json'), 'predictions': []}
    dump(directory / 'mechanism_plan.json', plan)
    with c.store('exp') as store:
        ref = register_json_artifact(store, plan)
        c.writer('exp', store).append('next_step_decided', {'action': 'freeze_mechanism_plan',
            'reason': 'Synthetic prediction fixture.', 'evidence_refs': [ref]}, candidate_id='exp-001', attempt_id='exp-001',
            event_id='exp-001-mechanism-plan-frozen')

    def completed(stage):
        value = {'status': 'passed', 'exit_code': 0, 'synthetic': True}
        dump(task / 'executions/001' / stage / 'execution.json', value)
        with c.store('exp') as store:
            ref = register_json_artifact(store, value)
            c.writer('exp', store).append('stage_completed', {'stage': 'profile' if stage.startswith('profile') else stage,
                'status': 'passed', 'reason': None, 'execution': None, 'artifact_refs': [ref]},
                candidate_id='exp-001', attempt_id='exp-001')
        return value

    completed('build')
    def correctness(op, identifier, **kwargs):
        dump(c.accuracy_report(op, identifier), {'status': 'passed', 'case_count': 20, 'passed_count': 20,
            'case_ids': list(range(1, 21)), 'cases': [{'case_id': case, 'status': 'passed', 'kernel_exit_code': 0} for case in range(1, 21)]})
        return completed('correctness')
    c.correctness = correctness
    c.profile_case = lambda op, identifier, *, case, **kwargs: completed(f'profile-{case:02d}')
    c.measure_case = lambda *args, **kwargs: pytest.fail('no timing command is authorized')
    diagnostic.execute_operator('exp', campaign=c)
    result = Finalizer(run).finalize_operator('exp')
    rows = [json.loads(line) for line in (task / 'optimization_traces.jsonl').read_text().splitlines()]
    assert rows[0]['validation']['timing']['status'] == 'not_run'
    assert rows[0]['result']['speedup'] is None and rows[0]['lesson']['status'] == 'inconclusive'
    assert result['best_source']['candidate_id'] is None
    verifier = CampaignVerifier(run)
    verifier.tasks['exp'] = {'registrations': [json.loads((directory / 'registration.json').read_text())],
        'summaries': rows, 'report': result, 'events': [json.loads(line) for line in (task / 'trace_events.jsonl').read_text().splitlines()]}
    with ReadOnlyStore(run / 'train/episodes.sqlite') as store:
        assert verify_optimization_traces(task / 'optimization_traces.jsonl', store)['attempt_count'] == 1
        assert verifier.blocked_measurements('exp', store)['measurement_status'] == 'blocked'
        rows[0]['result']['verdict'] = 'benchmark_specialized_gain'
        with pytest.raises(StoreError, match='cannot claim a measured gain'):
            verifier.blocked_measurements('exp', store)
