#!/usr/bin/env python3
"""Frozen R1-only serial coordinator. No authoring, retries or protocol changes.

Prepare after the previous controller is quiescent and engineering is frozen.
An interrupted child needs explicit recovery: a missing durable exit receipt is
never permission to launch the same command again.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import level2_iteration as iteration
import level2_finalize as finalizer
import msprof_exploration_campaign as campaign
import msprof_exploration_report as report
from level2_failure_classification import classify_failure
from msprof_exploration_execute import load, pointer, sha
from msprof_exploration_provenance import FRESH_PRODUCERS, verify_pointer_tree
from msprof_raw_storage import LOCAL
from prepare_trace_pilot import create_source_snapshot

VERSION = 'level2_r1_serial_queue_v2'
SETTINGS = {'epoch': 'local-raw-01', 'capture_storage': LOCAL}
GROUP = 'aa-local-01'
ROOT = Path(__file__).resolve().parents[1]


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical_path(value):
    path = Path(value).absolute()
    require('..' not in path.parts and path == path.resolve()
            and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe queue path')
    return path


def checked(ref):
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'invalid queue pointer')
    path = canonical_path(ref['path'])
    require(path.is_file() and pointer(path) == ref, 'queue bound file changed: ' + str(path))
    return load(path)


def sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic(path, value, *, exclusive=False):
    path = canonical_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not exclusive or not path.exists(), 'immutable queue evidence already exists')
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    if exclusive:
        os.link(name, path)
        os.unlink(name)
    else:
        os.replace(name, path)
    sync_dir(path.parent)


def ledger_for(entry):
    task = canonical_path(entry['task'])
    return campaign.Campaign(task.parents[1] / 'ledger'), task


def check_entry(entry, *, allow_later=False, require_registered=False):
    for ref in entry['bindings'].values():
        path = canonical_path(ref['path'])
        require(pointer(path) == ref, 'queue operator input changed')
    ledger, task = ledger_for(entry)
    state = ledger.state['tasks'][entry['operator']]
    if not allow_later:
        require(not state['frozen'] and set(state['candidates']) <= {entry['candidate_id']}
                and state['new_source_attempts'] <= 1 and state['new_rounds_started'] <= 1,
                'queue scope is exactly R1; another source/round already exists')
    else:
        require(entry['candidate_id'] in state['candidates']
                and state['new_source_attempts'] <= 3 and state['new_rounds_started'] <= 3,
                'completed R1 source is absent or policy rounds exceeded')
    require(ledger.config['schema_version'] == campaign.FRESH_SCHEMA
            and ledger.config['policy']['max_new_rounds'] == 3, 'queue requires frozen fresh campaign')
    parent = task / 'candidates' / entry['candidate_id']
    preview = entry['bindings']['source_preview']
    require(preview['path'] == str(parent / 'pre-registration-source.tar'),
            'queue preview must retain its original materialized location')
    require(entry['bindings']['baseline_source']['sha256']
            == ledger.config['tasks'][entry['operator']]['baseline_source_hash'],
            'queue baseline differs from frozen ledger')
    proposal = load(entry['bindings']['proposal']['path'])
    require(proposal['candidate_id'] == entry['candidate_id']
            and proposal['operator'] == entry['operator']
            and proposal['source_parent'] == 'baseline'
            and proposal['implementation_source_hash'] == preview['sha256'],
            'R1 proposal source/parent differs')
    iteration.verify_source_snapshot(preview['path'], parent / 'op')
    # Verify the complete deterministic snapshot, including protected non-native
    # files and modes. The native-only role-tree check alone is insufficient.
    with tempfile.TemporaryDirectory(prefix='aprof-queue-source-check-') as temporary:
        replay = Path(temporary) / 'source.tar'
        create_source_snapshot(parent / 'op', replay, root_label=entry['candidate_id'])
        require(sha(replay) == preview['sha256'], 'materialized preview differs from complete source tree')
    item = state['candidates'].get(entry['candidate_id'])
    formal = canonical_path(parent / 'source.tar')
    require(item is not None or not require_registered, 'candidate has no formal registration')
    if item is None:
        require(not formal.exists(), 'unregistered formal archive requires explicit review')
    else:
        formal_ref = pointer(canonical_path(formal))
        require(formal_ref['sha256'] == preview['sha256'] == item['source_hash']
                and item.get('artifacts', {}).get('source') == formal_ref
                and item.get('artifacts', {}).get('proposal') == entry['bindings']['proposal']
                and item['source_parent'] == {'candidate_id': None,
                    'source_hash': entry['bindings']['baseline_source']['sha256']},
                'registered source/ledger differs from immutable materialized preview')
        iteration.verify_source_snapshot(formal, parent / 'op')
    return ledger, task


def prepare(run, schedule, engineering, output):
    run, schedule, engineering, output = map(canonical_path, (run, schedule, engineering, output))
    require(not output.exists(), 'fresh queue directory required')
    require(output.is_relative_to(run / 'preflight'), 'queue belongs under run/preflight')
    schedule_value, frozen = load(schedule), load(engineering)
    order = schedule_value['scheduling']['after_current_recommended_new_operator_order']
    require(len(order) == len(set(order)) == 15 and 'maximum' not in order
            and set(order) == set(iteration.OPERATORS) - {'maximum'}, 'queue must contain remaining15 exactly')
    require(frozen.get('version') == 'level2_frozen_engineering_v1'
            and engineering.parent == run / 'bootstrap', 'engineering manifest identity differs')
    identities = {row['path']: row for row in frozen['files']}
    producer_names = sorted(FRESH_PRODUCERS | {'level2_r1_queue.py', 'run_msprof_exploration_stage.py', 'prepare_trace_pilot.py'})
    producers = []
    for name in producer_names:
        path = ROOT / 'scripts' / name
        identity = identities.get(str(path))
        require(identity is not None and sha(path) == identity['sha256']
                and sha(identity['snapshot']) == identity['sha256'], 'producer absent from frozen engineering: ' + name)
        producers.append(pointer(path))
    rows = {row['operator']: row for row in schedule_value['operators']}
    entries = []
    for op in order:
        row = rows[op]; task = run / row['split'] / 'tasks' / op
        cid = row['r1_candidate']; parent = task / 'candidates' / cid
        require(cid == op + ('001v2' if op in ('scatter', 'unsorted_segment_sum', 'cross_entropy_loss') else '001'),
                'queue is restricted to the existing declared R1 IDs')
        bindings = {'proposal': pointer(parent / 'proposal.json'), 'source_preview': pointer(parent / 'pre-registration-source.tar'),
                    'measurement_policy': pointer(task / 'measurement-policy.json'),
                    'manifest': pointer(task / 'manifest.json'), 'baseline_source': pointer(task / 'baseline-source.tar')}
        require(bindings['proposal'] == row['input_bindings']['proposal']
                and bindings['measurement_policy'] == row['input_bindings']['policy'], 'schedule inputs differ')
        entry = {'operator': op, 'candidate_id': cid, 'task': str(task), 'bindings': bindings}
        check_entry(entry)
        entries.append(entry)
    request = {'version': VERSION, 'run': str(run), 'schedule': pointer(schedule),
        'engineering': pointer(engineering), 'producers': producers, 'python': str(Path(sys.executable).resolve()),
        'settings': SETTINGS, 'calibration_group': GROUP, 'deduplicate_outputs': True,
        'entries': entries, 'scope': 'R1 only; no R2/R3 or final evaluation; no automatic recovery'}
    output.mkdir(parents=True)
    atomic(output / 'request.json', request, exclusive=True)
    atomic(output / 'state.json', {'version': VERSION, 'request': pointer(output / 'request.json'),
        'status': 'prepared', 'operators': {row['operator']: {'status': 'pending'} for row in entries}})
    return {'status': 'prepared', 'queue': str(output), 'operators': order}


def argv(request, entry, phase):
    command = [request['python'], str(ROOT / 'scripts/level2_iteration.py'), phase,
        '--run', request['run'], '--operator', entry['operator'], '--capture-storage', 'local',
        '--epoch', 'local-raw-01', '--calibration-group', GROUP, '--deduplicate-outputs']
    if phase == 'candidate':
        command.extend(['--candidate', entry['candidate_id']])
    return command


def run_command(command, directory, lock_fd):
    started = time.time()
    with (directory / 'stdout.log').open('xb') as stdout, (directory / 'stderr.log').open('xb') as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, pass_fds=(lock_fd,), cwd=ROOT)
        # The child retains the flock if this coordinator dies. Once it exits,
        # missing finished.json still blocks resumption; never guess/relaunch.
        code = process.wait()
        stdout.flush(); stderr.flush(); os.fsync(stdout.fileno()); os.fsync(stderr.fileno())
    return {'argv': command, 'pid': process.pid, 'started_at': started,
            'ended_at': time.time(), 'returncode': code}


def baseline_runtime(ledger, operator, task, row):
    ref = row['attempts'][-1]['evidence']['runtime']; value = checked(ref)
    verify_pointer_tree(value, evidence_path=ref['path'])
    binding = iteration.successful_correctness_binding(ledger, operator, None, task,
        ledger.config['tasks'][operator]['baseline_source_hash'])
    directory = Path(binding['correctness_directory'])
    require(value.get('status') == 'passed' and value.get('correctness_stage_result') == binding['correctness_result']
            and value.get('correctness') == pointer(directory / 'completion.json'), 'baseline runtime binding differs')
    completion = checked(value['correctness'])
    require(completion.get('status') == 'passed' and sorted(int(r['case_id']) for r in completion['completed']) == campaign.ALL_CASES,
            'baseline prepared correctness coverage differs')
    native = [directory / f'case_{c:02d}/native.json' for c in campaign.ALL_CASES]
    standalone = directory.parent / 'standalone/completion.json'
    require(value.get('native_results') == [pointer(p) for p in [*native, standalone]], 'baseline native coverage differs')
    for path in native:
        row = load(path)
        require(row.get('exit_code') == 0 and all(row.get(k) is True for k in
            ('stream_destroyed', 'context_destroyed', 'finalized')), 'baseline native teardown failed')
    original = load(standalone)
    require(original.get('status') == 'passed' and original.get('passed_count') == 20, 'baseline standalone coverage differs')


def baseline_evidence(request, entry, *, allow_later=False, observation_id=None):
    ledger, task = check_entry(entry, allow_later=allow_later); state = ledger.state['tasks'][entry['operator']]
    refs = []
    for kind, group in [('correctness', 'correctness'), ('runtime', 'runtime'), ('control', GROUP)]:
        sid = 'baseline-' + group; row = state['stages'][sid]
        result, ref = finalizer.recorded_stage(request['run'], entry['operator'], 'baseline', sid, row)
        require(result['status'] == 'passed', 'baseline stage did not pass')
        refs.append(ref)
    baseline_runtime(ledger, entry['operator'], task, state['stages']['baseline-runtime'])
    directory = task / 'stages' / GROUP / 'cohort'
    plan = load(directory / 'plan.json')
    require(plan == state['stages']['baseline-' + GROUP]['plan']['cohort']
            and plan['case_ids'] == campaign.ALL_CASES and plan['comparison_kind'] == 'aa',
            'baseline A/A frozen coverage differs')
    iteration.check_control_settings(plan, SETTINGS)
    completion = load(directory / 'group-completion.json')
    directories = [str(directory / row['name']) for row in plan['schedule']]
    require(completion.get('status') == 'passed' and completion.get('error') is None
            and completion.get('completed_sessions') == directories, 'baseline A/A incomplete')
    actual = report.analyze_task_cohort(directories, plan)
    report.compare_saved_report(load(directory / 'report.json'), actual, evidence_path=directory / 'report.json')
    require(actual['evidence_status'] == 'verified_complete', 'baseline A/A evidence incomplete')
    return {'status': 'baseline_validated_and_calibrated', 'stages': refs,
            'calibration': pointer(directory / 'report.json')}


def candidate_evidence(request, entry, *, allow_later=False, observation_id=None):
    ledger, task = check_entry(entry, allow_later=allow_later, require_registered=True); state = ledger.state['tasks'][entry['operator']]
    cid = entry['candidate_id']; item = state['candidates'][cid]
    require((allow_later or state['new_source_attempts'] == state['new_rounds_started'] == 1)
            and (item['feedback_closed'] or (allow_later and state.get('frozen') is True))
            and item['observation_ids'], 'R1 has no closed real source feedback')
    observation_id = observation_id or item['observation_ids'][-1]
    require(observation_id in item['observation_ids'], 'completed R1 observation identity differs')
    observation = state['observations'][observation_id]
    require(observation.get('close_feedback') is True
            and not observation.get('quality', {}).get('infrastructure_blocked'), 'R1 infrastructure block')
    ref = iteration.feedback_pointer(task, cid, observation); feedback = checked(ref)
    require(feedback.get('source_hash') == item['source_hash']
            and feedback.get('source_parent') == item['source_parent']
            and not feedback.get('measurement_error'), 'R1 feedback lineage/measurement block')
    parent = task / 'candidates' / cid; results = []
    source_stages = {sid: row for sid, row in state['stages'].items() if row['candidate_id'] == cid
                     and not (row['kind'] == 'timing' and row.get('plan', {}).get('purpose') == 'final')}
    require(source_stages and set(observation['stage_attempts']) == set(source_stages), 'R1 feedback omits stages')
    for row in feedback['stages']:
        sid = row['stage_id']; recorded = source_stages[sid]
        require(observation['stage_attempts'][sid] == len(recorded['attempts']), 'R1 stage attempts differ')
        value, result_ref = finalizer.recorded_stage(request['run'], entry['operator'], cid, sid, recorded)
        require(result_ref == row['result'] and all(row.get(k) == value.get(k) for k in ('kind', 'status', 'error')),
                'R1 feedback stage differs')
        results.append(value)
    require({row['stage_id'] for row in results} == set(source_stages), 'R1 feedback result coverage differs')
    guard = None
    if feedback.get('semantic_guards') is not None:
        require(feedback['semantic_guards'] == pointer(parent / 'boundary-validation/completion.json'), 'guard identity differs')
        guard = iteration.boundary_result(task, parent, entry['operator'], cid)
        verify_pointer_tree(guard, evidence_path=feedback['semantic_guards']['path'])
    if feedback['status'] == 'source_attempt_failed':
        failed = next((value for value in results if value['status'] != 'passed'), None)
        classification = classify_failure(task, parent, stage=failed, guard=guard)
        require(classification['status'] == 'source_attempt_failed'
                and classification == feedback.get('failure_classification'), 'source failure lacks unchanged positive evidence')
        verify_pointer_tree(classification, evidence_path=ref['path'])
    else:
        require(feedback['status'] == 'measured' and guard is not None and guard['status'] == 'passed'
                and not guard.get('error') and not guard.get('verification_error')
                and guard.get('cases') and all(r.get('expected_process_passed') is True
                    and r.get('dispatch_log_passed') is True for r in guard['cases'])
                and all(value['status'] == 'passed' for value in results), 'R1 measured status lacks successful checks')
        finalizer.runtime_evidence(ledger, entry['operator'], cid, parent, source_stages[cid + '-runtime'])
        plan = load(parent / 'plans/search/stage-plan.json')
        iteration.check_timing_settings(plan, {**SETTINGS, 'calibration_path': task / 'stages' / GROUP / 'cohort/report.json'})
        comparisons = iteration.comparison_reports(task, parent, entry['operator'], item,
            ledger.config['tasks'][entry['operator']]['baseline_source_hash'], required=True)
        require(comparisons == feedback.get('comparisons'), 'R1 feedback differs from actual search reports')
    return {'status': feedback['status'], 'feedback': ref, 'source_rounds': 1,
            'classification': feedback.get('failure_classification'), 'observation_id': observation_id}


def request_state(queue):
    state = load(queue / 'state.json'); request = checked(state['request'])
    require(request['version'] == state['version'] == VERSION and request['settings'] == SETTINGS
            and request['calibration_group'] == GROUP and request['deduplicate_outputs'] is True,
            'queue protocol identity differs')
    schedule = checked(request['schedule']); engineering = checked(request['engineering'])
    expected_order = schedule['scheduling']['after_current_recommended_new_operator_order']
    require([e['operator'] for e in request['entries']] == expected_order
            and len(expected_order) == len(set(expected_order)) == 15
            and set(expected_order) == set(iteration.OPERATORS) - {'maximum'}, 'queue order/scope changed')
    expected_names = FRESH_PRODUCERS | {'level2_r1_queue.py', 'run_msprof_exploration_stage.py', 'prepare_trace_pilot.py'}
    require({Path(r['path']).name for r in request['producers']} == expected_names
            and len(request['producers']) == len(expected_names), 'queue producer closure differs')
    frozen_files = {r['path']: r for r in engineering['files']}
    require(all(ref['path'] == str(ROOT / 'scripts' / Path(ref['path']).name)
                and frozen_files.get(ref['path'], {}).get('sha256') == ref['sha256']
                and sha(frozen_files[ref['path']]['snapshot']) == ref['sha256']
                for ref in request['producers']), 'queue producer engineering binding differs')
    require(request['python'] == str(Path(sys.executable).resolve()), 'queue Python interpreter differs')
    require(canonical_path(request['run']) == queue.parents[1] and queue.parent.name == 'preflight', 'queue run location differs')
    scheduled_rows = {row['operator']: row for row in schedule['operators']}
    for entry in request['entries']:
        row = scheduled_rows[entry['operator']]
        require(entry['candidate_id'] == row['r1_candidate']
                and entry['task'] == str(Path(request['run']) / row['split'] / 'tasks' / entry['operator'])
                and entry['bindings']['proposal'] == row['input_bindings']['proposal']
                and entry['bindings']['measurement_policy'] == row['input_bindings']['policy'], 'queue entry differs from frozen schedule')
    for ref in request['producers']:
        require(pointer(canonical_path(ref['path'])) == ref, 'queue producer changed')
    return state, request


def execute(queue, *, max_new_operators=None):
    require(max_new_operators is None or (type(max_new_operators) is int and max_new_operators > 0),
            'max_new_operators must be a positive integer')
    queue = canonical_path(queue)
    with (queue / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state, request = request_state(queue)
        require(state['status'] != 'blocked', 'queue blocked; explicit evidence recovery required')
        new_completed = 0
        state.pop('stop', None)
        for index, entry in enumerate(request['entries']):
            op = entry['operator']; checkpoint = queue / op / 'checkpoint.json'
            phase = None
            try:
                allow_later = (queue / op / 'candidate/finished.json').is_file()
                require(not allow_later or (queue / op / 'baseline/finished.json').is_file(), 'completed R1 lacks baseline receipt')
                check_entry(entry, allow_later=allow_later)
                for phase, auditor in [('baseline', baseline_evidence), ('candidate', candidate_evidence)]:
                    directory = queue / op / phase
                    finished = directory / 'finished.json'
                    command = argv(request, entry, phase)
                    for ref in request['producers']:
                        require(pointer(ref['path']) == ref, 'queue producer changed')
                    if finished.exists():
                        receipt = load(finished)
                        require(receipt['request'] == pointer(queue / 'request.json')
                                and receipt['execution']['argv'] == command
                                and receipt['logs'] == [pointer(directory / name) for name in ('stdout.log', 'stderr.log')]
                                and receipt['execution'] == load(directory / 'execution.json')
                                and load(directory / 'started.json')['argv'] == command
                                and (receipt['execution']['returncode'] == (1 if receipt['audit']['status'] == 'source_attempt_failed' else 0)
                                     or 'recovery' in receipt),
                                'completed queue command identity differs')
                        if 'recovery' in receipt:
                            validate_recovery_receipt(receipt, directory)
                        require(auditor(request, entry, allow_later=allow_later,
                            observation_id=receipt['audit'].get('observation_id')) == receipt['audit'], 'completed queue evidence changed')
                    else:
                        require(not directory.exists(), 'interrupted child requires explicit recovery; command will not be rerun')
                        directory.mkdir(parents=True)
                        atomic(directory / 'started.json', {'request': pointer(queue / 'request.json'),
                            'argv': command, 'started_at': time.time()}, exclusive=True)
                        atomic(checkpoint, {'operator': op, 'phase': phase, 'status': 'running',
                            'started': pointer(directory / 'started.json')})
                        print(json.dumps({'operator': op, 'phase': phase, 'status': 'running'}), flush=True)
                        execution = run_command(command, directory, lock.fileno())
                        atomic(directory / 'execution.json', execution, exclusive=True)
                        audit = auditor(request, entry)
                        expected_code = 1 if audit['status'] == 'source_attempt_failed' else 0
                        require(execution['returncode'] == expected_code, 'child exit does not match verified outcome')
                        receipt = {'request': pointer(queue / 'request.json'), 'execution': execution, 'audit': audit,
                            'logs': [pointer(directory / name) for name in ('stdout.log', 'stderr.log')]}
                        atomic(finished, receipt, exclusive=True)
                    atomic(checkpoint, {'operator': op, 'phase': phase, 'status': receipt['audit']['status'],
                        'finished': pointer(finished)})
                state['operators'][op] = {'status': receipt['audit']['status'], 'checkpoint': pointer(checkpoint)}
                state['status'] = 'running'; atomic(queue / 'state.json', state)
                print(json.dumps({'operator': op, 'status': receipt['audit']['status']}), flush=True)
                if not allow_later:
                    new_completed += 1
                if (max_new_operators is not None and new_completed >= max_new_operators
                        and index + 1 < len(request['entries'])):
                    # Scheduling yield only after the complete operator receipt
                    # and checkpoint are durable. No ledger/protocol/request edit;
                    # the next invocation reaudits all earlier finished receipts.
                    state['status'] = 'operator_limit_reached'
                    state['stop'] = {'max_new_operators': max_new_operators,
                        'new_operators_completed': new_completed, 'after_operator': op,
                        'checkpoint': pointer(checkpoint)}
                    atomic(queue / 'state.json', state)
                    return {'status': state['status'], **state['stop'], 'scope': 'R1 only'}
            except Exception as exc:
                error = {'type': type(exc).__name__, 'message': str(exc)}
                history = queue / op
                count = len(list(history.glob('blocked*.json')))
                blocked_path = history / ('blocked.json' if count == 0 else f'blocked-{count+1:02d}.json')
                directory = history / phase if phase is not None else None
                evidence = {name: pointer(directory / name) for name in
                    ('started.json', 'execution.json', 'stdout.log', 'stderr.log')
                    if directory is not None and (directory / name).is_file()}
                atomic(blocked_path, {'request': pointer(queue / 'request.json'), 'operator': op,
                    'phase': phase, 'error': error, 'evidence': evidence, 'at': time.time()}, exclusive=True)
                state['status'] = 'blocked'; state['operators'][op] = {'status': 'infrastructure_blocked',
                    'error': error, 'blocked': pointer(blocked_path)}
                atomic(queue / 'state.json', state)
                return {'status': 'blocked', 'operator': op, 'error': error}
        state['status'] = 'completed'; atomic(queue / 'state.json', state)
        return {'status': 'completed', 'operators': state['operators'], 'scope': 'R1 only'}


def validate_recovery_receipt(receipt, directory):
    proof = checked(receipt['recovery'])
    blocked = checked(proof['blocked'])
    require(proof.get('no_child_executed') is True and proof.get('audit') == receipt['audit']
            and proof.get('request') == receipt['request'] and blocked.get('request') == receipt['request']
            and proof.get('execution') == pointer(directory / 'execution.json'), 'recovery receipt differs')
    require(set(blocked['evidence']) == {'started.json', 'execution.json', 'stdout.log', 'stderr.log'}
            and all(ref == pointer(directory / name) for name, ref in blocked['evidence'].items()),
            'blocked child evidence changed after recovery')


def recover(queue, operator, reason):
    """Explicit read-only reconciliation; never launches or recharges a child."""
    queue = canonical_path(queue)
    require(isinstance(reason, str) and reason.strip(), 'explicit recovery reason required')
    with (queue / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state, request = request_state(queue)
        require(state['status'] == 'blocked' and operator in state['operators']
                and state['operators'][operator].get('status') == 'infrastructure_blocked', 'operator is not the current queue block')
        blocked_ref = state['operators'][operator]['blocked']; blocked = checked(blocked_ref)
        phase = blocked.get('phase')
        require(phase in ('baseline', 'candidate') and blocked['operator'] == operator
                and blocked['request'] == pointer(queue / 'request.json'), 'blocked phase identity differs')
        entry = next(row for row in request['entries'] if row['operator'] == operator)
        check_entry(entry)
        directory = queue / operator / phase
        require(set(blocked['evidence']) == {'started.json', 'execution.json', 'stdout.log', 'stderr.log'}
                and all(ref == pointer(directory / name) for name, ref in blocked['evidence'].items()),
                'complete unchanged child exit/log evidence required; no native retry allowed')
        execution = load(directory / 'execution.json'); started = load(directory / 'started.json')
        require(execution['argv'] == started['argv'] == argv(request, entry, phase)
                and started['request'] == pointer(queue / 'request.json')
                and type(execution['returncode']) is int and execution['started_at'] <= execution['ended_at'],
                'executed child identity differs')
        auditor = baseline_evidence if phase == 'baseline' else candidate_evidence
        proof_path = queue / operator / ('recovery-' + Path(blocked_ref['path']).stem + '.json')
        existing = load(proof_path) if proof_path.exists() else None
        audit = auditor(request, entry, observation_id=existing['audit'].get('observation_id') if existing else None)
        require(audit['status'] in ('baseline_validated_and_calibrated', 'measured', 'source_attempt_failed'),
                'phase still needs explicit infrastructure/stage repair')
        core = {'request': pointer(queue / 'request.json'), 'blocked': blocked_ref, 'audit': audit,
                'execution': pointer(directory / 'execution.json'), 'no_child_executed': True}
        if existing is not None:
            require(all(existing.get(k) == v for k, v in core.items()), 'recovery proof changed')
        else:
            atomic(proof_path, {**core, 'reason': reason, 'at': time.time()}, exclusive=True)
        receipt = {'request': pointer(queue / 'request.json'), 'execution': execution, 'audit': audit,
            'logs': [pointer(directory / name) for name in ('stdout.log', 'stderr.log')], 'recovery': pointer(proof_path)}
        validate_recovery_receipt(receipt, directory)
        finished = directory / 'finished.json'
        if finished.exists():
            require(load(finished) == receipt, 'existing finished receipt differs')
        else:
            atomic(finished, receipt, exclusive=True)
        checkpoint = queue / operator / 'checkpoint.json'
        atomic(checkpoint, {'operator': operator, 'phase': phase, 'status': audit['status'], 'finished': pointer(finished)})
        state['operators'][operator] = {'status': 'reconciled', 'checkpoint': pointer(checkpoint), 'recovery': pointer(proof_path)}
        state['status'] = 'ready_after_recovery'; atomic(queue / 'state.json', state)
        return {'status': 'reconciled', 'operator': operator, 'phase': phase, 'recovery': pointer(proof_path), 'no_child_executed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare')
    for name in ('run', 'schedule', 'engineering', 'output'):
        create.add_argument('--' + name, type=Path, required=True)
    start = commands.add_parser('run'); start.add_argument('--queue', type=Path, required=True)
    start.add_argument('--max-new-operators', type=int,
        help='Stop successfully after N newly completed operator checkpoints; completed receipts are reaudited and do not count.')
    reconcile = commands.add_parser('recover')
    reconcile.add_argument('--queue', type=Path, required=True)
    reconcile.add_argument('--operator', required=True, choices=iteration.OPERATORS)
    reconcile.add_argument('--reason', required=True)
    args = parser.parse_args()
    result = (prepare(args.run, args.schedule, args.engineering, args.output)
              if args.command == 'prepare' else recover(args.queue, args.operator, args.reason)
              if args.command == 'recover' else execute(args.queue, max_new_operators=args.max_new_operators))
    print(json.dumps(result), flush=True)
    return 0 if result['status'] in ('prepared', 'completed', 'reconciled', 'operator_limit_reached') else 1


if __name__ == '__main__':
    raise SystemExit(main())
