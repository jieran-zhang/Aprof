#!/usr/bin/env python3
"""Two once-only native Task API facility checks; never method admission."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import time

from run_aprof_job import run as job_run
from run_shared_timing_confirmation import (BASE_ENVIRONMENT, ROOT, RELEASE, binding, locks,
    native_messages, production_oracle, save_new)
from replay_timing_diagnosis import Evidence, digest, read, require
from diagnose_task_duration import oracle, execution_interval
from qualify_shared_timing_v051 import source_files
from task_profile_native import adapt_host, adapt_cmake, HEADER
from measurement_source_archive import HistoricalEvidence

sys.path.insert(0, str(RELEASE / 'runtime/src'))
from aprof_runtime.task_timing import partition_task_samples, protocol_commands
from aprof_runtime.measurement_admission import _phase_controls

PURPOSE = 'native_task_api_facility_probe_not_admission'
PRIOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2'
SLOTS = [('exp', 1), ('sigmoid', 4)]
BUDGETS = {'native': 120, 'export': 300, 'oracle': 120, 'outer': 1500}
PROFILE_ENV_PREFIXES = ('APROF_SHARED_', 'APROF_TASK_PROFILE_', 'ACL_PROF', 'ASCEND_PROF', 'PROF_', 'PROFILING_')


def clean_parent_environment():
    require(not any(key.startswith(PROFILE_ENV_PREFIXES) for key in os.environ),
            'inherited native timing/profiling controls are not registered')


def check_controls(quality):
    require(all(quality[p]['role_bias'] <= .02 and all(quality[p][r + '_cv'] <= .05
            for r in ('baseline', 'candidate')) for p in ('aa_before', 'formal', 'aa_after'))
            and all(v <= .02 for v in quality['drift'].values()), 'local Task A/A control failed')


def bound_json(ref):
    require(binding(ref['path']) == ref, 'bound JSON changed')
    return read(ref['path'])


def source_identity(source_root, operator):
    folder = source_root / operator; review = read(folder / 'source-review.json'); build = read(folder / 'build-receipt.json')
    old, source = PRIOR / operator / 'source', folder / 'source'
    require(review['operator'] == operator and review['original_source'] == str(old)
            and review['adapted_source'] == str(source) and source_files(old) == review['original_files']
            and source_files(source) == review['adapted_files'], 'native source review differs')
    require(set(review['patches']) == {f'op_host/{operator}.asc', 'CMakeLists.txt'}
            and set(review['adapted_files']) - set(review['original_files']) == {'op_host/device_task_profile.h'}, 'native adapter scope differs')
    for name, adapter in ((f'op_host/{operator}.asc', adapt_host), ('CMakeLists.txt', adapt_cmake)):
        require((source / name).read_text() == adapter((old / name).read_text(), operator), 'mechanical native adapter differs')
    for name, expected in review['original_files'].items():
        if name not in review['patches']: require(review['adapted_files'][name] == expected, 'protected kernel/header/oracle changed')
    require(digest(source / 'op_host/device_task_profile.h') == digest(HEADER), 'profiling API header differs')
    require(build['status'] == 'passed' and build['source_review'] == binding(folder / 'source-review.json')
            and build['binary'] == binding(source / 'build' / operator) and len(build['commands']) == 2, 'native build receipt differs')
    files = {str(base / p): 'sha256:' + h.removeprefix('sha256:') for base, inventory in
             ((old, review['original_files']), (source, review['adapted_files'])) for p, h in inventory.items()}
    for command in build['commands']:
        execution = bound_json(command['execution'])
        require(execution['status'] == 'passed' and execution['exit_code'] == 0, 'native build command failed')
        files[command['execution']['path']] = command['execution']['sha256']
        for key in ('stdout', 'stderr'): files[execution[key]['path']] = execution[key]['sha256']
    files.update(build['tool_files']); files.update({p: 'sha256:' + h.removeprefix('sha256:') for p, h in review['producers'].items()})
    for p in (folder / 'source-review.json', folder / 'build-receipt.json', source / 'build' / operator): files[str(p)] = digest(p)
    return source, files


def prepare(output, source_root):
    output = Path(output).resolve(); source_root = Path(source_root).resolve(strict=True)
    require(not output.exists(), 'probe directory already exists; no retry')
    output.mkdir(parents=True); save_new(output / 'prepare-started.json', {'at': time.time()})
    commands = output / 'commands.txt'; commands.write_text('\n'.join(protocol_commands()) + '\n')
    files = {str(commands): digest(commands)}; slots = []; profiler = Path(shutil.which('msprof')).resolve(strict=True)
    for operator, case_id in SLOTS:
        source, identity = source_identity(source_root, operator); files.update(identity)
        config_path = PRIOR / operator / 'config.json'; config = read(config_path)
        case = deepcopy(next(c for c in config['cases'] if c['case_id'] == case_id))
        require(case['command'][0] == str(PRIOR / operator / 'source/build' / operator), 'original command differs')
        case['command'][0] = str(source / 'build' / operator)
        for p in [config_path, *map(Path, case['prepared_files'])]: files[str(p)] = digest(p)
        slots.append({'slot_id': f'{operator}-{case_id:02d}', 'operator': operator, 'case_id': case_id,
                      'source': str(source), 'original_config': binding(config_path), 'case': case,
                      'role_kernel_names': {r: [operator + '_kernel'] for r in ('baseline', 'candidate')}})
    producers = [Path(__file__), HEADER, *[Path(__file__).with_name(n) for n in ('run_aprof_job.py',
        'run_shared_timing_confirmation.py', 'replay_timing_diagnosis.py', 'diagnose_task_duration.py',
        'qualify_shared_timing_v051.py', 'task_profile_native.py', 'measurement_source_archive.py')]]
    producers += list((RELEASE / 'runtime/src/aprof_runtime').glob('*.py'))
    for p in [profiler, Path(sys.executable).resolve(), *producers]: files[str(p)] = digest(p)
    plan = {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(), 'source_root': str(source_root),
        'repeat': 100, 'cycle': 0, 'commands': binding(commands), 'task_count': 4222, 'native_events': 30,
        'slots': slots, 'budgets': BUDGETS, 'profiler': binding(profiler), 'files': files,
        'max_attempts': 1, 'stop_on_failure': 'all_remaining_slots', 'resampling': 'none', 'eligible_for_publication': False,
        'reject_inherited_environment_prefixes': list(PROFILE_ENV_PREFIXES),
        'cost_scope': 'Two facility lifetimes only; CLI oracles cold-start. These costs do not establish a full 20-case qualification budget.'}
    save_new(output / 'plan.json', plan); return binding(output / 'plan.json')


def checked_plan(output, evidence=None):
    plan = read(output / 'plan.json'); evidence = evidence or Evidence()
    require(plan['purpose'] == PURPOSE and plan['repeat'] == 100 and plan['cycle'] == 0 and plan['task_count'] == 4222
            and plan['native_events'] == 30 and [(x['operator'], x['case_id']) for x in plan['slots']] == SLOTS
            and plan['budgets'] == BUDGETS and plan['max_attempts'] == 1 and plan['resampling'] == 'none'
            and plan['reject_inherited_environment_prefixes'] == list(PROFILE_ENV_PREFIXES)
            and plan['stop_on_failure'] == 'all_remaining_slots' and plan['eligible_for_publication'] is False, 'fixed facility scope differs')
    require(binding(output / 'commands.txt') == plan['commands']
            and (output / 'commands.txt').read_text().splitlines() == protocol_commands(), 'native command file differs')
    for slot in plan['slots']:
        config = bound_json(slot['original_config']); source = Path(plan['source_root']) / slot['operator'] / 'source'
        case = deepcopy(next(c for c in config['cases'] if c['case_id'] == slot['case_id']))
        case['command'][0] = str(source / 'build' / slot['operator'])
        require(slot['source'] == str(source) and slot['case'] == case
                and slot['role_kernel_names'] == {r: [slot['operator'] + '_kernel'] for r in ('baseline', 'candidate')}, 'original case contract differs')
    for path, expected in plan['files'].items(): evidence.bind(path, expected)
    return plan


def freeze(output):
    output = Path(output).resolve(strict=True); plan = checked_plan(output)
    save_new(output / 'freeze.json', {'schema_version': 1, 'created_at': time.time(), 'plan': binding(output / 'plan.json'), 'files': plan['files']})
    return binding(output / 'freeze.json')


def anchored(output, anchor, latest, evidence=None):
    frozen, value = read(output / 'freeze.json'), read(anchor); stamp = datetime.fromisoformat(value['recorded_at_utc'])
    require(Path(anchor).resolve().parent == ROOT / 'scaffolding/curation' and value == {'schema_version': 1, 'purpose': PURPOSE,
        'freeze': binding(output / 'freeze.json'), 'max_attempts': 1, 'resampling': 'none', 'recorded_at_utc': value['recorded_at_utc']}
        and stamp.tzinfo is not None and frozen['created_at'] <= stamp.timestamp() <= latest, 'root anchor differs')
    plan = checked_plan(output, evidence)
    require(frozen['plan'] == binding(output / 'plan.json') and frozen['files'] == plan['files'], 'freeze differs')
    return plan


def native_job(output, plan, slot):
    folder = output / slot['slot_id']; native = folder / 'native'
    return {'job_id': slot['slot_id'] + '-native', 'argv': [x.replace('{cycle_dir}', str(native)) for x in slot['case']['command']],
        'cwd': slot['source'], 'output_dir': str(folder / 'native-job'), 'timeout_seconds': BUDGETS['native'],
        'environment': dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_MODE='confirmation', APROF_SHARED_CYCLE='0',
            APROF_SHARED_REPEAT='100', APROF_SHARED_COMMANDS=str(output / 'commands.txt'), APROF_TASK_PROFILE_DIR=str(folder / 'profile'))}


def export_job(output, plan, slot, profile):
    return {'job_id': slot['slot_id'] + '-export', 'argv': [plan['profiler']['path'], '--export=on', '--type=text', '--output=' + str(profile)],
        'cwd': slot['source'], 'output_dir': str(output / slot['slot_id'] / 'export-job'), 'timeout_seconds': BUDGETS['export'], 'environment': BASE_ENVIRONMENT}


def parse_slot(folder, slot):
    tables = list((folder / 'profile').rglob('op_summary*.csv')); require(len(tables) == 1, 'unique complete Task table required')
    messages = native_messages(folder / 'native/stdout.log')
    partition = partition_task_samples(tables[0], messages, operator=slot['operator'], cycle=0, repeat=100, role_kernel_names=slot['role_kernel_names'])
    quality = _phase_controls(partition['values_ns_per_call']); check_controls(quality)
    require(partition['task_count'] == 4222, 'full native Task scope differs')
    return {'table': binding(tables[0]), 'partition': partition, 'controls': quality, 'local_controls_passed': True, 'eligible_for_publication': False}


def run_slot(output, plan, slot):
    folder = output / slot['slot_id']; folder.mkdir(); native = folder / 'native'; native.mkdir(); (folder / 'profile').mkdir()
    row = {'slot_id': slot['slot_id'], 'started_at': time.time(), 'status': 'failed', 'verifications': {}, 'costs_seconds': {}}
    try:
        job = native_job(output, plan, slot); start = time.time(); execution = job_run(job)
        row['costs_seconds']['native'] = time.time() - start
        require(execution['exit_code'] == 0, 'native facility capture failed')
        roots = list((folder / 'profile').glob('PROF_*')); require(len(roots) == 1, 'one native profiler directory required')
        start = time.time(); execution = job_run(export_job(output, plan, slot, roots[0]))
        row['costs_seconds']['export'] = time.time() - start
        require(execution['exit_code'] == 0, 'native Task export failed')
        shutil.copyfile(folder / 'native-job/stdout.log', native / 'stdout.log')
        for role in ('baseline', 'candidate'):
            start = time.time(); row['verifications'][role] = oracle(native, role, slot['case'], slot['source'])
            row['costs_seconds'][role + '_cold_cli_oracle'] = time.time() - start
        row['finished_at'] = time.time()
        for role in ('baseline', 'candidate'): production_oracle(native, role, slot['case'], row, Evidence())
        start = time.time()
        try: parsed = parse_slot(folder, slot)
        finally: row['costs_seconds']['parse_and_controls'] = time.time() - start
        save_new(folder / 'parsed.json', parsed); row['parsed'] = binding(folder / 'parsed.json'); row['status'] = 'passed'
    except BaseException as error:
        row['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        for name in ('native-job', 'export-job'):
            path = folder / name / 'execution.json'
            if path.exists():
                row[name] = binding(path)
                row['costs_seconds'].setdefault(name.removesuffix('-job'), read(path)['duration_seconds'])
        for role in ('baseline', 'candidate'):
            path = native / f'{role}-verify-receipt.json'
            if path.exists():
                verification = read(path); row['verifications'][role] = verification
                row['costs_seconds'].setdefault(role + '_cold_cli_oracle', verification['finished_at'] - verification['started_at'])
        row['finished_at'] = time.time(); save_new(folder / 'receipt.json', row)
    return row


def run(output, anchor):
    clean_parent_environment()
    output = Path(output).resolve(strict=True); plan = anchored(output, anchor, time.time())
    save_new(output / 'started.json', {'at': time.time(), 'anchor': binding(anchor)}); results = {}; previous = None
    with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]):
        for slot in plan['slots']:
            if previous and results[previous]['status'] != 'passed':
                folder = output / slot['slot_id']; folder.mkdir()
                row = {'slot_id': slot['slot_id'], 'status': 'not_run', 'prerequisite': binding(output / previous / 'receipt.json')}
                save_new(folder / 'receipt.json', row)
            else: row = run_slot(output, plan, slot)
            results[slot['slot_id']] = row; previous = slot['slot_id']
    terminal = {'finished_at': time.time(), 'slots': {name: binding(output / name / 'receipt.json') for name in results},
        'facility_complete': all(r['status'] == 'passed' for r in results.values()), 'eligible_for_publication': False,
        'cost_scope': plan['cost_scope']}
    save_new(output / 'terminal.json', terminal); return terminal


def replay(output, anchor, source_archive_refs=()):
    evidence = HistoricalEvidence(source_archive_refs, logical_paths=True) if source_archive_refs else Evidence()
    output = Path(output).resolve(strict=True); started = read(output / 'started.json'); plan = anchored(output, anchor, started['at'], evidence)
    for name, function in (('task_timing.py', partition_task_samples), ('measurement_admission.py', _phase_controls)):
        path = RELEASE / 'runtime/src/aprof_runtime' / name
        require(Path(function.__code__.co_filename).resolve() == path and digest(path) == plan['files'][str(path)],
                'actually executed pure parser/control code differs from the frozen probe')
    require(started['anchor'] == binding(anchor), 'executed root anchor differs')
    terminal = read(output / 'terminal.json'); previous = started['at']; rows = {}
    for slot in plan['slots']:
        folder = output / slot['slot_id']; row = evidence.json(folder / 'receipt.json')
        require(terminal['slots'][slot['slot_id']] == binding(folder / 'receipt.json'), 'slot receipt differs')
        if row['status'] == 'passed':
            require(previous <= row['started_at'] <= row['finished_at'] <= terminal['finished_at'], 'slot chronology differs')
            execution = bound_json(row['native-job'])
            end = execution_interval(execution, native_job(output, plan, slot), row['started_at'], row['finished_at'], evidence)
            require(digest(folder / 'native/stdout.log') == execution['stdout']['sha256'], 'native stdout copy differs')
            roots = list((folder / 'profile').glob('PROF_*')); require(len(roots) == 1, 'profile directory differs')
            end = execution_interval(bound_json(row['export-job']), export_job(output, plan, slot, roots[0]), end, row['finished_at'], evidence)
            require(set(row['verifications']) == {'baseline', 'candidate'}, 'both original oracle receipts required')
            for role in ('baseline', 'candidate'):
                verification = row['verifications'][role]
                require(verification == evidence.json(folder / 'native' / f'{role}-verify-receipt.json') and end <= verification['started_at']
                        and verification['status'] == 'passed' and verification['output_after_sha256'] == verification['output_sha256']
                        and verification['finished_at'] - verification['started_at'] <= 120, 'oracle chronology differs')
                production_oracle(folder / 'native', role, slot['case'], row, evidence); end = verification['finished_at']
            parsed = parse_slot(folder, slot)
            require(parsed == bound_json(row['parsed']), 'saved Task partition differs')
            previous = row['finished_at']
        elif row['status'] == 'not_run':
            require(rows and list(rows.values())[-1]['status'] == 'failed' and not (folder / 'native').exists()
                    and row['prerequisite'] == binding(output / list(rows)[-1] / 'receipt.json'), 'unjustified skipped slot')
        else: require(row['status'] == 'failed', 'unknown slot outcome')
        rows[slot['slot_id']] = row
    require(terminal['facility_complete'] == all(x['status'] == 'passed' for x in rows.values())
            and terminal['eligible_for_publication'] is False, 'facility aggregate differs')
    return {'facility_complete': terminal['facility_complete'], 'eligible_for_publication': False, 'slots': rows,
            'terminal': binding(output / 'terminal.json'), 'scope': plan['cost_scope'],
            'resolved_files': getattr(evidence, 'resolved_files', {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action', choices=('prepare', 'freeze', 'run', 'replay'))
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--source-root', type=Path); parser.add_argument('--anchor', type=Path)
    args = parser.parse_args(); actions = {'prepare': lambda: prepare(args.output, args.source_root), 'freeze': lambda: freeze(args.output),
        'run': lambda: run(args.output, args.anchor), 'replay': lambda: replay(args.output, args.anchor)}
    print(json.dumps(actions[args.action](), sort_keys=True, allow_nan=False))


if __name__ == '__main__': main()
