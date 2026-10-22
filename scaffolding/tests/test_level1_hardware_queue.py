from __future__ import annotations

import json
from pathlib import Path
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import run_level1_hardware_queue as hardware
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import TraceWriter, verify_trace


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


class FakeCampaign:
    def __init__(self, root, *, identifiers=('001',), build_passed=True, correctness_passed=True, unstable=False):
        self.run = root
        self.manifest = {'sentinel_case_ids': [1, 8, 14, 20], 'budget': {'full_profile_limit': 3}}
        self.calls, self.aggregates, self.frozen = [], [], []
        self.correctness_passed, self.unstable = correctness_passed, unstable
        self.on_measure = None
        self.calls_lock = threading.Lock()
        for identifier in identifiers:
            dump(self.task('exp') / 'candidates' / identifier / 'registration.json', {'candidate_id': 'exp-' + identifier})
            dump(self.task('exp') / 'candidates' / identifier / 'mechanism_plan.json', {'frozen': True})
            dump(self.task('exp') / 'executions' / identifier / 'build/execution.json', {'status': 'passed' if build_passed else 'failed', 'exit_code': 0 if build_passed else 1})
        dump(root / 'calibration/selection.json', {'accepted': True, 'physical_devices_by_host': {'local': [0, 1]}})

    def task(self, op):
        return self.run / 'tasks' / op

    def store(self, op):
        return EpisodeStore(self.run / 'train/episodes.sqlite')

    def writer(self, op, store):
        return TraceWriter(self.task(op) / 'trace_events.jsonl', run_id=self.run.name, task_id=op, session_id=op + '-campaign', store=store)

    def accuracy_report(self, op, identifier):
        return self.task(op) / 'correctness' / identifier / 'correctness.json'

    def correctness(self, op, identifier, **kwargs):
        with self.calls_lock:
            self.calls.append(('correctness', identifier, None))
        report = {'status': 'passed' if self.correctness_passed else 'failed', 'passed_count': 20 if self.correctness_passed else 0}
        dump(self.accuracy_report(op, identifier), report)
        return report

    def measure_case(self, op, identifier, *, case, phase='search', **kwargs):
        with self.calls_lock:
            self.calls.append((phase, identifier, case))
        if self.on_measure:
            return self.on_measure(identifier, case, phase)
        return {'status': 'passed', 'exit_code': 0, 'stable': not self.unstable}

    def aggregate(self, op, identifier, phase):
        self.aggregates.append((identifier, phase))
        return {'stable': not self.unstable, 'speedup': None if self.unstable else 1.1,
            'per_case': [{'case_id': case, 'speedup': 1.1} for case in self.manifest['sentinel_case_ids']]}

    def freeze(self, op):
        self.frozen = [path.parent.name for path in sorted((self.task(op) / 'candidates').glob('*/registration.json'))]
        dump(self.task(op) / 'frozen-roster.json', {'identifiers': self.frozen})

    def profile_case(self, op, identifier, *, case, **kwargs):
        with self.calls_lock:
            self.calls.append(('profile', identifier, case))
        return {'status': 'passed', 'exit_code': 0}


def test_dispatch_stops_queued_cases_but_retains_inflight_work(tmp_path):
    campaign = FakeCampaign(tmp_path)
    controller = hardware.HardwareQueue(campaign, 'exp', [('local', 0), ('local', 1)])
    second_started, failure_recorded = threading.Event(), threading.Event()
    started = []
    original_event = controller.event
    def event(kind, payload, **kwargs):
        original_event(kind, payload, **kwargs)
        if payload.get('action') == 'stop_candidate_after_execution_failure':
            failure_recorded.set()
    controller.event = event
    def execute(item, host, device):
        started.append(item)
        if item[1] == 1:
            assert second_started.wait(5)
            return {'status': 'failed', 'exit_code': 7}
        if item[1] == 2:
            second_started.set()
            assert failure_recorded.wait(5)
            return {'status': 'passed', 'exit_code': 0}
        pytest.fail('queued case started after candidate failure')
    result = controller.dispatch([('001', case) for case in range(1, 7)], execute, 'search')
    assert sorted(started) == [('001', 1), ('001', 2)]
    assert [row['status'] for row in result] == ['failed', 'passed', 'skipped', 'skipped', 'skipped', 'skipped']
    assert result[1]['result_ref'].startswith('sha256:')
    with campaign.store('exp') as store:
        assert verify_trace(campaign.task('exp') / 'trace_events.jsonl', store)['valid']
        assert json.loads(store.verify_artifact(controller.phase_refs['search']).read_text())['items'] == [['001', i] for i in range(1, 7)]
        assert json.loads(store.verify_artifact(result[1]['result_ref']).read_text())['status'] == 'passed'


def test_controller_exception_has_strict_no_execution_record_and_other_candidate_continues(tmp_path):
    campaign = FakeCampaign(tmp_path, identifiers=('001', '002'))
    controller = hardware.HardwareQueue(campaign, 'exp', [('local', 0)])
    def execute(item, host, device):
        if item[0] == '001':
            raise RuntimeError('transport failed before remote execution could be confirmed')
        return {'status': 'passed', 'exit_code': 0}
    result = controller.dispatch([('001', 1), ('001', 8), ('002', 1)], execute, 'search')
    assert [item['status'] for item in result] == ['error', 'skipped', 'passed']
    events = [json.loads(line) for line in (campaign.task('exp') / 'trace_events.jsonl').read_text().splitlines()]
    interrupted = next(event for event in events if event['event_type'] == 'execution_interrupted')
    assert interrupted['payload']['execution'] is None
    assert interrupted['payload']['stage'] == 'search_timing'
    assert interrupted['artifact_refs']
    with campaign.store('exp') as store:
        assert verify_trace(campaign.task('exp') / 'trace_events.jsonl', store)['valid']


def test_failed_search_skips_profiles_and_final_but_aggregates_partial_evidence(tmp_path, monkeypatch):
    campaign = FakeCampaign(tmp_path)
    # One slot makes the exact remaining-case skip observable end to end.
    dump(tmp_path / 'calibration/selection.json', {'accepted': True, 'physical_devices_by_host': {'local': [0]}})
    campaign.on_measure = lambda identifier, case, phase: {'status': 'failed', 'exit_code': 2}
    monkeypatch.setattr(hardware, 'Campaign', lambda: campaign)
    result = hardware.execute_operator('exp')
    assert [call for call in campaign.calls if call[0] != 'correctness'] == [('search', '001', 1)]
    assert campaign.aggregates == [('001', 'search'), ('001', 'final')]
    assert campaign.frozen == ['001']
    assert result['blocked_candidates']['001']['stage'] == 'search_timing'
    final = json.loads((campaign.task('exp') / 'queue/final.json').read_text())
    assert len(final) == 20 and all(row['status'] == 'skipped' for row in final)
    assert (campaign.task('exp') / 'queue/hardware_complete.json').exists()


def test_cv_instability_does_not_stop_successful_execution(tmp_path, monkeypatch):
    campaign = FakeCampaign(tmp_path, unstable=True)
    monkeypatch.setattr(hardware, 'Campaign', lambda: campaign)
    result = hardware.execute_operator('exp')
    assert result['blocked_candidates'] == {}
    assert len([call for call in campaign.calls if call[0] == 'search']) == 4
    assert len([call for call in campaign.calls if call[0] == 'profile']) == 4
    assert len([call for call in campaign.calls if call[0] == 'final']) == 20


@pytest.mark.parametrize('build_passed,existing_accuracy', [(False, False), (True, False), (True, True)])
def test_all_failed_candidates_still_freeze_and_complete_without_retry(tmp_path, monkeypatch, build_passed, existing_accuracy):
    campaign = FakeCampaign(tmp_path, identifiers=('001', '002'), build_passed=build_passed, correctness_passed=False)
    if existing_accuracy:
        for identifier in ('001', '002'):
            dump(campaign.accuracy_report('exp', identifier), {'status': 'failed', 'passed_count': 0})
    monkeypatch.setattr(hardware, 'Campaign', lambda: campaign)
    result = hardware.execute_operator('exp')
    assert result['status'] == 'completed'
    assert result['correctness_qualified'] == []
    assert campaign.frozen == ['001', '002']
    assert set(campaign.aggregates) == {('001', 'search'), ('002', 'search'), ('001', 'final'), ('002', 'final')}
    assert not any(call[0] in ('search', 'profile', 'final') for call in campaign.calls)
    if existing_accuracy or not build_passed:
        assert campaign.calls == []
    assert (campaign.task('exp') / 'queue/hardware_complete.json').exists()


def test_nonzero_exit_blocks_even_if_report_status_claims_passed(tmp_path):
    campaign = FakeCampaign(tmp_path)
    controller = hardware.HardwareQueue(campaign, 'exp', [('local', 0)])
    result = controller.dispatch([('001', 1), ('001', 2)],
        lambda *args: {'status': 'passed', 'exit_code': 9}, 'search')
    assert '001' in controller.blocked
    assert result[0]['exit_code'] == 9
    assert result[1]['status'] == 'skipped'


def test_profile_failure_stops_remaining_profile_cases_and_all_final_work(tmp_path, monkeypatch):
    campaign = FakeCampaign(tmp_path)
    dump(tmp_path / 'calibration/selection.json', {'accepted': True, 'physical_devices_by_host': {'local': [0]}})
    def fail_profile(op, identifier, *, case, **kwargs):
        campaign.calls.append(('profile', identifier, case))
        return {'status': 'failed', 'exit_code': 3}
    campaign.profile_case = fail_profile
    monkeypatch.setattr(hardware, 'Campaign', lambda: campaign)
    result = hardware.execute_operator('exp')
    assert [call for call in campaign.calls if call[0] == 'profile'] == [('profile', '001', 1)]
    assert not any(call[0] == 'final' for call in campaign.calls)
    assert result['blocked_candidates']['001']['stage'] == 'profile'
    assert campaign.aggregates[-1] == ('001', 'final')
    assert result['status'] == 'completed'


def test_aggregation_exception_is_attested_and_candidate_still_closes(tmp_path, monkeypatch):
    campaign = FakeCampaign(tmp_path)
    original = campaign.aggregate
    def aggregate(op, identifier, phase):
        if phase == 'search':
            raise ValueError('raw source index does not match its measurement case')
        return original(op, identifier, phase)
    campaign.aggregate = aggregate
    monkeypatch.setattr(hardware, 'Campaign', lambda: campaign)
    result = hardware.execute_operator('exp')
    assert result['blocked_candidates']['001']['stage'] == 'search_aggregation'
    assert campaign.frozen == ['001']
    assert not any(call[0] in ('profile', 'final') for call in campaign.calls)
    events = [json.loads(line) for line in (campaign.task('exp') / 'trace_events.jsonl').read_text().splitlines()]
    assert any(event['event_type'] == 'execution_interrupted' and event['payload']['stage'] == 'search_aggregation' for event in events)
