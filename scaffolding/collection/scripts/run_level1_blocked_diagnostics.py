#!/usr/bin/env python3
"""Collect correctness and counters only after both timing ladders reject admission."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from collect_level1_traces import Campaign, DEFAULT_RUN, WRITER_LOCK
from run_aprof_job import dump
from run_level1_hardware_queue import HardwareQueue, execution_failed
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.traces import verify_trace

DIAGNOSTIC_SLOTS = [('local', 14), ('decode', 14)]
BLOCK_REASON = ('Both unpinned and affinity-v1 timing calibration ladders rejected admission. '
    'Collect correctness and profiler counters only; no candidate timing or performance gain is admitted.')


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, reason):
    if not condition:
        raise StoreError(reason)


def calibration_failure_files(run):
    """Read-only precondition: an old rejected selection is not terminal recovery."""
    root = Path(run) / 'calibration'
    unpinned_path, final_path = root / 'selection-unpinned.json', root / 'selection.json'
    unpinned, final = read(unpinned_path), read(final_path)
    for selection in (unpinned, final):
        require(selection.get('accepted') is False and selection.get('max_device_jobs') == 0
            and bool(selection.get('reason')), 'both calibration selections must conclusively reject admission')
    protocol_path = root / 'affinity-v1/protocol.json'
    require(Path(final.get('protocol_ref', '')).resolve() == protocol_path.resolve(),
        'affinity-v1 recovery is still pending: selection does not bind its protocol')
    protocol = read(protocol_path)
    require(protocol.get('name') == 'affinity-v1' and protocol.get('widths') == [8, 4, 2, 1],
        'unexpected affinity recovery ladder')
    paths = [unpinned_path, final_path, protocol_path]
    for directory, widths in ((root, (32, 16, 8, 4, 2, 1)), (root / 'affinity-v1', (8, 4, 2, 1))):
        for width in widths:
            path = directory / f'calibration-{width}.json'
            report = read(path)
            outcomes = report.get('outcomes', [])
            require(report.get('width') == width and report.get('accepted') is False
                and len(outcomes) == width and all(type(row.get('passed')) is bool for row in outcomes)
                and any(row['passed'] is False for row in outcomes),
                'calibration ladder lacks a complete rejected round: ' + str(path))
            paths.append(path)
    return paths


def no_candidate_timing(task):
    for phase in ('search', 'final'):
        for path in (task / 'timing' / phase).glob('*/**/raw_measurements.json'):
            raw = read(path)
            require(not raw.get('records') and not raw.get('case_sources'),
                'diagnostic fallback cannot overwrite existing candidate timing evidence: ' + str(path))
    stream = task / 'trace_events.jsonl'
    if stream.exists():
        for event in map(json.loads, stream.read_text().splitlines()):
            if event.get('candidate_id') and event['event_type'] in ('stage_completed', 'execution_interrupted'):
                stage = event['payload'].get('stage', '').replace('-', '_')
                require(not any(name in stage for name in ('search_timing', 'final_timing')),
                    'candidate timing has already been attempted; use the original queue evidence')


def verify_mechanism_plan(campaign, op, identifier):
    from bind_level1_mechanisms import MechanismBinder
    directory = campaign.task(op) / 'candidates' / identifier
    plan = read(directory / 'mechanism_plan.json')
    require(plan['candidate_id'] == op + '-' + identifier
        and plan['candidate_plan_hash'] == file_hash(directory / 'candidate_plan.json'),
        'mechanism prediction no longer matches its registered candidate plan')
    with WRITER_LOCK, campaign.store(op) as store:
        MechanismBinder(campaign.run).verify_plan_event(op, plan, store)
        store.verify_artifact(content_hash(plan))
    return content_hash(plan)


def execute_operator(op, run=DEFAULT_RUN, *, campaign=None):
    c = campaign or Campaign(run)
    require(op in c.manifest['operators'], 'operator is outside this campaign')
    # All admission checks precede CAS, queue, source-freeze or hardware mutation.
    calibration_files = calibration_failure_files(c.run)
    task = c.task(op)
    no_candidate_timing(task)
    complete_path = task / 'queue/hardware_complete.json'
    if complete_path.exists():
        complete = read(complete_path)
        require(complete.get('collection_mode') == 'blocked_diagnostics'
            and complete.get('status') == 'completed' and complete.get('measurement_status') == 'blocked',
            'existing hardware closure is not this diagnostic fallback')
        return complete
    registered = [path.parent.name for path in sorted((task / 'candidates').glob('*/registration.json'))]
    require(0 < len(registered) <= min(6, c.manifest['budget']['candidate_limit']), 'expected 1..6 registered candidates')
    profile_selection_path = task / 'profile_selection.json'
    previous_selection = read(profile_selection_path) if profile_selection_path.exists() else None
    limit = min(3, c.manifest['budget']['full_profile_limit'])
    existing_profile_ids = {path.name for path in (task / 'profiles').glob('*')
        if path.is_dir() and path.name.isdigit() and any(path.rglob('*.csv'))}
    require(not existing_profile_ids or previous_selection is not None,
        'existing candidate profiler results lack a predeclared profile selection')
    if previous_selection is not None:
        selected = previous_selection['candidate_ids']
        require(len(selected) == len(set(selected)) <= limit and set(selected).issubset(registered)
            and previous_selection['sentinel_case_ids'] == c.manifest['sentinel_case_ids'],
            'immutable profile selection exceeds the frozen roster/case budget')
        require(existing_profile_ids.issubset(selected), 'existing profiler evidence is outside the immutable selected list')
    with c.store(op) as store:
        if (task / 'trace_events.jsonl').exists():
            verify_trace(task / 'trace_events.jsonl', store)
        from recover_level1_profile_preflight import load_verified_recovery
        recovery = load_verified_recovery(c, op, store)
    recovered_event_ids = set(recovery['ignored_event_ids'])
    controller = HardwareQueue(c, op, DIAGNOSTIC_SLOTS)
    with WRITER_LOCK, c.store(op) as store:
        calibration_refs = [store.register_artifact(path) for path in calibration_files]
    calibration = {'schema_version': '1.0.0', 'kind': 'blocked_timing_admission', 'reason': BLOCK_REASON,
        'measurement_status': 'blocked', 'sources': [{'path': str(path), 'sha256': digest}
            for path, digest in zip(calibration_files, calibration_refs)],
        'diagnostic_slots': [{'host': host, 'physical_device': device} for host, device in DIAGNOSTIC_SLOTS],
        'timing_qualification_claimed': False}
    calibration_ref = controller.artifact(calibration)
    dump(task / 'queue/calibration_block.json', calibration)
    for identifier in registered:
        controller.event('next_step_decided', {'action': 'block_timing_after_calibration_failure',
            'reason': BLOCK_REASON, 'evidence_refs': sorted(set([calibration_ref, *calibration_refs]))},
            identifier=identifier, event_id=op + '-' + identifier + '-diagnostic-timing-blocked')
    # Verify every registered source, including failed builds, before freezing.
    try:
        for identifier in registered:
            c.verify_source_identity(op, identifier)
        frozen = c.freeze(op)
        require({row['candidate_id'] for row in frozen['candidates']} == {op + '-' + identifier for identifier in registered},
            'frozen roster omitted a registered diagnostic attempt')
    except Exception as error:
        controller.event('execution_interrupted', {'stage': 'freeze', 'execution': None,
            'reason': f'Diagnostic source freeze failed: {type(error).__name__}: {error}'}, refs=[calibration_ref])
        raise
    frozen_ref = controller.artifact(frozen)
    built = []
    for identifier in registered:
        path = task / 'executions' / identifier / 'build/execution.json'
        report = read(path) if path.exists() else {'status': 'not_run'}
        if report.get('status') == 'passed' and not execution_failed(report):
            built.append(identifier)
        else:
            controller.block(identifier, {'item': identifier, 'phase': 'build', 'stage': 'build',
                'status': report.get('status', 'not_run'), 'exit_code': report.get('exit_code'),
                'error': 'No successful recorded build; diagnostic hardware work is skipped.',
                'build_report_ref': controller.artifact(report) if path.exists() else None})

    def correctness(identifier, host, device):
        path = c.accuracy_report(op, identifier)
        if path.exists() and read(path).get('status') in ('passed', 'failed'):
            return read(path)  # Never retry terminal correctness for this source.
        execution = task / 'executions' / identifier / 'correctness/execution.json'
        if execution.exists() and execution_failed(read(execution)):
            return read(execution)
        return c.correctness(op, identifier, host=host, device=device)

    controller.dispatch(built, correctness, 'correctness')
    qualified = []
    for identifier in built:
        path = c.accuracy_report(op, identifier)
        if identifier in controller.blocked:
            continue
        report = read(path) if path.exists() else {}
        if report.get('status') == 'passed' and report.get('passed_count') == 20 and report.get('case_ids') == list(range(1, 21)):
            qualified.append(identifier)
        else:
            controller.block(identifier, {'item': identifier, 'phase': 'correctness', 'stage': 'correctness',
                'status': 'failed', 'error': 'All 20 declared correctness cases did not qualify this source.'})
    selected = previous_selection['candidate_ids'] if previous_selection is not None else sorted(qualified)[:limit]
    selection = previous_selection or {'candidate_ids': selected, 'sentinel_case_ids': c.manifest['sentinel_case_ids'],
        'basis': 'lexical first correctness-qualified candidates; no candidate timing observed or used',
        'collection_mode': 'blocked_diagnostics', 'calibration_block_ref': calibration_ref}
    if previous_selection is None:
        dump(profile_selection_path, selection)
    selection_ref = controller.artifact(selection)
    controller.event('next_step_decided', {'action': 'freeze_diagnostic_profile_selection',
        'reason': 'Honor the immutable profile list; collect only its correctness-qualified sources with predeclared mechanisms.',
        'evidence_refs': [selection_ref, frozen_ref, calibration_ref]}, event_id=op + '-diagnostic-profile-selection')
    mechanism_refs = {}
    prior_events = [json.loads(line) for line in (task / 'trace_events.jsonl').read_text().splitlines()]
    for identifier in selected:
        if identifier not in qualified or identifier in controller.blocked:
            continue
        try:
            mechanism_refs[identifier] = verify_mechanism_plan(c, op, identifier)
            failures = [event for event in prior_events if event.get('candidate_id') == op + '-' + identifier
                and event['event_id'] not in recovered_event_ids
                and 'profile' in (event['payload'].get('stage') or (event['payload'].get('reason') or '').split(':', 1)[0])
                and (event['event_type'] == 'execution_interrupted'
                    or (event['event_type'] == 'stage_completed' and event['payload'].get('status') != 'passed')
                    or event['payload'].get('action') == 'stop_candidate_after_execution_failure')]
            if failures:
                controller.block(identifier, {'item': identifier, 'phase': 'profiles', 'stage': 'profile', 'status': 'failed',
                    'error': 'An earlier profile execution/controller failure is terminal for this candidate.',
                    'previous_event_ids': [event['event_id'] for event in failures]})
                continue
            for path in (task / 'executions' / identifier).glob('profile-*/execution.json'):
                if execution_failed(read(path)):
                    controller.block(identifier, {'item': identifier, 'phase': 'profiles', 'stage': 'profile', 'status': 'failed',
                        'error': 'A previous profile execution failed; do not retry this candidate.', 'execution_ref': controller.artifact(read(path))})
                    break
        except Exception as error:
            controller.block(identifier, {'item': identifier, 'phase': 'profiles', 'stage': 'profile', 'status': 'error',
                'error': f'Pre-profile mechanism commitment failed: {type(error).__name__}: {error}'}, interrupted=True)
    plan = {'schema_version': '1.0.0', 'operator': op, 'collection_mode': 'blocked_diagnostics',
        'candidate_ids': registered, 'profile_candidate_ids': selected, 'mechanism_plan_refs': mechanism_refs,
        'frozen_roster_ref': frozen_ref, 'profile_selection_ref': selection_ref, 'calibration_block_ref': calibration_ref,
        'measurement_status': 'blocked', 'reason': BLOCK_REASON}
    dump(task / 'queue/diagnostic_plan.json', plan)
    plan_ref = controller.artifact(plan)

    def profile(item, host, device):
        identifier, case = item
        path = task / 'executions' / identifier / f'profile-{case:02d}/execution.json'
        if path.exists():
            return read(path)  # Retain existing terminal profiler evidence.
        return c.profile_case(op, identifier, case=case, host=host, device=device)

    profile_results = controller.dispatch([(identifier, case) for identifier in selected for case in c.manifest['sentinel_case_ids']], profile, 'profiles')
    passed_profile_cases = {(row['item'][0], row['item'][1]) for row in profile_results
        if row['status'] == 'passed' and not execution_failed(row) and row.get('result_ref')}
    profiled = sorted({identifier for identifier, case in passed_profile_cases})
    full_profiles = [identifier for identifier in selected
        if all((identifier, case) in passed_profile_cases for case in c.manifest['sentinel_case_ids'])]
    # Empty projections communicate absent measurement. No timing/aggregation
    # stage_completed event is synthesized: no such hardware stage ran.
    search_reports = controller.aggregate(registered, 'search')
    final_reports = controller.aggregate(registered, 'final')
    complete = {'schema_version': '1.0.0', 'operator': op, 'candidate_ids': registered,
        'successfully_built': built, 'correctness_qualified': qualified, 'selected_profile_candidate_ids': selected,
        'profiled_candidate_ids': profiled, 'full_profile_candidate_ids': full_profiles,
        'blocked_candidates': controller.blocked, 'search_reports': search_reports, 'final_reports': final_reports,
        'collection_mode': 'blocked_diagnostics', 'status': 'completed', 'measurement_status': 'blocked',
        'reason': BLOCK_REASON, 'calibration_block_ref': calibration_ref, 'calibration_refs': calibration_refs,
        'diagnostic_plan_ref': plan_ref, 'timing_qualification_claimed': False}
    if recovery['manifest_ref']:
        complete['controller_recovery_ref'] = recovery['manifest_ref']
    dump(complete_path, complete)
    ref = controller.artifact(complete)
    controller.event('next_step_decided', {'action': 'hardware_collection_complete', 'reason': BLOCK_REASON,
        'evidence_refs': [ref, calibration_ref, plan_ref]}, event_id=op + '-diagnostic-hardware-complete'
            + ('-after-' + recovery['recovery_id'] if recovery['manifest_ref'] else ''))
    return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run'])
    parser.add_argument('--operator', required=True)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    print(json.dumps(execute_operator(args.operator, args.run), allow_nan=False))


if __name__ == '__main__':
    main()
