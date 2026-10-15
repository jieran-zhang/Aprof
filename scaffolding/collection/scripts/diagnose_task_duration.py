#!/usr/bin/env python3
"""One Task-only exp case-10 capture; diagnostic evidence, never admission."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
from decimal import Decimal
import os
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import time

from run_aprof_job import run as job_run
from run_shared_timing_confirmation import (BASE_ENVIRONMENT, ROOT, RELEASE, binding,
    locks, native_messages, production_oracle, save_new, task_counts, timeline_protocol, timeline_spans)
from qualify_shared_timing_v051 import protocol_commands, source_files
from replay_timing_diagnosis import Evidence, digest, read, require

PURPOSE = 'exp_case10_task_only_diagnostic_not_admission'
PRIOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014'
PREDECESSOR = PRIOR / 'production-confirmation-duration-v2'
ENQUEUE = PRIOR / 'long-enqueue-diagnostic-20261014'
FLAGS = ['--task-time=l1', '--ai-core=off', '--ascendcl=off', '--runtime-api=off',
         '--ge-api=off', '--aicpu=off', '--type=text']
CASE, REPEAT, TASKS = 10, 7300, 220222


def verify(files, evidence=None):
    for path, expected in files.items():
        if evidence is None:
            require(digest(path) == expected, 'frozen file changed: ' + path)
        else:
            evidence.bind(path, expected)


def prepare(output):
    output = Path(output).resolve()
    require(not output.exists(), 'diagnostic directory already exists; no retry')
    config_path = PREDECESSOR / 'exp/config.json'; config = read(config_path)
    case = next(c for c in config['cases'] if c['case_id'] == CASE)
    require(config['build']['binary'] == str(PREDECESSOR / 'exp/source/build/exp'), 'original production binary required')
    require(case['workload']['shape'] == [2049, 513] and case['workload']['dtype'] == 'float16'
            and case['workload']['numel'] == 1051137, 'original case differs')
    require(read(PREDECESSOR / 'exp/confirmation/registration.json')['repeat_by_case'][str(CASE)] == REPEAT,
            'original frozen repeat differs')
    profiler = Path(shutil.which('msprof')).resolve(strict=True)
    output.mkdir(parents=True); commands = output / 'commands.txt'
    commands.write_text('\n'.join(protocol_commands()) + '\n')
    native = output / 'native'
    argv = [x.replace('{cycle_dir}', str(native)) for x in case['command']]
    env = dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_CYCLE='0',
               APROF_SHARED_MODE='confirmation', APROF_SHARED_REPEAT=str(REPEAT), APROF_SHARED_COMMANDS=str(commands))
    collector = RELEASE / 'skills/ascendc-aprof-profiling/scripts/device_shared_timing.py'
    tree = ast.parse(collector.read_text())
    producers = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PRODUCERS' for t in n.targets))
    history = [PREDECESSOR / name for name in ('plan.json', 'freeze.json', 'roster.json', 'campaign/campaign.json')]
    history += [ENQUEUE / name for name in ('plan.json', 'freeze.json', 'terminal.json', 'analysis-report.json',
                'independent-replay-with-anchor.json')]
    history += [PRIOR / 'measurement-method-v2-source-archive-20261014/index.json']
    source = Path(config['build']['source_dir'])
    files = [config_path, Path(config['build']['binary']), *map(Path, config['build']['receipt_files']),
             *map(Path, case['prepared_files']), *[source / name for name in source_files(source)],
             *[RELEASE / p for p in producers], *history, commands, profiler, Path(__file__)]
    files += [Path(__file__).with_name(name) for name in ('run_aprof_job.py', 'run_shared_timing_confirmation.py',
              'qualify_shared_timing_v051.py', 'replay_timing_diagnosis.py')]
    previous = read(PREDECESSOR / 'plan.json')['frozen_files'] | read(PREDECESSOR / 'freeze.json')['frozen_files']
    for path in (config_path, Path(config['build']['binary']), *map(Path, case['prepared_files']),
                 *[source / name for name in source_files(source)]):
        require(str(path) in previous and digest(path).removeprefix('sha256:') ==
                previous[str(path)].removeprefix('sha256:'), 'production source/input changed: ' + str(path))
    plan = {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(), 'config': binding(config_path),
            'case': case, 'repeat': REPEAT, 'cycle': 0, 'events': 30, 'complete_kernel_tasks': TASKS,
            'command_file': binding(commands), 'native_argv': argv, 'environment': env,
            'capture_job': {'job_id': 'exp10-task-only-once', 'argv': [str(profiler), '--output=' + str(output / 'profile'),
                            *FLAGS, '--application=' + shlex.join(argv)], 'cwd': config['build']['source_dir'],
                            'output_dir': str(output / 'capture-job'), 'timeout_seconds': 600, 'environment': env},
            'policy': {'max_attempts': 1, 'resampling': 'none', 'export_timeout': 300, 'oracle_timeout': 120,
                       'outer_timeout': 1200, 'accepted': False, 'publication_acceptance': False},
            'files': {str(p.resolve()): digest(p) for p in files}, 'history': [binding(p) for p in history]}
    save_new(output / 'plan.json', plan)
    return binding(output / 'plan.json')


def checked_plan(output, evidence=None):
    plan = read(output / 'plan.json'); config = read(plan['config']['path'])
    case = next(c for c in config['cases'] if c['case_id'] == CASE)
    require(plan['purpose'] == PURPOSE and plan['case'] == case and plan['repeat'] == REPEAT
            and plan['cycle'] == 0 and plan['events'] == 30 and plan['complete_kernel_tasks'] == TASKS
            and plan['policy'] == {'max_attempts': 1, 'resampling': 'none', 'export_timeout': 300,
                'oracle_timeout': 120, 'outer_timeout': 1200, 'accepted': False, 'publication_acceptance': False},
            'fixed diagnostic scope differs')
    require(binding(plan['config']['path']) == plan['config'] and
            binding(output / 'commands.txt') == plan['command_file'] and
            (output / 'commands.txt').read_text().splitlines() == protocol_commands(), 'config or command file differs')
    argv = [x.replace('{cycle_dir}', str(output / 'native')) for x in case['command']]
    env = dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_CYCLE='0', APROF_SHARED_MODE='confirmation',
               APROF_SHARED_REPEAT=str(REPEAT), APROF_SHARED_COMMANDS=str(output / 'commands.txt'))
    job = plan['capture_job']
    require(plan['native_argv'] == argv and plan['environment'] == env and job == {
        'job_id': 'exp10-task-only-once', 'argv': [job['argv'][0], '--output=' + str(output / 'profile'),
            *FLAGS, '--application=' + shlex.join(argv)], 'cwd': config['build']['source_dir'],
        'output_dir': str(output / 'capture-job'), 'timeout_seconds': 600, 'environment': env}, 'capture contract differs')
    verify(plan['files'], evidence)
    return plan, config


def freeze(output):
    output = Path(output).resolve(strict=True)
    require(not (output / 'freeze.json').exists(), 'already frozen')
    plan, _ = checked_plan(output)
    save_new(output / 'freeze.json', {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(),
        'plan': binding(output / 'plan.json'), 'files': plan['files'], 'accepted': False})
    return binding(output / 'freeze.json')


def anchored(output, anchor_path, latest, evidence=None):
    frozen = read(output / 'freeze.json'); anchor_path = Path(anchor_path).resolve(strict=True)
    anchor = read(anchor_path); stamp = datetime.fromisoformat(anchor['recorded_at_utc'])
    require(anchor_path.parent == ROOT / 'scaffolding/curation' and anchor == {
        'schema_version': 1, 'purpose': PURPOSE, 'freeze': binding(output / 'freeze.json'),
        'max_attempts': 1, 'resampling': 'none', 'recorded_at_utc': anchor['recorded_at_utc']}
        and stamp.tzinfo is not None and frozen['created_at'] <= stamp.timestamp() <= latest,
        'root preregistration anchor differs')
    require(frozen['plan'] == binding(output / 'plan.json') and frozen['accepted'] is False, 'freeze differs')
    plan, config = checked_plan(output, evidence)
    require(frozen['files'] == plan['files'], 'frozen inventory differs')
    return plan, config


def summary(table, messages, config):
    timeline_protocol(messages, config, REPEAT)
    spans = timeline_spans(table, messages, 'exp')
    for row in spans:
        tasks = row.pop('tasks')
        durations = [float(t['Task Duration(us)']) for t in tasks]
        gaps = [float((Decimal(b['Task Start Time(us)']) - Decimal(a['Task Start Time(us)'])
                       - Decimal(a['Task Duration(us)'])) * 1000) for a, b in zip(tasks, tasks[1:])]
        row.update(task_duration_us={'min': min(durations), 'median': statistics.median(durations),
            'mean': statistics.fmean(durations), 'max': max(durations)}, maximum_gap_ns=max(gaps),
            host_wall_ns=row['native_finished_monotonic_ns'] - row['native_started_monotonic_ns'],
            event_minus_span_ns=row['acl_event_range_ns'] - row['first_last_kernel_span_ns'],
            span_minus_task_sum_ns=row['first_last_kernel_span_ns'] - row['kernel_total_duration_ns'])
    return {'purpose': PURPOSE, 'accepted': False, 'publication_acceptance': False, 'repeat': REPEAT,
            'complete_kernel_tasks': sum(task_counts(REPEAT).values()), 'events': len(spans), 'samples': spans,
            'scope': 'The 30 event groups are summarized; the complete unfiltered task CSV remains the evidence.',
            'interpretation': 'Same-capture Task Duration, task gaps, event and host wall only; no formal gain or explanation of unprofiled tails.'}


def oracle(native, role, case, cwd):
    argv = [x.replace('{cycle_dir}', str(native)) for x in case['verify_commands'][role]]
    row = {'argv': argv, 'started_at': time.time(), 'exit_status': None, 'status': 'failed'}
    try:
        row['output_sha256'] = digest(native / f'{role}.bin')
        with (native / f'{role}-verify.log').open('xb') as log:
            done = subprocess.run(argv, cwd=cwd, env=dict(os.environ, **BASE_ENVIRONMENT),
                                  stdout=log, stderr=subprocess.STDOUT, timeout=120)
        row['exit_status'] = done.returncode
        require(done.returncode == 0 and digest(native / f'{role}.bin') == row['output_sha256'], 'native oracle failed')
        row['status'] = 'passed'
    except BaseException as error:
        row['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        row['finished_at'] = time.time()
        for key, path in [('log_sha256', native / f'{role}-verify.log'), ('output_after_sha256', native / f'{role}.bin')]:
            if path.is_file(): row[key] = digest(path)
        save_new(native / f'{role}-verify-receipt.json', row)
    return row


def run(output, anchor):
    output = Path(output).resolve(strict=True)
    plan, config = anchored(output, anchor, time.time())
    save_new(output / 'started.json', {'at': time.time(), 'anchor': binding(anchor), 'freeze': binding(output / 'freeze.json')})
    terminal = {'purpose': PURPOSE, 'accepted': False, 'publication_acceptance': False, 'status': 'failed'}
    receipt = {'argv': plan['native_argv'], 'started_at': time.time(), 'verifications': {}}
    try:
        with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]):
            native = output / 'native'; native.mkdir(exist_ok=False)
            save_new(output / 'capture-job.json', plan['capture_job'])
            execution = job_run(plan['capture_job']); terminal['capture'] = binding(output / 'capture-job/execution.json')
            shutil.copyfile(output / 'capture-job/stdout.log', native / 'stdout.log')
            require(execution['exit_code'] == 0, 'Task-only capture failed; no retry or flag change')
            messages = native_messages(native / 'stdout.log'); timeline_protocol(messages, config, REPEAT)
            tables = list((output / 'profile').rglob('op_summary*.csv'))
            if not tables:
                profiles = list((output / 'profile').glob('PROF_*'))
                require(len(profiles) == 1, 'ambiguous profile output')
                export = dict(plan['capture_job'], job_id='exp10-task-only-export', output_dir=str(output / 'export-job'),
                    timeout_seconds=300, argv=[plan['capture_job']['argv'][0], '--export=on', '--type=text', '--output=' + str(profiles[0])])
                save_new(output / 'export-job.json', export)
                require(job_run(export)['exit_code'] == 0, 'Task-only export failed')
                tables = list((output / 'profile').rglob('op_summary*.csv'))
            require(len(tables) == 1, 'expected exactly one complete task table')
            result = summary(tables[0], messages, config); terminal['table'] = binding(tables[0])
            for role in ('baseline', 'candidate'):
                receipt['verifications'][role] = oracle(native, role, plan['case'], config['build']['source_dir'])
            receipt['finished_at'] = time.time()
            for role in ('baseline', 'candidate'):
                production_oracle(native, role, plan['case'], receipt, Evidence())
            verify(plan['files']); save_new(output / 'summary.json', result)
            terminal.update(status='complete_diagnostic_only', summary=binding(output / 'summary.json'))
    except BaseException as error:
        terminal['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        for role in ('baseline', 'candidate'):
            path = output / 'native' / f'{role}-verify-receipt.json'
            if path.is_file(): receipt['verifications'][role] = read(path)
        receipt['finished_at'] = time.time(); save_new(output / 'native-receipt.json', receipt)
        terminal['finished_at'] = time.time(); terminal['native'] = binding(output / 'native-receipt.json')
        save_new(output / 'terminal.json', terminal)
    return terminal


def execution_interval(execution, expected, earliest, latest, evidence):
    start, finish = [datetime.fromisoformat(execution[k].replace('Z', '+00:00')).timestamp()
                     for k in ('started_at', 'finished_at')]
    require(execution['job'] == expected and execution['exit_code'] == 0 and execution['status'] == 'passed'
            and earliest <= start <= finish <= latest
            and 0 <= execution['duration_seconds'] <= expected['timeout_seconds'], 'execution identity/time differs')
    for key in ('stdout', 'stderr'):
        evidence.bind(execution[key]['path'], execution[key]['sha256'])
    return finish


def replay(output, anchor, *, source_archive_refs=None):
    if source_archive_refs is None:
        evidence = Evidence()
    else:
        from measurement_source_archive import HistoricalEvidence
        evidence = HistoricalEvidence(source_archive_refs, logical_paths=True)
    output = Path(output).resolve(strict=True); started = read(output / 'started.json')
    plan, config = anchored(output, anchor, started['at'], evidence if source_archive_refs is not None else None)
    terminal = read(output / 'terminal.json')
    require(started['anchor'] == binding(anchor) and started['freeze'] == binding(output / 'freeze.json'), 'run anchor differs')
    require(terminal['status'] == 'complete_diagnostic_only' and terminal['accepted'] is False, 'diagnostic incomplete')
    execution = evidence.json(output / 'capture-job/execution.json')
    require(terminal['capture'] == binding(output / 'capture-job/execution.json'), 'capture reference differs')
    end = execution_interval(execution, plan['capture_job'], started['at'], terminal['finished_at'], evidence)
    native = output / 'native'; require(digest(native / 'stdout.log') == execution['stdout']['sha256'], 'native stdout differs')
    tables = list((output / 'profile').rglob('op_summary*.csv'))
    require(len(tables) == 1 and binding(tables[0]) == terminal['table'], 'task table changed')
    result = summary(tables[0], native_messages(native / 'stdout.log'), config)
    require(read(output / 'summary.json') == result and binding(output / 'summary.json') == terminal['summary'], 'summary differs')
    receipt = read(output / 'native-receipt.json'); require(binding(output / 'native-receipt.json') == terminal['native'], 'oracle receipt differs')
    require(receipt['argv'] == plan['native_argv'] and set(receipt['verifications']) == {'baseline', 'candidate'}, 'native/oracle identity differs')
    if (output / 'export-job/execution.json').exists():
        exported = evidence.json(output / 'export-job/execution.json')
        expected = dict(plan['capture_job'], job_id='exp10-task-only-export', output_dir=str(output / 'export-job'),
            timeout_seconds=300, argv=[plan['capture_job']['argv'][0], '--export=on', '--type=text', '--output=' + str(tables[0].parents[1])])
        end = execution_interval(exported, expected, end, terminal['finished_at'], evidence)
    for role in ('baseline', 'candidate'):
        row = receipt['verifications'][role]
        require(row == evidence.json(native / f'{role}-verify-receipt.json') and row['status'] == 'passed'
                and end <= row['started_at'] <= row['finished_at'] <= terminal['finished_at']
                and row['finished_at'] - row['started_at'] <= 120
                and row['output_after_sha256'] == row['output_sha256'], 'oracle receipt/time differs')
        production_oracle(native, role, plan['case'], receipt, evidence); end = row['finished_at']
    result = {'complete_diagnostic_only': True, 'accepted': False, 'publication_acceptance': False,
              'events': 30, 'complete_kernel_tasks': TASKS, 'summary': terminal['summary'], 'files': evidence.files}
    if source_archive_refs is not None:
        result.update(eligible_for_publication=False, resolved_producers=evidence.resolved_files,
                      source_archives=source_archive_refs)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'freeze', 'run', 'replay'))
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--anchor', type=Path)
    args = parser.parse_args()
    if args.action in ('run', 'replay'):
        require(args.anchor is not None, 'root anchor required')
    result = {'prepare': lambda: prepare(args.output), 'freeze': lambda: freeze(args.output),
              'run': lambda: run(args.output, args.anchor), 'replay': lambda: replay(args.output, args.anchor)}[args.action]()
    print(__import__('json').dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
