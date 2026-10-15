#!/usr/bin/env python3
"""One fixed six-cycle long task timeline; diagnostic evidence only.

Reuses the previously frozen native binary, header, input and oracle. It cannot
grant measurement admission, retry a failed slot, or extend sample counts.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import shlex
import statistics
import sys
import time

import diagnose_submission_stalls as prior
from run_shared_timing_confirmation import BASE_ENVIRONMENT, PROFILE_FLAGS, binding, locks, native_messages, save_new

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


class Evidence:
    def __init__(self):
        self.files = {}

    def bind(self, ref):
        actual = binding(ref['path'])
        require(actual == ref, 'evidence hash mismatch: ' + ref['path'])
        self.files[actual['path']] = actual['sha256']
        return Path(actual['path'])

    def json(self, path):
        self.bind(binding(path))
        return read(path)


def verify_oracles(plan, directory, verifications, evidence):
    for role in ('baseline', 'candidate'):
        row = verifications[role]
        expected = [v.replace('{cycle_dir}', str(directory)) for v in plan['case']['verify_commands'][role]]
        require(row['argv'] == expected and row['exit_status'] == 0 and row['finished_at'] > row['started_at'],
                'oracle command or execution differs')
        for key in ('output', 'log', 'result'):
            evidence.bind(row[key])
        require(row['output']['path'] == str(directory / f'{role}.bin')
                and row['log']['path'] == str(directory / f'{role}-verify.log')
                and row['result']['path'] == str(directory / f'{role}-result.json'), 'oracle outputs relocated')
        result = read(row['result']['path'])
        printed = []
        for line in Path(row['log']['path']).read_text().splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and 'passed' in item:
                printed.append(item)
        require(printed == [result], 'oracle stdout/result disagreement')
        require(result['case_id'] == 6 and result['dtype'] == 'bfloat16' and result['numel'] == 1046529
                and result['shape'] == [1023, 1023] and result['threshold'] == 2**-7
                and math.isfinite(result['mere']) and 0 <= result['mere'] < result['threshold']
                and math.isfinite(result['mare']) and 0 <= result['mare'] < 10 * result['threshold']
                and result['special_values_match'] is True and result['passed'] is True,
                'independent oracle metrics do not satisfy the frozen rule')


def task_spans(table, messages, pairs):
    expected = 422 + pairs * 200
    with Path(table).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    require(all(r['Op Name'] == 'exp_kernel' or r['Task Type'] not in ('AI_CORE', 'AI_VECTOR_CORE', 'MIX_AIC', 'MIX_AIV')
                for r in rows), 'unregistered compute tasks')
    tasks = sorted((r for r in rows if r['Op Name'] == 'exp_kernel'),
                   key=lambda r: Decimal(r['Task Start Time(us)'].strip()))
    require(len(tasks) == expected and {r['Device_id'] for r in tasks} == {'0'}
            and len({r['Stream ID'] for r in tasks}) == 1, 'complete task count or stream/device identity differs')
    require(len({(r['Device_id'], r['Stream ID'], r['Task ID'], r['Task Start Time(us)']) for r in tasks}) == expected,
            'duplicate task records')
    prior.task_intervals(tasks)
    cursor = 420; spans = []
    median = statistics.median(m[role]['elapsed_ms'] for m in messages[2:-1] for role in m['order'])
    for message in messages[2:-1]:
        for role in message['order']:
            sample = message[role]
            intervals = prior.task_intervals(tasks[cursor:cursor + 100])
            elapsed = sample['elapsed_ms'] * 1000
            spans.append({'pair_index': message['pair_index'], 'role': role, 'order': message['order'],
                          'task_count': 100, 'task_indices': [cursor, cursor + 100], **intervals,
                          'acl_event_us': elapsed,
                          'event_minus_task_span_us': elapsed - intervals['first_last_span_us'],
                          'span_minus_kernel_sum_us': intervals['first_last_span_us'] - intervals['kernel_sum_us'],
                          'ratio_to_cycle_event_median': sample['elapsed_ms'] / median,
                          'descriptive_tail': sample['elapsed_ms'] / median > 1.10,
                          'enqueue_wall_ns': sample['enqueue_after_ns'] - sample['enqueue_before_ns'],
                          'enqueue_thread_cpu_ns': sample['thread_cpu_enqueue_after_ns'] - sample['thread_cpu_enqueue_before_ns'],
                          'native_started_monotonic_ns': sample['started_monotonic_ns'],
                          'native_finished_monotonic_ns': sample['finished_monotonic_ns']})
            cursor += 100
    require(cursor == expected - 2 and len(spans) == pairs * 2, 'sample-to-task partition differs')
    return spans


def replay_submission_diagnosis(directory, anchor_path):
    directory = Path(directory).resolve(strict=True); evidence = Evidence()
    anchor = evidence.json(anchor_path); frozen = evidence.json(directory / 'freeze.json')
    require(anchor['purpose'] == 'preregistered_submission_stall_diagnosis'
            and anchor['freeze'] == binding(directory / 'freeze.json'), 'diagnostic trusted anchor differs')
    for path, digest in frozen['files'].items():
        evidence.bind({'path': path, 'sha256': digest})
    plan = read(directory / 'plan-final.json'); started = evidence.json(directory / 'started.json')
    require(started['anchor'] == binding(anchor_path) and started['freeze'] == binding(directory / 'freeze.json')
            and frozen['created_at'] < started['started_at'], 'diagnostic registration chronology differs')
    terminal = evidence.json(directory / 'terminal.json')
    require(terminal['status'] == 'complete_diagnostic_only' and terminal['accepted'] is False
            and terminal['resampling'] == 'none' and set(terminal['slots']) == set(plan['order']), 'diagnostic roster not complete')
    receipts = []; pids = []
    for cycle in range(6):
        slot = terminal['slots'][f'observe-{cycle}']; evidence.bind(slot['receipt'])
        location = directory / f'observe-{cycle}'; receipt = read(slot['receipt']['path'])
        require(slot['status'] == 'completed_diagnostic_only' and receipt['exit_status'] == 0
                and receipt['accepted'] is False and receipt['cycle'] == cycle and receipt['pairs'] == 500,
                'diagnostic observation is incomplete')
        for key in ('stdout', 'stderr'):
            evidence.bind(receipt[key])
        messages = native_messages(location / 'stdout.log')
        require(messages == receipt['messages'], 'native stdout and observation receipt disagree')
        prior.validate_messages(messages, cycle, 500)
        require([r['command'] for r in receipt['receipts']] == prior.commands(500), 'actual command roster differs')
        require(receipt['argv'] == [v.replace('{cycle_dir}', str(location)) for v in plan['case']['command']],
                'native executable or input changed')
        require(started['started_at'] <= receipt['started_at'] < receipt['finished_at'] <= terminal['finished_at'],
                'observation outside fixed campaign')
        verify_oracles(plan, location, receipt['verifications'], evidence)
        receipts.append(receipt); pids.append(messages[0]['pid'])
    require(len(set(pids)) == 6, 'observations did not use six fresh native processes')
    summary = prior.summarize(receipts)
    require(evidence.json(directory / 'descriptive-summary.json') == summary, 'descriptive statistics do not replay')
    timeline_ref = terminal['slots']['independent-profile']['timeline']; evidence.bind(timeline_ref)
    timeline = read(timeline_ref['path'])
    for key in ('table', 'execution', 'stdout'):
        evidence.bind(timeline[key])
    messages = native_messages(timeline['stdout']['path']); prior.validate_messages(messages, 0, 5)
    spans = task_spans(timeline['table']['path'], messages, 5)
    for original, derived in zip(timeline['spans'], spans):
        require(all(original[k] == derived[k] for k in ('pair_index', 'role', 'task_indices', 'task_count',
                                                       'kernel_sum_us', 'first_last_span_us', 'maximum_intertask_gap_us', 'acl_event_us')),
                'short independent task timeline differs')
    require(len(spans) == len(timeline['spans']) == 10 and timeline['complete_kernel_tasks'] == 1422,
            'short independent task count differs')
    verify_oracles(plan, directory / 'independent-profile', timeline['verifications'], evidence)
    execution = evidence.json(directory / 'diagnostic-job/execution.json')
    require(execution['exit_code'] == 0, 'diagnostic outer execution failed')
    return {'schema_version': 1, 'purpose': 'submission_diagnostic_readonly_replay', 'valid': True, 'accepted': False,
            'anchor': binding(anchor_path), 'freeze': binding(directory / 'freeze.json'), 'native_cycles': 6,
            'observation_events': 6000, 'observation_pairs': 3000, 'independent_task_count': 1422,
            'complete_kernel_calls': 603954, 'independent_oracles': 14, 'wall_seconds': execution['duration_seconds'],
            'summary': summary, 'independent_spans': spans, 'files': evidence.files}


def prepare(output, predecessor, predecessor_anchor):
    output.mkdir(exist_ok=False)
    previous = replay_submission_diagnosis(predecessor, predecessor_anchor)
    save_new(output / 'predecessor-replay.json', previous)
    old_plan = read(predecessor / 'plan-final.json'); frozen = read(predecessor / 'freeze.json')
    command_file = output / 'commands.txt'
    with command_file.open('x') as stream:
        stream.write('\n'.join(prior.commands(500)) + '\n')
    slots = []
    for cycle in range(6):
        location = output / f'profile-{cycle}'
        application = [v.replace('{cycle_dir}', str(location)) for v in old_plan['case']['command']]
        env = dict(BASE_ENVIRONMENT, APROF_SHARED_CYCLE=str(cycle), APROF_SUBMISSION_DIAGNOSTIC_MODE='observe',
                   APROF_SHARED_COMMANDS=str(command_file))
        slots.append({'slot_id': f'profile-{cycle}', 'cycle': cycle, 'application': application,
                      'argv': [frozen['profiler'], '--output=' + str(location / 'profile'), *PROFILE_FLAGS,
                               '--application=' + shlex.join(application)], 'environment': env,
                      'output': str(location), 'expected_tasks': 100422, 'pairs': 500})
    files = dict(frozen['files'])
    files.update(previous['files'])
    for path in [Path(__file__), Path(prior.__file__), predecessor / 'plan-final.json', predecessor / 'freeze.json',
                 predecessor_anchor, predecessor / 'terminal.json', predecessor / 'descriptive-summary.json',
                 output / 'predecessor-replay.json', command_file]:
        files[str(path.resolve())] = binding(path)['sha256']
    plan = {'schema_version': 1, 'purpose': 'long_task_tail_diagnosis_only', 'created_at': time.time(),
            'predecessor': str(predecessor), 'predecessor_anchor': binding(predecessor_anchor),
            'predecessor_replay': binding(output / 'predecessor-replay.json'), 'native_plan': old_plan,
            'slots': slots, 'max_attempts_per_slot': 1, 'resampling': 'none', 'pairs_per_cycle': 500,
            'event_count': 6000, 'total_kernel_tasks': 602532, 'cpu_affinity': old_plan['cpu_affinity'],
            'failure_policy': 'First execution, identity, task completeness, or oracle failure stops remaining slots; timing tails never removed.',
            'tail_definition': 'event / median(all 1000 events within its fresh process) > 1.10; descriptive only',
            'clock_rule': 'Ordered 100-task groups; never equate native monotonic and profiler UTC origins.',
            'profile_perturbation': 'Report profiled distribution against all earlier unprofiled cycles; this is not a formal performance estimate.',
            'command_delivery': 'Explicit complete command file; native stdout is captured by msprof/run_aprof_job between pairs.',
            'decision': 'No reproduced tail is inconclusive. No retry, publication admission, or gate relaxation.',
            'estimated_profile_storage_bytes': 2100000000, 'files': files}
    save_new(output / 'plan.json', plan)


def capture(plan, slot):
    from run_aprof_job import run as run_job
    location = Path(slot['output']); location.mkdir(exist_ok=False)
    native_plan = plan['native_plan']
    job = {'job_id': slot['slot_id'], 'argv': slot['argv'], 'cwd': native_plan['source_dir'],
           'output_dir': str(location / 'job'), 'timeout_seconds': 1800, 'environment': slot['environment']}
    save_new(location / 'job.json', job)
    execution = run_job(job); require(execution['exit_code'] == 0, 'long profiler execution failed')
    messages = native_messages(location / 'job/stdout.log'); prior.validate_messages(messages, slot['cycle'], 500)
    verifications = prior.oracle(native_plan, location)
    tables = list((location / 'profile').rglob('op_summary*.csv'))
    if not tables:
        roots = list((location / 'profile').glob('PROF_*')); require(len(roots) == 1, 'ambiguous long profiler output')
        job = dict(job, job_id=slot['slot_id'] + '-export', output_dir=str(location / 'export-job'),
                   argv=[slot['argv'][0], '--export=on', '--type=text', '--output=' + str(roots[0])])
        save_new(location / 'export-job.json', job)
        require(run_job(job)['exit_code'] == 0, 'long task export failed')
        tables = list((location / 'profile').rglob('op_summary*.csv'))
    require(len(tables) == 1, 'long task table absent or ambiguous')
    spans = task_spans(tables[0], messages, 500)
    report = {'schema_version': 1, 'purpose': plan['purpose'], 'cycle': slot['cycle'], 'accepted': False,
              'table': binding(tables[0]), 'stdout': binding(location / 'job/stdout.log'),
              'execution': binding(location / 'job/execution.json'), 'native_pid': messages[0]['pid'],
              'verifications': verifications, 'complete_kernel_tasks': 100422, 'spans': spans,
              'descriptive_tails': [s for s in spans if s['descriptive_tail']]}
    save_new(location / 'timeline.json', report)
    return report


def run(output, anchor_path):
    plan = read(output / 'plan.json'); anchor = read(anchor_path)
    require(anchor['purpose'] == 'preregistered_long_task_tail_diagnosis' and anchor['plan'] == binding(output / 'plan.json'),
            'long timeline trusted anchor differs')
    require(sorted(os.sched_getaffinity(0)) == plan['cpu_affinity'], 'CPU affinity changed')
    for path, digest in plan['files'].items():
        require(binding(path)['sha256'] == digest, 'frozen long timeline input changed')
    save_new(output / 'started.json', {'started_at': time.time(), 'anchor': binding(anchor_path), 'plan': binding(output / 'plan.json')})
    terminal = {'accepted': False, 'resampling': 'none', 'slots': {}}
    try:
        with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]):
            for slot in plan['slots']:
                name = slot['slot_id']; started = time.time()
                capture(plan, slot)
                terminal['slots'][name] = {'status': 'completed_diagnostic_only', 'started_at': started, 'finished_at': time.time(),
                                           'timeline': binding(Path(slot['output']) / 'timeline.json')}
                print(f'completed {name}: 500 pairs and 100422 complete tasks retained', flush=True)
        terminal['status'] = 'complete_diagnostic_only'
    except Exception as error:
        terminal.update(status='failed', error=str(error))
        for slot in plan['slots']:
            terminal['slots'].setdefault(slot['slot_id'], {'status': 'failed' if Path(slot['output']).exists() else 'not_run'})
        raise
    finally:
        terminal['finished_at'] = time.time(); save_new(output / 'terminal.json', terminal)


def replay(output, anchor_path):
    evidence = Evidence(); plan = evidence.json(output / 'plan.json'); anchor = evidence.json(anchor_path)
    require(anchor['purpose'] == 'preregistered_long_task_tail_diagnosis' and anchor['plan'] == binding(output / 'plan.json'),
            'long timeline trusted anchor differs')
    for path, digest in plan['files'].items():
        evidence.bind({'path': path, 'sha256': digest})
    previous = replay_submission_diagnosis(Path(plan['predecessor']), Path(plan['predecessor_anchor']['path']))
    require(read(plan['predecessor_replay']['path']) == previous, 'predecessor diagnosis changed')
    started = evidence.json(output / 'started.json'); terminal = evidence.json(output / 'terminal.json')
    require(started['anchor'] == binding(anchor_path) and started['plan'] == binding(output / 'plan.json')
            and plan['created_at'] < started['started_at'] <= terminal['finished_at'], 'long timeline chronology differs')
    require(terminal['status'] == 'complete_diagnostic_only' and terminal['accepted'] is False
            and set(terminal['slots']) == {s['slot_id'] for s in plan['slots']}, 'long timeline roster incomplete')
    pids = []; all_spans = []; per_cycle = []
    for slot in plan['slots']:
        location = Path(slot['output']); row = terminal['slots'][slot['slot_id']]
        require(row['status'] == 'completed_diagnostic_only', 'long timeline slot failed')
        evidence.bind(row['timeline']); report = read(row['timeline']['path'])
        for key in ('table', 'stdout', 'execution'):
            evidence.bind(report[key])
        execution = read(report['execution']['path'])
        require(execution['exit_code'] == 0 and execution['job']['argv'] == slot['argv']
                and execution['job']['environment'] == slot['environment'], 'actual profiler invocation differs')
        messages = native_messages(report['stdout']['path']); prior.validate_messages(messages, slot['cycle'], 500)
        require(messages[0]['cpu_affinity'] == plan['cpu_affinity'], 'native CPU mask changed')
        spans = task_spans(report['table']['path'], messages, 500)
        require(report['spans'] == spans and report['descriptive_tails'] == [s for s in spans if s['descriptive_tail']],
                'long task decomposition does not replay')
        verify_oracles(plan['native_plan'], location, report['verifications'], evidence)
        pids.append(messages[0]['pid'])
        all_spans.extend(dict(s, cycle=slot['cycle']) for s in spans)
        per_cycle.append({'cycle': slot['cycle'], 'events': 1000,
                          'median_event_us': statistics.median(s['acl_event_us'] for s in spans),
                          'median_kernel_sum_us': statistics.median(s['kernel_sum_us'] for s in spans),
                          'tail_count': sum(s['descriptive_tail'] for s in spans)})
    require(len(set(pids)) == 6 and len(all_spans) == 6000, 'long timeline fresh process/event count differs')
    unprofiled = [s['elapsed_ms'] * 1000 for s in previous['summary']['events']]
    result = {'schema_version': 1, 'purpose': plan['purpose'], 'valid': True, 'accepted': False, 'resampling': 'none',
              'anchor': binding(anchor_path), 'plan': binding(output / 'plan.json'), 'events': 6000, 'kernel_tasks': 602532,
              'per_cycle': per_cycle, 'tail_events': [s for s in all_spans if s['descriptive_tail']],
              'profiled_median_event_us': statistics.median(s['acl_event_us'] for s in all_spans),
              'unprofiled_median_event_us': statistics.median(unprofiled),
              'all_event_spans': all_spans, 'files': evidence.files,
              'limitations': 'Separate profiled/unprofiled processes are not paired causal observations. Profiling changes the measurement apparatus; results are never formal performance estimates.'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'replay', 'replay-predecessor'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path)
    parser.add_argument('--anchor', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(); output = args.output.resolve()
    if args.action == 'prepare': prepare(output, args.predecessor.resolve(), args.anchor.resolve())
    elif args.action == 'run': run(output, args.anchor.resolve())
    else:
        result = replay_submission_diagnosis(output, args.anchor.resolve()) if args.action == 'replay-predecessor' else replay(output, args.anchor.resolve())
        save_new(args.report, result)
        print(json.dumps({'valid': result['valid'], 'accepted': result['accepted'], 'report': binding(args.report)}))


if __name__ == '__main__':
    main()
