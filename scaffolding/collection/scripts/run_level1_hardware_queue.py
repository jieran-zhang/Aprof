#!/usr/bin/env python3
"""Run bounded candidate jobs, stopping future work after execution failures."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import threading
from pathlib import Path

from collect_level1_traces import Campaign, WRITER_LOCK
from run_aprof_job import dump
from aprof_runtime.traces import register_json_artifact, verify_trace

STAGES = {'correctness': 'correctness', 'search': 'search_timing',
          'profiles': 'profile', 'final': 'final_timing'}
FAILURE_STATUSES = {'failed', 'error', 'timeout', 'timed_out', 'interrupted', 'not_run'}


def candidate_of(item):
    return item[0] if isinstance(item, (list, tuple)) else item


def execution_failed(value):
    """CV/stability describes measurements, not a failed device execution."""
    return value.get('status') in FAILURE_STATUSES or any(
        value.get(key) is not None and value[key] != 0 for key in ('exit_code', 'exit_status'))


class HardwareQueue:
    def __init__(self, campaign, operator, slots):
        self.campaign, self.operator = campaign, operator
        self.task, self.slots = campaign.task(operator), slots
        self.blocked = {}
        self.lock = threading.RLock()
        self.phase_refs = {}

    def artifact(self, document):
        with WRITER_LOCK, self.campaign.store(self.operator) as store:
            return register_json_artifact(store, document)

    def event(self, kind, payload, *, identifier=None, refs=(), event_id=None):
        candidate_id = self.operator + '-' + identifier if identifier is not None else None
        with WRITER_LOCK, self.campaign.store(self.operator) as store:
            self.campaign.writer(self.operator, store).append(kind, payload,
                candidate_id=candidate_id, attempt_id=candidate_id, artifact_refs=refs, event_id=event_id)

    def block(self, identifier, result, *, interrupted=False):
        # The stop flag is visible before CAS/event I/O, so another worker cannot
        # dequeue new work while the failure attestation is being written.
        with self.lock:
            first = identifier not in self.blocked
            if first:
                self.blocked[identifier] = {'phase': result['phase'], 'stage': result['stage'],
                    'reason': result.get('error') or f"Recorded execution status={result.get('status')}, exit_code={result.get('exit_code')}.",
                    'evidence_ref': None}
        ref = self.artifact(result)
        with self.lock:
            if first:
                self.blocked[identifier]['evidence_ref'] = ref
        refs = [ref] + ([self.phase_refs[result['phase']]] if result['phase'] in self.phase_refs else [])
        reason = result.get('error') or f"Recorded execution status={result.get('status')}, exit_code={result.get('exit_code')}; stop candidate future stages."
        if interrupted:
            self.event('execution_interrupted', {'stage': result['stage'], 'reason': reason, 'execution': None},
                identifier=identifier, refs=refs)
        else:
            self.event('next_step_decided', {'action': 'stop_candidate_after_execution_failure',
                'reason': result['stage'] + ': ' + reason, 'evidence_refs': refs}, identifier=identifier)
        return ref

    def skip(self, item, label):
        identifier = candidate_of(item)
        with self.lock:
            failure = dict(self.blocked[identifier])
        result = {'item': item, 'phase': label, 'stage': STAGES.get(label, label), 'status': 'skipped',
            'reason': 'Candidate stopped after ' + failure['stage'] + ': ' + failure['reason']}
        refs = [self.phase_refs[label]]
        if failure['evidence_ref']:
            refs.append(failure['evidence_ref'])
        self.event('next_step_decided', {'action': 'skip_blocked_candidate_work',
            'reason': result['stage'] + ': ' + result['reason'], 'evidence_refs': refs}, identifier=identifier)
        return result

    def dispatch(self, items, function, label):
        items = list(items)
        plan = {'operator': self.operator, 'phase': label, 'items': items,
            'slots': [{'host': host, 'physical_device': device} for host, device in self.slots],
            'failure_policy': 'stop new candidate jobs immediately; retain already-inflight work'}
        dump(self.task / 'queue' / f'{label}-plan.json', plan)
        self.phase_refs[label] = self.artifact(plan)
        self.event('next_step_decided', {'action': 'dispatch_bounded_phase',
            'reason': f'Execute or explicitly skip every queued {label} item under the candidate failure policy.',
            'evidence_refs': [self.phase_refs[label]]})
        pending, results = iter(enumerate(items)), {}

        def worker(slot):
            host, device = slot
            while True:
                with self.lock:
                    try:
                        index, item = next(pending)
                    except StopIteration:
                        return
                    identifier = candidate_of(item)
                    stopped = identifier in self.blocked
                    # Taking an item under this lock marks it in flight. A
                    # later failure leaves this already-dispatched job intact.
                if stopped:
                    result = self.skip(item, label)
                else:
                    try:
                        value = function(item, host, device)
                        if not isinstance(value, dict):
                            raise TypeError('campaign execution returned no structured report')
                        result = {'item': item, 'phase': label, 'stage': STAGES.get(label, label),
                            'host': value.get('host', host), 'physical_device': value.get('physical_device', device),
                            'status': value.get('status', 'completed'), 'exit_code': value.get('exit_code', value.get('exit_status'))}
                        # Publish a genuine execution failure immediately, before
                        # registering the complete returned report.
                        if execution_failed(value):
                            if result['status'] not in FAILURE_STATUSES:
                                result['reported_status'] = result['status']
                                result['status'] = 'failed'
                            self.block(identifier, result)
                        result['result_ref'] = self.artifact(value)
                    except Exception as error:
                        result = {'item': item, 'phase': label, 'stage': STAGES.get(label, label),
                            'host': host, 'physical_device': device, 'status': 'error',
                            'error': f'{type(error).__name__}: {error}'}
                        self.block(identifier, result, interrupted=True)
                with self.lock:
                    results[index] = result
                with WRITER_LOCK:
                    print(label, json.dumps(result, ensure_ascii=False), flush=True)

        if items:
            if not self.slots:
                raise ValueError('qualified topology has no execution slots')
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.slots)) as pool:
                list(pool.map(worker, self.slots))
        ordered = [results[index] for index in range(len(items))]
        dump(self.task / 'queue' / f'{label}.json', ordered)
        ref = self.artifact(ordered)
        self.event('next_step_decided', {'action': 'complete_bounded_phase',
            'reason': f'All {label} queue items have terminal execution or explicit skip evidence.',
            'evidence_refs': [self.phase_refs[label], ref]})
        return ordered

    def aggregate(self, identifiers, phase):
        reports = {}
        for identifier in identifiers:
            try:
                reports[identifier] = self.campaign.aggregate(self.operator, identifier, phase)
            except Exception as error:
                result = {'item': identifier, 'phase': phase, 'stage': phase + '_aggregation',
                    'status': 'error', 'error': f'{type(error).__name__}: {error}'}
                self.block(identifier, result, interrupted=True)
                reports[identifier] = result
        return reports


def execute_operator(op):
    c = Campaign()
    task = c.task(op)
    if (task / 'trace_events.jsonl').exists():
        verify_trace(task / 'trace_events.jsonl', c.store(op))
    qualification = c.run / 'calibration/selection.json'
    if not qualification.exists():
        raise ValueError('timing concurrency calibration is still pending')
    selection = json.loads(qualification.read_text())
    if not selection['accepted']:
        raise ValueError('no qualified timing topology; do not silently admit measurements')
    slots = [(host, device) for host, devices in selection['physical_devices_by_host'].items() for device in devices]
    if not slots:
        raise ValueError('qualified timing topology has no physical devices')
    controller = HardwareQueue(c, op, slots)
    registered = [path.parent.name for path in sorted((task / 'candidates').glob('*/registration.json'))]
    if not registered:
        raise ValueError('no registered candidates to freeze')
    built = []
    for identifier in registered:
        path = task / 'executions' / identifier / 'build/execution.json'
        report = json.loads(path.read_text()) if path.exists() else {'status': 'not_run'}
        if report.get('status') == 'passed' and not execution_failed(report):
            built.append(identifier)
        else:
            result = {'item': identifier, 'phase': 'build', 'stage': 'build', 'status': report.get('status', 'not_run'),
                'exit_code': report.get('exit_code'), 'error': 'No successful recorded build; candidate hardware work is skipped.',
                'build_report_ref': controller.artifact(report) if path.exists() else None}
            controller.block(identifier, result)

    def correctness(identifier, host, device):
        path = c.accuracy_report(op, identifier)
        if path.exists():
            current = json.loads(path.read_text())
            if current['status'] in ('passed', 'failed'):
                return current  # A terminal failure never retries the same candidate.
        return c.correctness(op, identifier, host=host, device=device)

    controller.dispatch(built, correctness, 'correctness')
    qualified = []
    for identifier in built:
        path = c.accuracy_report(op, identifier)
        if identifier in controller.blocked or not path.exists():
            continue
        report = json.loads(path.read_text())
        if report.get('status') == 'passed' and report.get('passed_count') == 20:
            qualified.append(identifier)
        else:
            controller.block(identifier, {'item': identifier, 'phase': 'correctness', 'stage': 'correctness',
                'status': 'failed', 'error': 'Full20 correctness did not qualify this candidate.'})
    sentinels = c.manifest['sentinel_case_ids']
    controller.dispatch([(identifier, case) for identifier in qualified for case in sentinels],
        lambda item, host, device: c.measure_case(op, item[0], case=item[1], host=host, device=device), 'search')
    # Even a failed or entirely skipped candidate gets the empty/partial adapter
    # projection, preserving all raw files without admitting incomplete arrays.
    search_reports = controller.aggregate(registered, 'search')

    def score(identifier):
        report = search_reports[identifier]
        if report.get('speedup') is not None:
            return report['speedup']
        values = [row['speedup'] for row in report.get('per_case', []) if row.get('speedup') is not None]
        return math.exp(sum(map(math.log, values)) / len(values)) if len(values) == len(sentinels) else 0

    healthy = [identifier for identifier in qualified if identifier not in controller.blocked]
    profile_ids = sorted(healthy, key=lambda identifier: (-score(identifier), identifier))[:c.manifest['budget']['full_profile_limit']]
    for identifier in profile_ids:
        if not (task / 'candidates' / identifier / 'mechanism_plan.json').exists():
            controller.block(identifier, {'item': identifier, 'phase': 'profiles', 'stage': 'profile',
                'status': 'error', 'error': 'Required before-profile mechanism plan is missing.'}, interrupted=True)
    profile_ids = [identifier for identifier in profile_ids if identifier not in controller.blocked]
    profile_selection = {'candidate_ids': profile_ids,
        'basis': 'sentinel-only paired geometric speedup; unstable successful executions remain exploratory and are not admitted',
        'sentinel_case_ids': sentinels, 'scores': {identifier: score(identifier) for identifier in healthy},
        'excluded_after_execution_failure': sorted(controller.blocked)}
    dump(task / 'profile_selection.json', profile_selection)
    ref = controller.artifact(profile_selection)
    controller.event('next_step_decided', {'action': 'freeze_candidates_before_acceptance',
        'reason': 'All registered attempts are retained; only sentinel measurements informed profile selection, and blocked candidates receive no future hardware work.',
        'evidence_refs': [ref]}, event_id=op + '-freeze-before-final')
    try:
        c.freeze(op)
    except Exception as error:
        controller.event('execution_interrupted', {'stage': 'freeze', 'reason': f'{type(error).__name__}: {error}', 'execution': None}, refs=[ref])
        raise
    controller.dispatch([(identifier, case) for identifier in profile_ids for case in sentinels],
        lambda item, host, device: c.profile_case(op, item[0], case=item[1], host=host, device=device), 'profiles')
    controller.dispatch([(identifier, case) for identifier in qualified for case in range(1, 21)],
        lambda item, host, device: c.measure_case(op, item[0], case=item[1], phase='final', host=host, device=device), 'final')
    final_reports = controller.aggregate(registered, 'final')
    complete = {'operator': op, 'candidate_ids': registered, 'successfully_built': built,
        'correctness_qualified': qualified, 'profiled_candidate_ids': profile_ids,
        'blocked_candidates': controller.blocked, 'final_reports': final_reports,
        'calibration': str(qualification), 'status': 'completed',
        'reason': 'Every registered attempt is frozen; hardware jobs ended or were explicitly skipped after failure.'}
    dump(task / 'queue/hardware_complete.json', complete)
    complete_ref = controller.artifact(complete)
    controller.event('next_step_decided', {'action': 'hardware_collection_complete',
        'reason': complete['reason'], 'evidence_refs': [complete_ref]})
    print('hardware_complete', op, flush=True)
    return complete


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operator')
    args = parser.parse_args()
    execute_operator(args.operator)
