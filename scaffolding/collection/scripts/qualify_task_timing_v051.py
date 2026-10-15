#!/usr/bin/env python3
"""Once-only Task Duration method qualification; never publish a skill release."""
from __future__ import annotations

import argparse
import contextlib
from copy import deepcopy
from datetime import datetime
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import statistics
import sys
import time

from run_aprof_job import run as job_run
from run_shared_timing_confirmation import (BASE_ENVIRONMENT, ROOT, RELEASE, binding, locks,
    native_messages, production_oracle, save_new, timeline_protocol)
from replay_timing_diagnosis import Evidence, digest, read, require
from qualify_shared_timing_v051 import protocol_commands, source_files
from diagnose_task_duration import oracle, execution_interval

PROTOCOL = 'shared_buffer_msprof_task_v2'
PURPOSE = 'preregistered_task_duration_local_method_qualification'
PREDECESSOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2'
HISTORY = ROOT / 'scaffolding/curation/graph-base-0.5.1-local-task-method-history.json'
COLLECTOR = RELEASE / 'skills/ascendc-aprof-profiling/scripts/device_task_timing.py'
FLAGS = ['--task-time=l1', '--ai-core=off', '--ascendcl=off', '--runtime-api=off', '--ge-api=off', '--aicpu=off', '--type=text']
OBSERVATIONS = {'exp': [(1, ['unprofiled', 'profiled']), (9, ['profiled', 'unprofiled'])],
                'sigmoid': [(1, ['profiled', 'unprofiled']), (4, ['unprofiled', 'profiled'])]}
BUDGETS = {'confirmation': 3600, 'observation': 1200, 'campaign': 12600}


def task_modules():
    sys.path.insert(0, str(COLLECTOR.parent)); sys.path.insert(0, str(RELEASE / 'runtime/src'))
    collector = importlib.import_module('device_task_timing')
    from aprof_runtime.task_measurement_admission import replay_task_measurement_admission
    from aprof_runtime.task_timing import partition_task_samples
    from aprof_runtime.measurement_admission import _phase_controls
    return collector, replay_task_measurement_admission, partition_task_samples, _phase_controls


def release_inventory():
    spec = importlib.util.spec_from_file_location('task_qualification_release', RELEASE / 'tools/release.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.inventory(RELEASE)


def check_controls(controls):
    for phase in ('aa_before', 'formal', 'aa_after'):
        require(controls[phase]['role_bias'] <= .02 and all(controls[phase][role + '_cv'] <= .05
                for role in ('baseline', 'candidate')), 'same-source Task A/A controls failed')
    require(all(value <= .02 for value in controls['drift'].values()), 'Task A/A drift failed')


def config_for(output, operator, profiler):
    config = deepcopy(read(PREDECESSOR / operator / 'config.json'))
    require(config['expected_case_ids'] == list(range(1, 21))
            and config['build']['binary'] == str(PREDECESSOR / operator / 'source/build' / operator), 'original full-case binary required')
    config.update(run_id=output.name, session_id=output.name + '-' + operator,
                  task_profile={'profiler': str(profiler),
                                'scratch_root': str(Path('/tmp') / f'aprof-task-{output.name}-{operator}'),
                                'role_kernel_names': {
                      role: [operator + '_kernel'] for role in ('baseline', 'candidate')}})
    return config


def prepare(output, history):
    output = Path(output).resolve(); require(not output.exists(), 'qualification already prepared; no retry')
    history = Path(history).resolve(strict=True)
    history_value = read(history)
    require(history == HISTORY and history_value['purpose'] == 'retained_history_for_local_task_duration_method_qualification'
            and history_value['protocol'] == PROTOCOL, 'local Task qualification history differs')
    history = binding(history); profiler = Path(shutil.which('msprof')).resolve(strict=True)
    output.mkdir(parents=True); save_new(output / 'prepare-started.json', {'at': time.time(), 'history': history})
    old_plan = read(PREDECESSOR / 'plan.json')
    old = old_plan['frozen_files'] | read(PREDECESSOR / 'freeze.json')['frozen_files']
    original = {}; configs = {}
    for op in ('exp', 'sigmoid'):
        config = config_for(output, op, profiler); configs[op] = str(output / op / 'config.json')
        require(not Path(config['task_profile']['scratch_root']).exists(),
                'local scratch must be created only by the collector')
        source = Path(config['build']['source_dir'])
        original_source = Path(old_plan['operators'][op]['original_source'])
        paths = [Path(config['build']['binary']), *[source / name for name in source_files(source)],
                 *[original_source / name for name in source_files(original_source)],
                 *map(Path, config['build']['receipt_files']), *[Path(p) for c in config['cases'] for p in c['prepared_files']]]
        for path in paths:
            require(str(path) in old, 'original source/input missing from old freeze: ' + str(path))
            original[str(path)] = 'sha256:' + old[str(path)].removeprefix('sha256:')
        save_new(Path(configs[op]), config)
    (output / 'commands.txt').write_text('\n'.join(protocol_commands()) + '\n')
    save_new(output / 'plan.json', {'schema_version': 1, 'purpose': PURPOSE, 'protocol': PROTOCOL,
        'created_at': time.time(), 'history': history, 'original_files': original, 'configs': configs,
        'operators': deepcopy(old_plan['operators']), 'frozen_files': {p: h.removeprefix('sha256:') for p, h in original.items()},
        'interpreter': binding(Path(sys.executable).resolve(strict=True)),
        'observations': OBSERVATIONS, 'budgets': BUDGETS, 'profiler': binding(profiler),
        'commands': binding(output / 'commands.txt'), 'max_attempts': 1, 'resampling': 'none', 'publication_acceptance': False})
    return binding(output / 'plan.json')


def roster_slots(output, plan):
    slots = []
    for op in ('exp', 'sigmoid'):
        previous = None
        entries = [('confirmation', None, None), *[('observation', case, order) for case, order in OBSERVATIONS[op]]]
        for kind, case, order in entries:
            slot_id = op + '-confirmation' if kind == 'confirmation' else f'{op}-observation-{case:02d}'
            argv = [plan['interpreter']['path'], str(COLLECTOR), '--config', plan['configs'][op], '--output', str(output / op / 'confirmation'),
                    '--store', str(output / op / 'evidence.sqlite'), '--timeout-seconds', str(BUDGETS[kind])] if kind == 'confirmation' else [
                    plan['interpreter']['path'], str(Path(__file__).resolve()), 'observe', '--output', str(output), '--operator', op, '--case-id', str(case)]
            job = {'job_id': slot_id, 'argv': argv, 'cwd': str(output), 'output_dir': str(output / 'campaign' / slot_id / 'job'),
                   'timeout_seconds': BUDGETS[kind], 'environment': BASE_ENVIRONMENT}
            slots.append({'slot_id': slot_id, 'kind': kind, 'operator': op, 'case_id': case, 'order': order,
                          'output_dir': str(output / op / 'confirmation') if kind == 'confirmation' else str(output / 'observations' / slot_id),
                          'prerequisite_slot': previous, 'job': job}); previous = slot_id
    return slots


def freeze(output):
    output = Path(output).resolve(strict=True); require(not (output / 'freeze.json').exists(), 'already frozen')
    plan = read(output / 'plan.json'); collector, _, _, _ = task_modules()
    require(collector.PROTOCOL == PROTOCOL and list(collector.PROFILE_FLAGS) == FLAGS, 'Task collector protocol differs')
    require(plan['operators'] == read(PREDECESSOR / 'plan.json')['operators'] and plan['budgets'] == BUDGETS,
            'mechanical source mapping or budget differs')
    files = dict(plan['original_files']); files[plan['history']['path']] = plan['history']['sha256']
    for op, path in plan['configs'].items():
        config = collector.config_value(read(path))
        require(config == config_for(output, op, Path(plan['profiler']['path'])), 'original case/config contract changed')
        require(not Path(config['task_profile']['scratch_root']).exists(),
                'local scratch exists before collector launch')
        actual = collector.inventory(config)['files']
        require(all(actual.get(p, h) == h for p, h in plan['original_files'].items()), 'original native/input identity changed')
        files.update(actual); files[path] = digest(path)
    sources = [RELEASE / name for name in collector.PRODUCER_FILES]
    sources += [Path(__file__), *[Path(__file__).with_name(name) for name in (
        'run_aprof_job.py', 'run_shared_timing_confirmation.py', 'replay_timing_diagnosis.py',
        'qualify_shared_timing_v051.py', 'diagnose_task_duration.py', 'replay_task_measurement_history.py',
        'measurement_source_archive.py', 'replay_measurement_transition.py', 'run_event_duration_study.py',
        'replay_task_cancellation.py', 'probe_native_task_profile.py', 'task_profile_native.py')],
        ROOT / 'scaffolding/benchmarks/cannbench/harness/device_task_profile.h',
        ROOT / 'scaffolding/tools/verify_measurement_publication.py']
    files.update({str(p): digest(p) for p in sources})
    files[str(output / 'plan.json')] = digest(output / 'plan.json'); files[plan['commands']['path']] = plan['commands']['sha256']
    files[plan['interpreter']['path']] = plan['interpreter']['sha256']
    for path, expected in files.items(): require(digest(path) == expected, 'freeze identity changed: ' + path)
    save_new(output / 'candidate-inventory.json', {'schema_version': 1, 'root': str(RELEASE), 'files': release_inventory()})
    files[str(output / 'candidate-inventory.json')] = digest(output / 'candidate-inventory.json')
    save_new(output / 'freeze.json', {'schema_version': 1, 'created_at': time.time(), 'plan': binding(output / 'plan.json'),
        'candidate_inventory': binding(output / 'candidate-inventory.json'), 'frozen_files': files, 'configs': plan['configs']})
    save_new(output / 'roster.json', {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(),
        'qualification_dir': str(output), 'freeze': binding(output / 'freeze.json'), 'slots': roster_slots(output, plan),
        'max_attempts': 1, 'resampling': 'none', 'timeout_seconds': BUDGETS['campaign']})
    return {'freeze': binding(output / 'freeze.json'), 'roster': binding(output / 'roster.json')}


def load_plan(output):
    output = Path(output).resolve(strict=True)
    return output, read(output / 'plan.json')


def checked_plan(output, evidence=None):
    output = Path(output).resolve(strict=True); evidence = evidence or Evidence()
    plan = evidence.json(output / 'plan.json'); freeze = evidence.json(output / 'freeze.json')
    require(plan['purpose'] == PURPOSE and plan['protocol'] == PROTOCOL and plan['budgets'] == BUDGETS
            and plan['observations'] == {op: [[case, order] for case, order in rows] for op, rows in OBSERVATIONS.items()}
            and plan['max_attempts'] == 1 and plan['resampling'] == 'none'
            and freeze['plan'] == binding(output / 'plan.json'), 'frozen Task plan differs')
    require(plan['frozen_files'] == {p: h.removeprefix('sha256:') for p, h in plan['original_files'].items()}
            and freeze['configs'] == plan['configs'], 'native inventory/config aliases differ')
    for path, expected in freeze['frozen_files'].items(): evidence.bind(path, expected)
    candidate = evidence.json(output / 'candidate-inventory.json')
    require(freeze['candidate_inventory'] == binding(output / 'candidate-inventory.json')
            and candidate == {'schema_version': 1, 'root': str(RELEASE), 'files': release_inventory()}, 'candidate payload changed after freeze')
    return plan, freeze


def full_admission(output, operator):
    _, replay, _, _ = task_modules()
    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory
    config = read(output / operator / 'config.json'); folder = output / operator / 'confirmation'
    receipt = read(folder / 'measurement_admission.json'); refs = read(folder / 'artifacts.json')
    require(config['expected_case_ids'] == list(range(1, 21)) and receipt['source_hashes']['baseline'] == receipt['source_hashes']['candidate'], 'full identical-source A/A required')
    path = output / operator / 'evidence.sqlite'
    with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.execute('BEGIN')
        result = replay(_ReadOnlyArtifacts(connection, default_object_directory(path)), refs['measurement_admission'], expected={
            **{key: config[key] for key in ('operator', 'run_id', 'session_id', 'candidate_id')}, 'source_hashes': receipt['source_hashes']})
    require(result['valid'] and result['report']['stable'], 'full Task runtime admission failed')
    for case in result['report']['controls']:
        for controls in [case['overall'], *case['cycles']]: check_controls(controls)
    return result


def run(roster_path, anchor):
    roster_path = Path(roster_path).resolve(strict=True); roster = read(roster_path)
    output = Path(roster['qualification_dir']); plan, _ = checked_plan(output); a = read(anchor)
    require(roster['slots'] == roster_slots(output, plan) and a == {'schema_version': 1, 'purpose': PURPOSE,
        'roster': binding(roster_path), 'max_attempts': 1, 'resampling': 'none', 'recorded_at_utc': a['recorded_at_utc']}
        and Path(anchor).resolve().parent == ROOT / 'scaffolding/curation'
        and roster['created_at'] <= datetime.fromisoformat(a['recorded_at_utc']).timestamp() <= time.time(), 'root roster anchor differs')
    campaign = output / 'campaign'; campaign.mkdir(exist_ok=False)
    save_new(campaign / 'started.json', {'at': time.time(), 'roster': binding(roster_path), 'anchor': binding(anchor)})
    terminals = {}
    with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(1, 16)]]):
        for slot in roster['slots']:
            folder = campaign / slot['slot_id']; folder.mkdir(); prior = slot['prerequisite_slot']
            terminal = {'slot_id': slot['slot_id'], 'kind': slot['kind'], 'operator': slot['operator'], 'status': 'not_run'}
            if prior and terminals[prior]['status'] != 'passed':
                terminal['prerequisite_ref'] = binding(campaign / prior / 'terminal.json')
            else:
                save_new(folder / 'started.json', {'at': time.time(), 'slot': slot})
                terminal.update(status='failed', started=binding(folder / 'started.json'))
                try:
                    execution = job_run(slot['job']); terminal['execution'] = binding(folder / 'job/execution.json')
                    require(execution['exit_code'] == 0, 'qualification slot failed')
                    replay = full_admission(output, slot['operator']) if slot['kind'] == 'confirmation' else replay_task_observation(
                        output / 'observations' / slot['slot_id'], qualification_dir=output, operator=slot['operator'], case_id=slot['case_id'])
                    report = folder / 'replay.json' if slot['kind'] == 'confirmation' else Path(slot['output_dir']) / 'observation-report.json'
                    save_new(report, replay); terminal.update(status='passed', replay=binding(report))
                    if slot['kind'] == 'observation': terminal['observation_report'] = binding(report)
                except Exception as error:
                    terminal['error'] = {'type': type(error).__name__, 'message': str(error)}
                    if (folder / 'job/execution.json').exists(): terminal['execution'] = binding(folder / 'job/execution.json')
            terminal['finished_at'] = time.time(); save_new(folder / 'terminal.json', terminal); terminals[slot['slot_id']] = terminal
            print(json.dumps({'slot': slot['slot_id'], 'status': terminal['status']}), flush=True)
    result = {'roster': binding(roster_path), 'slots': {name: binding(campaign / name / 'terminal.json') for name in terminals},
              'accepted': all(row['status'] == 'passed' for row in terminals.values()), 'authority': 'method_qualification_only_no_publication', 'resampling': 'none'}
    save_new(campaign / 'campaign.json', result); return result


def observation_job(output, config, case, mode):
    argv = [x.replace('{cycle_dir}', str(output)) for x in case['command']]
    env = dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_CYCLE='0', APROF_SHARED_MODE='confirmation',
               APROF_SHARED_REPEAT='100', APROF_SHARED_COMMANDS=str(output.parents[2] / 'commands.txt'))
    if mode == 'profiled':
        argv = [config['task_profile']['profiler'], '--output=' + str(observation_profile_path(output, config)),
                *FLAGS, '--application=' + shlex.join(argv)]
    return {'job_id': output.parent.name + '-' + mode, 'argv': argv, 'cwd': config['build']['source_dir'],
            'output_dir': str(output / 'job'), 'timeout_seconds': 600 if mode == 'profiled' else 120, 'environment': env}


def profile_inventory(directory):
    files = {}
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'profile symlink rejected')
        if path.is_file(): files[str(path)] = digest(path)
    require(files, 'empty profile inventory')
    return files


def observation_profile_path(directory, config):
    return Path(config['task_profile']['scratch_root']) / 'observations' / directory.parent.name / 'profile'


def checked_scratch_root(config):
    scratch = Path(config['task_profile']['scratch_root'])
    require(scratch.is_absolute() and scratch.resolve() == scratch and not scratch.is_symlink()
            and scratch.is_dir() and scratch.stat().st_mode & 0o777 == 0o700,
            'collector scratch root is missing or replaced')
    return scratch


def relative_profile_inventory(directory):
    return {Path(path).relative_to(directory).as_posix(): expected
            for path, expected in profile_inventory(directory).items()}


def replay_profile_transfer(directory, config, receipt, after, evidence):
    persisted = directory / 'profile'
    require(persisted.is_dir() and not persisted.is_symlink(), 'persisted observation profile missing')
    transfer_path = directory / 'profile-transfer.json'
    transfer = evidence.json(transfer_path)
    relative = relative_profile_inventory(persisted)
    require(receipt['profile_transfer'] == binding(transfer_path)
            and set(transfer) == {'source_dir', 'destination_dir', 'started_at', 'finished_at',
                                  'source_inventory', 'persisted_inventory', 'source_after_inventory'}
            and transfer['source_dir'] == str(observation_profile_path(directory, config))
            and transfer['destination_dir'] == str(persisted)
            and transfer['source_inventory'] == transfer['source_after_inventory'] ==
                transfer['persisted_inventory'] == relative
            and after <= transfer['started_at'] <= transfer['finished_at'] <= receipt['finished_at'],
            'observation local-to-persistent profile transfer differs')
    return transfer['finished_at']


def observation_mode(directory, config, case, mode, *, deadline=None):
    directory.mkdir(); job = observation_job(directory, config, case, mode)
    receipt = {'mode': mode, 'started_at': time.time(), 'argv': [x.replace('{cycle_dir}', str(directory)) for x in case['command']],
               'status': 'failed', 'verifications': {}}
    try:
        if mode == 'profiled':
            local_profile = observation_profile_path(directory, config)
            checked_scratch_root(config)
            require(local_profile.resolve() == local_profile and not local_profile.exists()
                    and not local_profile.is_symlink(), 'observation local profile path is not fresh')
            local_profile.parent.mkdir(parents=True, exist_ok=False)
        execution = job_run(job); receipt['execution'] = binding(directory / 'job/execution.json')
        require(execution['exit_code'] == 0, 'observation capture failed')
        shutil.copyfile(directory / 'job/stdout.log', directory / 'stdout.log')
        messages = native_messages(directory / 'stdout.log'); timeline_protocol(messages, config, 100)
        if mode == 'profiled':
            require(local_profile.is_dir() and not local_profile.is_symlink()
                    and local_profile.resolve() == local_profile, 'observation local profile is missing or replaced')
            tables = list(local_profile.rglob('op_summary*.csv'))
            if not tables:
                roots = list(local_profile.glob('PROF_*')); require(len(roots) == 1, 'ambiguous profile root')
                export = dict(job, job_id=job['job_id'] + '-export', output_dir=str(directory / 'export-job'), timeout_seconds=300,
                    argv=[config['task_profile']['profiler'], '--export=on', '--type=text', '--output=' + str(roots[0])])
                require(job_run(export)['exit_code'] == 0, 'observation export failed')
            tables = list(local_profile.rglob('op_summary*.csv')); require(len(tables) == 1, 'unique task table required')
            collector, _, partition, controls = task_modules()
            transfer = collector.copy_profile_tree(local_profile, directory / 'profile',
                relative_profile_inventory(local_profile),
                deadline=deadline if deadline is not None else time.monotonic() + BUDGETS['observation'])
            save_new(directory / 'profile-transfer.json', transfer)
            receipt['profile_transfer'] = binding(directory / 'profile-transfer.json')
            tables = list((directory / 'profile').rglob('op_summary*.csv')); require(len(tables) == 1, 'unique persisted task table required')
            receipt['profile_files'] = profile_inventory(directory / 'profile'); receipt['table'] = binding(tables[0])
        for role in ('baseline', 'candidate'): receipt['verifications'][role] = oracle(directory, role, case, config['build']['source_dir'])
        receipt['finished_at'] = time.time()
        for role in ('baseline', 'candidate'): production_oracle(directory, role, case, receipt, Evidence())
        if mode == 'profiled':
            result = partition(tables[0], messages, operator=config['operator'], cycle=0, repeat=100,
                               role_kernel_names=config['task_profile']['role_kernel_names'])
            save_new(directory / 'partition.json', result); receipt['partition'] = binding(directory / 'partition.json')
            receipt['task_controls'] = controls(result['values_ns_per_call']); check_controls(receipt['task_controls'])
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        for role in ('baseline', 'candidate'):
            path = directory / f'{role}-verify-receipt.json'
            if path.exists(): receipt['verifications'][role] = read(path)
        if (directory / 'job/execution.json').exists(): receipt['execution'] = binding(directory / 'job/execution.json')
        receipt['finished_at'] = time.time(); save_new(directory / 'receipt.json', receipt)
    return receipt


def observe(output, operator, case_id):
    output = Path(output).resolve(strict=True); plan, _ = checked_plan(output)
    order = dict(OBSERVATIONS[operator])[case_id]; folder = output / 'observations' / f'{operator}-observation-{case_id:02d}'
    folder.mkdir(parents=True, exist_ok=False); save_new(folder / 'started.json', {'at': time.time(), 'order': order})
    config = read(plan['configs'][operator]); case = next(c for c in config['cases'] if c['case_id'] == case_id)
    checked_scratch_root(config)
    deadline = time.monotonic() + BUDGETS['observation']
    modes = {}; failed = False
    with locks(['device-0.lock']):
        for mode in order:
            if failed:
                save_new(folder / (mode + '-not-run.json'), {'status': 'not_run', 'prerequisite': binding(folder / order[0] / 'receipt.json')})
                modes[mode] = {'status': 'not_run', 'receipt': binding(folder / (mode + '-not-run.json'))}
            else:
                result = observation_mode(folder / mode, config, case, mode, deadline=deadline); failed = result['status'] != 'passed'
                modes[mode] = {'status': result['status'], 'receipt': binding(folder / mode / 'receipt.json')}
    result = {'order': order, 'modes': modes, 'complete': not failed, 'finished_at': time.time(), 'publication_acceptance': False}
    save_new(folder / 'terminal.json', result)
    require(not failed, 'paired instrumentation observation failed; no retry')
    return result


def replay_task_observation(output, *, qualification_dir, operator, case_id):
    output = Path(output).resolve(strict=True); qualification_dir = Path(qualification_dir).resolve(strict=True)
    evidence = Evidence(); plan, _ = checked_plan(qualification_dir, evidence)
    require(output == qualification_dir / 'observations' / f'{operator}-observation-{case_id:02d}', 'observation outside frozen slot')
    terminal = evidence.json(output / 'terminal.json'); started = evidence.json(output / 'started.json')
    order = dict(OBSERVATIONS[operator])[case_id]
    require(terminal['order'] == started['order'] == order and terminal['complete'] and set(terminal['modes']) == set(order), 'observation incomplete/order differs')
    config = read(plan['configs'][operator]); case = next(c for c in config['cases'] if c['case_id'] == case_id)
    previous = started['at']; messages = {}; partition = None
    for mode in order:
        directory = output / mode; row = terminal['modes'][mode]; receipt = evidence.json(directory / 'receipt.json')
        require(row == {'status': 'passed', 'receipt': binding(directory / 'receipt.json')} and receipt['mode'] == mode
                and receipt['status'] == 'passed' and previous <= receipt['started_at'] <= receipt['finished_at'] <= terminal['finished_at'], 'mode terminal/order differs')
        require(receipt['argv'] == [x.replace('{cycle_dir}', str(directory)) for x in case['command']], 'native command differs')
        job = observation_job(directory, config, case, mode); execution = evidence.json(directory / 'job/execution.json')
        require(receipt['execution'] == binding(directory / 'job/execution.json'), 'mode execution reference differs')
        end = execution_interval(execution, job, receipt['started_at'], receipt['finished_at'], evidence)
        require(digest(directory / 'stdout.log') == execution['stdout']['sha256'], 'native stdout differs')
        messages[mode] = native_messages(directory / 'stdout.log'); timeline_protocol(messages[mode], config, 100)
        if (directory / 'export-job/execution.json').exists():
            require(mode == 'profiled', 'unprofiled export is invalid')
            profile_name = Path(receipt['table']['path']).parents[1].name
            require(profile_name.startswith('PROF_'), 'export profile identity differs')
            expected = dict(job, job_id=job['job_id'] + '-export', output_dir=str(directory / 'export-job'), timeout_seconds=300,
                argv=[config['task_profile']['profiler'], '--export=on', '--type=text',
                      '--output=' + str(observation_profile_path(directory, config) / profile_name)])
            end = execution_interval(evidence.json(directory / 'export-job/execution.json'), expected, end, receipt['finished_at'], evidence)
        if mode == 'profiled':
            end = replay_profile_transfer(directory, config, receipt, end, evidence)
        else:
            require('profile_transfer' not in receipt and not (directory / 'profile-transfer.json').exists()
                    and not (directory / 'profile').exists(), 'unprofiled observation has profiler artifacts')
        require(set(receipt['verifications']) == {'baseline', 'candidate'}, 'both original oracles required')
        for role in ('baseline', 'candidate'):
            verification = receipt['verifications'][role]
            require(verification == evidence.json(directory / f'{role}-verify-receipt.json') and verification['status'] == 'passed'
                    and end <= verification['started_at'] <= verification['finished_at'] <= receipt['finished_at']
                    and verification['finished_at'] - verification['started_at'] <= 120
                    and verification['output_after_sha256'] == verification['output_sha256'], 'oracle identity/time differs')
            production_oracle(directory, role, case, receipt, evidence); end = verification['finished_at']
        if mode == 'profiled':
            require(profile_inventory(directory / 'profile') == receipt['profile_files'], 'profile artifact inventory changed')
            for path, expected in receipt['profile_files'].items(): evidence.bind(path, expected)
            tables = list((directory / 'profile').rglob('op_summary*.csv'))
            require(len(tables) == 1 and binding(tables[0]) == receipt['table'], 'task table differs')
            _, _, parse, controls = task_modules()
            partition = parse(tables[0], messages[mode], operator=operator, cycle=0, repeat=100, role_kernel_names=config['task_profile']['role_kernel_names'])
            quality = controls(partition['values_ns_per_call']); check_controls(quality)
            require(evidence.json(directory / 'partition.json') == partition and binding(directory / 'partition.json') == receipt['partition']
                    and quality == receipt['task_controls'], 'Task partition/control summary differs')
        previous = receipt['finished_at']
    comparison = {}
    for mode in order:
        values = [message[role] for message in messages[mode] if message['kind'] == 'pair' for role in ('baseline', 'candidate')]
        comparison[mode] = {'event_ns_per_call': [v['elapsed_ns'] for v in values],
                           'host_ns_per_call': [(v['finished_monotonic_ns'] - v['started_monotonic_ns']) / 100 for v in values]}
    comparison['ratio_of_means_P_over_U'] = {key: statistics.fmean(comparison['profiled'][key]) / statistics.fmean(comparison['unprofiled'][key]) for key in ('event_ns_per_call', 'host_ns_per_call')}
    comparison['scope'] = 'Event/Host auxiliary only, no threshold; unprofiled Task Duration ground truth is unavailable.'
    return {'complete': True, 'order': order, 'task_partition': partition, 'task_controls': quality, 'comparison': comparison,
            'files': {p: v['sha256'] for p, v in evidence.files.items()}}


def replay_task_campaign(roster_path, *, qualification_dir):
    output = Path(qualification_dir).resolve(strict=True); roster_path = Path(roster_path).resolve(strict=True)
    evidence = Evidence(); plan, freeze = checked_plan(output, evidence); roster = evidence.json(roster_path)
    require(roster_path == output / 'roster.json' and roster['qualification_dir'] == str(output)
            and roster['freeze'] == binding(output / 'freeze.json') and roster['slots'] == roster_slots(output, plan)
            and roster['max_attempts'] == 1 and roster['resampling'] == 'none'
            and roster['timeout_seconds'] == BUDGETS['campaign'], 'campaign roster differs')
    directory = output / 'campaign'; started = evidence.json(directory / 'started.json'); campaign = evidence.json(directory / 'campaign.json')
    anchor = evidence.json(started['anchor']['path']); evidence.bind(started['anchor']['path'], started['anchor']['sha256'])
    require(started['roster'] == campaign['roster'] == binding(roster_path) and anchor == {
        'schema_version': 1, 'purpose': PURPOSE, 'roster': binding(roster_path), 'max_attempts': 1,
        'resampling': 'none', 'recorded_at_utc': anchor['recorded_at_utc']}
        and Path(started['anchor']['path']).parent == ROOT / 'scaffolding/curation'
        and freeze['created_at'] <= roster['created_at'] <= datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= started['at'],
        'campaign was not independently anchored before execution')
    ids = [slot['slot_id'] for slot in roster['slots']]
    require(set(campaign['slots']) == set(ids) == {p.name for p in directory.iterdir() if p.is_dir()}
            and campaign['resampling'] == 'none', 'unknown or missing campaign slots')
    previous = started['at']; results = {}
    for slot in roster['slots']:
        path = directory / slot['slot_id']; terminal = evidence.json(path / 'terminal.json')
        require(campaign['slots'][slot['slot_id']] == binding(path / 'terminal.json') and all(terminal[k] == slot[k] for k in ('slot_id', 'kind', 'operator')),
                'slot terminal binding differs')
        result = {**{key: terminal[key] for key in ('status', 'kind', 'operator')}, 'terminal': binding(path / 'terminal.json')}
        prior = slot['prerequisite_slot']
        if terminal['status'] == 'not_run':
            require(prior and results[prior]['status'] != 'passed' and terminal['prerequisite_ref'] == binding(directory / prior / 'terminal.json')
                    and not (path / 'started.json').exists() and 'execution' not in terminal, 'not-run prerequisite differs')
        else:
            require(terminal['status'] in ('passed', 'failed') and (not prior or results[prior]['status'] == 'passed'), 'illegal attempted slot')
            entry = evidence.json(path / 'started.json')
            require(entry['slot'] == slot and terminal['started'] == binding(path / 'started.json')
                    and previous <= entry['at'] <= terminal['finished_at'], 'slot order/start differs')
            if 'execution' in terminal:
                execution = evidence.json(path / 'job/execution.json')
                require(terminal['execution'] == binding(path / 'job/execution.json') and execution['job'] == slot['job'], 'actual slot job differs')
                for key in ('stdout', 'stderr'): evidence.bind(execution[key]['path'], execution[key]['sha256'])
                require(entry['at'] <= datetime.fromisoformat(execution['started_at']).timestamp()
                        <= datetime.fromisoformat(execution['finished_at']).timestamp() <= terminal['finished_at'], 'slot execution outside interval')
                result['execution'] = execution
            if terminal['status'] == 'passed':
                execution_interval(result['execution'], slot['job'], entry['at'], terminal['finished_at'], evidence)
                result_key = 'admission' if slot['kind'] == 'confirmation' else 'observation'
                result[result_key] = full_admission(output, slot['operator']) if slot['kind'] == 'confirmation' else replay_task_observation(
                    output / 'observations' / slot['slot_id'], qualification_dir=output, operator=slot['operator'], case_id=slot['case_id'])
                report = path / 'replay.json' if slot['kind'] == 'confirmation' else Path(slot['output_dir']) / 'observation-report.json'
                require(terminal['replay'] == binding(report) and evidence.json(report) == result[result_key], 'saved slot replay differs')
                if slot['kind'] == 'observation': require(terminal['observation_report'] == binding(report), 'observation report reference differs')
        require(previous <= terminal['finished_at'], 'terminal time reversed')
        previous = terminal['finished_at']; results[slot['slot_id']] = result
    accepted = all(row['status'] == 'passed' for row in results.values())
    require(campaign['accepted'] == accepted, 'campaign aggregate differs')
    return {'complete': True, 'accepted': accepted, 'authority': 'method_qualification_only_no_publication',
            'protocol': PROTOCOL, 'slots': results, 'files': {p: v['sha256'] for p, v in evidence.files.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'freeze', 'run', 'observe'))
    parser.add_argument('--output', type=Path); parser.add_argument('--history', type=Path)
    parser.add_argument('--roster', type=Path); parser.add_argument('--anchor', type=Path)
    parser.add_argument('--operator', choices=('exp', 'sigmoid')); parser.add_argument('--case-id', type=int)
    args = parser.parse_args()
    result = {'prepare': lambda: prepare(args.output, args.history), 'freeze': lambda: freeze(args.output),
        'run': lambda: run(args.roster, args.anchor), 'observe': lambda: observe(args.output, args.operator, args.case_id)}[args.action]()
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__': main()
