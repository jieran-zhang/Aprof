#!/usr/bin/env python3
"""Once-only exp case-1 baseline prewarm diagnosis; never publication evidence."""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime
from io import StringIO
import json
import os
from pathlib import Path
import shlex
import shutil
import statistics
import sys
import time

from run_aprof_job import run as job_run
from run_shared_timing_confirmation import (BASE_ENVIRONMENT, ROOT, RELEASE, binding,
    locks, native_messages, production_oracle, save_new, timeline_protocol)
from qualify_shared_timing_v051 import protocol_commands, source_files
from qualify_task_timing_v051 import FLAGS, task_modules
from diagnose_task_duration import execution_interval, oracle
from replay_timing_diagnosis import Evidence, digest, read, require

PURPOSE = 'exp_case1_baseline_prewarm_diagnostic_only'
PREDECESSOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2/exp'
PARENT = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-task-confirmation-v2-local'
MARKER = '    const uint64_t warmup_started = Now();\n'
PREWARM_PREFIX = 'APROF_PREWARM_JSON:'
BATCHES, CALLS, PREFIX_TASKS, ORIGINAL_TASKS = 25, 400, 10000, 4222
SLOT_BUDGET = 1500
MATRIX = [(cycle, arm) for cycle in range(6)
          for arm in (('A', 'B') if cycle % 2 == 0 else ('B', 'A'))]


def slot_id(cycle, arm):
    require(type(cycle) is int and 0 <= cycle < 6 and arm in ('A', 'B'), 'unknown diagnostic slot')
    return f'cycle-{cycle}-{arm}'


def prewarm_patch(header):
    """Insert one diagnostic block into the exact old header, leaving all other bytes."""
    require(header.count(MARKER) == 1, 'prewarm insertion marker is not unique')
    block = r'''    if (mode != "confirmation" || kRepeat != 100 || std::string(operator_name) != "exp"
            || baseline_launches != 1 || candidate_launches != 1)
        throw std::invalid_argument("fixed exp diagnostic identity differs");
    const uint64_t prewarm_started = Now();
    std::ostringstream prewarm_report;
    prewarm_report << "APROF_PREWARM_JSON:{\"schema_version\":1,\"protocol\":\"exp_baseline_prewarm_v1\""
        << ",\"operator\":\"exp\",\"cycle_index\":" << cycle_index
        << ",\"pid\":" << identity.pid << ",\"device\":" << identity.device
        << ",\"context_address\":" << Address(identity.context)
        << ",\"stream_address\":" << Address(stream)
        << ",\"baseline_calls\":10000,\"batch_count\":25,\"calls_per_batch\":400"
        << ",\"started_monotonic_ns\":" << prewarm_started << ",\"batches\":[";
    for (int batch = 0; batch < 25; ++batch) {
        const uint64_t began = Now();
        for (int call = 0; call < 400; ++call) baseline(stream, buffers);
        Check(aclrtSynchronizeStream(stream), "prewarm batch synchronize");
        const uint64_t ended = Now();
        if (batch) prewarm_report << ',';
        prewarm_report << "{\"batch_index\":" << batch << ",\"calls\":400,\"cumulative_calls\":"
            << (batch + 1) * 400 << ",\"started_monotonic_ns\":" << began
            << ",\"finished_monotonic_ns\":" << ended << '}';
    }
    prewarm_report << "],\"finished_monotonic_ns\":" << Now() << '}';
    std::cout << prewarm_report.str() << std::endl;
    if (!std::cout) throw std::runtime_error("prewarm diagnostic output failed");
'''
    return header.replace(MARKER, block + MARKER)


def _case_and_failure():
    old = read(PREDECESSOR / 'config.json')
    parent = read(PARENT / 'exp/config.json')
    case = old['cases'][0]
    require(old['operator'] == parent['operator'] == 'exp'
            and old['expected_case_ids'] == parent['expected_case_ids'] == list(range(1, 21))
            and case['case_id'] == 1 and case == parent['cases'][0]
            and old['build'] == parent['build'] and old['roles'] == parent['roles'],
            'original exp case-1 kernel/input/oracle mapping changed')
    raw = read(PARENT / 'exp/confirmation/raw_measurements.json')
    terminal = read(PARENT / 'campaign/exp-confirmation/terminal.json')
    require(raw['complete'] is False and len(raw['sessions']) == 4
            and raw['error']['message'] == 'case 1 cycle 3: Task control failed'
            and terminal['status'] == 'failed', 'expected exp case-1 cycle-3 failure is absent')
    return old, case


def _source_proof(old_source, new_source):
    old_files, new_files = source_files(old_source), source_files(new_source)
    header = 'op_host/device_shared_timing.h'
    require(set(old_files) == set(new_files) and header in old_files,
            'B source bundle differs from original')
    require(all(new_files[name] == value for name, value in old_files.items() if name != header)
            and new_files[header] != old_files[header]
            and (new_source / header).read_text() == prewarm_patch((old_source / header).read_text()),
            'B changes more than the exact diagnostic header insertion')
    return {'original': old_files, 'diagnostic': new_files, 'only_changed_file': header,
            'marker': MARKER, 'prewarm_batches': BATCHES, 'calls_per_batch': CALLS}


def prepare(output):
    output = Path(output).resolve()
    require(not output.exists(), 'diagnostic directory already exists; no retry')
    config, case = _case_and_failure()
    old_source = Path(config['build']['source_dir'])
    require(config['build']['binary'] == str(PREDECESSOR / 'source/build/exp'),
            'A must use the original v2 binary')
    profiler = Path(shutil.which('msprof')).resolve(strict=True)
    scratch = Path('/tmp') / f'aprof-exp-prewarm-{output.name}'
    require(not scratch.exists() and not scratch.is_symlink(), 'diagnostic scratch path already exists')
    collector, _, _, _ = task_modules()
    mount = collector.select_mount(Path('/proc/self/mountinfo').read_text(), scratch)
    require(mount['filesystem_type'] in collector.LOCAL_PROFILE_FILESYSTEMS,
            'diagnostic scratch is not on a supported local filesystem')
    output.mkdir(parents=True, exist_ok=False)
    new_source = output / 'B/source'
    for name in source_files(old_source):
        target = new_source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_source / name, target)
    header = new_source / 'op_host/device_shared_timing.h'
    header.write_text(prewarm_patch(header.read_text()))
    proof = _source_proof(old_source, new_source)
    save_new(output / 'source-proof.json', proof)
    commands = output / 'commands.txt'
    commands.write_text('\n'.join(protocol_commands()) + '\n')
    parent_started = read(PARENT / 'campaign/started.json')
    require(parent_started['anchor'] == binding(parent_started['anchor']['path'])
            and parent_started['roster'] == binding(PARENT / 'roster.json'),
            'parent failure lacks its root-anchored roster')
    history = [PREDECESSOR / 'config.json', PREDECESSOR.parent / 'plan.json',
               PREDECESSOR.parent / 'freeze.json', PARENT / 'plan.json', PARENT / 'freeze.json',
               PARENT / 'roster.json', PARENT / 'campaign/started.json',
               Path(parent_started['anchor']['path']), PARENT / 'exp/config.json',
               PARENT / 'exp/confirmation/raw_measurements.json',
               PARENT / 'campaign/exp-confirmation/terminal.json']
    old_files = [old_source / name for name in proof['original']]
    old_files += [Path(config['build']['binary']), *map(Path, config['build']['receipt_files']),
                  *map(Path, case['prepared_files'])]
    plan = {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(),
            'publication_acceptance': False, 'accepted': False, 'case_id': 1,
            'matrix': [{'cycle': cycle, 'arm': arm, 'slot_id': slot_id(cycle, arm)} for cycle, arm in MATRIX],
            'slot_budget_seconds': SLOT_BUDGET, 'history': [binding(p) for p in history],
            'original_files': {str(p): digest(p) for p in old_files},
            'original_config': binding(PREDECESSOR / 'config.json'), 'case': case,
            'A_binary': binding(config['build']['binary']), 'B_source': str(new_source),
            'B_binary': str(new_source / 'build/exp'), 'source_proof': binding(output / 'source-proof.json'),
            'profiler': binding(profiler), 'interpreter': binding(Path(sys.executable).resolve(strict=True)),
            'commands': binding(commands), 'scratch_root': str(scratch),
            'flags': FLAGS, 'repeat': 100, 'prefix_tasks': PREFIX_TASKS,
            'original_tasks': ORIGINAL_TASKS, 'max_attempts': 1, 'resampling': 'none'}
    save_new(output / 'plan.json', plan)
    return binding(output / 'plan.json')


def _checked_plan(output):
    output = Path(output).resolve(strict=True)
    plan = read(output / 'plan.json')
    config, case = _case_and_failure()
    require(plan['purpose'] == PURPOSE and plan['case'] == case and plan['case_id'] == 1
            and plan['matrix'] == [{'cycle': c, 'arm': a, 'slot_id': slot_id(c, a)} for c, a in MATRIX]
            and plan['slot_budget_seconds'] == SLOT_BUDGET and plan['flags'] == FLAGS
            and plan['repeat'] == 100 and plan['prefix_tasks'] == PREFIX_TASKS
            and plan['original_tasks'] == ORIGINAL_TASKS and plan['max_attempts'] == 1
            and plan['resampling'] == 'none' and plan['accepted'] is False
            and plan['publication_acceptance'] is False, 'fixed diagnostic scope differs')
    require(plan['original_config'] == binding(PREDECESSOR / 'config.json')
            and plan['A_binary'] == binding(config['build']['binary'])
            and plan['B_source'] == str(output / 'B/source')
            and plan['B_binary'] == str(output / 'B/source/build/exp')
            and plan['commands'] == binding(output / 'commands.txt')
            and plan['source_proof'] == binding(output / 'source-proof.json'),
            'diagnostic source/config binding differs')
    require((output / 'commands.txt').read_text().splitlines() == protocol_commands(),
            'diagnostic native commands differ')
    proof = _source_proof(Path(config['build']['source_dir']), Path(plan['B_source']))
    require(proof == read(output / 'source-proof.json') and
            {str(Path(p)): digest(p) for p in plan['original_files']} == plan['original_files'],
            'original or B source changed')
    require(plan['profiler'] == binding(plan['profiler']['path'])
            and plan['interpreter'] == binding(plan['interpreter']['path'])
            and plan['scratch_root'] == str(Path('/tmp') / f'aprof-exp-prewarm-{output.name}'),
            'profiler/interpreter/scratch identity differs')
    for ref in plan['history']:
        require(binding(ref['path']) == ref, 'diagnostic predecessor evidence changed')
    return plan, config


def build(output):
    output = Path(output).resolve(strict=True)
    plan, _ = _checked_plan(output)
    require(not (output / 'B/build-receipt.json').exists(), 'B was already built')
    source = Path(plan['B_source'])
    result = {'purpose': PURPOSE, 'started_at': time.time(), 'status': 'failed',
              'plan': binding(output / 'plan.json'), 'commands': []}
    save_new(output / 'B/build-started.json', result)
    try:
        for index, argv in enumerate((['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                                      ['cmake', '--build', str(source / 'build'), '-j2'])):
            job = {'job_id': f'B-build-{index}', 'argv': argv, 'cwd': str(source),
                   'output_dir': str(output / 'B' / f'build-job-{index}'), 'timeout_seconds': 900,
                   'environment': BASE_ENVIRONMENT}
            execution = job_run(job)
            result['commands'].append(binding(Path(job['output_dir']) / 'execution.json'))
            require(execution['exit_code'] == 0, 'diagnostic B build failed')
        require(Path(plan['B_binary']).is_file() and not Path(plan['B_binary']).is_symlink(),
                'diagnostic B binary missing')
        _checked_plan(output)
        result.update(status='passed', binary=binding(plan['B_binary']))
    except BaseException as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        result['finished_at'] = time.time()
        save_new(output / 'B/build-receipt.json', result)
    return binding(output / 'B/build-receipt.json')


def freeze(output):
    output = Path(output).resolve(strict=True)
    require(not (output / 'freeze.json').exists(), 'diagnostic already frozen')
    plan, config = _checked_plan(output)
    built = read(output / 'B/build-receipt.json')
    require(built['status'] == 'passed' and built['binary'] == binding(plan['B_binary']),
            'B build receipt/binary differs')
    build_jobs = [output / 'B' / f'build-job-{index}' / 'execution.json' for index in range(2)]
    require(built['commands'] == [binding(path) for path in build_jobs]
            and all(read(path)['exit_code'] == 0 for path in build_jobs),
            'B fixed two-command CANN build evidence differs')
    source = Path(plan['B_source'])
    commands = (['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                ['cmake', '--build', str(source / 'build'), '-j2'])
    build_logs = []
    for index, path in enumerate(build_jobs):
        record = read(path)
        require(record['status'] == 'passed' and record['job'] == {
            'job_id': f'B-build-{index}', 'argv': commands[index], 'cwd': str(source),
            'output_dir': str(path.parent), 'timeout_seconds': 900, 'environment': BASE_ENVIRONMENT},
            'B CANN build command/environment differs')
        for role in ('stdout', 'stderr'):
            ref = record[role]
            require(ref == binding(ref['path']), 'B build log changed: ' + role)
            build_logs.append(Path(ref['path']))
    collector, _, _, _ = task_modules()
    files = [output / 'plan.json', output / 'commands.txt', output / 'source-proof.json',
             output / 'B/build-receipt.json', *build_jobs, *build_logs, Path(plan['B_binary']),
             *[Path(plan['B_source']) / name for name in source_files(plan['B_source'])],
             *[Path(p) for p in plan['original_files']],
             *[Path(ref['path']) for ref in plan['history']],
             Path(plan['profiler']['path']), Path(plan['interpreter']['path']), Path(__file__),
             *[RELEASE / name for name in collector.PRODUCER_FILES],
             *[Path(__file__).with_name(name) for name in (
                 'run_aprof_job.py', 'run_shared_timing_confirmation.py', 'qualify_shared_timing_v051.py',
                 'qualify_task_timing_v051.py', 'diagnose_task_duration.py', 'replay_timing_diagnosis.py')]]
    manifest = {str(path): digest(path) for path in files}
    require(all(manifest[path] == expected for path, expected in plan['original_files'].items()),
            'original kernel/input source changed')
    save_new(output / 'freeze.json', {'schema_version': 1, 'purpose': PURPOSE,
        'created_at': time.time(), 'plan': binding(output / 'plan.json'), 'frozen_files': manifest,
        'matrix': plan['matrix'], 'publication_acceptance': False, 'accepted': False})
    return binding(output / 'freeze.json')


def _checked_freeze(output, *, historical_evidence=None):
    plan, config = _checked_plan(output)
    frozen = read(output / 'freeze.json')
    require(frozen['purpose'] == PURPOSE and frozen['plan'] == binding(output / 'plan.json')
            and frozen['matrix'] == plan['matrix'] and frozen['accepted'] is False
            and frozen['publication_acceptance'] is False, 'diagnostic freeze differs')
    for path, expected in frozen['frozen_files'].items():
        if historical_evidence is None:
            require(digest(path) == expected, 'frozen diagnostic file changed: ' + path)
        else:
            historical_evidence.bind(path, expected)
    require(plan['B_binary'] in frozen['frozen_files']
            and str(Path(__file__).resolve()) in frozen['frozen_files'],
            'diagnostic binary/script is not frozen')
    return plan, config, frozen


def _anchored(output, anchor, *, historical_evidence=None):
    plan, config, frozen = _checked_freeze(output, historical_evidence=historical_evidence)
    anchor = Path(anchor).resolve(strict=True)
    value = read(anchor)
    recorded = datetime.fromisoformat(value['recorded_at_utc'])
    require(recorded.tzinfo is not None
            and anchor.parent == ROOT / 'scaffolding/curation'
            and value == {'schema_version': 1, 'purpose': PURPOSE,
                          'freeze': binding(output / 'freeze.json'),
                          'max_attempts': 1, 'resampling': 'none',
                          'recorded_at_utc': value['recorded_at_utc']}
            and frozen['created_at'] <= recorded.timestamp() <= time.time(),
            'root diagnostic anchor differs')
    return plan, config


def _remaining(deadline):
    left = deadline - time.monotonic()
    require(left > 0, 'diagnostic slot deadline exceeded')
    return left


def prewarm_receipt(stdout, messages, cycle, arm):
    """The B receipt is independent of the original 20 native messages."""
    lines = Path(stdout).read_text().splitlines()
    indices = [i for i, line in enumerate(lines) if line.startswith(PREWARM_PREFIX)]
    ready_indices = [i for i, line in enumerate(lines) if line.startswith('APROF_SHARED_TIMING_JSON:')]
    if arm == 'A':
        require(not indices, 'A unexpectedly ran diagnostic prewarm')
        return None
    require(len(indices) == 1 and ready_indices and indices[0] < ready_indices[0],
            'B prewarm receipt must precede original READY')
    row = json.loads(lines[indices[0]][len(PREWARM_PREFIX):])
    ready = messages[0]
    require(set(row) == {'schema_version', 'protocol', 'operator', 'cycle_index', 'pid', 'device',
                         'context_address', 'stream_address', 'baseline_calls', 'batch_count',
                         'calls_per_batch', 'started_monotonic_ns', 'finished_monotonic_ns',
                         'batches'}
            and row['schema_version'] == 1 and row['protocol'] == 'exp_baseline_prewarm_v1'
            and row['operator'] == 'exp' and row['cycle_index'] == cycle
            and all(type(row[key]) is int for key in ('cycle_index', 'pid', 'device',
                'baseline_calls', 'batch_count', 'calls_per_batch'))
            and row['baseline_calls'] == PREFIX_TASKS and row['batch_count'] == BATCHES
            and row['calls_per_batch'] == CALLS
            and all(row[key] == ready[key] for key in ('pid', 'device', 'context_address', 'stream_address')),
            'B prewarm identity/count/input receipt differs')
    batches = row['batches']
    require(isinstance(batches, list) and len(batches) == BATCHES
            and type(row['started_monotonic_ns']) is int
            and type(row['finished_monotonic_ns']) is int,
            'B prewarm batch cardinality or clocks differ')
    previous = row['started_monotonic_ns']
    for index, batch in enumerate(batches):
        require(set(batch) == {'batch_index', 'calls', 'cumulative_calls',
                               'started_monotonic_ns', 'finished_monotonic_ns'}
                and all(type(batch[key]) is int for key in batch)
                and batch['batch_index'] == index and batch['calls'] == CALLS
                and batch['cumulative_calls'] == (index + 1) * CALLS
                and type(batch['started_monotonic_ns']) is int
                and type(batch['finished_monotonic_ns']) is int
                and previous <= batch['started_monotonic_ns'] < batch['finished_monotonic_ns'],
                'B prewarm batch count/order/monotonic chronology differs')
        previous = batch['finished_monotonic_ns']
    require(previous <= row['finished_monotonic_ns'] <= ready['warmup_started_monotonic_ns'],
            'B prewarm was not wholly before the original warmup')
    return row


def full_task_partition(table, messages, *, cycle, arm, derived_path=None, allow_create=True):
    """Check every original CSV task, then feed only B's original 4222 tasks to frozen parser."""
    _, _, partition, _ = task_modules()
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    before = binding(table)
    if arm == 'A':
        result = partition(table, messages, operator='exp', cycle=cycle, repeat=100,
                           role_kernel_names=names)
        require(result['task_count'] == ORIGINAL_TASKS and result['csv_row_count'] == ORIGINAL_TASKS,
                'A complete Task CSV cardinality differs')
        audit = {'arm': 'A', 'full_task_count': ORIGINAL_TASKS, 'prefix_task_count': 0,
                 'original_table': before, 'derived_table': None, 'prefix_batches': []}
    else:
        from aprof_runtime.task_timing import _tasks
        source = Path(table).read_text(encoding='utf-8')
        csv_rows = csv.DictReader(StringIO(source))
        names_in_csv = csv_rows.fieldnames
        rows, tasks, noncompute = _tasks(source, messages[0], names)
        require(len(rows) == len(tasks) == PREFIX_TASKS + ORIGINAL_TASKS and not noncompute,
                'B full CSV must contain exactly 14222 registered compute tasks')
        require(all(task['op_name'] == 'exp_kernel' for task in tasks[:PREFIX_TASKS]),
                'B prefix is not 10000 original baseline kernel tasks')
        batches = []
        for index in range(BATCHES):
            selected = tasks[index * CALLS:(index + 1) * CALLS]
            require(len(selected) == CALLS, 'B prefix batch is incomplete')
            batches.append({'batch_index': index, 'task_indices': [index * CALLS, (index + 1) * CALLS],
                            'original_csv_row_indices': [task['csv_row_index'] for task in selected],
                            'task_duration_total_ns': float(sum(task['duration_us'] for task in selected) * 1000),
                            'first_start_us': str(selected[0]['start_us']),
                            'last_end_us': str(selected[-1]['end_us'])})
        require(derived_path is not None, 'B derived Task CSV path is required')
        tail_indices = [task['csv_row_index'] for task in tasks[PREFIX_TASKS:]]
        derived = StringIO(newline='')
        writer = csv.DictWriter(derived, fieldnames=names_in_csv)
        writer.writeheader()
        writer.writerows(rows[index] for index in tail_indices)
        if Path(derived_path).exists():
            require(Path(derived_path).read_bytes() == derived.getvalue().encode('utf-8'),
                    'B derived Task CSV changed after exact full-table partition')
        else:
            require(allow_create, 'B derived Task CSV is missing during read-only replay')
            with Path(derived_path).open('x', newline='', encoding='utf-8') as stream:
                stream.write(derived.getvalue())
        result = partition(derived_path, messages, operator='exp', cycle=cycle, repeat=100,
                           role_kernel_names=names)
        require(result['task_count'] == ORIGINAL_TASKS and result['csv_row_count'] == ORIGINAL_TASKS,
                'B original 4222-task suffix differs')
        audit = {'arm': 'B', 'full_task_count': len(tasks), 'prefix_task_count': PREFIX_TASKS,
                 'original_table': before, 'derived_table': binding(derived_path),
                 'suffix_original_csv_row_indices': tail_indices, 'prefix_batches': batches,
                 'full_stream': tasks[0]['stream'], 'full_device': tasks[0]['device']}
    require(binding(table) == before, 'original Task CSV changed during diagnostic parse')
    return result, audit


def _slot_job(output, plan, config, case, cycle, arm, slot):
    argv = [plan['A_binary']['path'] if arm == 'A' else plan['B_binary'],
            *[argument.replace('{cycle_dir}', str(slot)) for argument in case['command'][1:]]]
    environment = dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_CYCLE=str(cycle),
        APROF_SHARED_MODE='confirmation', APROF_SHARED_REPEAT='100',
        APROF_SHARED_COMMANDS=str(output / 'commands.txt'))
    local = Path(plan['scratch_root']) / slot.name / 'profile'
    cwd = config['build']['source_dir'] if arm == 'A' else plan['B_source']
    job = {'job_id': slot.name + '-capture', 'argv': [plan['profiler']['path'],
           '--output=' + str(local), *FLAGS, '--application=' + shlex.join(argv)],
           'cwd': cwd, 'output_dir': str(slot / 'capture-job'),
           'timeout_seconds': 900, 'environment': environment}
    return argv, local, job


def _run_slot(output, plan, config, entry):
    cycle, arm = entry['cycle'], entry['arm']
    slot = output / 'campaign' / entry['slot_id']
    slot.mkdir(exist_ok=False)
    deadline = time.monotonic() + SLOT_BUDGET
    case = plan['case']
    argv, local, job = _slot_job(output, plan, config, case, cycle, arm, slot)
    receipt = {'schema_version': 1, 'purpose': PURPOSE, 'slot_id': entry['slot_id'],
               'cycle': cycle, 'arm': arm, 'argv': argv, 'started_at': time.time(),
               'verifications': {}, 'status': 'failed', 'publication_acceptance': False}
    save_new(slot / 'started.json', receipt)
    try:
        require(not local.exists() and not local.is_symlink(), 'local diagnostic profile already exists')
        local.parent.mkdir(parents=True, exist_ok=False)
        job['timeout_seconds'] = min(job['timeout_seconds'], _remaining(deadline))
        execution = job_run(job)
        receipt['capture'] = binding(slot / 'capture-job/execution.json')
        require(execution['exit_code'] == 0, 'diagnostic msprof capture failed')
        messages = native_messages(slot / 'capture-job/stdout.log')
        timeline_protocol(messages, config, 100, cycle=cycle)
        require(messages[-1]['kind'] == 'complete' and messages[-1]['input_bytes_unchanged'] is True,
                'original complete did not verify immutable input across the prewarm and native sequence')
        prewarm = prewarm_receipt(slot / 'capture-job/stdout.log', messages, cycle, arm)
        if prewarm is not None:
            save_new(slot / 'prewarm.json', prewarm)
            receipt['prewarm'] = binding(slot / 'prewarm.json')
        collector, _, _, controls = task_modules()
        capture_files = collector.profile_inventory(local, deadline=deadline)
        save_new(slot / 'capture-inventory.json', capture_files)
        receipt['capture_inventory'] = binding(slot / 'capture-inventory.json')
        final_files = capture_files
        tables = [name for name in final_files if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        if not tables:
            capture_transfer = collector.copy_profile_tree(local, slot / 'capture-profile',
                capture_files, deadline=deadline)
            save_new(slot / 'capture-transfer.json', capture_transfer)
            receipt['capture_transfer'] = binding(slot / 'capture-transfer.json')
            roots = [path for path in local.glob('PROF_*') if path.is_dir() and not path.is_symlink()]
            require(len(roots) == 1, 'diagnostic capture requires exactly one PROF root')
            export_job = dict(job, job_id=slot.name + '-export',
                argv=[plan['profiler']['path'], '--export=on', '--type=text', '--output=' + str(roots[0])],
                output_dir=str(slot / 'export-job'), timeout_seconds=min(300, _remaining(deadline)))
            export = job_run(export_job)
            receipt['export'] = binding(slot / 'export-job/execution.json')
            require(export['exit_code'] == 0, 'diagnostic msprof export failed')
            final_files = collector.profile_inventory(local, deadline=deadline)
            tables = [name for name in final_files if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        require(len(tables) == 1, 'diagnostic profile requires one complete op_summary CSV')
        save_new(slot / 'final-inventory.json', final_files)
        receipt['final_inventory'] = binding(slot / 'final-inventory.json')
        transfer = collector.copy_profile_tree(local, slot / 'profile', final_files, deadline=deadline)
        save_new(slot / 'profile-transfer.json', transfer)
        receipt['profile_transfer'] = binding(slot / 'profile-transfer.json')
        table = slot / 'profile' / tables[0]
        result, audit = full_task_partition(table, messages, cycle=cycle, arm=arm,
            derived_path=slot / 'original-task-sequence.csv' if arm == 'B' else None)
        save_new(slot / 'task-audit.json', audit)
        save_new(slot / 'partition.json', result)
        receipt['task_audit'] = binding(slot / 'task-audit.json')
        receipt['partition'] = binding(slot / 'partition.json')
        receipt['task_controls'] = controls(result['values_ns_per_call'])
        for role in ('baseline', 'candidate'):
            receipt['verifications'][role] = oracle(slot, role, case, config['build']['source_dir'])
        receipt['finished_at'] = time.time()
        for role in ('baseline', 'candidate'):
            production_oracle(slot, role, case, receipt, Evidence())
        for path in case['prepared_files']:
            require(digest(path) == plan['original_files'][path], 'prepared input changed during prewarm slot')
        _remaining(deadline)
        receipt['status'] = 'complete_diagnostic_only'
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        for key, path in (('capture', slot / 'capture-job/execution.json'),
                          ('export', slot / 'export-job/execution.json')):
            if path.is_file() and key not in receipt:
                receipt[key] = binding(path)
        for role in ('baseline', 'candidate'):
            path = slot / f'{role}-verify-receipt.json'
            if path.is_file(): receipt['verifications'][role] = read(path)
        receipt['finished_at'] = time.time()
        save_new(slot / 'result.json', receipt)
    return receipt


def _analysis(output, plan, config):
    from aprof_runtime.measurement_admission import _summarize_values
    values = {'A': [], 'B': []}
    paired = []
    for cycle in range(6):
        rows = {arm: read(output / 'campaign' / slot_id(cycle, arm) / 'result.json') for arm in ('A', 'B')}
        pair = {'cycle': cycle}
        for arm, row in rows.items():
            partition = read(row['partition']['path'])
            values[arm].append(partition['values_ns_per_call'])
            formal = partition['values_ns_per_call']['formal']
            pair[arm + '_formal_ns_per_call'] = statistics.fmean(formal['baseline'] + formal['candidate'])
        pair['B_over_A_ratio'] = pair['B_formal_ns_per_call'] / pair['A_formal_ns_per_call']
        paired.append(pair)
    one = deepcopy(config)
    one['expected_case_ids'] = [1]
    one['cases'] = [plan['case']]
    return {'schema_version': 1, 'purpose': PURPOSE, 'metric': 'msprof.op_summary.Task_Duration',
            'publication_acceptance': False, 'accepted': False, 'matrix': plan['matrix'],
            'paired_cycles': paired,
            'controls': {arm: _summarize_values({1: samples}, one, protocol='shared_buffer_msprof_task_v2')
                         for arm, samples in values.items()},
            'scope': 'All 30 original pairs per arm and cycle; B prefix is retained but excluded from pair means.'}


def run(output, anchor):
    output = Path(output).resolve(strict=True)
    plan, config = _anchored(output, anchor)
    scratch = Path(plan['scratch_root'])
    require(not (output / 'campaign').exists() and not scratch.exists() and not scratch.is_symlink(),
            'diagnostic was already attempted')
    campaign = output / 'campaign'
    campaign.mkdir(exist_ok=False)
    save_new(campaign / 'started.json', {'at': time.time(), 'anchor': binding(anchor),
                                        'freeze': binding(output / 'freeze.json')})
    terminal = {'purpose': PURPOSE, 'status': 'failed', 'accepted': False,
                'publication_acceptance': False, 'slots': []}
    try:
        scratch.mkdir(mode=0o700, exist_ok=False)
        require(scratch.stat().st_mode & 0o777 == 0o700, 'diagnostic scratch is not private mode 0700')
        collector, _, _, _ = task_modules()
        mountinfo = Path('/proc/self/mountinfo').read_text()
        mount = collector.select_mount(mountinfo, scratch)
        require(mount['filesystem_type'] in collector.LOCAL_PROFILE_FILESYSTEMS,
                'diagnostic scratch is not on a supported local filesystem')
        (campaign / 'mountinfo.txt').write_text(mountinfo)
        save_new(campaign / 'storage.json', {'scratch_root': str(scratch), 'directory_mode': 0o700,
            'mountinfo': binding(campaign / 'mountinfo.txt'), 'scratch_mount': mount,
            'created_at': time.time()})
        terminal['storage'] = binding(campaign / 'storage.json')
        with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]):
            for entry in plan['matrix']:
                _run_slot(output, plan, config, entry)
                terminal['slots'].append(binding(campaign / entry['slot_id'] / 'result.json'))
            report = _analysis(output, plan, config)
            save_new(campaign / 'analysis.json', report)
            terminal['analysis'] = binding(campaign / 'analysis.json')
            terminal['status'] = 'complete_diagnostic_only'
    except BaseException as error:
        terminal['error'] = {'type': type(error).__name__, 'message': str(error)}
        if 'entry' in locals() and (campaign / entry['slot_id'] / 'result.json').is_file():
            terminal['failed_slot'] = binding(campaign / entry['slot_id'] / 'result.json')
        raise
    finally:
        terminal['finished_at'] = time.time()
        save_new(campaign / 'terminal.json', terminal)
    return terminal


def _execution_replay(reference, expected_job, earliest, latest, *, maximum):
    require(reference == binding(reference['path']), 'diagnostic job execution binding changed')
    actual = read(reference['path'])
    job = dict(expected_job)
    timeout = actual['job']['timeout_seconds']
    require(type(timeout) in (int, float) and 0 < timeout <= maximum,
            'diagnostic job timeout exceeds preregistered budget')
    job['timeout_seconds'] = timeout
    execution_interval(actual, job, earliest, latest, Evidence())
    return datetime.fromisoformat(actual['finished_at'].replace('Z', '+00:00')).timestamp()


def _transfer_replay(reference, source, destination, files, earliest, latest):
    require(reference == binding(reference['path']), 'diagnostic profile transfer binding changed')
    transfer = read(reference['path'])
    require(set(transfer) == {'source_dir', 'destination_dir', 'started_at', 'finished_at',
                              'source_inventory', 'persisted_inventory', 'source_after_inventory'}
            and transfer['source_dir'] == str(source) and transfer['destination_dir'] == str(destination)
            and transfer['source_inventory'] == transfer['persisted_inventory'] ==
                transfer['source_after_inventory'] == files
            and earliest <= transfer['started_at'] <= transfer['finished_at'] <= latest,
            'diagnostic local-to-persistent profile transfer differs')
    collector, _, _, _ = task_modules()
    require(collector.profile_inventory(destination, deadline=time.monotonic() + 600) == files,
            'persisted diagnostic profile tree changed')
    return transfer['finished_at']


def replay(output, anchor, *, source_archive_refs=None):
    """Recompute the complete diagnostic from persisted evidence, without /tmp."""
    output = Path(output).resolve(strict=True)
    historical = None
    if source_archive_refs is not None:
        from measurement_source_archive import HistoricalEvidence
        require(source_archive_refs, 'explicit historical producer archives required')
        historical = HistoricalEvidence(source_archive_refs, logical_paths=True)
        frozen = read(output / 'freeze.json')
        # Resolve old identity only. Execute the current pure parser/math only
        # while their actual bytes still equal the frozen diagnostic versions.
        for name in ('task_timing.py', 'measurement_admission.py'):
            path = RELEASE / 'runtime/src/aprof_runtime' / name
            Evidence().bind(path, frozen['frozen_files'][str(path)])
    plan, config = _anchored(output, anchor, historical_evidence=historical)
    campaign = output / 'campaign'
    started = read(campaign / 'started.json')
    terminal = read(campaign / 'terminal.json')
    require(started['anchor'] == binding(anchor) and started['freeze'] == binding(output / 'freeze.json')
            and terminal['purpose'] == PURPOSE and terminal['status'] == 'complete_diagnostic_only'
            and terminal['accepted'] is False and terminal['publication_acceptance'] is False
            and len(terminal['slots']) == len(MATRIX), 'diagnostic campaign was not fully completed')
    require(terminal['storage'] == binding(campaign / 'storage.json'),
            'diagnostic local storage receipt changed')
    storage = read(campaign / 'storage.json')
    collector, _, _, _ = task_modules()
    require(storage['scratch_root'] == plan['scratch_root'] and storage['directory_mode'] == 0o700
            and storage['mountinfo'] == binding(campaign / 'mountinfo.txt')
            and storage['scratch_mount'] == collector.select_mount(
                (campaign / 'mountinfo.txt').read_text(), Path(plan['scratch_root']))
            and storage['scratch_mount']['filesystem_type'] in collector.LOCAL_PROFILE_FILESYSTEMS,
            'diagnostic local scratch filesystem evidence differs')
    for entry, reference in zip(plan['matrix'], terminal['slots']):
        slot = campaign / entry['slot_id']
        require(reference == binding(slot / 'result.json'), 'diagnostic slot order or binding changed')
        row = read(slot / 'result.json')
        cycle, arm = entry['cycle'], entry['arm']
        argv, local, job = _slot_job(output, plan, config, plan['case'], cycle, arm, slot)
        require(row['slot_id'] == entry['slot_id'] and row['cycle'] == cycle and row['arm'] == arm
                and row['argv'] == argv and row['status'] == 'complete_diagnostic_only'
                and row['publication_acceptance'] is False
                and started['at'] <= row['started_at'] <= row['finished_at'] <= terminal['finished_at'],
                'diagnostic slot identity/status/chronology differs')
        capture_end = _execution_replay(row['capture'], job, row['started_at'], row['finished_at'], maximum=900)
        messages = native_messages(slot / 'capture-job/stdout.log')
        timeline_protocol(messages, config, 100, cycle=cycle)
        require(messages[-1]['kind'] == 'complete' and messages[-1]['input_bytes_unchanged'] is True,
                'original complete did not verify immutable input across the prewarm and native sequence')
        prewarm = prewarm_receipt(slot / 'capture-job/stdout.log', messages, cycle, arm)
        require((row.get('prewarm') is None if arm == 'A' else
                 row.get('prewarm') == binding(slot / 'prewarm.json')
                 and prewarm == read(slot / 'prewarm.json')),
                'diagnostic prewarm receipt changed')
        require(row['capture_inventory'] == binding(slot / 'capture-inventory.json'),
                'diagnostic capture inventory binding changed')
        captured = read(slot / 'capture-inventory.json')
        tables_before = [name for name in captured if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        prior = capture_end
        if tables_before:
            require(len(tables_before) == 1 and 'export' not in row and 'capture_transfer' not in row,
                    'diagnostic export occurred despite an existing unique table')
        else:
            roots = {Path(name).parts[0] for name in captured if Path(name).parts[0].startswith('PROF_')}
            require(len(roots) == 1 and row.get('capture_transfer') == binding(slot / 'capture-transfer.json'),
                    'diagnostic pre-export capture proof is incomplete')
            prior = _transfer_replay(row['capture_transfer'], local, slot / 'capture-profile',
                                     captured, capture_end, row['finished_at'])
            export_job = dict(job, job_id=slot.name + '-export',
                argv=[plan['profiler']['path'], '--export=on', '--type=text',
                      '--output=' + str(local / next(iter(roots)))],
                output_dir=str(slot / 'export-job'))
            require('export' in row, 'diagnostic export receipt missing')
            prior = _execution_replay(row['export'], export_job, prior, row['finished_at'], maximum=300)
        require(row['final_inventory'] == binding(slot / 'final-inventory.json'),
                'diagnostic final profile inventory binding changed')
        final = read(slot / 'final-inventory.json')
        require(final == captured if tables_before else final != captured,
                'diagnostic export changed or failed to change the capture profile unexpectedly')
        tables = [name for name in final if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        require(len(tables) == 1, 'diagnostic persisted profile requires one Task table')
        _transfer_replay(row['profile_transfer'], local, slot / 'profile', final, prior, row['finished_at'])
        table = slot / 'profile' / tables[0]
        partition, audit = full_task_partition(table, messages, cycle=cycle, arm=arm,
            derived_path=slot / 'original-task-sequence.csv' if arm == 'B' else None,
            allow_create=False)
        require(row['partition'] == binding(slot / 'partition.json')
                and partition == read(slot / 'partition.json')
                and row['task_audit'] == binding(slot / 'task-audit.json')
                and audit == read(slot / 'task-audit.json'),
                'diagnostic Task partition/audit changed')
        _, _, _, controls = task_modules()
        require(row['task_controls'] == controls(partition['values_ns_per_call'])
                and set(row['verifications']) == {'baseline', 'candidate'},
                'diagnostic controls or original oracle scope changed')
        for role in ('baseline', 'candidate'):
            require(row['verifications'][role] == read(slot / f'{role}-verify-receipt.json'),
                    'diagnostic oracle receipt changed')
            production_oracle(slot, role, plan['case'], row, Evidence())
    require(terminal['analysis'] == binding(campaign / 'analysis.json')
            and read(campaign / 'analysis.json') == _analysis(output, plan, config),
            'diagnostic A/B analysis differs from raw Task partitions')
    result = {'complete': True, 'accepted': False, 'eligible_for_publication': False,
              'purpose': PURPOSE, 'slots': len(MATRIX), 'metric': 'msprof.op_summary.Task_Duration'}
    if historical is not None:
        result.update(authority='historical_diagnostic_only', resolved_producers=historical.resolved_files)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'build', 'freeze', 'run', 'replay'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--anchor', type=Path)
    args = parser.parse_args()
    actions = {'prepare': lambda: prepare(args.output), 'build': lambda: build(args.output),
               'freeze': lambda: freeze(args.output), 'run': lambda: run(args.output, args.anchor),
               'replay': lambda: replay(args.output, args.anchor)}
    print(json.dumps(actions[args.action](), sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
