#!/usr/bin/env python3
"""Once-only exp Task Duration sampling-window diagnosis; never admission."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import sys
import time

from run_aprof_job import run as job_run
from run_shared_timing_confirmation import (BASE_ENVIRONMENT, ROOT, RELEASE, binding,
    locks, native_messages, production_oracle, save_new, task_counts, timeline_protocol,
    timeline_spans)
from qualify_shared_timing_v051 import protocol_commands, source_files
from qualify_task_timing_v051 import FLAGS, task_modules
from diagnose_exp_case1_prewarm import _execution_replay, _remaining, _transfer_replay
from replay_timing_diagnosis import Evidence, digest, read, require

PURPOSE = 'exp_task_sampling_window_diagnostic_only'
PREDECESSOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2/exp'
SUPPLEMENT = ROOT / 'scaffolding/curation/graph-base-0.5.1-local-task-history-supplement-20261014.json'
ANALYSIS_INDEX = ROOT.parent / 'validation-graph-base-0.5.1-20261014/task-duration-window-analysis-20261014/artifact-index.json'
ANALYSIS = ANALYSIS_INDEX.with_name('analysis.json')
PREWARM_ANALYSIS = ROOT.parent / 'validation-graph-base-0.5.1-20261014/exp-case1-prewarm-v2-task-timeline-analysis/summary.json'
PREWARM_REPLAY = ROOT.parent / 'validation-graph-base-0.5.1-20261014/exp-case1-prewarm-v2-replay-audit-20261014/result.json'
PREWARM_FREEZE = ROOT.parent / 'validation-graph-base-0.5.1-20261014/exp-case1-prewarm-diagnostic-v2/freeze.json'
PREWARM_TERMINAL = PREWARM_FREEZE.parent / 'campaign/terminal.json'
LONG_DIAGNOSIS = ROOT.parent / 'validation-graph-base-0.5.1-20261014/long-enqueue-diagnostic-20261014/analysis-report.json'
LONG_FREEZE = LONG_DIAGNOSIS.with_name('freeze.json')
LONG_TERMINAL = LONG_DIAGNOSIS.with_name('terminal.json')
PLAN_DOC = ROOT / 'scaffolding/curation/graph-base-0.5.1-task-sampling-window-diagnostic-plan.md'
SUPPLEMENT_SHA256 = 'sha256:c01ae21f78ca5404d385a0df8f9cc5a12e53484f27d932c2cde77f775bce9258'
ANALYSIS_INDEX_SHA256 = 'sha256:5bdfb92a233600d0f622049f0b11fb72f389cab14626d6bb8c4e7e1442703ca0'
ANALYSIS_SHA256 = 'sha256:20230410b730d9a636f6edcde1ca068b630813abb9f828ea73d686856c8ecd15'
CASES, REPEATS, CYCLES = (1, 10), (100, 7300), 6
SLOT_BUDGET, CAPTURE_BUDGET, EXPORT_BUDGET, ORACLE_BUDGET = 1500, 900, 300, 120
NAMES = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
PHASES = ('aa_before', 'formal', 'aa_after')
ROLES = ('baseline', 'candidate')


def matrix():
    return [{'cycle': cycle, 'case_id': case_id, 'repeat': repeat,
             'slot_id': f'case-{case_id:02d}-R{repeat}-cycle-{cycle}'
             } for cycle in range(CYCLES)
            for case_id in (CASES if cycle % 2 == 0 else CASES[::-1])
            for repeat in (REPEATS if cycle % 2 == 0 else REPEATS[::-1])]


def _config():
    config = read(PREDECESSOR / 'config.json')
    require(config['operator'] == 'exp' and config['device'] == 0
            and config['expected_case_ids'] == list(range(1, 21))
            and config['build']['binary'] == str(PREDECESSOR / 'source/build/exp')
            and config['roles']['baseline']['source_dir'] == config['roles']['candidate']['source_dir']
            and all(config['roles'][role]['launches_per_operator'] == 1 for role in ROLES)
            and [config['cases'][i - 1]['case_id'] for i in CASES] == list(CASES),
            'original exp source, device, or selected case mapping differs')
    return config


def _source_paths(config):
    source = Path(config['build']['source_dir'])
    return [source / name for name in source_files(source)]


def prepare(output):
    output = Path(output).resolve()
    require(not output.exists(), 'diagnostic directory already exists; no retry')
    config = _config()
    profiler = Path(shutil.which('msprof')).resolve(strict=True)
    scratch = Path('/tmp') / f'aprof-task-window-{output.name}'
    require(not scratch.exists() and not scratch.is_symlink(), 'diagnostic scratch already exists')
    collector, _, _, _ = task_modules()
    require(collector.select_mount(Path('/proc/self/mountinfo').read_text(), scratch)['filesystem_type']
            in collector.LOCAL_PROFILE_FILESYSTEMS, 'scratch is not local')
    historical = [SUPPLEMENT, ANALYSIS_INDEX, PREWARM_ANALYSIS, PREWARM_REPLAY, LONG_DIAGNOSIS,
                  ANALYSIS, PREWARM_FREEZE, PREWARM_TERMINAL, LONG_FREEZE, LONG_TERMINAL,
                  PREDECESSOR / 'config.json', PREDECESSOR.parent / 'plan.json',
                  PREDECESSOR.parent / 'freeze.json']
    require(digest(SUPPLEMENT) == SUPPLEMENT_SHA256 and digest(ANALYSIS_INDEX) == ANALYSIS_INDEX_SHA256
            and digest(ANALYSIS) == ANALYSIS_SHA256,
            'registered predecessor analysis or history supplement changed')
    original = [Path(config['build']['binary']), *_source_paths(config),
                *map(Path, config['build']['receipt_files']),
                *[Path(path) for case_id in CASES for path in config['cases'][case_id - 1]['prepared_files']]]
    output.mkdir(parents=True, exist_ok=False)
    commands = output / 'commands.txt'
    commands.write_text('\n'.join(protocol_commands()) + '\n')
    plan = {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(),
            'accepted': False, 'eligible_for_publication': False, 'metric': 'msprof.op_summary.Task_Duration',
            'matrix': matrix(), 'selected_case_ids': list(CASES), 'repeats': list(REPEATS),
            'cycles': CYCLES, 'slot_budget_seconds': SLOT_BUDGET,
            'capture_budget_seconds': CAPTURE_BUDGET, 'export_budget_seconds': EXPORT_BUDGET,
            'oracle_budget_seconds': ORACLE_BUDGET, 'max_attempts': 1, 'resampling': 'none',
            'original_config': binding(PREDECESSOR / 'config.json'),
            'original_files': {str(path): digest(path) for path in original},
            'binary': binding(config['build']['binary']), 'profiler': binding(profiler),
            'interpreter': binding(Path(sys.executable).resolve(strict=True)),
            'commands': binding(commands), 'scratch_root': str(scratch),
            'flags': FLAGS, 'design': binding(PLAN_DOC),
            'history': [binding(path) for path in historical]}
    save_new(output / 'plan.json', plan)
    return binding(output / 'plan.json')


def _checked_plan(output):
    output = Path(output).resolve(strict=True)
    plan, config = read(output / 'plan.json'), _config()
    require(plan['purpose'] == PURPOSE and plan['metric'] == 'msprof.op_summary.Task_Duration'
            and plan['matrix'] == matrix() and plan['selected_case_ids'] == list(CASES)
            and plan['repeats'] == list(REPEATS) and plan['cycles'] == CYCLES
            and [plan[k] for k in ('slot_budget_seconds', 'capture_budget_seconds',
                                    'export_budget_seconds', 'oracle_budget_seconds')]
            == [SLOT_BUDGET, CAPTURE_BUDGET, EXPORT_BUDGET, ORACLE_BUDGET]
            and plan['max_attempts'] == 1 and plan['resampling'] == 'none'
            and plan['accepted'] is False and plan['eligible_for_publication'] is False
            and plan['flags'] == FLAGS, 'fixed diagnostic scope differs')
    require(plan['original_config'] == binding(PREDECESSOR / 'config.json')
            and plan['binary'] == binding(config['build']['binary'])
            and plan['commands'] == binding(output / 'commands.txt')
            and (output / 'commands.txt').read_text().splitlines() == protocol_commands()
            and plan['design'] == binding(PLAN_DOC)
            and plan['scratch_root'] == str(Path('/tmp') / f'aprof-task-window-{output.name}')
            and plan['profiler'] == binding(plan['profiler']['path'])
            and plan['interpreter'] == binding(plan['interpreter']['path']),
            'diagnostic source, tool, command, or scratch identity differs')
    expected = [Path(config['build']['binary']), *_source_paths(config),
                *map(Path, config['build']['receipt_files']),
                *[Path(path) for case_id in CASES for path in config['cases'][case_id - 1]['prepared_files']]]
    require(plan['original_files'] == {str(path): digest(path) for path in expected},
            'original binary, source, or prepared input changed')
    require([ref['path'] for ref in plan['history'][:5]] ==
            [str(path.resolve()) for path in (SUPPLEMENT, ANALYSIS_INDEX, PREWARM_ANALYSIS,
                                               PREWARM_REPLAY, LONG_DIAGNOSIS)],
            'required predecessor history missing')
    require(digest(SUPPLEMENT) == SUPPLEMENT_SHA256 and digest(ANALYSIS_INDEX) == ANALYSIS_INDEX_SHA256
            and digest(ANALYSIS) == ANALYSIS_SHA256,
            'registered predecessor analysis or history supplement changed')
    for reference in plan['history']:
        require(binding(reference['path']) == reference, 'predecessor evidence changed')
    return plan, config


def freeze(output):
    output = Path(output).resolve(strict=True)
    require(not (output / 'freeze.json').exists(), 'diagnostic already frozen')
    plan, _ = _checked_plan(output)
    collector, _, _, _ = task_modules()
    files = [output / 'plan.json', output / 'commands.txt', PLAN_DOC,
             *[Path(path) for path in plan['original_files']],
             *[Path(ref['path']) for ref in plan['history']],
             Path(plan['profiler']['path']), Path(plan['interpreter']['path']), Path(__file__),
             *[RELEASE / name for name in collector.PRODUCER_FILES],
             *[Path(__file__).with_name(name) for name in (
                 'run_aprof_job.py', 'run_shared_timing_confirmation.py',
                 'qualify_shared_timing_v051.py', 'qualify_task_timing_v051.py',
                 'diagnose_exp_case1_prewarm.py', 'diagnose_task_duration.py',
                 'replay_timing_diagnosis.py')]]
    manifest = {str(path.resolve(strict=True)): digest(path) for path in files}
    save_new(output / 'freeze.json', {'schema_version': 1, 'purpose': PURPOSE,
        'created_at': time.time(), 'plan': binding(output / 'plan.json'),
        'frozen_files': manifest, 'matrix': matrix(),
        'accepted': False, 'eligible_for_publication': False})
    return binding(output / 'freeze.json')


def _anchored(output, anchor, *, historical_evidence=None):
    plan, config = _checked_plan(output)
    frozen = read(output / 'freeze.json')
    require(frozen['purpose'] == PURPOSE and frozen['plan'] == binding(output / 'plan.json')
            and frozen['matrix'] == matrix() and frozen['accepted'] is False
            and frozen['eligible_for_publication'] is False, 'diagnostic freeze differs')
    for path, expected in frozen['frozen_files'].items():
        if historical_evidence is None:
            require(digest(path) == expected, 'frozen diagnostic file changed: ' + path)
        else:
            historical_evidence.bind(path, expected)
    require(str(Path(__file__).resolve()) in frozen['frozen_files'], 'diagnostic script was not frozen')
    anchor = Path(anchor).resolve(strict=True)
    value = read(anchor)
    recorded = datetime.fromisoformat(value['recorded_at_utc'])
    require(recorded.tzinfo is not None and anchor.parent == ROOT / 'scaffolding/curation'
            and value == {'schema_version': 1, 'purpose': PURPOSE,
                          'freeze': binding(output / 'freeze.json'), 'max_attempts': 1,
                          'resampling': 'none', 'recorded_at_utc': value['recorded_at_utc']}
            and frozen['created_at'] <= recorded.timestamp() <= time.time(),
            'root diagnostic anchor differs')
    return plan, config


def partition_slot(table, messages, config, *, cycle, repeat):
    """Strict full CSV check followed by 30 intact macro samples; no R100 parser alias."""
    from aprof_runtime.task_timing import _native, _tasks
    require(type(cycle) is int and 0 <= cycle < CYCLES and type(repeat) is int
            and repeat in REPEATS and config['operator'] == 'exp',
            'diagnostic cycle, repeat, or operator is outside the fixed matrix')
    timeline_protocol(messages, config, repeat, cycle=cycle)
    before = binding(table)
    ready = _native(messages, 'exp', cycle, repeat, NAMES)
    rows, tasks, auxiliary = _tasks(Path(table).read_text(encoding='utf-8'), ready, NAMES)
    expected = sum(task_counts(repeat).values())
    require(len(rows) == len(tasks) == expected and not auxiliary
            and all(task['op_name'] == 'exp_kernel' for task in tasks),
            'complete single-kernel Task table differs')
    spans = timeline_spans(table, messages, 'exp')
    values = {phase: {role: [] for role in ROLES} for phase in PHASES}
    slim = []
    cursor = 20
    for phase_index, phase in enumerate(PHASES):
        cursor += 400
        for pair in range(5):
            message = messages[2 + 6 * phase_index + pair]
            for role in message['order']:
                span = next((s for s in spans if s['phase'] == phase and
                             s['pair_index'] == pair and s['role'] == role), None)
                require(span is not None and span['task_indices'] == [cursor, cursor + repeat]
                        and span['task_count'] == repeat and span['implementation'] == message[role]['implementation'],
                        'Task macro interval or phase differs')
                selected = tasks[cursor:cursor + repeat]
                require(len(selected) == len(span['tasks']) == repeat and all(
                    task['task_id'] == row['Task ID']
                    and task['start_us'] == Decimal(row['Task Start Time(us)'].strip())
                    and task['duration_us'] == Decimal(row['Task Duration(us)'].strip())
                    for task, row in zip(selected, span['tasks'])),
                    'strict Task parser and timeline row sequence differ')
                total = sum((task['duration_us'] for task in selected), Decimal(0)) * 1000
                require(abs(float(total) - span['kernel_total_duration_ns']) <=
                        max(1e-5, abs(float(total)) * 1e-12), 'Task duration aggregation differs')
                group = {key: value for key, value in span.items() if key != 'tasks'}
                group['csv_row_indices'] = [task['csv_row_index'] for task in selected]
                group['task_duration_ns_per_call'] = float(total / repeat)
                slim.append(group)
                values[phase][role].append(group['task_duration_ns_per_call'])
                cursor += repeat
    require(cursor == expected - 2 and len(slim) == 30
            and all(len(values[phase][role]) == 5 for phase in PHASES for role in ROLES)
            and binding(table) == before, 'complete macro partition or CSV identity changed')
    return {'metric': 'msprof.op_summary.Task_Duration', 'native_protocol': ready['protocol'],
            'native_intervals': 'derived_payload_validation_only', 'cycle': cycle,
            'repeat': repeat, 'task_count': expected, 'csv_row_count': len(rows),
            'noncompute_csv_row_indices': [], 'table': before, 'groups': slim,
            'values_ns_per_call': values}


def _job(output, plan, config, entry, slot):
    case, cycle, repeat = (config['cases'][entry['case_id'] - 1], entry['cycle'], entry['repeat'])
    argv = [plan['binary']['path'], *[arg.replace('{cycle_dir}', str(slot)) for arg in case['command'][1:]]]
    environment = dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_CYCLE=str(cycle),
        APROF_SHARED_MODE='confirmation', APROF_SHARED_REPEAT=str(repeat),
        APROF_SHARED_COMMANDS=str(output / 'commands.txt'))
    local = Path(plan['scratch_root']) / entry['slot_id'] / 'profile'
    job = {'job_id': entry['slot_id'] + '-capture',
           'argv': [plan['profiler']['path'], '--output=' + str(local), *FLAGS,
                    '--application=' + shlex.join(argv)],
           'cwd': config['build']['source_dir'], 'output_dir': str(slot / 'capture-job'),
           'timeout_seconds': CAPTURE_BUDGET, 'environment': environment}
    return case, argv, local, job


def _identity_expected(plan, config, case):
    source = Path(config['build']['source_dir'])
    paths = [path for path in plan['original_files'] if Path(path).is_relative_to(source)]
    paths += [plan['binary']['path'], *case['prepared_files'], plan['profiler']['path']]
    expected = {path: plan['original_files'][path] for path in paths if path != plan['profiler']['path']}
    expected[plan['profiler']['path']] = plan['profiler']['sha256']
    return expected


def _identity_now(expected):
    return {path: digest(path) for path in expected}


def _oracle(slot, role, case, cwd, deadline):
    argv = [part.replace('{cycle_dir}', str(slot)) for part in case['verify_commands'][role]]
    row = {'argv': argv, 'started_at': time.time(), 'exit_status': None, 'status': 'failed'}
    try:
        row['output_sha256'] = digest(slot / f'{role}.bin')
        with (slot / f'{role}-verify.log').open('xb') as log:
            done = subprocess.run(argv, cwd=cwd, env=dict(os.environ, **BASE_ENVIRONMENT),
                                  stdout=log, stderr=subprocess.STDOUT,
                                  timeout=min(ORACLE_BUDGET, _remaining(deadline)))
        row['exit_status'] = done.returncode
        require(done.returncode == 0 and digest(slot / f'{role}.bin') == row['output_sha256'],
                'diagnostic original oracle failed')
        row['status'] = 'passed'
    except BaseException as error:
        row['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        row['finished_at'] = time.time()
        for key, path in [('log_sha256', slot / f'{role}-verify.log'),
                          ('output_after_sha256', slot / f'{role}.bin')]:
            if path.is_file(): row[key] = digest(path)
        save_new(slot / f'{role}-verify-receipt.json', row)
    return row


def _costs(row, slot):
    capture = read(row['capture']['path'])['duration_seconds'] if 'capture' in row else None
    export = read(row['export']['path'])['duration_seconds'] if 'export' in row else None
    copied = [read(row[key]['path']) for key in ('capture_transfer', 'profile_transfer') if key in row]
    copy = sum(item['finished_at'] - item['started_at'] for item in copied) if copied else None
    oracles = {role: (row['verifications'][role]['finished_at'] - row['verifications'][role]['started_at'])
               if role in row['verifications'] else None for role in ROLES}
    oracle = sum(oracles.values()) if all(value is not None for value in oracles.values()) else None
    return {'capture_seconds': capture, 'export_seconds': export, 'copy_seconds': copy,
            'oracle_seconds': oracle, 'oracle_by_role_seconds': oracles,
            'total_wall_seconds': row['finished_at'] - row['started_at']}


def _run_slot(output, plan, config, entry):
    slot = output / 'campaign' / entry['slot_id']
    slot.mkdir(exist_ok=False)
    deadline = time.monotonic() + SLOT_BUDGET
    case, argv, local, job = _job(output, plan, config, entry, slot)
    row = {'schema_version': 1, 'purpose': PURPOSE, **entry, 'argv': argv,
           'started_at': time.time(), 'verifications': {}, 'status': 'failed',
           'accepted': False, 'eligible_for_publication': False}
    save_new(slot / 'started.json', row)
    try:
        expected_identity = _identity_expected(plan, config, case)
        row['identity_before'] = _identity_now(expected_identity)
        require(row['identity_before'] == expected_identity, 'original source, binary, input, or profiler changed')
        require(not local.exists() and not local.is_symlink(), 'scratch slot already exists')
        local.parent.mkdir(parents=True, exist_ok=False)
        job['timeout_seconds'] = min(CAPTURE_BUDGET, _remaining(deadline))
        execution = job_run(job)
        row['capture'] = binding(slot / 'capture-job/execution.json')
        require(execution['exit_code'] == 0, 'diagnostic capture failed')
        messages = native_messages(slot / 'capture-job/stdout.log')
        timeline_protocol(messages, config, entry['repeat'], cycle=entry['cycle'])
        row['native'] = {'pid': messages[0]['pid'], 'capture_started_at': execution['started_at']}
        require(messages[-1]['kind'] == 'complete' and messages[-1]['input_bytes_unchanged'] is True,
                'native complete did not verify immutable input')
        collector, _, _, _ = task_modules()
        captured = collector.profile_inventory(local, deadline=deadline)
        save_new(slot / 'capture-inventory.json', captured)
        row['capture_inventory'] = binding(slot / 'capture-inventory.json')
        final = captured
        tables = [name for name in final if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        if not tables:
            transfer = collector.copy_profile_tree(local, slot / 'capture-profile', captured, deadline=deadline)
            save_new(slot / 'capture-transfer.json', transfer)
            row['capture_transfer'] = binding(slot / 'capture-transfer.json')
            roots = [path for path in local.glob('PROF_*') if path.is_dir() and not path.is_symlink()]
            require(len(roots) == 1, 'capture requires one PROF root')
            export_job = dict(job, job_id=slot.name + '-export',
                argv=[plan['profiler']['path'], '--export=on', '--type=text', '--output=' + str(roots[0])],
                output_dir=str(slot / 'export-job'),
                timeout_seconds=min(EXPORT_BUDGET, _remaining(deadline)))
            export = job_run(export_job)
            row['export'] = binding(slot / 'export-job/execution.json')
            require(export['exit_code'] == 0, 'diagnostic export failed')
            final = collector.profile_inventory(local, deadline=deadline)
            tables = [name for name in final if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        require(len(tables) == 1, 'diagnostic profile requires one Task CSV')
        save_new(slot / 'final-inventory.json', final)
        row['final_inventory'] = binding(slot / 'final-inventory.json')
        transfer = collector.copy_profile_tree(local, slot / 'profile', final, deadline=deadline)
        save_new(slot / 'profile-transfer.json', transfer)
        row['profile_transfer'] = binding(slot / 'profile-transfer.json')
        result = partition_slot(slot / 'profile' / tables[0], messages, config,
                                cycle=entry['cycle'], repeat=entry['repeat'])
        save_new(slot / 'partition.json', result)
        row['partition'] = binding(slot / 'partition.json')
        for role in ROLES:
            row['verifications'][role] = _oracle(slot, role, case, config['build']['source_dir'], deadline)
        row['finished_at'] = time.time()
        for role in ROLES:
            production_oracle(slot, role, case, row, Evidence())
        for path in case['prepared_files']:
            require(digest(path) == plan['original_files'][path], 'original prepared input changed')
        row['identity_after'] = _identity_now(expected_identity)
        require(row['identity_after'] == expected_identity,
                'original source, binary, input, or profiler changed during slot')
        _remaining(deadline)
        row['status'] = 'complete_diagnostic_only'
    except BaseException as error:
        row['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        for key, path in (('capture', slot / 'capture-job/execution.json'),
                          ('export', slot / 'export-job/execution.json')):
            if path.is_file() and key not in row: row[key] = binding(path)
        for role in ROLES:
            path = slot / f'{role}-verify-receipt.json'
            if path.is_file(): row['verifications'][role] = read(path)
        if 'identity_before' in row and 'identity_after' not in row:
            try: row['identity_after'] = _identity_now(expected_identity)
            except BaseException as error:
                row['identity_after_error'] = {'type': type(error).__name__, 'message': str(error)}
        row['finished_at'] = time.time()
        try: row['costs'] = _costs(row, slot)
        except BaseException as error:
            row['costs_error'] = {'type': type(error).__name__, 'message': str(error)}
        save_new(slot / 'result.json', row)
        if row['status'] == 'complete_diagnostic_only' and 'costs_error' in row:
            raise ValueError('completed diagnostic lacks its cost receipt')
    return row


def summarize_matrix(slots, config):
    from aprof_runtime.measurement_admission import _phase_controls, _summarize_values
    require(len(slots) == len(matrix()) and [row['slot_id'] for row in slots] ==
            [entry['slot_id'] for entry in matrix()], 'diagnostic matrix incomplete or reordered')
    result = {'schema_version': 1, 'purpose': PURPOSE, 'metric': 'msprof.op_summary.Task_Duration',
              'accepted': False, 'eligible_for_publication': False, 'formal_pairs_per_arm': 30,
              'native_metric_role': 'Event and host wall are diagnostic only',
              'interpretation': 'R7300 changes submitted work and may change device behavior; mean shift is not solely a precision effect.',
              'arms': [], 'long_over_short': []}
    for case_id in CASES:
        arm_summaries = {}
        for repeat in REPEATS:
            selected = [row for row in slots if row['case_id'] == case_id and row['repeat'] == repeat]
            require(len(selected) == CYCLES and [row['cycle'] for row in selected] == list(range(CYCLES)),
                    'six fresh cycles per arm required')
            values = [row['partition']['values_ns_per_call'] for row in selected]
            one = deepcopy(config); one['expected_case_ids'] = [case_id]
            one['cases'] = [config['cases'][case_id - 1]]
            controls = _summarize_values({case_id: values}, one, protocol='diagnostic_task_sampling_window_v1')
            pooled = {phase: {role: [sample for cycle in values for sample in cycle[phase][role]]
                              for role in ROLES} for phase in PHASES}
            require(all(len(pooled[phase][role]) == 30 for phase in PHASES for role in ROLES),
                    'macro pair count differs from N30')
            # Both roles call the same original kernel, including the formal phase.
            formal_bias = _phase_controls(pooled)['formal']['role_bias']
            if formal_bias > .02:
                controls['stable'] = False
                controls['reasons'].append(f'case {case_id} pooled formal: same-source role bias exceeds 2%')
            for cycle_index, cycle in enumerate(values):
                if _phase_controls(cycle)['formal']['role_bias'] > .02:
                    controls['stable'] = False
                    controls['reasons'].append(
                        f'case {case_id} cycle {cycle_index} formal: same-source role bias exceeds 2%')
            formal_mean = statistics.fmean(pooled['formal']['baseline'] + pooled['formal']['candidate'])
            costs = {}
            for key in ('capture_seconds', 'export_seconds', 'copy_seconds',
                        'oracle_seconds', 'total_wall_seconds'):
                present = [row['costs'][key] for row in selected if row['costs'][key] is not None]
                costs[key] = statistics.fmean(present) if present else None
            costs['exported_slots'] = sum(row['costs']['export_seconds'] is not None for row in selected)
            arm = {'case_id': case_id, 'repeat': repeat, 'cycles': CYCLES,
                   'formal_pairs': 30, 'formal_mean_ns_per_call': formal_mean,
                   'same_source_formal_role_bias': formal_bias,
                   'stable_controls': controls['stable'], 'controls': controls,
                   'mean_cost_seconds_per_executed_stage': costs}
            result['arms'].append(arm); arm_summaries[repeat] = arm
        short, long = arm_summaries[REPEATS[0]], arm_summaries[REPEATS[1]]
        result['long_over_short'].append({'case_id': case_id,
            'difference_ns_per_call': long['formal_mean_ns_per_call'] - short['formal_mean_ns_per_call'],
            'ratio': long['formal_mean_ns_per_call'] / short['formal_mean_ns_per_call'],
            'short_mean_ns_per_call': short['formal_mean_ns_per_call'],
            'long_mean_ns_per_call': long['formal_mean_ns_per_call']})
    return result


def _save_checked_analysis(output, anchor, campaign, rows, config):
    report = summarize_matrix(rows, config)
    _anchored(output, anchor)
    path = campaign / 'analysis.json'
    save_new(path, report)
    return binding(path)


def run(output, anchor):
    output = Path(output).resolve(strict=True)
    plan, config = _anchored(output, anchor)
    scratch = Path(plan['scratch_root'])
    campaign = output / 'campaign'
    require(not campaign.exists() and not scratch.exists() and not scratch.is_symlink(),
            'diagnostic was already attempted')
    campaign.mkdir(exist_ok=False)
    save_new(campaign / 'started.json', {'at': time.time(), 'anchor': binding(anchor),
                                        'freeze': binding(output / 'freeze.json')})
    terminal = {'purpose': PURPOSE, 'status': 'failed', 'accepted': False,
                'eligible_for_publication': False, 'slots': []}
    try:
        scratch.mkdir(mode=0o700, exist_ok=False)
        require(scratch.stat().st_mode & 0o777 == 0o700, 'scratch is not private mode 0700')
        collector, _, _, _ = task_modules()
        mountinfo = Path('/proc/self/mountinfo').read_text()
        mount = collector.select_mount(mountinfo, scratch)
        require(mount['filesystem_type'] in collector.LOCAL_PROFILE_FILESYSTEMS,
                'scratch is not on a supported local filesystem')
        (campaign / 'mountinfo.txt').write_text(mountinfo)
        save_new(campaign / 'storage.json', {'scratch_root': str(scratch),
            'directory_mode': 0o700, 'mountinfo': binding(campaign / 'mountinfo.txt'),
            'scratch_mount': mount, 'created_at': time.time()})
        terminal['storage'] = binding(campaign / 'storage.json')
        with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]):
            for entry in plan['matrix']:
                _run_slot(output, plan, config, entry)
                terminal['slots'].append(binding(campaign / entry['slot_id'] / 'result.json'))
            rows = []
            for entry in plan['matrix']:
                receipt = read(campaign / entry['slot_id'] / 'result.json')
                receipt['partition'] = read(receipt['partition']['path'])
                rows.append(receipt)
            terminal['analysis'] = _save_checked_analysis(output, anchor, campaign, rows, config)
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


def _oracle_sequence(verifications, prior, finished):
    for role in ROLES:
        receipt = verifications[role]
        require(receipt['status'] == 'passed' and receipt['exit_status'] == 0
                and receipt['output_sha256'] == receipt['output_after_sha256']
                and prior <= receipt['started_at'] < receipt['finished_at'] <= finished
                and receipt['finished_at'] - receipt['started_at'] <= ORACLE_BUDGET,
                'oracle failed, exceeded 120s, or ran before persisted profile transfer')
        prior = receipt['finished_at']
    return prior


def _unique_native_identity(pid, capture_started_at, seen):
    require(type(pid) is int and pid > 0 and isinstance(capture_started_at, str)
            and capture_started_at, 'invalid native process identity')
    key = (pid, capture_started_at)
    require(key not in seen, 'diagnostic native process identity was reused')
    seen.add(key)
    return key


def replay(output, anchor, *, source_archive_refs=None):
    """Verify the frozen 24-slot diagnosis from persisted files, without /tmp."""
    output = Path(output).resolve(strict=True)
    historical = None
    if source_archive_refs is not None:
        from measurement_source_archive import HistoricalEvidence
        require(source_archive_refs, 'explicit historical producer archives required')
        historical = HistoricalEvidence(source_archive_refs, logical_paths=True)
        frozen = read(output / 'freeze.json')
        for name in ('task_timing.py', 'measurement_admission.py'):
            path = RELEASE / 'runtime/src/aprof_runtime' / name
            Evidence().bind(path, frozen['frozen_files'][str(path)])
    plan, config = _anchored(output, anchor, historical_evidence=historical)
    campaign = output / 'campaign'
    started, terminal = read(campaign / 'started.json'), read(campaign / 'terminal.json')
    require(started['anchor'] == binding(anchor) and started['freeze'] == binding(output / 'freeze.json')
            and terminal['purpose'] == PURPOSE and terminal['status'] == 'complete_diagnostic_only'
            and terminal['accepted'] is False and terminal['eligible_for_publication'] is False
            and len(terminal['slots']) == len(matrix()), 'diagnostic campaign incomplete')
    require(terminal['storage'] == binding(campaign / 'storage.json'), 'storage receipt changed')
    storage = read(campaign / 'storage.json')
    collector, _, _, _ = task_modules()
    require(storage['scratch_root'] == plan['scratch_root'] and storage['directory_mode'] == 0o700
            and storage['mountinfo'] == binding(campaign / 'mountinfo.txt')
            and storage['scratch_mount'] == collector.select_mount(
                (campaign / 'mountinfo.txt').read_text(), Path(plan['scratch_root']))
            and storage['scratch_mount']['filesystem_type'] in collector.LOCAL_PROFILE_FILESYSTEMS,
            'local storage evidence differs')
    rows = []
    previous = started['at']
    native_processes = set()
    for entry, reference in zip(plan['matrix'], terminal['slots']):
        slot = campaign / entry['slot_id']
        require(reference == binding(slot / 'result.json'), 'slot order or binding changed')
        row = read(slot / 'result.json')
        case, argv, local, job = _job(output, plan, config, entry, slot)
        require(all(row[key] == value for key, value in entry.items())
                and row['argv'] == argv and row['status'] == 'complete_diagnostic_only'
                and row['accepted'] is False and row['eligible_for_publication'] is False
                and previous <= row['started_at'] <= row['finished_at'] <= terminal['finished_at']
                and row['finished_at'] - row['started_at'] <= SLOT_BUDGET,
                'slot identity, status, or budget differs')
        previous = row['finished_at']
        identity = _identity_expected(plan, config, case)
        require(row['identity_before'] == row['identity_after'] == identity
                and _identity_now(identity) == identity,
                'slot original source, binary, input, or profiler identity differs')
        capture_end = _execution_replay(row['capture'], job, row['started_at'], row['finished_at'],
                                        maximum=CAPTURE_BUDGET)
        messages = native_messages(slot / 'capture-job/stdout.log')
        timeline_protocol(messages, config, entry['repeat'], cycle=entry['cycle'])
        capture_record = read(row['capture']['path'])
        require(row['native'] == {'pid': messages[0]['pid'],
                                  'capture_started_at': capture_record['started_at']},
                'diagnostic native process identity was altered')
        _unique_native_identity(messages[0]['pid'], capture_record['started_at'], native_processes)
        require(messages[-1]['kind'] == 'complete' and messages[-1]['input_bytes_unchanged'] is True,
                'immutable input verification missing')
        require(row['capture_inventory'] == binding(slot / 'capture-inventory.json'),
                'capture inventory changed')
        captured = read(slot / 'capture-inventory.json')
        before = [name for name in captured if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        prior = capture_end
        if before:
            require(len(before) == 1 and 'export' not in row and 'capture_transfer' not in row,
                    'unexpected diagnostic export')
        else:
            roots = {Path(name).parts[0] for name in captured if Path(name).parts[0].startswith('PROF_')}
            require(len(roots) == 1 and row.get('capture_transfer') == binding(slot / 'capture-transfer.json'),
                    'pre-export capture evidence incomplete')
            prior = _transfer_replay(row['capture_transfer'], local, slot / 'capture-profile',
                                     captured, capture_end, row['finished_at'])
            export_job = dict(job, job_id=slot.name + '-export',
                argv=[plan['profiler']['path'], '--export=on', '--type=text',
                      '--output=' + str(local / next(iter(roots)))],
                output_dir=str(slot / 'export-job'))
            prior = _execution_replay(row['export'], export_job, prior, row['finished_at'],
                                      maximum=EXPORT_BUDGET)
        require(row['final_inventory'] == binding(slot / 'final-inventory.json'),
                'final inventory changed')
        final = read(slot / 'final-inventory.json')
        require(final == captured if before else final != captured,
                'export failed to preserve or update profile inventory')
        tables = [name for name in final if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        require(len(tables) == 1, 'persisted Task CSV missing or ambiguous')
        prior = _transfer_replay(row['profile_transfer'], local, slot / 'profile',
                                 final, prior, row['finished_at'])
        result = partition_slot(slot / 'profile' / tables[0], messages, config,
                                cycle=entry['cycle'], repeat=entry['repeat'])
        require(row['partition'] == binding(slot / 'partition.json')
                and read(slot / 'partition.json') == result,
                'raw Task CSV partition differs')
        require(set(row['verifications']) == set(ROLES), 'independent oracle scope differs')
        for role in ROLES:
            require(row['verifications'][role] == read(slot / f'{role}-verify-receipt.json'),
                    'oracle receipt changed')
        _oracle_sequence(row['verifications'], prior, row['finished_at'])
        for role in ROLES:
            production_oracle(slot, role, case, row, Evidence())
        require(row['costs'] == _costs(row, slot), 'cost report differs from execution receipts')
        row['partition'] = result
        rows.append(row)
    require(terminal['analysis'] == binding(campaign / 'analysis.json')
            and read(campaign / 'analysis.json') == summarize_matrix(rows, config),
            'summary differs from all 24 raw Task intervals')
    result = {'purpose': PURPOSE, 'complete': True, 'accepted': False,
              'eligible_for_publication': False, 'slots': len(matrix()),
              'metric': 'msprof.op_summary.Task_Duration'}
    if historical is not None:
        result.update(authority='historical_diagnostic_only', resolved_producers=historical.resolved_files)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'freeze', 'run', 'replay'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--anchor', type=Path)
    args = parser.parse_args()
    actions = {'prepare': lambda: prepare(args.output), 'freeze': lambda: freeze(args.output),
               'run': lambda: run(args.output, args.anchor),
               'replay': lambda: replay(args.output, args.anchor)}
    print(json.dumps(actions[args.action](), sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
