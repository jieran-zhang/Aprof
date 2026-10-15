#!/usr/bin/env python3
"""Finite diagnostic of host submission stalls; never produces admission.

Six fresh contexts, 500 A/A pairs each, followed by one independent five-pair
task timeline. No retry, sample removal, or extension after observing results.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import selectors
import shlex
import shutil
import statistics
import subprocess
import time

from run_shared_timing_confirmation import BASE_ENVIRONMENT, PROFILE_FLAGS, binding, locks, native_messages, save_new

ROOT = Path(__file__).resolve().parents[3]
HEADER = ROOT / 'scaffolding/benchmarks/cannbench/harness/device_submission_diagnostic.h'
PREFIX = 'APROF_SHARED_TIMING_JSON:'
PROTOCOL = 'shared_buffer_submission_diagnostic_v1'
USAGE = ('nvcsw', 'nivcsw', 'minflt', 'majflt')


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def commands(pairs):
    require(pairs in (5, 500), 'unregistered diagnostic sample count')
    return ['prime 0 formal', *[f'pair {i + 1} formal {i}' for i in range(pairs)], f'finish {pairs + 1}']


def task_intervals(tasks):
    """Subtract absolute microsecond timestamps before converting to float."""
    starts = [Decimal(r['Task Start Time(us)'].strip()) for r in tasks]
    durations = [Decimal(r['Task Duration(us)'].strip()) for r in tasks]
    require(all(v.is_finite() and v > 0 for v in starts + durations), 'invalid diagnostic task timestamp')
    gaps = [starts[i+1] - starts[i] - durations[i] for i in range(len(tasks) - 1)]
    require(all(gap >= Decimal('-.002') for gap in gaps), 'overlapping diagnostic kernel tasks')
    return {'kernel_sum_us': float(sum(durations)),
            'first_last_span_us': float(starts[-1] + durations[-1] - starts[0]),
            'maximum_intertask_gap_us': float(max(gaps)) if gaps else 0.0}


def source_files(directory):
    return sorted(p for p in directory.rglob('*') if p.is_file() and 'build' not in p.relative_to(directory).parts
                  and '__pycache__' not in p.parts)


def process_state(pid):
    directory = Path('/proc') / str(pid)
    threads = {}
    for task in sorted((directory / 'task').iterdir()):
        try:
            threads[task.name] = {'affinity': sorted(os.sched_getaffinity(int(task.name))),
                                  'stat': (task / 'stat').read_text(), 'status': (task / 'status').read_text()}
        except OSError as error:
            threads[task.name] = {'read_error': str(error)}
    return {'pid': pid, 'recorded_monotonic_ns': time.monotonic_ns(), 'threads': threads}


def cgroup_state():
    values = {}
    for name in ('cpu.cfs_quota_us', 'cpu.cfs_period_us', 'cpu.stat'):
        path = Path('/sys/fs/cgroup/cpu') / name
        try:
            values[str(path)] = {'text': path.read_text()}
        except OSError as error:
            values[str(path)] = {'read_error': str(error)}
    return {'recorded_monotonic_ns': time.monotonic_ns(), 'files': values,
            'interpretation': 'Historical/cycle counters alone do not identify a particular sample stall.'}


def prepare(output, predecessor):
    output.mkdir(exist_ok=False)
    predecessor = predecessor.resolve(strict=True)
    original = read(predecessor / 'exp/config.json')
    case = next(c for c in original['cases'] if c['case_id'] == 6)
    old_source = Path(original['build']['source_dir'])
    source = output / 'source'
    shutil.copytree(old_source, source, ignore=shutil.ignore_patterns('build', '__pycache__'))
    shutil.copyfile(HEADER, source / 'op_host/device_shared_timing.h')
    changed = [str(p.relative_to(source)) for p in source_files(source)
               if binding(p)['sha256'] != binding(old_source / p.relative_to(source))['sha256']]
    require(changed == ['op_host/device_shared_timing.h'], 'diagnosis must modify the header only')
    case['command'][0] = str(source / 'build/exp')
    for role in ('baseline', 'candidate'):
        case['verify_commands'][role] = [v.replace(str(old_source), str(source)) for v in case['verify_commands'][role]]
    plan = {'schema_version': 1, 'purpose': 'submission_stall_diagnosis_only', 'created_at': time.time(),
            'predecessor': str(predecessor), 'case': case, 'source_dir': str(source), 'cycles': list(range(6)),
            'observe_pairs': 500, 'profile_pairs': 5, 'repeat': 100, 'prime_repeat': 100, 'warmup_per_role': 10,
            'cpu_affinity': sorted(os.sched_getaffinity(0)), 'environment': BASE_ENVIRONMENT,
            'cpu_topology': {str(cpu): {name: (Path(f'/sys/devices/system/cpu/cpu{cpu}/topology') / name).read_text().strip()
                                      for name in ('physical_package_id', 'core_id', 'thread_siblings_list')}
                             for cpu in sorted(os.sched_getaffinity(0))},
            'control_native_cpu_separation': 'No isolation; both inherit the unchanged mask. Record actual thread masks before priming.',
            'allocation': 'one process/context/stream/shared buffer set per cycle; identical baseline callbacks',
            'command_delivery': 'interactive stdin, exactly one command after each native ACK; RAM-only stdout until exit',
            'diagnostic_overhead': 'aggregate monotonic/rusage boundaries only; no per-launch instrumentation',
            'source_intervention': changed,
            'order': [f'observe-{i}' for i in range(6)] + ['independent-profile'],
            'failure_policy': 'Execution/identity/oracle failure stops; timing anomalies retained and all fixed diagnostic cycles complete.',
            'resampling': 'none', 'max_attempts_per_slot': 1,
            'decision': 'No anomaly reproduction is inconclusive. No result in this diagnostic grants publication or changes prior rejection.',
            'descriptive_tail_rule': 'event / median(all events in its allocation cycle) > 1.10; retain and report every sample',
            'profile_expected_tasks': 1422, 'observe_expected_tasks_per_cycle': 100422,
            'profile_flags': PROFILE_FLAGS, 'source_files': {str(p): binding(p)['sha256'] for p in source_files(source)},
            'original_source_files': {str(p): binding(p)['sha256'] for p in source_files(old_source)},
            'input_files': {p: binding(p)['sha256'] for p in case['prepared_files']},
            'producers': {str(p): binding(p)['sha256'] for p in
                          (Path(__file__), HEADER, Path(__file__).with_name('run_shared_timing_confirmation.py'),
                           Path(__file__).with_name('replay_timing_diagnosis.py'), Path(__file__).with_name('run_aprof_job.py'))}}
    save_new(output / 'plan.json', plan)


def build(output):
    plan = read(output / 'plan.json'); source = Path(plan['source_dir'])
    save_new(output / 'build-started.json', {'started_at': time.time(), 'plan': binding(output / 'plan.json')})
    rows = []
    try:
        for i, argv in enumerate((['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                                  ['cmake', '--build', str(source / 'build'), '-j2'])):
            began = time.time()
            with (output / f'build-{i}.log').open('xb') as log:
                result = subprocess.run(argv, cwd=source, stdout=log, stderr=subprocess.STDOUT, timeout=600)
            rows.append({'argv': argv, 'started_at': began, 'finished_at': time.time(), 'exit_status': result.returncode,
                         'log': binding(output / f'build-{i}.log')})
            require(result.returncode == 0, 'diagnostic build failed')
        save_new(output / 'build-terminal.json', {'status': 'passed', 'commands': rows,
                                                  'binary': binding(source / 'build/exp')})
    except Exception as error:
        save_new(output / 'build-terminal.json', {'status': 'failed', 'commands': rows, 'error': str(error)})
        raise


def finalize_plan(output):
    # Preparation is not hardware registration. Keep the original plan used by
    # the real build, and bind the final analysis producer in a new document.
    plan = read(output / 'plan.json')
    for key in ('source_files', 'original_source_files', 'input_files'):
        require(all(binding(path)['sha256'] == digest for path, digest in plan[key].items()),
                'native source or input changed during preparation')
    plan['preparation_plan'] = binding(output / 'plan.json')
    plan['preparation_producers'] = plan['producers']
    plan['producers'] = {path: binding(path)['sha256'] for path in plan['producers']}
    plan['preparation_note'] = 'Final analysis uses Decimal before subtracting absolute profiler timestamps; native source, binary and experiment unchanged.'
    plan['finalized_at'] = time.time()
    save_new(output / 'plan-final.json', plan)


def freeze(output):
    plan = read(output / 'plan-final.json'); build_result = read(output / 'build-terminal.json')
    require(build_result['status'] == 'passed', 'failed build cannot freeze')
    predecessor = Path(plan['predecessor'])
    history = [predecessor / 'roster.json', predecessor / 'freeze.json', predecessor / 'campaign/campaign.json',
               *[predecessor / op / 'confirmation' / name for op in ('exp', 'sigmoid')
                 for name in ('raw_measurements.json', 'measurement_report.json', 'measurement_admission.json')],
               *[predecessor / 'campaign' / f'{op}-confirmation' / name for op in ('exp', 'sigmoid')
                 for name in ('terminal.json', 'job/execution.json')]]
    all_files = {}
    for key in ('source_files', 'original_source_files', 'input_files', 'producers'):
        for path, digest in plan[key].items():
            require(binding(path)['sha256'] == digest, 'diagnostic preparation changed')
            all_files[path] = digest
    for path in [output / 'plan.json', output / 'plan-final.json', output / 'build-started.json',
                 output / 'build-terminal.json', Path(build_result['binary']['path']), *history]:
        all_files[str(path)] = binding(path)['sha256']
    profile_commands = output / 'profile-commands.txt'
    with profile_commands.open('x') as stream:
        stream.write('\n'.join(commands(5)) + '\n')
    all_files[str(profile_commands)] = binding(profile_commands)['sha256']
    profiler = Path(shutil.which('msprof') or '/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof').resolve(strict=True)
    all_files[str(profiler)] = binding(profiler)['sha256']
    save_new(output / 'freeze.json', {'schema_version': 1, 'purpose': plan['purpose'], 'created_at': time.time(),
                                    'files': all_files, 'profiler': str(profiler), 'history': [binding(p) for p in history],
                                    'profile_commands': binding(profile_commands), 'accepted': False})


def validate_messages(messages, cycle, pairs):
    require(len(messages) == pairs + 3 and messages[0]['kind'] == 'ready'
            and messages[1]['kind'] == 'prime' and messages[-1]['kind'] == 'complete', 'incomplete native protocol')
    first = messages[0]
    for msg in messages:
        require(msg['protocol'] == PROTOCOL and msg['cycle_index'] == cycle and msg['repeat'] == 100
                and msg['warmup'] == 10 and msg['prime_repeat'] == 100 and msg['device'] == 0
                and msg['launches_per_operator'] == {'baseline': 1, 'candidate': 1}
                and all(msg[k] == first[k] for k in ('pid', 'context_address', 'stream_address', 'device', 'buffers')),
                'native identity or protocol changed')
    require(messages[1]['prime_order'] == (['baseline', 'candidate', 'candidate', 'baseline'] if cycle % 2 == 0
                                         else ['candidate', 'baseline', 'baseline', 'candidate']), 'prime order differs')
    for i, msg in enumerate(messages[2:-1]):
        require(msg['kind'] == 'pair' and msg['pair_index'] == i and msg['command_index'] == i + 1
                and msg['phase'] == 'formal' and msg['order'] == (['baseline', 'candidate'] if (cycle + i) % 2 == 0
                                                               else ['candidate', 'baseline']), 'pair sequence differs')
        for role in ('baseline', 'candidate'):
            sample = msg[role]
            keys = ['started_monotonic_ns', 'start_record_before_ns', 'start_record_after_ns', 'enqueue_before_ns',
                    'enqueue_after_ns', 'end_record_before_ns', 'end_record_after_ns', 'synchronize_before_ns',
                    'synchronize_after_ns', 'finished_monotonic_ns']
            require(all(sample[a] <= sample[b] for a, b in zip(keys, keys[1:])), 'diagnostic timestamp order differs')
            require(math.isfinite(sample['elapsed_ms']) and sample['elapsed_ms'] > 0
                    and sample['launches_per_operator'] == 1 and sample['implementation'] == role,
                    'invalid event interval or callback')
            usage = ['thread_usage_before', 'thread_usage_start_record_after', 'thread_usage_enqueue_after',
                     'thread_usage_end_record_after', 'thread_usage_synchronize_after', 'thread_usage_after']
            require(all(sample[a][key] <= sample[b][key] for a, b in zip(usage, usage[1:]) for key in USAGE),
                    'thread resource counter went backwards')
    require(messages[-1]['input_bytes_unchanged'] is True and messages[-1]['pairs_per_phase'] == pairs,
            'immutable input verification or sample count failed')


def oracle(plan, directory):
    result = {}
    for role in ('baseline', 'candidate'):
        argv = [v.replace('{cycle_dir}', str(directory)) for v in plan['case']['verify_commands'][role]]
        started = time.time(); output = binding(directory / f'{role}.bin')
        with (directory / f'{role}-verify.log').open('xb') as log:
            completed = subprocess.run(argv, cwd=plan['source_dir'], stdout=log, stderr=subprocess.STDOUT, timeout=180)
        row = {'argv': argv, 'started_at': started, 'finished_at': time.time(), 'exit_status': completed.returncode,
               'output': output, 'log': binding(directory / f'{role}-verify.log'),
               'result': binding(directory / f'{role}-result.json')}
        result[role] = row
        require(completed.returncode == 0 and binding(directory / f'{role}.bin') == output, 'callback correctness failed')
    return result


def observe(plan, output, cycle):
    directory = output / f'observe-{cycle}'; directory.mkdir(exist_ok=False)
    argv = [v.replace('{cycle_dir}', str(directory)) for v in plan['case']['command']]
    env = {k: v for k, v in os.environ.items() if not k.startswith('APROF_')}
    env.update(plan['environment'], APROF_SHARED_CYCLE=str(cycle), APROF_SUBMISSION_DIAGNOSTIC_MODE='observe')
    receipt = {'started_at': time.time(), 'argv': argv, 'cycle': cycle, 'pairs': 500, 'messages': [], 'receipts': [], 'accepted': False}
    save_new(directory / 'started.json', {'started_at': receipt['started_at'], 'argv': argv})
    transcript = bytearray(); stderr_path = directory / 'stderr.log'; pending = bytearray()
    with stderr_path.open('xb') as stderr:
        child = subprocess.Popen(argv, cwd=plan['source_dir'], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        selector = selectors.DefaultSelector(); selector.register(child.stdout, selectors.EVENT_READ)
        def ack():
            deadline = time.monotonic() + 120
            while True:
                while b'\n' in pending:
                    line, _, rest = pending.partition(b'\n'); pending[:] = rest
                    if line.startswith(PREFIX.encode()):
                        return json.loads(line[len(PREFIX):])
                require(time.monotonic() < deadline, 'native diagnostic ACK timeout')
                if not selector.select(min(1, max(0, deadline - time.monotonic()))):
                    continue
                chunk = os.read(child.stdout.fileno(), 65536)
                require(bool(chunk), 'native exited before diagnostic ACK')
                transcript.extend(chunk); pending.extend(chunk)
                require(len(transcript) <= 16 * 1024 * 1024, 'native diagnostic stdout exceeded RAM bound')
        try:
            receipt['messages'].append(ack())
            receipt['controller_before_prime'] = process_state(os.getpid())
            receipt['native_before_prime'] = process_state(child.pid)
            receipt['cgroup_before_prime'] = cgroup_state()
            for command in commands(500):
                requested = time.monotonic_ns(); child.stdin.write((command + '\n').encode()); child.stdin.flush()
                msg = ack(); receipt['messages'].append(msg)
                receipt['receipts'].append({'command': command, 'request_monotonic_ns': requested,
                                             'response_monotonic_ns': time.monotonic_ns()})
            child.stdin.close(); transcript.extend(child.stdout.read()); child.wait(timeout=120)
            receipt['exit_status'] = child.returncode
            require(child.returncode == 0, 'native diagnostic failed')
            validate_messages(receipt['messages'], cycle, 500)
            receipt['cgroup_after_measurement'] = cgroup_state()
            receipt['verifications'] = oracle(plan, directory)
            receipt['status'] = 'complete_diagnostic_only'
        except Exception as error:
            receipt.update(status='failed', error=str(error))
            if child.poll() is None:
                child.kill(); child.wait(timeout=20)
            raise
        finally:
            selector.close(); receipt['finished_at'] = time.time()
            with (directory / 'stdout.log').open('xb') as stream:
                stream.write(transcript)
            receipt['stdout'] = binding(directory / 'stdout.log'); receipt['stderr'] = binding(stderr_path)
            save_new(directory / 'receipt.json', receipt)
    return receipt


def profile(plan, frozen, output):
    from run_aprof_job import run as run_job
    directory = output / 'independent-profile'; directory.mkdir(exist_ok=False)
    argv = [v.replace('{cycle_dir}', str(directory)) for v in plan['case']['command']]
    job = {'job_id': 'submission-diagnostic-independent-profile',
           'argv': [frozen['profiler'], '--output=' + str(directory / 'profile'), *PROFILE_FLAGS, '--application=' + shlex.join(argv)],
           'cwd': plan['source_dir'], 'output_dir': str(directory / 'job'), 'timeout_seconds': 1200,
           'environment': dict(plan['environment'], APROF_SHARED_CYCLE='0', APROF_SUBMISSION_DIAGNOSTIC_MODE='profile',
                               APROF_SHARED_COMMANDS=frozen['profile_commands']['path'])}
    save_new(directory / 'job.json', job)
    execution = run_job(job); require(execution['exit_code'] == 0, 'independent diagnostic profiler failed')
    messages = native_messages(directory / 'job/stdout.log'); validate_messages(messages, 0, 5)
    verifications = oracle(plan, directory)
    tables = list((directory / 'profile').rglob('op_summary*.csv'))
    if not tables:
        roots = list((directory / 'profile').glob('PROF_*')); require(len(roots) == 1, 'ambiguous profile root')
        export = dict(job, job_id='submission-diagnostic-export', output_dir=str(directory / 'export-job'),
                      argv=[frozen['profiler'], '--export=on', '--type=text', '--output=' + str(roots[0])])
        save_new(directory / 'export-job.json', export)
        require(run_job(export)['exit_code'] == 0, 'diagnostic profile export failed')
        tables = list((directory / 'profile').rglob('op_summary*.csv'))
    require(len(tables) == 1, 'missing or duplicate task table')
    with tables[0].open(newline='') as stream:
        all_tasks = list(csv.DictReader(stream))
    require(all(row['Op Name'] == 'exp_kernel' or row['Task Type'] not in ('AI_CORE', 'AI_VECTOR_CORE', 'MIX_AIC', 'MIX_AIV')
                for row in all_tasks), 'unregistered compute kernel in diagnostic timeline')
    tasks = sorted((r for r in all_tasks if r['Op Name'] == 'exp_kernel'), key=lambda r: Decimal(r['Task Start Time(us)'].strip()))
    require(len(tasks) == 1422 and len({r['Stream ID'] for r in tasks}) == 1 and {r['Device_id'] for r in tasks} == {'0'},
            'independent complete-call task count or identity differs')
    require(len({(r['Device_id'], r['Stream ID'], r['Task ID'], r['Task Start Time(us)']) for r in tasks}) == len(tasks),
            'duplicate diagnostic task records')
    task_intervals(tasks)
    spans = []; cursor = 420
    for pair in messages[2:-1]:
        for role in pair['order']:
            selected = tasks[cursor:cursor + 100]
            spans.append({'pair_index': pair['pair_index'], 'role': role, 'task_indices': [cursor, cursor + 100],
                          'task_count': 100, **task_intervals(selected),
                          'acl_event_us': pair[role]['elapsed_ms'] * 1000, 'tasks': selected})
            cursor += 100
    result = {'purpose': 'independent_diagnostic_task_timeline', 'accepted': False, 'complete_kernel_tasks': 1422,
              'table': binding(tables[0]), 'execution': binding(directory / 'job/execution.json'),
              'stdout': binding(directory / 'job/stdout.log'), 'verifications': verifications, 'spans': spans,
              'clock_note': 'Ordered complete-call groups only; native monotonic and profiler UTC clock origins are not equated.'}
    save_new(directory / 'timeline.json', result)
    return result


def summarize(receipts):
    rows = []; cycles = []
    for receipt in receipts:
        samples = [(pair, role, pair[role]) for pair in receipt['messages'][2:-1] for role in pair['order']]
        median = statistics.median(sample['elapsed_ms'] for _, _, sample in samples)
        a = [pair['baseline']['elapsed_ms'] for pair in receipt['messages'][2:-1]]
        b = [pair['candidate']['elapsed_ms'] for pair in receipt['messages'][2:-1]]
        cycles.append({'cycle': receipt['cycle'], 'pairs': len(a), 'event_median_ms': median,
                       'role_bias': abs(math.exp(statistics.fmean(math.log(y/x) for x, y in zip(a, b))) - 1),
                       'baseline_cv': statistics.stdev(a)/statistics.fmean(a), 'candidate_cv': statistics.stdev(b)/statistics.fmean(b)})
        for pair, role, sample in samples:
            def delta(left, right):
                return {key: sample[right][key] - sample[left][key] for key in USAGE}
            rows.append({'cycle': receipt['cycle'], 'pair_index': pair['pair_index'], 'role': role,
                         'elapsed_ms': sample['elapsed_ms'], 'ratio_to_cycle_event_median': sample['elapsed_ms']/median,
                         'descriptive_tail': sample['elapsed_ms']/median > 1.10,
                         'enqueue_wall_ns': sample['enqueue_after_ns'] - sample['enqueue_before_ns'],
                         'enqueue_thread_cpu_ns': sample['thread_cpu_enqueue_after_ns'] - sample['thread_cpu_enqueue_before_ns'],
                         'synchronize_wall_ns': sample['synchronize_after_ns'] - sample['synchronize_before_ns'],
                         'synchronize_thread_cpu_ns': sample['thread_cpu_sync_after_ns'] - sample['thread_cpu_sync_before_ns'],
                         'enqueue_resource_delta': delta('thread_usage_start_record_after', 'thread_usage_enqueue_after'),
                         'synchronize_resource_delta': delta('thread_usage_end_record_after', 'thread_usage_synchronize_after'),
                         'whole_resource_delta': delta('thread_usage_before', 'thread_usage_after')})
    return {'purpose': 'descriptive_diagnostic_only', 'accepted': False, 'cycles': cycles, 'events': rows,
            'tail_events': [row for row in rows if row['descriptive_tail']],
            'interpretation': 'Absence of a reproduced tail is inconclusive; resource changes are evidence, not proof of causation.'}


def run(output, anchor_path):
    plan = read(output / 'plan-final.json'); frozen = read(output / 'freeze.json'); anchor = read(anchor_path)
    require(anchor['purpose'] == 'preregistered_submission_stall_diagnosis' and anchor['freeze'] == binding(output / 'freeze.json'),
            'trusted diagnostic anchor differs')
    require(sorted(os.sched_getaffinity(0)) == plan['cpu_affinity'], 'CPU affinity changed')
    for path, digest in frozen['files'].items():
        require(binding(path)['sha256'] == digest, 'registered diagnostic dependency changed')
    save_new(output / 'started.json', {'started_at': time.time(), 'anchor': binding(anchor_path), 'freeze': binding(output / 'freeze.json')})
    receipts = []; terminal = {'accepted': False, 'resampling': 'none', 'slots': {}}
    try:
        with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]):
            for cycle in plan['cycles']:
                receipts.append(observe(plan, output, cycle))
                terminal['slots'][f'observe-{cycle}'] = {'status': 'completed_diagnostic_only', 'receipt': binding(output / f'observe-{cycle}/receipt.json')}
                print(f'completed diagnostic cycle {cycle}: 500 pairs retained', flush=True)
            save_new(output / 'descriptive-summary.json', summarize(receipts))
            profile(plan, frozen, output)
            terminal['slots']['independent-profile'] = {'status': 'completed_diagnostic_only', 'timeline': binding(output / 'independent-profile/timeline.json')}
        terminal['status'] = 'complete_diagnostic_only'
    except Exception as error:
        terminal.update(status='failed', error=str(error))
        for name in plan['order']:
            terminal['slots'].setdefault(name, {'status': 'failed' if (output / name).exists() else 'not_run'})
        raise
    finally:
        terminal['finished_at'] = time.time(); save_new(output / 'terminal.json', terminal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'build', 'finalize-plan', 'freeze', 'run'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path)
    parser.add_argument('--anchor', type=Path)
    args = parser.parse_args(); output = args.output.resolve()
    if args.action == 'prepare': prepare(output, args.predecessor)
    elif args.action == 'build': build(output)
    elif args.action == 'finalize-plan': finalize_plan(output)
    elif args.action == 'freeze': freeze(output)
    else: run(output, args.anchor)


if __name__ == '__main__':
    main()
