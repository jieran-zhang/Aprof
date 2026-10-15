#!/usr/bin/env python3
"""Read-only replay of the preregistered 72-cell timing-method diagnosis.

This is an entry check for a *new* production-method qualification, never a
performance admission. It reads actual worker/oracle/profiler evidence, checks
the finite protocol, and recomputes controls instead of trusting saved flags.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shlex
import statistics
import types

PREFIX = 'APROF_DIAG_JSON:'
ROLES = ('A', 'B')
FACTORS = ('row_logging', 'buffered')
MODES = ('shared', 'split', 'residency')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return 'sha256:' + result.hexdigest()


class Evidence:
    def __init__(self):
        self.files = {}

    def bind(self, path, expected=None):
        path = Path(path).resolve(strict=True)
        key = str(path)
        if key not in self.files:
            self.files[key] = {'path': key, 'sha256': digest(path), 'bytes': path.stat().st_size}
        value = self.files[key]
        require(expected is None or value['sha256'] == expected, 'changed evidence: ' + key)
        return dict(value)

    def json(self, path):
        self.bind(path)
        return read(path)


def stdout_messages(path, evidence):
    evidence.bind(path)
    return [json.loads(line[len(PREFIX):]) for line in Path(path).read_text().splitlines()
            if line.startswith(PREFIX)]


def verify_completed(message, ready, previous_end):
    require(set(message) == {'type', 'operator', 'pid', 'device', 'context', 'stream', 'monotonic_ns', 'unix_ns', 'cpu'}
            and message['type'] == 'completed', 'missing native completion ACK')
    require(all(message[key] == ready[key] for key in ('operator', 'pid', 'device', 'context', 'stream'))
            and message['monotonic_ns'] >= previous_end and message['cpu'] in ready['affinity'],
            'native completion identity or chronology differs')


def finite_positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def verify_sample(receipt, ready, kind, slot, sequence, previous_end):
    sample = receipt['sample']
    require(sample['type'] == kind and sample['slot'] == slot and sample['sequence'] == sequence,
            'command type, physical slot or sequence changed')
    for key in ('pid', 'context', 'stream', 'device', 'operator', 'repeat'):
        require(sample[key] == ready[key], 'worker identity changed: ' + key)
    require(sample['repeat'] == 100, 'repeat changed')
    clocks = [previous_end, receipt['request_monotonic_ns'], sample['started_monotonic_ns']]
    if kind == 'sample':
        clocks += [sample['enqueue_begin_monotonic_ns'], sample['enqueue_end_monotonic_ns'],
                   sample['synchronized_monotonic_ns']]
        require(finite_positive(sample['event_ns_per_operator']), 'invalid ACL event duration')
        require(sample['cpu_before'] in ready['affinity'] and sample['cpu_after'] in ready['affinity'],
                'sample CPU outside frozen affinity')
    clocks += [sample['monotonic_ns'], receipt['response_monotonic_ns']]
    require(all(isinstance(x, int) and x > 0 for x in clocks) and clocks == sorted(clocks),
            'invalid command chronology')
    require(sample['cpu'] in ready['affinity'], 'ACK CPU outside frozen affinity')
    return receipt['response_monotonic_ns']


def verify_oracle(directory, metadata, info, plan, evidence, *, timeline=False, earliest=0, latest=math.inf):
    metadata_path = directory / ('metadata.json' if timeline else 'metadata.json')
    execution_path = directory / ('verify.execution.json' if timeline else 'execution.json')
    stdout_path = directory / ('verify.stdout.log' if timeline else 'stdout.log')
    actual = evidence.json(metadata_path)
    require(actual == metadata, 'oracle metadata differs from frozen input and actual output')
    execution = evidence.json(execution_path)
    expected_argv = [plan['host_tools']['python']['path'], str(Path(info['source_dir']) / 'scripts/verify_result.py'),
                     '--metadata', str(metadata_path)]
    # sys.executable can retain its non-resolved spelling; require same frozen bytes.
    require(execution['argv'][1:] == expected_argv[1:], 'oracle argv changed')
    evidence.bind(execution['argv'][0], plan['host_tools']['python']['sha256'])
    require(execution['exit_status'] == 0 and earliest <= execution['started_at'] <= execution['finished_at'] <= latest,
            'oracle execution failed or lies outside the recorded execution')
    output_ref = evidence.bind(metadata['output'], execution['output_hash'])
    require(output_ref['bytes'] == metadata['numel'] * (4 if metadata['dtype'] == 'float32' else 2),
            'oracle output length differs')
    evidence.bind(stdout_path)
    values = []
    for line in stdout_path.read_text().splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and 'case_id' in value:
            values.append(value)
    result = evidence.json(directory / 'result.json')
    require(values == [result], 'native result differs from the actual verifier stdout')
    for key in ('case_id', 'shape', 'dtype', 'numel'):
        require(result[key] == metadata[key], 'native result workload mismatch')
    attrs = {key: metadata[key] for key in ('base', 'scale', 'shift')} if 'base' in metadata else {}
    require(result['attrs'] == attrs, 'native oracle attributes differ')
    threshold = {'float16': 2 ** -10, 'bfloat16': 2 ** -7, 'float32': 2 ** -13}[metadata['dtype']]
    require(result['threshold'] == threshold and result['special_values_match'] is True,
            'frozen oracle threshold or special-value check failed')
    require(all(isinstance(result[key], (int, float)) and math.isfinite(result[key]) and result[key] >= 0
                for key in ('mere', 'mare')), 'invalid oracle error metrics')
    require(result['mere'] < threshold and result['mare'] < 10 * threshold and result['passed'] is True,
            'native numerical correctness gate failed')
    if timeline:
        evidence.bind(directory / 'verify.stderr.log')
    return {'metadata': evidence.bind(metadata_path), 'execution': evidence.bind(execution_path),
            'stdout': evidence.bind(stdout_path), 'result': evidence.bind(directory / 'result.json'), 'output': output_ref}


def phase_names(cell):
    if cell['mode'] == 'shared':
        return ['shared']
    if cell['mode'] == 'split':
        return ['map_AB', 'map_BA'] if cell['cycle'] % 2 == 0 else ['map_BA', 'map_AB']
    return ['solo_before', 'secondary_idle', 'dual_active_serial', 'solo_after']


def physical_mapping(cell, phase, workers):
    main = workers[0]['ready']['pid']
    if phase in ('map_AB', 'map_BA'):
        slots = (0, 1) if phase == 'map_AB' else (1, 0)
        return dict(zip(ROLES, [(main, slot) for slot in slots]))
    if phase == 'dual_active_serial':
        second = workers[1]['ready']['pid']
        pids = (main, second) if cell['cycle'] % 2 == 0 else (second, main)
        return dict(zip(ROLES, [(pid, 0) for pid in pids]))
    return {role: (main, 0) for role in ROLES}


def verify_cell(directory, cell, plan, evidence, frozen):
    raw = evidence.json(directory / 'raw.json')
    require(raw['cell'] == cell and raw['schema_version'] == 1 and raw.get('complete') is True
            and 'error' not in raw, 'incomplete or unexpected diagnostic cell')
    require(raw['started_at'] < raw['finished_at'], 'cell time interval invalid')
    op = cell['operator']; info = plan['operators'][op]; metadata = read(info['metadata'])
    require(raw['logging_reference_payload'] == read(plan['logging_reference_payloads'][op]['path']),
            'historical logging payload differs')
    require([phase['name'] for phase in raw['phases']] == phase_names(cell), 'phase order changed')
    workers = raw['workers']
    require(len(workers) == (2 if cell['mode'] == 'residency' else 1), 'worker count changed')
    by_pid = {}; expected_stdout = {}; next_sequence = {}; previous_end = {}; worker_refs = []
    for index, worker in enumerate(workers):
        path = directory / ('primary' if index == 0 else 'secondary')
        ready, execution = worker['ready'], worker['execution']
        require(evidence.json(path / 'execution.json') == execution, 'worker execution receipt mismatch')
        require(execution['exit_status'] == 0 and raw['started_at'] <= execution['started_at'] < execution['finished_at'] <= raw['finished_at'],
                'worker execution failed or outside cell')
        require(ready['type'] == 'ready' and ready['device'] == 0 and ready['operator'] == op
                and ready['warmup'] == 10 and ready['repeat'] == 100
                and ready['allocation_policy'] == 'ACL_MEM_MALLOC_HUGE_FIRST', 'READY protocol mismatch')
        require(ready['pid'] == execution['pid'] == execution['wrapper_pid'] and ready['pid'] not in by_pid,
                'worker process identity mismatch')
        require(ready['affinity'] == execution['cpu_affinity'] == plan['cpu_affinity']
                and ready['cpu'] in ready['affinity'], 'CPU mask differs from frozen inherited mask')
        require(execution['started_at'] <= ready['unix_ns'] / 1e9 <= execution['finished_at'], 'READY time outside worker')
        require(int(ready['context'], 16) > 0 and int(ready['stream'], 16) > 0, 'missing ACL context or stream')
        slots = 2 if cell['mode'] == 'split' else 1
        require(len(ready['buffers']) == slots, 'physical allocation count differs')
        pointers = []
        for slot, buffer in enumerate(ready['buffers']):
            require(buffer['slot'] == slot and buffer['bytes'] == metadata['numel'] * (4 if metadata['dtype'] == 'float32' else 2)
                    and buffer['tiling_bytes'] > 0, 'buffer size or slot mismatch')
            pointers += [int(buffer[key], 16) for key in ('input', 'output', 'tiling')]
        require(all(pointers) and len(set(pointers)) == len(pointers), 'allocations alias unexpectedly')
        expected_app = frozen.worker_command(op, info, metadata, path / 'output0.bin')
        expected_argv = [plan['host_tools']['taskset']['path'], '-c', ','.join(map(str, plan['cpu_affinity'])), *expected_app]
        require(execution['application_argv'] == expected_app and execution['argv'] == expected_argv
                and execution['cwd'] == info['source_dir'], 'worker command or cwd changed')
        expected_env = dict(plan['environment'], APROF_DIAG_REPEAT='100', APROF_DIAG_SLOTS=str(slots))
        require(execution['environment'] == expected_env, 'worker environment changed')
        evidence.bind(path / 'stdout.log'); evidence.json(path / 'proc.json')
        by_pid[ready['pid']] = worker; expected_stdout[ready['pid']] = [ready]
        next_sequence[ready['pid']] = 0; previous_end[ready['pid']] = ready['monotonic_ns']
        worker_refs.append({'execution': evidence.bind(path / 'execution.json'), 'stdout': evidence.bind(path / 'stdout.log'),
                            'process_snapshot': evidence.bind(path / 'proc.json'), 'correctness': []})
    expected_rows = []; prior_phase_end = raw['started_at']; last_global_end = 0
    for phase in raw['phases']:
        name = phase['name']; mapping = physical_mapping(cell, name, workers)
        require(prior_phase_end <= phase['started_at'] <= phase['finished_at'] <= raw['finished_at'], 'phase chronology invalid')
        require([r['role'] for r in phase['prime_receipts']] == ['A', 'B', 'B', 'A'], 'fixed priming order changed')
        rows = [r for r in raw['records'] if r['condition'] == name]
        require(len(rows) == 5, 'not exactly five pairs per condition and fresh cycle')
        commands = [(r, 'prime', r['role']) for r in phase['prime_receipts']]
        for pair, row in enumerate(rows):
            expected_order = list(ROLES if (cell['cycle'] + pair) % 2 == 0 else ROLES[::-1])
            require(row['pair'] == pair and row['cycle'] == cell['cycle'] and row['order'] == expected_order
                    and set(row['roles']) == set(ROLES), 'fixed pair order or identity changed')
            commands.extend((row['roles'][role], 'sample', role) for role in expected_order)
        for receipt, kind, role in commands:
            pid, slot = mapping[role]; sample = receipt['sample']; ready = by_pid[pid]['ready']
            require(sample['pid'] == pid, 'role assigned to wrong physical worker')
            require(receipt['request_monotonic_ns'] >= last_global_end, 'overlapping or reordered commands')
            previous_end[pid] = verify_sample(receipt, ready, kind, slot, next_sequence[pid], previous_end[pid])
            last_global_end = previous_end[pid]; next_sequence[pid] += 1; expected_stdout[pid].append(sample)
            when = sample['unix_ns'] / 1e9
            require(prior_phase_end <= when <= phase['finished_at'], 'command outside condition interval')
            require((when <= phase['started_at']) if kind == 'prime' else (phase['started_at'] <= when),
                    'prime/sample separation differs')
        expected_rows += rows; prior_phase_end = phase['finished_at']
    require(raw['records'] == expected_rows, 'extra, omitted or reordered measurement rows')
    if cell['mode'] == 'residency':
        secondary = workers[1]; ready_at = secondary['ready']['unix_ns'] / 1e9
        require(raw['phases'][0]['finished_at'] <= secondary['execution']['started_at'] <= ready_at
                <= raw['phases'][1]['started_at'], 'secondary residency startup differs')
        # The final saved execution finished_at is refreshed during cleanup; actual
        # final ACK precedes solo_after. No process-liveness claim is inferred from it.
        require(all(r['sample']['pid'] == workers[0]['ready']['pid'] for r in raw['phases'][1]['prime_receipts']),
                'idle secondary received a prime')
    for index, worker in enumerate(workers):
        path = directory / ('primary' if index == 0 else 'secondary'); pid = worker['ready']['pid']
        actual_stdout = stdout_messages(path / 'stdout.log', evidence)
        require(actual_stdout[:-1] == expected_stdout[pid], 'actual stdout differs from raw command receipts')
        verify_completed(actual_stdout[-1], worker['ready'], previous_end[pid])
        latest_sample = max(x['unix_ns'] / 1e9 for x in expected_stdout[pid])
        for slot in range(len(worker['ready']['buffers'])):
            actual_metadata = dict(metadata, output=str(path / f'output{slot}.bin'))
            worker_refs[index]['correctness'].append(verify_oracle(path / f'verify-slot{slot}', actual_metadata,
                info, plan, evidence, earliest=latest_sample, latest=raw['finished_at']))
    persistence = raw.get('persistence_receipts', [])
    if cell['logging'] == 'buffered':
        require(not persistence, 'buffered condition persisted between pairs')
    else:
        require([(x['condition'], x['pair']) for x in persistence] == [(x['condition'], x['pair']) for x in raw['records']],
                'row-logging persistence coverage differs')
        for index, (receipt, row) in enumerate(zip(persistence, raw['records'])):
            last = row['roles'][row['order'][-1]]['response_monotonic_ns']
            require(last <= receipt['started_monotonic_ns'] <= receipt['finished_monotonic_ns']
                    and receipt['bytes'] >= plan['logging_reference_payloads'][op]['bytes'], 'logging persistence receipt invalid')
            if index + 1 < len(raw['records']) and row['condition'] == raw['records'][index + 1]['condition']:
                following = raw['records'][index + 1]
                require(receipt['finished_monotonic_ns'] <= following['roles'][following['order'][0]]['request_monotonic_ns'],
                        'pair overlaps synchronous persistence')
    snapshots = []
    for label in ('before', 'after'):
        snapshot = evidence.json(directory / f'device-{label}.json')
        require([c['argv'] for c in snapshot['commands']] == plan['device_state_commands']
                and snapshot['commands'][0]['exit_status'] == 0, 'device snapshot missing or changed')
        for command in snapshot['commands']:
            require(command['started_at'] <= command['finished_at'], 'device snapshot chronology invalid')
        require(set(snapshot['host']) == {'stat', 'loadavg', 'meminfo'}, 'host snapshot missing')
        snapshots.append(evidence.bind(directory / f'device-{label}.json'))
    return raw, {'cell': cell, 'raw': evidence.bind(directory / 'raw.json'), 'workers': worker_refs, 'snapshots': snapshots}


def recompute_controls(raws, plan):
    """Use new raw.records only; historical write-cost payloads never enter data."""
    rows = []; shifts = []
    for op in ('exp', 'sigmoid'):
        for mode, conditions in plan['conditions'].items():
            for logging in FACTORS:
                selected_raws = [r for r in raws if r['cell']['operator'] == op and r['cell']['mode'] == mode and r['cell']['logging'] == logging]
                for condition in conditions:
                    records = [r for raw in selected_raws for r in raw['records'] if r['condition'] == condition]
                    for cycle in [None, *range(6)]:
                        chosen = [r for r in records if cycle is None or r['cycle'] == cycle]
                        a, b = ([r['roles'][role]['sample']['event_ns_per_operator'] for r in chosen] for role in ROLES)
                        require(len(a) == (30 if cycle is None else 5), 'missing control stratum')
                        bias = abs(math.exp(statistics.fmean(math.log(y / x) for x, y in zip(a, b))) - 1)
                        cvs = [statistics.stdev(values) / statistics.fmean(values) for values in (a, b)]
                        slots = {}
                        if mode == 'split':
                            for slot in (0, 1):
                                values = [r['roles'][role]['sample']['event_ns_per_operator'] for r in chosen for role in ROLES if r['roles'][role]['sample']['slot'] == slot]
                                slots[str(slot)] = {'samples': len(values), 'mean_ns': statistics.fmean(values)}
                        rows.append(dict(operator=op, mode=mode, logging=logging, condition=condition, cycle=cycle,
                                         pairs=len(a), role_bias=bias, cv_A=cvs[0], cv_B=cvs[1], physical_slots=slots,
                                         passed=bias <= .02 and max(cvs) <= .05))
        for logging in FACTORS:
            records = [r for raw in raws if raw['cell']['operator'] == op and raw['cell']['mode'] == 'residency'
                       and raw['cell']['logging'] == logging for r in raw['records']]
            for cycle in [None, *range(6)]:
                for role in ROLES:
                    means = {phase: statistics.fmean(r['roles'][role]['sample']['event_ns_per_operator'] for r in records
                        if r['condition'] == phase and (cycle is None or r['cycle'] == cycle)) for phase in ('solo_before', 'solo_after')}
                    shift = abs(means['solo_after'] / means['solo_before'] - 1)
                    shifts.append(dict(operator=op, logging=logging, cycle=cycle, role=role, shift=shift, passed=shift <= .02))
    return dict(schema_version=1, authority='diagnosis_only_no_promotion', rows=rows, solo_shifts=shifts,
                all_controls_passed=all(row['passed'] for row in [*rows, *shifts]))


def load_frozen(path):
    module = types.ModuleType('_frozen_timing_diagnosis')
    module.__file__ = str(path)
    # Do not create __pycache__ inside the immutable experiment snapshot.
    exec(compile(Path(path).read_text(), str(path), 'exec'), module.__dict__)
    return module


def verify_job(root, name, action, plan_path, plan_hash, evidence, *, runner=None, output=None, expected_exit=0):
    job = evidence.json(root / (name + '-job.json'))
    expected = [job['argv'][0], str(runner or read(plan_path)['frozen_runner']), action, '--plan', str(plan_path),
                '--expected-sha256', plan_hash, '--output', str(output or root / ('measurements' if action == 'run' else 'timelines'))]
    require(job['argv'] == expected and job['cwd'] == str(root), 'outer diagnostic job changed')
    receipt = evidence.json(root / (name + '-job') / 'execution.json')
    require(receipt['exit_code'] == expected_exit, 'outer diagnostic job exit differs')
    # run_aprof_job records the input job verbatim under job.
    require(receipt['job'] == job, 'outer job receipt does not bind registered invocation')
    evidence.bind(root / (name + '-job') / 'stdout.log'); evidence.bind(root / (name + '-job') / 'stderr.log')
    return {'job': evidence.bind(root / (name + '-job.json')), 'execution': evidence.bind(root / (name + '-job') / 'execution.json'),
            'stdout': evidence.bind(root / (name + '-job') / 'stdout.log'), 'stderr': evidence.bind(root / (name + '-job') / 'stderr.log')}


def verify_timeline(directory, op, plan, evidence, frozen, *, amended=False):
    info = plan['operators'][op]; metadata = read(info['metadata'])
    commands = ''.join(f'prime 0 {i}\n' for i in range(4)) + 'sample 0 4\nquit\n'
    evidence.bind(directory / 'commands.txt')
    require((directory / 'commands.txt').read_text() == commands, 'independent timeline command count changed')
    execution = evidence.json(directory / 'execution.json')
    app = frozen.worker_command(op, info, metadata, directory / 'output0.bin')
    if not amended:
        app = [plan['host_tools']['taskset']['path'], '-c', ','.join(map(str, plan['cpu_affinity'])), *app]
    options = (['--task-time=l1', '--ai-core=on', '--aic-metrics=PipeUtilization', '--ascendcl=off', '--runtime-api=off']
               if amended else ['--task-time=on', '--runtime-api=on', '--ascendcl=on', '--ai-core=off'])
    argv = [plan['timeline']['tool'], '--output=' + str(directory / 'profile'), *options, '--type=text', '--application=' + shlex.join(app)]
    require(execution['argv'] == argv and execution['exit_status'] == 0
            and execution['tool_hash'] == plan['timeline']['tool_hash'], 'independent profiler invocation changed or failed')
    messages = stdout_messages(directory / 'stdout.log', evidence)
    require(len(messages) == 7 and messages[0]['type'] == 'ready', 'independent timeline ACK count changed')
    ready = messages[0]
    require(ready['operator'] == op and ready['device'] == 0 and ready['warmup'] == 10 and ready['repeat'] == 100
            and ready['affinity'] == plan['cpu_affinity'] and len(ready['buffers']) == 1, 'timeline READY differs')
    prior = ready['monotonic_ns']
    for sequence, message in enumerate(messages[1:-1]):
        kind = 'prime' if sequence < 4 else 'sample'
        receipt = {'sample': message, 'request_monotonic_ns': message['started_monotonic_ns'],
                   'response_monotonic_ns': message['monotonic_ns']}
        prior = verify_sample(receipt, ready, kind, 0, sequence, prior)
        require(execution['started_at'] <= message['unix_ns'] / 1e9 <= execution['finished_at'], 'timeline ACK outside profiler execution')
    verify_completed(messages[-1], ready, prior)
    tables = list((directory / 'profile').rglob('op_summary*.csv'))
    require(len(tables) == 1, 'independent timeline table count differs')
    evidence.bind(tables[0]); evidence.bind(directory / 'stderr.log')
    summary = frozen.timeline_summary(tables[0], directory / 'stdout.log', op)
    require(evidence.json(directory / 'timeline-summary.json') == summary, 'timeline summary does not replay')
    if (directory / 'export.execution.json').exists():
        exported = evidence.json(directory / 'export.execution.json')
        require(exported['exit_status'] == 0 and exported['argv'][0] == plan['timeline']['tool'], 'profiler export failed')
        evidence.bind(directory / 'export.stdout.log'); evidence.bind(directory / 'export.stderr.log')
    correctness = verify_oracle(directory, dict(metadata, output=str(directory / 'output0.bin')), info, plan,
                                evidence, timeline=True, earliest=execution['finished_at'])
    return {'operator': op, 'execution': evidence.bind(directory / 'execution.json'), 'stdout': evidence.bind(directory / 'stdout.log'),
            'task_table': evidence.bind(tables[0]), 'recomputed': summary, 'correctness': correctness}


def profile_amendment(anchor_path, root, plan_path, plan, evidence):
    """A fixed, externally anchored infrastructure repair; never a retry loop."""
    path = anchor_path.with_name('graph-base-0.5.1-measurement-diagnosis-profile-amendment.json')
    if not path.exists():
        return None
    wrapper = evidence.json(path)
    require(wrapper['schema_version'] == 1 and wrapper['purpose'] == 'preregistered_independent_profile_infrastructure_fix',
            'unknown profile infrastructure amendment anchor')
    evidence.bind(wrapper['amendment']['path'], wrapper['amendment']['sha256'])
    amendment = read(wrapper['amendment']['path'])
    require(amendment['schema_version'] == 1 and amendment['kind'] == 'independent_profile_infrastructure_fix'
            and amendment['original_anchor'] == {k: v for k, v in evidence.bind(anchor_path).items() if k != 'bytes'}
            and amendment['original_plan'] == {k: v for k, v in evidence.bind(plan_path).items() if k != 'bytes'},
            'profile amendment does not bind the original experiment')
    for name in ('old_runner', 'new_runner', 'reference_profiler_configuration', 'failed_original_job',
                 'failed_original_exp_capture', 'matrix_execution', 'matrix_controls'):
        evidence.bind(amendment[name]['path'], amendment[name]['sha256'])
    require(amendment['old_runner']['path'] == plan['frozen_runner'], 'profile amendment targets a different runner')
    old_app = "app=[plan['host_tools']['taskset']['path'],'-c',','.join(map(str,plan['cpu_affinity'])),*worker_command(op,info,metadata,directory/'output0.bin')]"
    old_options = "'--task-time=on','--runtime-api=on','--ascendcl=on','--ai-core=off','--type=text'"
    changes = [{'old': old_app, 'new': "app=worker_command(op,info,metadata,directory/'output0.bin')"},
               {'old': old_options, 'new': "'--task-time=l1','--ai-core=on','--aic-metrics=PipeUtilization','--ascendcl=off','--runtime-api=off','--type=text'"}]
    require(amendment['changes'] == changes and amendment['operators'] == ['exp', 'sigmoid']
            and amendment['max_attempts_per_operator'] == 1 and amendment['repeat_control_samples'] is False
            and amendment['expected_kernel_tasks'] == 510, 'amendment exceeds fixed infrastructure scope')
    original = Path(amendment['old_runner']['path']).read_text()
    for change in changes:
        require(original.count(change['old']) == 1, 'ambiguous profile infrastructure patch')
        original = original.replace(change['old'], change['new'], 1)
    require(Path(amendment['new_runner']['path']).read_text() == original, 'unregistered profile runner changes')
    require(amendment['replacement_output'] == str(root / 'timelines-infrastructure-fix')
            and amendment['replacement_job_path'] == str(root / 'timeline-infrastructure-fix-job.json'), 'amendment output or job relocated')
    evidence.bind(wrapper['replacement_job']['path'], wrapper['replacement_job']['sha256'])
    require(wrapper['replacement_job']['path'] == amendment['replacement_job_path'], 'replacement job binding differs')
    failed = evidence.json(root / 'timeline-job/execution.json')
    require(failed['exit_code'] != 0 and not (root / 'timelines/sigmoid').exists(), 'original failure/not-run history changed')
    for old_file in (root / 'timelines').rglob('*'):
        if old_file.is_file():
            evidence.bind(old_file)
    earliest = max(amendment['registered_at'], datetime.fromisoformat(wrapper['recorded_at_utc']).timestamp())
    return {'wrapper': evidence.bind(path), 'amendment': evidence.bind(wrapper['amendment']['path']),
            'value': amendment, 'earliest_start': earliest}


def replay_diagnosis(anchor_path: Path) -> dict:
    evidence = Evidence(); anchor_path = Path(anchor_path).resolve(strict=True); anchor = evidence.json(anchor_path)
    require(anchor['schema_version'] == 1 and anchor['purpose'] == 'preregistered_measurement_diagnosis_not_rule_promotion',
            'unexpected diagnostic anchor')
    plan_path = Path(anchor['plan']).resolve(strict=True); root = plan_path.parent
    evidence.bind(plan_path, anchor['plan_sha256']); plan = read(plan_path)
    require(plan['purpose'] == 'timing_method_diagnosis_no_skill_promotion', 'unexpected diagnostic purpose')
    expected_cells = [dict(operator=op, cycle=cycle, mode=MODES[(cycle + offset) % 3], logging=factor)
        for op in ('exp', 'sigmoid') for cycle in range(6) for offset in range(3)
        for factor in (FACTORS if cycle % 2 == 0 else FACTORS[::-1])]
    require(plan['cells'] == expected_cells and plan['cycles'] == 6 and plan['pairs_per_cycle'] == 5
            and plan['repeat'] == 100 and plan['warmup'] == 10 and plan['prime_repeat'] == 100, 'fixed finite matrix changed')
    require(plan['thresholds'] == {'max_role_bias': .02, 'max_sample_cv': .05, 'max_solo_mean_shift': .02}, 'control thresholds changed')
    require(plan['conditions'] == {'shared': ['shared'], 'split': ['map_AB', 'map_BA'],
            'residency': ['solo_before', 'secondary_idle', 'dual_active_serial', 'solo_after']}, 'condition scope changed')
    for path, expected in plan['producer'].items():
        evidence.bind(path, expected)
    require(anchor['frozen_runner'] == plan['frozen_runner'] and plan['frozen_runner'] in plan['producer'], 'runner not anchored')
    frozen = load_frozen(plan['frozen_runner'])
    for tool in [*plan['host_tools'].values(), {'path': plan['timeline']['tool'], 'sha256': plan['timeline']['tool_hash']}]:
        evidence.bind(tool['path'], tool['sha256'])
    for op, info in plan['operators'].items():
        evidence.bind(info['binary'], info['binary_hash'])
        for path, expected in info['input_files'].items():
            evidence.bind(path, expected)
        for path, expected in info['source_files'].items():
            evidence.bind(Path(info['source_dir']) / path, expected)
        for path, expected in info['original_kernel_files'].items():
            require(info['source_files'][path] == expected, 'diagnostic kernel differs from frozen baseline')
        payload_info = plan['logging_reference_payloads'][op]
        evidence.bind(payload_info['path'], payload_info['sha256'])
        evidence.bind(payload_info['source'], payload_info['source_hash'])
        payload = read(payload_info['path']); historical = read(payload_info['source'])
        require(payload['authority'] == 'historical_logging_bytes_only_not_new_measurements'
                and payload['source_path'] == payload_info['source'] and payload['source_sha256'] == payload_info['source_hash'],
                'historical payload authority/source differs')
        for key in ('records', 'case_executions'):
            historical[key] = [row for row in historical[key] if row['case_id'] < info['case_id']]
        require(payload['historical_payload'] == historical and Path(payload_info['path']).stat().st_size == payload_info['bytes'],
                'historical logging payload selection differs')
    matrix_dir = root / 'measurements'; actual_dirs = {p.name for p in matrix_dir.iterdir() if p.is_dir()}
    expected_names = {f"{c['operator']}-{c['cycle']}-{c['mode']}-{c['logging']}" for c in expected_cells}
    require(actual_dirs == expected_names, 'omitted or extra diagnostic cells')
    raws = []; cells = []; previous_finished = datetime.fromisoformat(anchor['recorded_at_utc']).timestamp()
    for cell in expected_cells:
        directory = matrix_dir / f"{cell['operator']}-{cell['cycle']}-{cell['mode']}-{cell['logging']}"
        raw, refs = verify_cell(directory, cell, plan, evidence, frozen)
        require(previous_finished <= raw['started_at'], 'matrix execution order differs or overlaps')
        previous_finished = raw['finished_at']; raws.append(raw); cells.append(refs)
    controls = recompute_controls(raws, plan)
    saved = evidence.json(matrix_dir / 'controls.json')
    # Preserve order-independent strata equality; file iteration order cannot
    # legitimately affect the accepted statistics beyond floating rounding.
    require(controls == saved, 'saved controls differ from independent raw replay')
    amendment = profile_amendment(anchor_path, root, plan_path, plan, evidence)
    timeline_root = Path(amendment['value']['replacement_output']) if amendment else root / 'timelines'
    timelines = [verify_timeline(timeline_root / op, op, plan, evidence, frozen, amended=bool(amendment)) for op in ('exp', 'sigmoid')]
    if amendment:
        previous_finished = max(previous_finished, amendment['earliest_start'])
    for timeline in timelines:
        execution = read(timeline['execution']['path'])
        require(previous_finished <= execution['started_at'], 'timeline overlaps controls or its predecessor')
        previous_finished = execution['finished_at']
    jobs = {'matrix': verify_job(root, 'matrix', 'run', plan_path, anchor['plan_sha256'], evidence)}
    if amendment:
        jobs['original_failed_timeline'] = verify_job(root, 'timeline', 'timeline', plan_path, anchor['plan_sha256'], evidence, expected_exit=1)
        jobs['timeline'] = verify_job(root, 'timeline-infrastructure-fix', 'timeline', plan_path, anchor['plan_sha256'], evidence,
                                    runner=amendment['value']['new_runner']['path'], output=timeline_root)
    else:
        jobs['timeline'] = verify_job(root, 'timeline', 'timeline', plan_path, anchor['plan_sha256'], evidence)
    actual_cells = [json.loads(line) for line in Path(jobs['matrix']['stdout']['path']).read_text().splitlines() if line.strip()]
    require(actual_cells == [{'cell': cell, 'status': 'completed'} for cell in expected_cells], 'actual outer stdout does not cover the fixed matrix')
    shared = [row for row in controls['rows'] if row['mode'] == 'shared']
    require(len(shared) == 28, 'shared-buffer strata missing')
    return {'schema_version': 1, 'authority': 'diagnosis_entry_only_not_production_admission',
            'anchor': evidence.bind(anchor_path), 'plan': evidence.bind(plan_path), 'replayer': evidence.bind(__file__),
            'cells': cells, 'timelines': timelines, 'jobs': jobs, 'recomputed_controls': controls,
            'profile_infrastructure_amendment': amendment,
            'shared_buffer_entry_qualified': all(row['passed'] for row in shared),
            'historical_payload_in_statistics': False, 'raw_file_fingerprints': list(evidence.files.values()),
            'limitations': ['Device pointers are virtual addresses, not physical HBM-channel evidence.',
                           'This diagnosis cannot replace independent production-method confirmation.',
                           'Oracle metrics are replayed from bound native executions; the verifier is not rerun.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchor', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); result = replay_diagnosis(args.anchor)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
    print(json.dumps({'report': str(args.output), 'sha256': digest(args.output),
                      'shared_buffer_entry_qualified': result['shared_buffer_entry_qualified']}))


if __name__ == '__main__':
    main()
