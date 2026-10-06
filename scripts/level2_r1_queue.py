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
CONTINUATION_VERSION = 'level2_r1_serial_queue_suffix_v1'
HANDOFF_VERSION = 'level2_r1_serial_queue_handoff_v1'
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


# The pre-candidate-guard roster is an explicit historical protocol, never an
# arbitrary subset of today's producers. Only these reviewed frozen queue and
# provenance producer bytes define that roster. New/live queue admission always
# requires the complete current set.
LEGACY_PRODUCER_NAMES = frozenset({
    'cannbench_msprof_timing.py', 'cannbench_shared_context.py',
    'cannbench_shared_context_profile.py', 'level2_adapters.py',
    'level2_boundaries.py', 'level2_campaign.py',
    'level2_failure_classification.py', 'level2_finalize.py',
    'level2_iteration.py', 'level2_pilot.py', 'level2_r1_queue.py',
    'level2_raw_method.py', 'level2_storage.py', 'msprof_exploration_archive.py',
    'msprof_exploration_campaign.py', 'msprof_exploration_execute.py',
    'msprof_exploration_oracle.py', 'msprof_exploration_provenance.py',
    'msprof_exploration_report.py', 'msprof_exploration_safety.py',
    'msprof_exploration_standalone.py', 'msprof_raw_storage.py',
    'prepare_trace_pilot.py', 'run_msprof_exploration_stage.py',
    'shared_context_build.py',
})
LEGACY_QUEUE_ROSTERS = {
    # Last original full queue and first immutable suffix continuation.
    'sha256:f02258c805442d2752b43f0eb9758d684f368b077d22fac0142f0dca411f11f1': VERSION,
    'sha256:181913d7615a783036d0e304eddc76e2b9c5b45c68b0391e0746064ac6476562': CONTINUATION_VERSION,
}
LEGACY_PROVENANCE_HASH = 'sha256:4fce29e17c97a815fbc49fbefd3e184bc86392a91d427d637a2cb9efb35fdfdc'


def producer_names(request, *, live_producers):
    current = FRESH_PRODUCERS | {'level2_r1_queue.py', 'run_msprof_exploration_stage.py', 'prepare_trace_pilot.py'}
    refs = request['producers']
    names = {Path(ref['path']).name for ref in refs}
    require(len(refs) == len(names), 'duplicate queue producer identity')
    if names == current:
        return current
    require(not live_producers and names == LEGACY_PRODUCER_NAMES,
            'queue producer closure differs')
    identities = {Path(ref['path']).name: ref['sha256'] for ref in refs}
    require(LEGACY_QUEUE_ROSTERS.get(identities['level2_r1_queue.py']) == request['version']
            and identities['msprof_exploration_provenance.py'] == LEGACY_PROVENANCE_HASH,
            'unreviewed historical queue producer roster')
    # request_identity below verifies every complete legacy identity against the
    # immutable engineering manifest and its actual source-CAS bytes.
    return LEGACY_PRODUCER_NAMES


def request_identity(queue, state, request, *, live_producers=True):
    require(request['version'] == state['version']
            and request['version'] in (VERSION, CONTINUATION_VERSION, HANDOFF_VERSION) and request['settings'] == SETTINGS
            and request['calibration_group'] == GROUP and request['deduplicate_outputs'] is True,
            'queue protocol identity differs')
    schedule = checked(request['schedule']); engineering = checked(request['engineering'])
    expected_order = schedule['scheduling']['after_current_recommended_new_operator_order']
    full_order = expected_order
    if request['version'] == CONTINUATION_VERSION:
        require('handoff' not in request, 'legacy continuation cannot declare handoff')
        require(full_order[:3] == ['apply_adam_w', 'group_norm', 'rms_norm'], 'unsupported continuation prefix')
        expected_order = full_order[2:]
    elif request['version'] == HANDOFF_VERSION:
        inheritance = request.get('handoff')
        require(isinstance(inheritance, dict) and 'continuation' not in request, 'handoff proof missing or ambiguous')
        prefix = inheritance.get('completed_prefix')
        require(isinstance(prefix, list) and 3 <= len(prefix) < len(full_order)
                and prefix == full_order[:len(prefix)], 'handoff completed prefix differs')
        expected_order = full_order[len(prefix):]
    else:
        require('continuation' not in request and 'handoff' not in request, 'legacy queue cannot declare continuation')
    require([e['operator'] for e in request['entries']] == expected_order
            and len(full_order) == len(set(full_order)) == 15
            and set(full_order) == set(iteration.OPERATORS) - {'maximum'}, 'queue order/scope changed')
    expected_names = producer_names(request, live_producers=live_producers)
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
    if live_producers:
        for ref in request['producers']:
            require(pointer(canonical_path(ref['path'])) == ref, 'queue producer changed')


def request_state(queue):
    state = load(queue / 'state.json'); request = checked(state['request'])
    require(state['request'] == pointer(queue / 'request.json'), 'queue request location differs')
    request_identity(queue, state, request)
    inherited_request_evidence(queue, request)
    return state, request


def inherited_request_evidence(queue, request):
    """Replay a frozen ancestor chain without requiring its old producers live."""
    if request['version'] == CONTINUATION_VERSION:
        inheritance = request.get('continuation')
        require(isinstance(inheritance, dict), 'continuation proof missing')
        previous = canonical_path(inheritance['previous_queue'])
        require(queue == previous.with_name('r1-queue-02'), 'continuation queue location differs')
        with (previous / 'queue.lock').open('rb') as historical_lock:
            fcntl.flock(historical_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            require(continuation_evidence(previous, inheritance['observation_id']) == inheritance,
                    'inherited queue evidence changed')
        require(request['schedule'] == inheritance['schedule']
                and request['entries'] == inheritance['remaining_entries'], 'continuation suffix differs')
    elif request['version'] == HANDOFF_VERSION:
        inheritance = request.get('handoff')
        require(isinstance(inheritance, dict), 'handoff proof missing')
        previous = canonical_path(inheritance['previous_queue'])
        require(queue == previous.with_name('r1-queue-%02d' % (queue_number(previous) + 1)),
                'handoff queue location differs')
        with (previous / 'queue.lock').open('rb') as historical_lock:
            fcntl.flock(historical_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            require(handoff_evidence(previous, inheritance['observation_id']) == inheritance,
                    'inherited handoff evidence changed')
        require(request['schedule'] == inheritance['schedule']
                and request['entries'] == inheritance['remaining_entries'], 'handoff suffix differs')


def inherited_child(previous, request, entry, phase, *, finished):
    """Bind historical exit/logs without rewriting or rerunning the old child."""
    directory = previous / entry['operator'] / phase
    names = ('started.json', 'execution.json', 'stdout.log', 'stderr.log')
    refs = {name: pointer(canonical_path(directory / name)) for name in names}
    started, execution = (checked(refs[name]) for name in names[:2])
    require(started.get('request') == pointer(previous / 'request.json')
            and started.get('argv') == execution.get('argv') == argv(request, entry, phase)
            and type(execution.get('returncode')) is int
            and isinstance(execution.get('started_at'), (int, float))
            and isinstance(execution.get('ended_at'), (int, float))
            and execution['started_at'] <= execution['ended_at'], 'historical child identity/exit differs')
    if finished:
        ref = pointer(directory / 'finished.json'); receipt = checked(ref)
        require(receipt.get('request') == pointer(previous / 'request.json')
                and receipt.get('execution') == execution
                and receipt.get('logs') == [refs[name] for name in names[2:]], 'historical finished receipt differs')
        if 'recovery' in receipt:
            validate_recovery_receipt(receipt, directory)
        else:
            require(execution['returncode'] == (1 if receipt['audit']['status'] == 'source_attempt_failed' else 0),
                    'historical finished exit contradicts audit')
        auditor = baseline_evidence if phase == 'baseline' else candidate_evidence
        audit = auditor(request, entry, allow_later=True,
                        observation_id=receipt['audit'].get('observation_id'))
        require(audit == receipt['audit'], 'historical finished evidence changed')
        refs['finished.json'] = ref
    else:
        require(not (directory / 'finished.json').exists() and execution['returncode'] == 1,
                'blocked historical candidate must have a completed unsuccessful child')
    return refs


def recovered_guard_evidence(previous, request, entry, observation_id, child):
    """Only a closed append-only reclassification of this exact old block qualifies."""
    audit = candidate_evidence(request, entry, allow_later=True, observation_id=observation_id)
    require(audit['status'] == 'source_attempt_failed' and audit.get('observation_id') == observation_id,
            'continuation requires a closed positively classified GN R1')
    feedback = checked(audit['feedback']); recovery = feedback.get('reclassification', {})
    old_ref = recovery.get('previous_feedback'); old = checked(old_ref)
    parent = canonical_path(entry['task']) / 'candidates' / entry['candidate_id']
    require(old_ref['path'] == str(parent.parent.parent / 'feedback' / (entry['candidate_id'] + '.json'))
            and old.get('status') == 'infrastructure_blocked'
            and old.get('source_hash') == feedback.get('source_hash')
            and old.get('source_parent') == feedback.get('source_parent')
            and old.get('stages') == feedback.get('stages')
            and old.get('semantic_guards') == feedback.get('semantic_guards')
            and not old.get('measurement_error')
            and recovery.get('native_reexecuted') is False and recovery.get('source_attempt_added') is False,
            'GN reclassification does not preserve the exact original blocked evidence')
    verify_pointer_tree(feedback, evidence_path=audit['feedback']['path'])
    historical_summary = json.loads(Path(child['stdout.log']['path']).read_text().splitlines()[-1])
    require(historical_summary == {'operator':entry['operator'], 'candidate_id':entry['candidate_id'],
                'status':'infrastructure_blocked', 'observation_id':recovery.get('previous_observation_id'),
                'feedback':old_ref}, 'historical child stdout does not bind recovered blocked feedback')
    request_ref = recovery.get('request'); recorded = checked(request_ref)
    require(request_ref['path'] == str(parent / 'feedback-recovery' / recovery['recovery_id'] / 'request.json')
            and recorded.get('operator') == entry['operator'] and recorded.get('candidate_id') == entry['candidate_id']
            and recorded.get('new_observation_id') == observation_id
            and recorded.get('blocked_observation_id') == recovery['previous_observation_id']
            and recorded.get('previous_feedback') == old_ref
            and recorded.get('classification') == audit['classification']
            and recorded.get('native_rerun') is False and recorded.get('source_attempt_added') is False,
            'GN recovery request identity differs')
    ledger, _ = ledger_for(entry); state = ledger.state['tasks'][entry['operator']]
    old_observation = state['observations'].get(recovery['previous_observation_id'], {})
    require(old_observation.get('candidate_id') == entry['candidate_id']
            and old_observation.get('close_feedback') is False
            and old_observation.get('quality', {}).get('infrastructure_blocked') is True
            and old_observation.get('feedback') == old and old_observation.get('report_ref') == old_ref['sha256'],
            'old blocked observation is absent or changed')
    return {'audit':audit, 'previous_feedback':old_ref, 'recovery_request':request_ref}


def continuation_evidence(previous, observation_id):
    """Pure audit of exactly queue-01's completed Adam and recovered GN prefix."""
    previous = canonical_path(previous)
    require(previous.name == 'r1-queue-01' and previous.parent.name == 'preflight', 'unsupported predecessor queue')
    state_ref, request_ref = pointer(previous / 'state.json'), pointer(previous / 'request.json')
    state, request = checked(state_ref), checked(request_ref)
    require(state.get('request') == request_ref and request.get('version') == VERSION,
            'predecessor must be the original complete-schedule v2 queue')
    request_identity(previous, state, request, live_producers=False)
    require([e['operator'] for e in request['entries'][:3]] == ['apply_adam_w', 'group_norm', 'rms_norm'],
            'unsupported predecessor ordering')
    entries = request['entries']; adam, gn = entries[:2]
    require(state.get('status') == 'blocked'
            and set(state['operators']) == {e['operator'] for e in entries}
            and state['operators']['group_norm'].get('status') == 'infrastructure_blocked', 'predecessor is not the GN block')
    for entry in entries[2:]:
        require(state['operators'][entry['operator']] == {'status':'pending'}
                and not (previous / entry['operator']).exists(), 'predecessor suffix already has queue work')
    blocked_ref = state['operators']['group_norm'].get('blocked'); blocked = checked(blocked_ref)
    require(blocked_ref['path'] == str(previous / 'group_norm/blocked.json')
            and blocked.get('request') == request_ref and blocked.get('operator') == 'group_norm'
            and blocked.get('phase') == 'candidate', 'predecessor blocked evidence differs')
    receipts = {}
    for entry, phase in ((adam,'baseline'), (adam,'candidate'), (gn,'baseline')):
        receipts[entry['operator'] + '/' + phase] = inherited_child(previous, request, entry, phase, finished=True)
    adam_checkpoint_ref = state['operators']['apply_adam_w'].get('checkpoint')
    adam_checkpoint = checked(adam_checkpoint_ref)
    require(adam_checkpoint_ref['path'] == str(previous / 'apply_adam_w/checkpoint.json')
            and adam_checkpoint.get('finished') == receipts['apply_adam_w/candidate']['finished.json']
            and adam_checkpoint.get('phase') == 'candidate'
            and adam_checkpoint.get('status') == state['operators']['apply_adam_w'].get('status'),
            'completed Adam checkpoint differs')
    child = inherited_child(previous, request, gn, 'candidate', finished=False)
    require(blocked.get('evidence') == child, 'GN block does not bind unchanged exited child')
    gn_checkpoint_ref = pointer(previous / 'group_norm/checkpoint.json'); gn_checkpoint = checked(gn_checkpoint_ref)
    require(gn_checkpoint == {'operator':'group_norm','phase':'candidate','status':'running','started':child['started.json']},
            'GN historical checkpoint differs')
    recovered = recovered_guard_evidence(previous, request, gn, observation_id, child)
    return {'version':'level2_queue_prefix_transfer_v1', 'previous_queue':str(previous),
            'previous_request':request_ref, 'previous_state':state_ref, 'previous_blocked':blocked_ref,
            'schedule':request['schedule'], 'checkpoints':[adam_checkpoint_ref, gn_checkpoint_ref],
            'completed_children':receipts, 'blocked_child':child, 'recovered_guard':recovered,
            'observation_id':observation_id, 'remaining_entries':entries[2:],
            'scope':'rms_norm and remaining12 R1 operators; historical queue retained unchanged',
            'native_reexecuted':False,'source_attempt_added':False}


def prepare_continuation(previous, engineering, output, observation_id):
    """Publish a new suffix request only after complete immutable-prefix review."""
    previous, engineering, output = map(canonical_path, (previous, engineering, output))
    require(previous.name == 'r1-queue-01' and output == previous.with_name('r1-queue-02'),
            'continuation is restricted to queue-01 -> queue-02')
    require(not output.exists(), 'fresh continuation directory required')
    with (previous / 'queue.lock').open('rb') as old_lock:
        # Exclusive read-only-fd flock serializes publishers and rejects a live
        # predecessor; no predecessor bytes are changed. Recheck after locking.
        fcntl.flock(old_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not output.exists(), 'fresh continuation directory required')
        inherited = continuation_evidence(previous, observation_id)
        old_request = checked(inherited['previous_request']); run = canonical_path(old_request['run'])
        frozen = load(engineering)
        require(engineering.parent == run / 'bootstrap' and engineering != Path(old_request['engineering']['path'])
                and frozen.get('version') == 'level2_frozen_engineering_v1', 'fresh engineering manifest required')
        identities = {row['path']:row for row in frozen['files']}
        names = sorted(FRESH_PRODUCERS | {'level2_r1_queue.py','run_msprof_exploration_stage.py','prepare_trace_pilot.py'})
        producers = []
        for name in names:
            path = ROOT / 'scripts' / name; identity = identities.get(str(path))
            require(identity is not None and sha(path) == identity['sha256']
                    and sha(canonical_path(identity['snapshot'])) == identity['sha256'], 'new engineering producer differs: '+name)
            producers.append(pointer(path))
        for entry in inherited['remaining_entries']:
            check_entry(entry)
        request = {'version':CONTINUATION_VERSION, 'run':str(run), 'schedule':inherited['schedule'],
            'engineering':pointer(engineering), 'producers':producers, 'python':str(Path(sys.executable).resolve()),
            'settings':SETTINGS, 'calibration_group':GROUP, 'deduplicate_outputs':True,
            'entries':inherited['remaining_entries'], 'continuation':inherited,
            'scope':'R1 suffix only; inherited prefix audited without replaying children; no R2/R3, native retries or budget reset'}
        require(continuation_evidence(previous, observation_id) == inherited, 'predecessor changed during continuation preparation')
        # Publish a complete directory in one rename. Failed writes leave no
        # official queue/request behind; the state pins the final request path.
        with tempfile.TemporaryDirectory(prefix='.r1-queue-02-staging-', dir=output.parent) as temporary:
            staging = Path(temporary)
            atomic(staging / 'request.json', request, exclusive=True)
            request_ref = {'path':str(output / 'request.json'), 'sha256':sha(staging / 'request.json')}
            atomic(staging / 'state.json', {'version':CONTINUATION_VERSION,'request':request_ref,
                'status':'prepared','operators':{entry['operator']:{'status':'pending'} for entry in request['entries']}})
            sync_dir(staging)
            require(not output.exists(), 'fresh continuation directory required')
            os.rename(staging, output)
            sync_dir(output.parent)
    return {'status':'prepared','queue':str(output),'operators':[e['operator'] for e in request['entries']],
            'inherited_prefix':['apply_adam_w','group_norm'], 'no_child_executed':True}


def queue_number(queue):
    """Monotonic names prevent cycles or substitution of unrelated queues."""
    suffix = queue.name.removeprefix('r1-queue-')
    require(queue.parent.name == 'preflight' and suffix.isascii() and suffix.isdigit()
            and 1 <= int(suffix) <= 15 and queue.name == 'r1-queue-%02d' % int(suffix),
            'unsupported numbered queue')
    return int(suffix)


def handoff_evidence(previous, observation_id):
    """Audit an exited candidate block and its complete inherited prefix.

    Callers hold the predecessor lock. Ancestors retain their original bytes,
    requests and engineering epochs; this function only replays their evidence.
    """
    previous = canonical_path(previous)
    require(queue_number(previous) >= 2, 'handoff requires a suffix predecessor')
    state_ref, request_ref = pointer(previous / 'state.json'), pointer(previous / 'request.json')
    state, request = checked(state_ref), checked(request_ref)
    require(state.get('request') == request_ref and request.get('version') in (CONTINUATION_VERSION, HANDOFF_VERSION),
            'handoff predecessor must be a bound suffix queue')
    request_identity(previous, state, request, live_producers=False)
    inherited_request_evidence(previous, request)
    entries = request['entries']; operators = state.get('operators', {})
    require(state.get('status') == 'blocked' and set(operators) == {e['operator'] for e in entries},
            'handoff predecessor is not blocked with its exact operator set')
    blocked_indices = [i for i, entry in enumerate(entries)
                       if operators[entry['operator']].get('status') == 'infrastructure_blocked']
    require(len(blocked_indices) == 1, 'handoff needs exactly one blocked operator')
    index = blocked_indices[0]; entry = entries[index]; op = entry['operator']
    remaining = entries[index + 1:]
    require(remaining, 'handoff has no remaining operators')
    for pending in remaining:
        require(operators[pending['operator']] == {'status':'pending'}
                and not (previous / pending['operator']).exists(), 'handoff suffix already has queue work')
    blocked_ref = operators[op].get('blocked'); blocked = checked(blocked_ref)
    require(blocked_ref['path'] == str(previous / op / 'blocked.json')
            and blocked.get('request') == request_ref and blocked.get('operator') == op
            and blocked.get('phase') == 'candidate', 'handoff block is not the original candidate exit')
    receipts, checkpoints = {}, []
    for completed in entries[:index]:
        name = completed['operator']
        require(operators[name].get('status') in ('measured', 'source_attempt_failed'), 'handoff prefix is unfinished')
        for phase in ('baseline', 'candidate'):
            receipts[name + '/' + phase] = inherited_child(previous, request, completed, phase, finished=True)
        checkpoint_ref = operators[name].get('checkpoint'); checkpoint = checked(checkpoint_ref)
        require(checkpoint_ref['path'] == str(previous / name / 'checkpoint.json')
                and checkpoint == {'operator':name, 'phase':'candidate', 'status':operators[name]['status'],
                                   'finished':receipts[name + '/candidate']['finished.json']},
                'handoff completed checkpoint differs')
        checkpoints.append(checkpoint_ref)
    receipts[op + '/baseline'] = inherited_child(previous, request, entry, 'baseline', finished=True)
    child = inherited_child(previous, request, entry, 'candidate', finished=False)
    require(blocked.get('evidence') == child, 'handoff block does not bind unchanged exited child')
    checkpoint_ref = pointer(previous / op / 'checkpoint.json'); checkpoint = checked(checkpoint_ref)
    require(checkpoint == {'operator':op,'phase':'candidate','status':'running','started':child['started.json']},
            'handoff blocked checkpoint differs')
    checkpoints.append(checkpoint_ref)
    recovered = recovered_guard_evidence(previous, request, entry, observation_id, child)
    full_order = checked(request['schedule'])['scheduling']['after_current_recommended_new_operator_order']
    prefix = full_order[:-len(remaining)]
    require([row['operator'] for row in remaining] == full_order[len(prefix):]
            and prefix[-1] == op, 'handoff would skip or reorder scheduled operators')
    return {'version':'level2_queue_prefix_handoff_v1', 'previous_queue':str(previous),
            'previous_request':request_ref, 'previous_state':state_ref, 'previous_blocked':blocked_ref,
            'previous_inheritance':request.get('handoff', request.get('continuation')),
            'schedule':request['schedule'], 'checkpoints':checkpoints, 'completed_children':receipts,
            'blocked_child':child, 'recovered_candidate':recovered, 'observation_id':observation_id,
            'completed_prefix':prefix, 'remaining_entries':remaining,
            'scope':'unchanged original R1 suffix; all prior queues retained and reaudited',
            'native_reexecuted':False, 'source_attempt_added':False}


def prepare_handoff(previous, engineering, output, observation_id):
    """Atomically publish a fresh producer epoch after explicit feedback recovery."""
    previous, engineering, output = map(canonical_path, (previous, engineering, output))
    require(output == previous.with_name('r1-queue-%02d' % (queue_number(previous) + 1))
            and queue_number(output) >= 3, 'handoff must advance exactly one numbered queue')
    require(not output.exists(), 'fresh handoff directory required')
    with (previous / 'queue.lock').open('rb') as old_lock:
        fcntl.flock(old_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not output.exists(), 'fresh handoff directory required')
        inherited = handoff_evidence(previous, observation_id)
        old_request = checked(inherited['previous_request']); run = canonical_path(old_request['run'])
        frozen = load(engineering)
        require(engineering.parent == run / 'bootstrap' and engineering != Path(old_request['engineering']['path'])
                and frozen.get('version') == 'level2_frozen_engineering_v1', 'fresh engineering manifest required')
        identities = {row['path']:row for row in frozen['files']}
        names = sorted(FRESH_PRODUCERS | {'level2_r1_queue.py','run_msprof_exploration_stage.py','prepare_trace_pilot.py'})
        producers = []
        for name in names:
            path = ROOT / 'scripts' / name; identity = identities.get(str(path))
            require(identity is not None and sha(path) == identity['sha256']
                    and sha(canonical_path(identity['snapshot'])) == identity['sha256'], 'new engineering producer differs: '+name)
            producers.append(pointer(path))
        for entry in inherited['remaining_entries']:
            check_entry(entry)
        request = {'version':HANDOFF_VERSION, 'run':str(run), 'schedule':inherited['schedule'],
            'engineering':pointer(engineering), 'producers':producers, 'python':str(Path(sys.executable).resolve()),
            'settings':SETTINGS, 'calibration_group':GROUP, 'deduplicate_outputs':True,
            'entries':inherited['remaining_entries'], 'handoff':inherited,
            'scope':'R1 suffix only; immutable ancestor chain; no authoring, retries, cost reset or new source attempt'}
        require(handoff_evidence(previous, observation_id) == inherited, 'predecessor changed during handoff preparation')
        with tempfile.TemporaryDirectory(prefix='.' + output.name + '-staging-', dir=output.parent) as temporary:
            staging = Path(temporary)
            atomic(staging / 'request.json', request, exclusive=True)
            request_ref = {'path':str(output / 'request.json'), 'sha256':sha(staging / 'request.json')}
            state = {'version':HANDOFF_VERSION, 'request':request_ref, 'status':'prepared',
                     'operators':{entry['operator']:{'status':'pending'} for entry in request['entries']}}
            request_identity(output, state, request)
            atomic(staging / 'state.json', state)
            sync_dir(staging)
            require(not output.exists(), 'fresh handoff directory required')
            os.rename(staging, output)
            sync_dir(output.parent)
    return {'status':'prepared','queue':str(output),'operators':[e['operator'] for e in request['entries']],
            'inherited_prefix':inherited['completed_prefix'], 'no_child_executed':True}


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
                    if request['version'] in (CONTINUATION_VERSION, HANDOFF_VERSION):
                        request_state(queue)
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
    continuation = commands.add_parser('prepare-continuation')
    for name in ('previous-queue', 'engineering', 'output'):
        continuation.add_argument('--' + name, type=Path, required=True)
    continuation.add_argument('--observation-id', required=True)
    handoff = commands.add_parser('prepare-handoff')
    for name in ('previous-queue', 'engineering', 'output'):
        handoff.add_argument('--' + name, type=Path, required=True)
    handoff.add_argument('--observation-id', required=True)
    start = commands.add_parser('run'); start.add_argument('--queue', type=Path, required=True)
    start.add_argument('--max-new-operators', type=int,
        help='Stop successfully after N newly completed operator checkpoints; completed receipts are reaudited and do not count.')
    reconcile = commands.add_parser('recover')
    reconcile.add_argument('--queue', type=Path, required=True)
    reconcile.add_argument('--operator', required=True, choices=iteration.OPERATORS)
    reconcile.add_argument('--reason', required=True)
    args = parser.parse_args()
    result = (prepare_handoff(args.previous_queue, args.engineering, args.output, args.observation_id)
              if args.command == 'prepare-handoff' else prepare_continuation(args.previous_queue, args.engineering, args.output, args.observation_id)
              if args.command == 'prepare-continuation' else prepare(args.run, args.schedule, args.engineering, args.output)
              if args.command == 'prepare' else recover(args.queue, args.operator, args.reason)
              if args.command == 'recover' else execute(args.queue, max_new_operators=args.max_new_operators))
    print(json.dumps(result), flush=True)
    return 0 if result['status'] in ('prepared', 'completed', 'reconciled', 'operator_limit_reached') else 1


if __name__ == '__main__':
    raise SystemExit(main())
