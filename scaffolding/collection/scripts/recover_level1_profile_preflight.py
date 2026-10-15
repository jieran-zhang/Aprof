#!/usr/bin/env python3
"""Attest one known non-hardware profiler preflight recovery, preserving history."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from collect_level1_traces import Campaign, DEFAULT_RUN, ROOT
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import canonical_json, content_hash, file_hash
from aprof_runtime.traces import register_json_artifact, utcnow, verify_trace

RECOVERY_ID = 'profile-preflight-null-reason-v1'
KNOWN_FAILURE = "Pre-profile mechanism commitment failed: AttributeError: 'NoneType' object has no attribute 'split'"
PRODUCER = ROOT / 'scaffolding/collection/scripts/run_level1_blocked_diagnostics.py'
BAD_EXPRESSION = "event['payload'].get('stage', event['payload'].get('reason', '').split(':', 1)[0])"
FIXED_EXPRESSION = "(event['payload'].get('stage') or (event['payload'].get('reason') or '').split(':', 1)[0])"


def read(path):
    return json.loads(Path(path).read_text())


def require(value, reason):
    if not value:
        raise StoreError(reason)


def immutable_write(path, payload):
    path = Path(path)
    require(not path.is_symlink(), 'recovery archive must not be a symlink')
    if path.exists():
        require(path.read_bytes() == payload, 'immutable recovery archive differs: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(payload)
    path.chmod(0o444)


def events_for(task, store):
    path = task / 'trace_events.jsonl'
    verify_trace(path, store)
    return [json.loads(line) for line in path.read_text().splitlines()]


def is_profile_event(event):
    payload = event['payload']
    return bool(event.get('candidate_id') and 'profile' in (payload.get('stage') or '')
        and event['event_type'] in ('stage_completed', 'execution_interrupted'))


def profile_files(task, identifiers):
    """Include pending jobs and logs, not just successful profiler CSV output."""
    found = set()
    for identifier in identifiers:
        for directory in (task / 'executions' / identifier).glob('profile*'):
            found.update(path for path in directory.rglob('*') if path.is_file())
        found.update(path for path in (task / 'profiles' / identifier).rglob('*.csv') if path.is_file())
    for path in (task / 'jobs').rglob('*.json'):
        job = read(path)
        if any(token == 'msprof' or Path(str(token)).name == 'msprof' for token in job.get('argv', [])):
            # Baseline jobs are permitted; only selected candidate jobs matter.
            job_id = job.get('job_id', path.stem)
            if any(task.name + '-' + identifier in job_id for identifier in identifiers):
                found.add(path)
        elif any(identifier + '/profile' in job.get('job_id', '') or identifier + '-profile' in path.stem for identifier in identifiers):
            found.add(path)
    return sorted(found)


def verify_candidate_bindings(campaign, op, store, bindings):
    from verify_level1_campaign import verify_snapshot
    task = campaign.task(op)
    frozen = {row['candidate_id']: row for row in read(task / 'frozen-roster.json')['candidates']}
    for identifier, binding in bindings.items():
        directory = task / 'candidates' / identifier
        registration = read(directory / 'registration.json')
        require(all(frozen[op + '-' + identifier].get(key) == value for key, value in registration.items())
            and frozen[op + '-' + identifier]['frozen_plan_sha256'] == binding['candidate_plan_ref'],
            'registered candidate differs from its original frozen source roster')
        for name, path in [('registration_ref', directory / 'registration.json'),
                           ('candidate_plan_ref', directory / 'candidate_plan.json'),
                           ('build_report_ref', task / 'executions' / identifier / 'build/execution.json'),
                           ('correctness_report_ref', campaign.accuracy_report(op, identifier))]:
            require(file_hash(path) == binding[name], 'recovery input changed: ' + str(path))
            store.verify_artifact(binding[name])
        require(registration['plan_hash'] == binding['candidate_plan_ref'], 'registered candidate plan changed')
        require(content_hash(read(directory / 'mechanism_plan.json')) == binding['mechanism_plan_ref'], 'frozen mechanism plan changed')
        store.verify_artifact(binding['mechanism_plan_ref'])
        require(registration['source_hashes'] == binding['source_hashes'], 'registered source identity changed')
        for label, tree in [('baseline', task / 'baseline'), ('candidate', directory / 'op')]:
            verify_snapshot(store, binding['source_hashes'][label], tree)
        campaign.verify_candidate_boundary(op, identifier)
        accuracy = read(campaign.accuracy_report(op, identifier))
        require(accuracy.get('status') == 'passed' and accuracy.get('passed_count') == 20
            and accuracy.get('case_ids') == list(range(1, 21)), 'recovery cannot rerun or override failed correctness')


def load_verified_recovery(campaign, op, store):
    """Read-only. Return only event IDs covered by the immutable qualification."""
    task = campaign.task(op)
    pointer_path = task / 'profile_preflight_recovery.json'
    if not pointer_path.exists():
        return {'ignored_event_ids': [], 'per_candidate_event_ids': {}, 'manifest_ref': None, 'warnings': []}
    pointer = read(pointer_path)
    manifest_ref = pointer['manifest_ref']
    manifest = read(store.verify_artifact(manifest_ref))
    base = task / 'controller_recoveries' / RECOVERY_ID
    require(manifest == read(base / 'manifest.json') and manifest['kind'] == 'aprof_profile_preflight_recovery'
        and manifest['recovery_id'] == RECOVERY_ID and manifest['operator'] == op
        and manifest['run_id'] == campaign.run.name and manifest['failure_signature'] == KNOWN_FAILURE,
        'recovery manifest identity/content mismatch')
    for entry in manifest['archive']:
        path = base / 'queue' / entry['name']
        require(Path(entry['name']).name == entry['name'] and file_hash(path) == entry['artifact_ref'], 'recovery queue archive changed')
        store.verify_artifact(entry['artifact_ref'])
    old = read(base / 'queue/hardware_complete.json')
    require(content_hash(old) == manifest['old_completion_ref'], 'old diagnostic completion differs from its attestation')
    store.verify_artifact(manifest['old_completion_ref'])
    require(content_hash(read(task / 'frozen-roster.json')) == manifest['frozen_roster_ref']
        and content_hash(read(task / 'profile_selection.json')) == manifest['profile_selection_ref'], 'recovery changed frozen roster/profile selection')
    require(file_hash(PRODUCER) == manifest['new_producer_ref'], 'qualified recovery controller bytes changed')
    for key in ('old_producer_ref', 'new_producer_ref', 'frozen_roster_ref', 'profile_selection_ref'):
        store.verify_artifact(manifest[key])
    verify_candidate_bindings(campaign, op, store, manifest['candidate_bindings'])
    events = events_for(task, store)
    by_id = {event['event_id']: event for event in events}
    boundary = manifest['trace_boundary']
    require(by_id.get(boundary['event_id'], {}).get('event_hash') == boundary['event_hash']
        and by_id[boundary['event_id']]['sequence'] == boundary['sequence'], 'recovery trace boundary changed')
    historical = [event for event in events if event['sequence'] <= boundary['sequence'] and is_profile_event(event)]
    allowed = manifest['qualified_event_ids']
    require(len(allowed) == len(set(allowed)) and set(allowed) == {event['event_id'] for event in historical},
        'recovery cannot ignore an unqualified or actual historical profile event')
    per_candidate = {}
    for event in historical:
        identifier = event['candidate_id'].removeprefix(op + '-')
        require(event['event_type'] == 'execution_interrupted' and event['payload']['execution'] is None
            and event['payload']['reason'] == KNOWN_FAILURE and old['blocked_candidates'][identifier]['evidence_ref'] in event['artifact_refs'],
            'qualified interruption is not the exact non-hardware null-reason failure')
        per_candidate.setdefault(event['candidate_id'], []).append(event['event_id'])
    qualification_events = {}
    for candidate_id in per_candidate:
        event = by_id.get(candidate_id + '-' + RECOVERY_ID)
        require(event is not None and event['candidate_id'] == candidate_id
            and event['payload'].get('action') == 'qualify_profile_controller_recovery'
            and manifest_ref in event['payload'].get('evidence_refs', [])
            and event['sequence'] > boundary['sequence'], 'recovery lacks its per-attempt hash-chain attestation')
        qualification_events[candidate_id] = event
    qualified_at = datetime.fromisoformat(manifest['qualified_at'].replace('Z', '+00:00'))
    for event in events:
        if event['sequence'] <= boundary['sequence'] or not is_profile_event(event):
            continue
        qualification = qualification_events.get(event['candidate_id'])
        require(qualification is not None and event['sequence'] > qualification['sequence'], 'a profile event predates its recovery authorization')
        execution = event['payload'].get('execution')
        if execution:
            require(datetime.fromisoformat(execution['started_at'].replace('Z', '+00:00')) >= qualified_at,
                'actual profile execution began before recovery qualification')
    for identifier in manifest['candidate_bindings']:
        for path in (task / 'executions' / identifier).glob('profile*/execution.json'):
            execution = read(path)
            require(datetime.fromisoformat(execution['started_at'].replace('Z', '+00:00')) >= qualified_at,
                'profile execution file predates recovery qualification')
    require(manifest['preflight_inventory'] == {'profile_job_or_output_files': [], 'actual_profile_events': [],
        'finalization_present': False}, 'recovery did not attest an empty pre-profile inventory')
    return {'ignored_event_ids': allowed, 'per_candidate_event_ids': per_candidate, 'manifest_ref': manifest_ref,
        'recovery_id': RECOVERY_ID, 'old_completion_ref': manifest['old_completion_ref'],
        'warnings': [manifest['reason']], 'qualified_at': manifest['qualified_at']}


def prepare_recovery(campaign, op, old_producer):
    task = campaign.task(op)
    require(not any((task / name).exists() for name in ('finalization_report.json', 'optimization_traces.jsonl', 'exploration_outcomes.json')),
        'profile recovery must precede finalization')
    with campaign.store(op) as store:
        if (task / 'profile_preflight_recovery.json').exists():
            recovered = load_verified_recovery(campaign, op, store)
            marker = task / 'queue/hardware_complete.json'
            if marker.exists() and content_hash(read(marker)) == recovered['old_completion_ref']:
                marker.unlink()  # Resume an interrupted archive/marker operation only.
            return recovered
        events = events_for(task, store)
        require(not any(event['event_type'] in ('attempt_finished', 'task_finished') for event in events), 'a finalized attempt cannot be reopened')
        complete_path = task / 'queue/hardware_complete.json'
        complete = read(complete_path)
        frozen, selection = read(task / 'frozen-roster.json'), read(task / 'profile_selection.json')
        diagnostic_plan = read(store.verify_artifact(complete['diagnostic_plan_ref']))
        require(diagnostic_plan == read(task / 'queue/diagnostic_plan.json')
            and diagnostic_plan['frozen_roster_ref'] == content_hash(frozen)
            and diagnostic_plan['profile_selection_ref'] == content_hash(selection),
            'original diagnostic source/profile commitments changed')
        identifiers = [path.parent.name for path in sorted((task / 'candidates').glob('*/registration.json'))]
        require(complete['candidate_ids'] == identifiers and {row['candidate_id'] for row in frozen['candidates']} == {op + '-' + identifier for identifier in identifiers},
            'old completion and frozen source roster differ')
        selected = selection['candidate_ids']
        require(complete['status'] == 'completed' and complete['collection_mode'] == 'blocked_diagnostics'
            and complete['measurement_status'] == 'blocked' and complete['profiled_candidate_ids'] == selected
            and complete['correctness_qualified'] == identifiers and set(complete['blocked_candidates']) == set(selected),
            'old completion is not exclusively the known selected-profile preflight failure')
        require(not profile_files(task, identifiers), 'actual or pending profiler job/output exists; this recovery is forbidden')
        qualified = [event for event in events if is_profile_event(event)]
        require(len(qualified) == len(selected) and {event['candidate_id'] for event in qualified} == {op + '-' + identifier for identifier in selected},
            'profile history contains missing, repeated or actual execution events')
        for event in qualified:
            identifier = event['candidate_id'].removeprefix(op + '-')
            blocked = complete['blocked_candidates'][identifier]
            require(blocked['phase'] == 'profiles' and blocked['stage'] == 'profile' and blocked['reason'] == KNOWN_FAILURE
                and event['event_type'] == 'execution_interrupted' and event['payload']['execution'] is None
                and event['payload']['reason'] == KNOWN_FAILURE and blocked['evidence_ref'] in event['artifact_refs'],
                'only the exact null-reason controller failure qualifies')
            failure = read(store.verify_artifact(blocked['evidence_ref']))
            require(failure['item'] == identifier and failure['phase'] == 'profiles' and failure['stage'] == 'profile'
                and failure['status'] == 'error' and failure['error'] == KNOWN_FAILURE, 'preflight failure CAS record differs')
        old_ref = content_hash(complete)
        require(any(event['payload'].get('action') == 'hardware_collection_complete'
            and old_ref in event['payload'].get('evidence_refs', []) for event in events), 'old completion lacks its event/CAS binding')
        store.verify_artifact(old_ref)
        require(BAD_EXPRESSION in Path(old_producer).read_text() and BAD_EXPRESSION not in PRODUCER.read_text()
            and FIXED_EXPRESSION in PRODUCER.read_text(), 'old/new controller sources do not contain the reviewed null-handling change')
        bindings = {}
        for identifier in identifiers:
            directory = task / 'candidates' / identifier
            registration = read(directory / 'registration.json')
            bindings[identifier] = {'source_hashes': registration['source_hashes'],
                'registration_ref': file_hash(directory / 'registration.json'), 'candidate_plan_ref': file_hash(directory / 'candidate_plan.json'),
                'build_report_ref': file_hash(task / 'executions' / identifier / 'build/execution.json'),
                'correctness_report_ref': file_hash(campaign.accuracy_report(op, identifier)),
                'mechanism_plan_ref': content_hash(read(directory / 'mechanism_plan.json'))}
            if identifier in selected:
                require(bindings[identifier]['mechanism_plan_ref'] == diagnostic_plan['mechanism_plan_refs'][identifier],
                    'mechanism plan differs from its preflight commitment')
            # Registration/build/accuracy files may not previously be raw-file
            # CAS entries. Bind their current bytes before the full verification.
            for path in (directory / 'registration.json', directory / 'candidate_plan.json',
                         task / 'executions' / identifier / 'build/execution.json', campaign.accuracy_report(op, identifier)):
                store.register_artifact(path)
        verify_candidate_bindings(campaign, op, store, bindings)
        base = task / 'controller_recoveries' / RECOVERY_ID
        archive = []
        for path in sorted((task / 'queue').glob('*.json')):
            archived = base / 'queue' / path.name
            immutable_write(archived, path.read_bytes())
            archive.append({'name': path.name, 'artifact_ref': store.register_artifact(archived)})
        manifest = {'schema_version': '1.0.0', 'kind': 'aprof_profile_preflight_recovery', 'recovery_id': RECOVERY_ID,
            'run_id': campaign.run.name, 'operator': op, 'qualified_at': utcnow(), 'failure_signature': KNOWN_FAILURE,
            'reason': 'The recorded null-reason AttributeError occurred in controller preflight before any profiler job. '
                'Only the listed non-hardware interruptions may be bypassed; all original evidence and any later real failures remain authoritative.',
            'qualified_event_ids': [event['event_id'] for event in qualified], 'candidate_bindings': bindings,
            'trace_boundary': {key: events[-1][key] for key in ('sequence', 'event_id', 'event_hash')},
            'old_completion_ref': old_ref, 'archive': archive,
            'frozen_roster_ref': register_json_artifact(store, frozen), 'profile_selection_ref': register_json_artifact(store, selection),
            'old_producer_ref': store.register_artifact(old_producer), 'new_producer_ref': store.register_artifact(PRODUCER),
            'old_producer_provenance': 'reconstructed_from_known_single_line_patch',
            'old_producer_limitation': 'Review reconstruction; no contemporaneous controller source hash was recorded for the failed run.',
            'attestation': 'CAS content hash plus append-only trace event hash chain; no external cryptographic signer.',
            'preflight_inventory': {'profile_job_or_output_files': [], 'actual_profile_events': [], 'finalization_present': False}}
        manifest_ref = register_json_artifact(store, manifest)
        immutable_write(base / 'manifest.json', (canonical_json(manifest) + '\n').encode())
        for event in qualified:
            candidate_id = event['candidate_id']
            campaign.writer(op, store).append('next_step_decided', {'action': 'qualify_profile_controller_recovery',
                'reason': manifest['reason'], 'evidence_refs': sorted({manifest_ref, manifest['old_producer_ref'], manifest['new_producer_ref'], old_ref})},
                candidate_id=candidate_id, attempt_id=candidate_id, event_id=candidate_id + '-' + RECOVERY_ID)
        immutable_write(task / 'profile_preflight_recovery.json', (canonical_json({'schema_version': '1.0.0', 'manifest_ref': manifest_ref}) + '\n').encode())
        recovered = load_verified_recovery(campaign, op, store)
        require(file_hash(complete_path) == next(row['artifact_ref'] for row in archive if row['name'] == 'hardware_complete.json'),
            'completion changed while recovery was being attested')
        complete_path.unlink()  # The only removed file; all bytes are archived and CAS-bound.
        return recovered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--old-producer', type=Path, required=True, help='Reviewed reconstruction of the immediately preceding controller source.')
    args = parser.parse_args()
    print(json.dumps(prepare_recovery(Campaign(args.run), args.operator, args.old_producer), allow_nan=False))


if __name__ == '__main__':
    main()
