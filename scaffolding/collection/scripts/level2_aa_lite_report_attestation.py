#!/usr/bin/env python3
"""Retrospectively replay the one closed Gather lite A/A report.

This audit runs no native work and creates no source attempt. Its task event is
an append-only report anchor for storage; it does not backdate the report.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path

from level2_final_report_attestation import (
    Evidence, Runtime, canonical, digest, engineering, publish_directory,
    require, safe, syncdir, task_events,
)

VERSION = 'level2_aa_lite_report_consistency_attestation_v1'
EVENT = 'aa_lite_report_consistency_attested'
CASES = [1, 8, 14, 20]
CLAIM = 'Retained evidence and the saved lite A/A report were consistent at this retrospective audit; no earlier report authority is asserted.'


def audit(runtime, run, engineering_path):
    run = safe(run)
    task = safe(run / 'train/tasks/gather')
    stage = safe(task / 'stages/aa-search-lite-031')
    cohort = safe(stage / 'cohort')
    ledger_dir = safe(run / 'train/ledger')
    with runtime.reader_session():
        evidence = Evidence(runtime)
        ledger = runtime.ledger(ledger_dir)
        sid = 'baseline-aa-search-lite-031'
        state = ledger.state['tasks']['gather']
        attempt = state['stages'][sid]['attempts'][-1]
        plan = evidence.document(cohort / 'plan.json')
        stage_plan = evidence.document(stage / 'stage-plan.json')
        result = evidence.document(stage / 'result.json')
        completion = evidence.document(cohort / 'group-completion.json')
        saved = evidence.document(cohort / 'report.json')
        require(attempt['outcome'] == 'success' and result['status'] == completion['status'] == 'passed'
                and result['stage_id'] == sid and result['candidate_id'] is None
                and result['native_started'] is True and state['stages'][sid]['plan'] == stage_plan
                and attempt['evidence']['result'] == evidence.pointer(stage / 'result.json')
                and stage_plan['cohort'] == plan,
                'closed lite A/A ledger/stage identity differs')
        require(plan['protocol'] == saved['protocol'] == completion['protocol'] == 'msprof_task_time_search_lite_v1'
                and plan['case_ids'] == CASES and saved['case_ids'] == [str(case) for case in CASES]
                and saved['comparison_kind'] == plan['comparison_kind'] == 'aa'
                and saved['source_hashes']['A'] == saved['source_hashes']['B']
                and saved['evidence_status'] == 'verified_complete', 'lite A/A report scope differs')
        names = [row['name'] for row in plan['schedule']]
        directories = [str(cohort / name) for name in names]
        require(len(names) == len(set(names)) == 2 and completion['completed_sessions'] == directories
                and [row['directory'] for row in saved['sessions']] == directories,
                'lite A/A process roster differs')
        require(len(saved['results']) == 8
                and {(row['case_id'], row['buffer_config']) for row in saved['results']}
                    == {(str(case), mode) for case in CASES for mode in ('normal', 'swapped')},
                'lite A/A case/config coverage differs')
        actual = runtime.analyze(directories, plan, None)
        observation_provenance = list(runtime.observation_provenance)
        compared = runtime.compare(saved, actual, cohort / 'report.json')
        require(compared['comparison']['matched'] is True, 'lite A/A report replay differs')
        historical_producers = [*observation_provenance, *compared['historical_producers']]
        for row in saved['sessions']:
            for path, expected in row['artifacts'].items():
                if runtime.fingerprint(path) == expected:
                    require(evidence.pointer(path)['sha256'] == expected, 'lite A/A artifact changed')
                else:
                    matches = [proof for proof in historical_producers
                               if proof.get('origin') == {'path': path, 'sha256': expected}]
                    require(matches and all(proof.get('snapshot', {}).get('sha256') == expected for proof in matches),
                            'lite A/A historical producer lacks frozen snapshot')
                    for proof in matches:
                        evidence.tree({key: value for key, value in proof.items() if key != 'origin'})
        frozen = engineering(evidence, runtime, engineering_path, task)
        evidence.recheck()
        fresh = runtime.ledger(ledger_dir)
        require(fresh.events == ledger.events and fresh.state == ledger.state, 'ledger changed during lite A/A audit')
        ledger_bytes = safe(ledger_dir / 'events.jsonl').read_bytes()
        require(len(ledger_bytes.splitlines()) == len(ledger.events), 'ledger tail changed')
        return {
            'version': VERSION, 'task': str(task), 'stage': str(stage),
            'report': evidence.pointer(cohort / 'report.json'),
            'stage_result': evidence.pointer(stage / 'result.json'),
            'stage_plan': evidence.pointer(stage / 'stage-plan.json'),
            'completion': evidence.pointer(cohort / 'group-completion.json'),
            'engineering': evidence.pointer(engineering_path),
            'producers': frozen,
            'comparison': compared['comparison'],
            'historical_producers': historical_producers,
            'replayed_report_sha256': digest(canonical(actual)),
            'evidence': sorted(evidence.refs.values(), key=lambda row: row['path']),
            'ledger_prefix': {'event_count': len(ledger.events), 'head_hash': ledger.events[-1]['hash'],
                              'sha256': digest(ledger_bytes)},
            'ledger_bytes': ledger_bytes,
        }


def attest(repository, run, engineering_path):
    runtime = Runtime(repository)
    task = safe(run / 'train/tasks/gather')
    with runtime.host_lock():
        with safe(run / 'train/ledger/.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            scope = audit(runtime, run, engineering_path)
            ledger_bytes = scope.pop('ledger_bytes')
            identity = digest(canonical({'stage': scope['stage'], 'report': scope['report'],
                                         'engineering': scope['engineering']}))
            directory = safe(Path(scope['stage']) / ('report-attestation-' + identity[7:23]))
            request = {'version': VERSION, 'attestation_id': identity, 'scope': scope}
            request_ref = {'path': str(directory / 'request.json'), 'sha256': digest(canonical(request))}
            value = {'version': VERSION, 'status': 'passed', 'kind': 'retrospective_lite_aa_report_replay',
                     'attestation_id': identity, 'audited_at': datetime.now(timezone.utc).isoformat(),
                     'request': request_ref, 'comparison': scope['comparison'], 'native_executed': False,
                     'formal_admission': 'not_evaluated', 'graph_policy_eligible': False, 'claim': CLAIM}
            if directory.exists():
                existing = json.loads(safe(directory / 'request.json').read_bytes())
                require(existing == request, 'existing lite A/A audit request differs')
                value = json.loads(safe(directory / 'attestation.json').read_bytes())
            else:
                publish_directory(directory, {'request.json': canonical(request),
                                              'attestation.json': canonical(value),
                                              'ledger-prefix.jsonl': ledger_bytes})
            attestation_ref = {'path': str(directory / 'attestation.json'),
                               'sha256': digest(safe(directory / 'attestation.json').read_bytes())}
            require(safe(directory / 'ledger-prefix.jsonl').read_bytes() == ledger_bytes
                    and value['request'] == request_ref and value['status'] == 'passed'
                    and value['comparison'] == scope['comparison'], 'stored lite A/A audit differs')
            event_value = {'operator': 'gather', 'stage_id': 'baseline-aa-search-lite-031',
                           'report': scope['report'], 'attestation': attestation_ref,
                           'authority_timing': 'retrospective_audit_now_not_original_measurement'}
            for path in directory.iterdir():
                with safe(path).open('rb') as stream: os.fsync(stream.fileno())
            syncdir(directory); syncdir(directory.parent)
            with safe(task / '.recorder.lock').open('rb') as recorder:
                fcntl.flock(recorder, fcntl.LOCK_EX)
                rows = task_events(task)
                prior = [row for row in rows if row['kind'] == EVENT]
                require(len(prior) <= 1, 'duplicate lite A/A report event')
                if prior:
                    require(prior[0]['value'] == event_value, 'prior lite A/A report event differs')
                    return {'status': 'already_attested', 'attestation': attestation_ref, 'event': prior[0]}
                with runtime.reader_session():
                    runtime.reverify()
                    check = Evidence(runtime)
                    for ref in scope['evidence']:
                        require(check.pointer(ref['path']) == ref, 'lite A/A evidence changed before event')
                require(safe(run / 'train/ledger/events.jsonl').read_bytes() == ledger_bytes,
                        'ledger changed before lite A/A event')
                row = {'sequence': len(rows), 'recorded_at': datetime.now(timezone.utc).isoformat(),
                       'kind': EVENT, 'previous_hash': rows[-1]['hash'] if rows else None,
                       'value': event_value}
                row['hash'] = digest(canonical(row))
                with safe(task / 'events.jsonl').open('ab') as stream:
                    stream.write(canonical(row)); stream.flush(); os.fsync(stream.fileno())
                syncdir(task)
                return {'status': 'attested', 'attestation': attestation_ref, 'event': row,
                        'native_executed': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--engineering', type=Path, required=True)
    p.add_argument('--writers-closed', action='store_true')
    a = p.parse_args()
    require(a.writers_closed, 'all native and report writers must be closed')
    print(json.dumps(attest(a.repository.resolve(), a.run.resolve(), a.engineering.resolve()), indent=2))


if __name__ == '__main__': main()
