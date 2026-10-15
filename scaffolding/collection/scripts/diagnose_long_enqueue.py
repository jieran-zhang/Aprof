#!/usr/bin/env python3
"""One preregistered exp case-10 enqueue diagnostic; never measurement admission.

prepare -> build -> freeze -> externally anchor -> run -> replay.  The only
native change from the failed production-duration-v2 campaign is the timing
header.  A failed attempt is retained and cannot be resumed or retried here.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import statistics
import subprocess
import time

from run_shared_timing_confirmation import BASE_ENVIRONMENT, binding, locks, save_new
from qualify_shared_timing_v051 import protocol_commands

ROOT = Path(__file__).resolve().parents[3]
PREDECESSOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2'
HEADER = ROOT / 'scaffolding/benchmarks/cannbench/harness/device_submission_diagnostic_v2.h'
PREFIX = b'APROF_SHARED_TIMING_JSON:'
PROTOCOL = 'shared_buffer_submission_diagnostic_v2'
PURPOSE = 'exp_case10_single_cycle_long_enqueue_diagnosis_only'
CASE_ID, CYCLE, REPEAT = 10, 0, 7300
PHASES = ('aa_before', 'formal', 'aa_after')
ROLES = ('baseline', 'candidate')
SEGMENTS = ('start_record', 'enqueue', 'end_record', 'sync')
USAGE = ('utime_ns', 'stime_ns', 'minflt', 'majflt', 'nvcsw', 'nivcsw')
MAX_RAM_LOG = 32 * 1024 * 1024
NATIVE_TIMEOUT = 330
ORACLE_TIMEOUT = 120


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError('long enqueue diagnostic: ' + message)


def source_files(root):
    return sorted(path for path in Path(root).rglob('*') if path.is_file()
                  and not {'build', '__pycache__', '.pytest_cache'} & set(path.relative_to(root).parts))


def file_bindings(paths):
    return {str(path): binding(path)['sha256'] for path in paths}


def verify_bindings(files):
    for filename, digest in files.items():
        require(binding(filename)['sha256'] == digest, 'frozen file changed: ' + filename)


def _history(predecessor):
    """Bind the complete failed six-slot campaign and its actual native output."""
    names = ['plan.json', 'freeze.json', 'roster.json', 'campaign/started.json',
             'campaign/campaign.json', 'post-exp-failure-observation.json']
    roster = read(predecessor / 'roster.json')
    require(roster['order'] == ['exp-confirmation', 'exp-timeline-01', 'exp-timeline-09',
                                'sigmoid-confirmation', 'sigmoid-timeline-01', 'sigmoid-timeline-04'],
            'predecessor slot roster changed')
    names += [f'campaign/{slot}/terminal.json' for slot in roster['order']]
    names += ['exp/confirmation/config.json', 'exp/confirmation/registration.json',
              'exp/confirmation/raw_measurements.json', 'exp/confirmation/measurement_report.json',
              'exp/confirmation/measurement_admission.json']
    campaign = read(predecessor / 'campaign/campaign.json')
    require(campaign['accepted'] is False and set(campaign['slots']) == set(roster['order'])
            and campaign['resampling'] == 'none', 'predecessor failure campaign incomplete')
    terminals = {slot: read(predecessor / 'campaign' / slot / 'terminal.json') for slot in roster['order']}
    require(terminals['exp-confirmation']['status'] == 'failed'
            and all(row['status'] in ('passed', 'failed', 'not_run') for row in terminals.values()),
            'predecessor exp failure or terminal inventory changed')
    for operator in ('exp', 'sigmoid'):
        for name in ('config.json', 'calibration.json', 'registration.json',
                     'raw_measurements.json', 'measurement_report.json', 'measurement_admission.json'):
            path = predecessor / operator / 'confirmation' / name
            if path.is_file() and str(path.relative_to(predecessor)) not in names:
                names.append(str(path.relative_to(predecessor)))
    return {str(predecessor / name): binding(predecessor / name)['sha256'] for name in names}


def prepare(output):
    output = Path(output).resolve()
    require(not output.exists(), 'output already exists; no implicit retry')
    predecessor = PREDECESSOR.resolve(strict=True)
    config = read(predecessor / 'exp/config.json')
    cases = [item for item in config['cases'] if item['case_id'] == CASE_ID]
    require(len(cases) == 1 and config['operator'] == 'exp', 'original case scope changed')
    require(HEADER.is_file(), 'new diagnostic header is not present')
    old_source = Path(config['build']['source_dir']).resolve(strict=True)
    old_files = source_files(old_source)
    output.mkdir(parents=True)
    source = output / 'source'
    shutil.copytree(old_source, source, ignore=shutil.ignore_patterns('build', '__pycache__', '.pytest_cache'))
    shutil.copyfile(HEADER, source / 'op_host/device_shared_timing.h')
    old_inventory = {str(path.relative_to(old_source)): binding(path)['sha256'] for path in old_files}
    new_inventory = {str(path.relative_to(source)): binding(path)['sha256'] for path in source_files(source)}
    require(set(old_inventory) == set(new_inventory)
            and [name for name in sorted(old_inventory) if old_inventory[name] != new_inventory[name]]
            == ['op_host/device_shared_timing.h'], 'source intervention is not exactly the header')
    case = cases[0]
    require(case['command'][0] == str(old_source / 'build/exp'), 'original native binary path changed')
    case['command'][0] = str(source / 'build/exp')
    for role in ROLES:
        case['verify_commands'][role] = [token.replace(str(old_source), str(source))
                                         for token in case['verify_commands'][role]]
    require(case['workload']['shape'] == [2049, 513] and case['workload']['dtype'] == 'float16'
            and case['workload']['numel'] == 1051137, 'case-10 workload changed')
    metadata = read(case['prepared_files'][0])
    require(metadata['case_id'] == CASE_ID and metadata['shape'] == [2049, 513]
            and metadata['dtype'] == 'float16' and Path(case['prepared_files'][1]).stat().st_size == 2102274,
            'original metadata/input differs')
    plan = {'schema_version': 1, 'purpose': PURPOSE, 'protocol': PROTOCOL, 'accepted': False,
            'created_at': time.time(), 'predecessor': str(predecessor),
            'predecessor_config': binding(predecessor / 'exp/config.json'),
            'case': case, 'source_dir': str(source), 'cycle': CYCLE, 'repeat': REPEAT,
            'commands': protocol_commands(), 'pairs_per_phase': 5, 'warmup_per_role': 10,
            'prime_repeat': 100, 'environment': BASE_ENVIRONMENT,
            'source_intervention': ['op_host/device_shared_timing.h'],
            'original_source_files': {str(old_source / name): digest for name, digest in old_inventory.items()},
            'source_files': {str(source / name): digest for name, digest in new_inventory.items()},
            'input_files': file_bindings(map(Path, case['prepared_files'])),
            'producer_files': file_bindings((Path(__file__), HEADER,
                                            Path(__file__).with_name('run_shared_timing_confirmation.py'),
                                            Path(__file__).with_name('qualify_shared_timing_v051.py'),
                                            Path(__file__).with_name('diagnose_submission_stalls.py'),
                                            Path(__file__).with_name('replay_timing_diagnosis.py'))),
            'policy': {'max_attempts': 1, 'resampling': 'none',
                       'measurement_admission_eligible': False, 'publication_acceptance': False,
                       'failure': 'preserve every sample and terminal; never replace this run'},
            'interpretation': 'Four host segments and 100-launch checkpoints are observations; no mechanism is inferred.'}
    save_new(output / 'plan.json', plan)
    return plan


def _check_plan(output, plan):
    require(plan['schema_version'] == 1 and plan['purpose'] == PURPOSE
            and plan['protocol'] == PROTOCOL and plan['accepted'] is False
            and plan['cycle'] == CYCLE and plan['repeat'] == REPEAT
            and plan['commands'] == protocol_commands()
            and plan['source_dir'] == str(output / 'source')
            and plan['source_intervention'] == ['op_host/device_shared_timing.h']
            and plan['environment'] == BASE_ENVIRONMENT
            and plan['policy']['max_attempts'] == 1 and plan['policy']['resampling'] == 'none'
            and plan['policy']['measurement_admission_eligible'] is False
            and plan['policy']['publication_acceptance'] is False,
            'fixed one-cycle diagnostic plan changed')
    predecessor = Path(plan['predecessor'])
    require(plan['predecessor_config'] == binding(predecessor / 'exp/config.json'),
            'predecessor exp config changed')
    config = read(predecessor / 'exp/config.json')
    cases = [item for item in config['cases'] if item['case_id'] == CASE_ID]
    require(config['operator'] == 'exp' and len(cases) == 1, 'predecessor exp case changed')
    expected = cases[0]
    old_source = str(Path(config['build']['source_dir']).resolve(strict=True))
    source = Path(plan['source_dir'])
    require(set(plan['original_source_files']) == {str(path) for path in source_files(Path(old_source))}
            and set(plan['source_files']) == {str(path) for path in source_files(source)},
            'source file inventory changed')
    original = {str(Path(path).relative_to(old_source)): digest
                for path, digest in plan['original_source_files'].items()}
    replacement = {str(Path(path).relative_to(source)): digest
                   for path, digest in plan['source_files'].items()}
    require(set(original) == set(replacement)
            and [name for name in sorted(original) if original[name] != replacement[name]]
            == ['op_host/device_shared_timing.h'], 'source intervention changed')
    expected['command'][0] = str(output / 'source/build/exp')
    for role in ROLES:
        expected['verify_commands'][role] = [token.replace(old_source, str(output / 'source'))
                                             for token in expected['verify_commands'][role]]
    require(plan['case'] == expected and set(plan['input_files']) == set(expected['prepared_files']),
            'original case, inputs, or oracles changed')


def build(output):
    output = Path(output).resolve(strict=True)
    plan = read(output / 'plan.json')
    require(not (output / 'build-started.json').exists(), 'build already attempted')
    verify_bindings(plan['source_files'] | plan['input_files'] | plan['producer_files'])
    source = Path(plan['source_dir'])
    build_env = os.environ.copy()
    environment = {key: build_env.get(key) for key in
                   ('PATH', 'ASCEND_HOME_PATH', 'ASCEND_OPP_PATH', 'LD_LIBRARY_PATH',
                    'CMAKE_PREFIX_PATH', 'ASC_DIR', 'CC', 'CXX')}
    successful = read(Path(plan['predecessor']) / 'exp/build-started.json')['environment']
    require(all(environment[key] == successful[key] for key in ('ASCEND_HOME_PATH', 'ASCEND_OPP_PATH'))
            and environment['PATH'] and shutil.which('cmake', path=environment['PATH'])
            and Path(environment['ASCEND_HOME_PATH'], 'lib64/cmake').is_dir()
            and Path(environment['ASCEND_OPP_PATH']).is_dir()
            and environment['LD_LIBRARY_PATH']
            and str(Path(environment['ASCEND_HOME_PATH']) / 'lib64')
            in environment['LD_LIBRARY_PATH'].split(os.pathsep),
            'successful CANN SDK/CMake environment is unavailable; build not attempted')
    save_new(output / 'build-started.json', {'at': time.time(), 'plan': binding(output / 'plan.json'),
                                             'environment': environment})
    rows = []
    commands = (['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                ['cmake', '--build', str(source / 'build'), '-j2'])
    try:
        for index, argv in enumerate(commands):
            began = time.time()
            with (output / f'build-{index}.log').open('xb') as log:
                done = subprocess.run(argv, cwd=source, env=build_env,
                                      stdout=log, stderr=subprocess.STDOUT, timeout=600)
            rows.append({'argv': argv, 'started_at': began, 'finished_at': time.time(),
                         'exit_status': done.returncode, 'log': binding(output / f'build-{index}.log')})
            require(done.returncode == 0, 'fixed build command failed')
        result = {'status': 'passed', 'environment': environment, 'commands': rows,
                  'binary': binding(source / 'build/exp')}
        save_new(output / 'build-terminal.json', result)
        return result
    except BaseException as error:
        save_new(output / 'build-terminal.json', {'status': 'failed', 'environment': environment,
                                                   'commands': rows,
                                                   'error': {'type': type(error).__name__, 'message': str(error)}})
        raise


def freeze(output):
    output = Path(output).resolve(strict=True)
    require(not (output / 'freeze.json').exists(), 'freeze already exists')
    plan, built = read(output / 'plan.json'), read(output / 'build-terminal.json')
    _check_plan(output, plan)
    require(built['status'] == 'passed' and len(built['commands']) == 2,
            'exactly one successful configure/build required')
    source = Path(plan['source_dir'])
    started = read(output / 'build-started.json')
    require(started['plan'] == binding(output / 'plan.json')
            and built['environment'] == started['environment']
            and [row['argv'] for row in built['commands']] == [
                ['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                ['cmake', '--build', str(source / 'build'), '-j2']]
            and all(row['exit_status'] == 0 and row['log'] == binding(row['log']['path'])
                    for row in built['commands'])
            and built['binary']['path'] == str(source / 'build/exp'),
            'fixed configure/build receipt differs')
    verify_bindings(plan['original_source_files'] | plan['source_files']
                    | plan['input_files'] | plan['producer_files'])
    require(binding(built['binary']['path']) == built['binary'], 'built binary changed')
    history = _history(Path(plan['predecessor']))
    from run_shared_timing_confirmation import replay_confirmation_campaign
    campaign = replay_confirmation_campaign(Path(plan['predecessor']) / 'roster.json',
                                             qualification_dir=Path(plan['predecessor']))
    require(campaign['complete'] is True and campaign['accepted'] is False,
            'predecessor campaign does not independently replay as a failure')
    files = ({plan['predecessor_config']['path']: plan['predecessor_config']['sha256']}
             | plan['original_source_files'] | plan['source_files'] | plan['input_files']
             | plan['producer_files'] | history | campaign['files'])
    for path in (output / 'plan.json', output / 'build-started.json', output / 'build-terminal.json'):
        files[str(path)] = binding(path)['sha256']
    for row in built['commands']:
        files[row['log']['path']] = row['log']['sha256']
    files[built['binary']['path']] = built['binary']['sha256']
    save_new(output / 'freeze.json', {'schema_version': 1, 'purpose': PURPOSE, 'accepted': False,
                                      'created_at': time.time(), 'files': files,
                                      'history': history, 'predecessor_campaign': binding(Path(plan['predecessor']) / 'campaign/campaign.json'),
                                      'plan': binding(output / 'plan.json'), 'build': binding(output / 'build-terminal.json'),
                                      'binary': built['binary'], 'max_attempts': 1, 'resampling': 'none',
                                      'diagnostic_only': True, 'measurement_admission_eligible': False,
                                      'publication_acceptance': False})


def _cgroup_state(pid):
    """Record process membership and counters visible in its mount namespace."""
    proc = Path('/proc') / str(pid)
    try:
        membership = (proc / 'cgroup').read_text()
        mountinfo = (proc / 'mountinfo').read_text()
    except OSError as error:
        return {'pid': pid, 'recorded_monotonic_ns': time.monotonic_ns(), 'read_error': str(error)}
    files = {}
    mounts = []
    for line in membership.splitlines():
        _, controllers, relative = line.split(':', 2)
        if controllers and 'cpu' not in controllers.split(',') and 'cpuset' not in controllers.split(','):
            continue
        for mount in mountinfo.splitlines():
            left, separator, right = mount.partition(' - ')
            if not separator:
                continue
            fields, filesystem = left.split(), right.split()
            if len(fields) < 5 or len(filesystem) < 3 or filesystem[0] != ('cgroup' if controllers else 'cgroup2'):
                continue
            if controllers and not set(controllers.split(',')) & set(filesystem[2].split(',')):
                continue
            mount_root, member = Path(fields[3]), Path(relative)
            if not member.is_relative_to(mount_root):
                continue
            directory = Path(fields[4]) / member.relative_to(mount_root)
            mounts.append({'controllers': controllers, 'membership': relative,
                           'mount_root': str(mount_root), 'mount_point': fields[4],
                           'visible_directory': str(directory)})
            for name in ('cpu.stat', 'cpu.max', 'cpu.cfs_quota_us', 'cpu.cfs_period_us',
                         'cpuset.cpus', 'cpuset.cpus.effective'):
                path = directory / name
                if path.is_file():
                    try:
                        files[str(path)] = path.read_text()
                    except OSError as error:
                        files[str(path)] = {'read_error': str(error)}
    return {'pid': pid, 'recorded_monotonic_ns': time.monotonic_ns(),
            'membership': membership, 'visible_mounts': mounts, 'files': files,
            'scope': 'Counters are from visible mounted cgroups; namespace-hidden ancestor limits are unknown.'}


def _thread_state(pid):
    from diagnose_submission_stalls import process_state
    return process_state(pid)


def _state(native_pid):
    state = {'recorded_monotonic_ns': time.monotonic_ns(),
             'controller_threads': _thread_state(os.getpid()), 'native_threads': _thread_state(native_pid),
             'controller_cgroup': _cgroup_state(os.getpid()), 'native_cgroup': _cgroup_state(native_pid)}
    for role, pid in (('controller', os.getpid()), ('native', native_pid)):
        require(str(pid) in state[f'{role}_threads']['threads']
                and 'read_error' not in state[f'{role}_threads']['threads'][str(pid)]
                and state[f'{role}_cgroup'].get('visible_mounts')
                and state[f'{role}_cgroup'].get('files'),
                'actual thread or visible cgroup status unavailable: ' + role)
    return state


def _parse_stdout(data):
    messages = []
    for line in data.splitlines():
        if line.startswith(PREFIX):
            messages.append(json.loads(line[len(PREFIX):]))
    return messages


def _moment(value):
    require(isinstance(value, dict) and set(value) == {'wall_ns', 'thread_cpu_ns', 'rusage'},
            'invalid segment timestamp')
    require(type(value['wall_ns']) is int and type(value['thread_cpu_ns']) is int
            and value['wall_ns'] > 0 and value['thread_cpu_ns'] >= 0,
            'invalid segment clock')
    usage = value['rusage']
    require(isinstance(usage, dict) and set(usage) == set(USAGE)
            and all(type(usage[key]) is int and usage[key] >= 0 for key in USAGE),
            'invalid per-thread resource counters')


def _sample(sample, implementation, affinity=None):
    require(sample['implementation'] == implementation and sample['launches_per_operator'] == 1,
            'sample used the wrong callback')
    if affinity is not None:
        require(sample['cpu_before'] in affinity and sample['cpu_after'] in affinity,
                'sample CPU outside native affinity')
    require(math.isfinite(sample['elapsed_ms']) and sample['elapsed_ms'] > 0
            and abs(sample['elapsed_ns'] - sample['elapsed_ms'] * 1e6 / REPEAT) < 0.1,
            'invalid event units/repeat')
    diagnostic = sample.get('submission_diagnostic')
    require(isinstance(diagnostic, dict), 'missing diagnostic sample')
    require(diagnostic['schema_version'] == 1 and diagnostic['checkpoint_interval'] == 100
            and set(diagnostic['segments']) == set(SEGMENTS), 'missing four diagnostic segments')
    previous = sample['started_monotonic_ns']
    previous_observation = None
    spans = {}
    for name in SEGMENTS:
        segment = diagnostic['segments'][name]
        require(set(segment) == {'before', 'after'}, 'invalid segment boundary')
        for side in ('before', 'after'):
            _moment(segment[side])
        before, after = segment['before'], segment['after']
        require(previous <= before['wall_ns'] <= after['wall_ns'] <= sample['finished_monotonic_ns'],
                'segment wall timestamps out of order')
        require(before['thread_cpu_ns'] <= after['thread_cpu_ns']
                and all(before['rusage'][key] <= after['rusage'][key] for key in USAGE),
                'segment resource counters reversed')
        if previous_observation is not None:
            require(previous_observation['thread_cpu_ns'] <= before['thread_cpu_ns']
                    and all(previous_observation['rusage'][key] <= before['rusage'][key] for key in USAGE),
                    'cumulative counters fell between segments')
        spans[name] = {'wall_ns': after['wall_ns'] - before['wall_ns'],
                       'thread_cpu_ns': after['thread_cpu_ns'] - before['thread_cpu_ns'],
                       'rusage_delta': {key: after['rusage'][key] - before['rusage'][key] for key in USAGE}}
        previous = after['wall_ns']
        previous_observation = after
    checkpoints = diagnostic['enqueue_checkpoints']
    require(isinstance(checkpoints, list) and len(checkpoints) == REPEAT // 100,
            'missing 100-launch checkpoints')
    cursor = diagnostic['segments']['enqueue']['before']
    gaps = []
    for index, point in enumerate(checkpoints, 1):
        require(set(point) == {'completed_launches', 'wall_ns', 'thread_cpu_ns'}
                and point['completed_launches'] == index * 100
                and type(point['wall_ns']) is int and type(point['thread_cpu_ns']) is int
                and cursor['wall_ns'] <= point['wall_ns'] <= diagnostic['segments']['enqueue']['after']['wall_ns']
                and cursor['thread_cpu_ns'] <= point['thread_cpu_ns'],
                'checkpoint clock/order differs')
        gaps.append({'completed_launches': index * 100,
                     'wall_ns': point['wall_ns'] - cursor['wall_ns'],
                     'thread_cpu_ns': point['thread_cpu_ns'] - cursor['thread_cpu_ns']})
        cursor = point
    require(cursor['thread_cpu_ns'] <= diagnostic['segments']['enqueue']['after']['thread_cpu_ns'],
            'last checkpoint exceeds enqueue CPU counter')
    return {'elapsed_ms': sample['elapsed_ms'], 'elapsed_ns': sample['elapsed_ns'],
            'segments': spans, 'checkpoint_intervals': gaps}


def _messages(messages):
    require(len(messages) == 20 and messages[0]['kind'] == 'ready'
            and messages[-1]['kind'] == 'complete', 'native wire is not one complete cycle')
    identity = messages[0]
    require(identity['execution_mode'] == 'direct_enqueue'
            and identity['role_symbols'] == {'baseline': 'launch_baseline',
                                             'candidate': 'launch_candidate'}
            and isinstance(identity['cpu_affinity'], list) and identity['cpu_affinity'],
            'native execution mode, callbacks, or CPU affinity changed')
    for message in messages:
        require(message['schema_version'] == '1.0.0' and message['protocol'] == PROTOCOL
                and message['diagnostic_only'] is True and message['measurement_admission_eligible'] is False
                and message['operator'] == 'exp' and message['cycle_index'] == CYCLE
                and message['mode'] == 'confirmation' and message['repeat'] == REPEAT
                and message['warmup'] == 10 and message['prime_repeat'] == 100
                and message['launches_per_operator'] == {'baseline': 1, 'candidate': 1}
                and message['pid'] == identity['pid']
                and all(message[key] == identity[key] for key in
                        ('device', 'context_address', 'stream_address', 'buffers', 'execution_mode',
                         'warmup_role_counts', 'role_symbols')),
                'native identity or diagnostic-only marker changed')
    require(messages[0]['warmup_role_counts'] == {'baseline': 10, 'candidate': 10},
            'diagnostic warmup changed')
    result = []
    position = 1
    previous = identity['warmup_finished_monotonic_ns']
    for phase in PHASES:
        prime = messages[position]
        require(prime['kind'] == 'prime' and prime['command_index'] == position - 1
                and prime['phase'] == phase and prime['prime_order'] == ['baseline', 'candidate', 'candidate', 'baseline']
                and previous <= prime['started_monotonic_ns'] <= prime['finished_monotonic_ns'],
                'phase prime differs')
        previous = prime['finished_monotonic_ns']
        position += 1
        for pair_index in range(5):
            row = messages[position]
            order = ['baseline', 'candidate'] if pair_index % 2 == 0 else ['candidate', 'baseline']
            require(row['kind'] == 'pair' and row['phase'] == phase
                    and row['command_index'] == position - 1 and row['pair_index'] == pair_index
                    and row['order'] == order, 'pair order differs')
            require(all(role in row for role in ROLES), 'pair sample missing')
            require(previous <= row['started_monotonic_ns']
                    <= row[order[0]]['started_monotonic_ns'] <= row[order[0]]['finished_monotonic_ns']
                    <= row[order[1]]['started_monotonic_ns'] <= row[order[1]]['finished_monotonic_ns']
                    <= row['finished_monotonic_ns'], 'pair sample chronology differs')
            for role in ROLES:
                implementation = 'candidate' if phase == 'formal' and role == 'candidate' else 'baseline'
                result.append({'phase': phase, 'pair_index': pair_index, 'role': role,
                               'order': order, **_sample(row[role], implementation, identity['cpu_affinity'])})
            previous = row['finished_monotonic_ns']
            position += 1
    complete = messages[-1]
    require(complete['command_index'] == 18 and complete['input_bytes_unchanged'] is True
            and complete['pairs_per_phase'] == 5
            and [item['role'] for item in complete['untimed_verifications']] == list(ROLES),
            'native completion or output snapshots differ')
    for snapshot, role in zip(complete['untimed_verifications'], ROLES, strict=True):
        require(snapshot['implementation'] == role and snapshot['scope'] == 'untimed_callback_verification'
                and previous <= snapshot['started_monotonic_ns'] <= snapshot['finished_monotonic_ns'],
                'untimed native output snapshot differs')
        previous = snapshot['finished_monotonic_ns']
    return result


def _oracles(plan, directory):
    results = {}
    failures = []
    for role in ROLES:
        argv = [token.replace('{cycle_dir}', str(directory)) for token in plan['case']['verify_commands'][role]]
        require(argv[1] == str(Path(plan['source_dir']) / 'scripts/verify_result.py'),
                'independent oracle script moved')
        paths = {'output': directory / f'{role}.bin', 'log': directory / f'{role}-verify.log',
                 'result': directory / f'{role}-result.json'}
        row = {'argv': argv, 'cwd': plan['source_dir'], 'started_at': time.time()}
        try:
            row['output_before'] = binding(paths['output'])
            with paths['log'].open('xb') as log:
                done = subprocess.run(argv, cwd=plan['source_dir'], stdout=log,
                                      stderr=subprocess.STDOUT, timeout=ORACLE_TIMEOUT)
            row['exit_status'] = done.returncode
            for key, path in paths.items():
                row[key] = binding(path)
            result = read(row['result']['path'])
            passed = [json.loads(line) for line in paths['log'].read_text().splitlines()
                      if line.lstrip().startswith('{') and '"passed"' in line]
            require(done.returncode == 0 and result.get('passed') is True
                    and result.get('case_id') == CASE_ID and passed == [result]
                    and row['output'] == row['output_before'],
                    'original independent oracle failed')
            row['status'] = 'passed'
        except Exception as error:
            row['status'] = 'failed'
            row['error'] = {'type': type(error).__name__, 'message': str(error)}
            for key, path in paths.items():
                if key not in row and path.is_file():
                    row[key] = binding(path)
            failures.append(role)
        finally:
            row['finished_at'] = time.time()
            save_new(directory / f'{role}-verify-receipt.json', row)
            results[role] = row
    require(not failures, 'original independent oracle failed: ' + ', '.join(failures))
    return results


def _native(plan, directory):
    argv = [token.replace('{cycle_dir}', str(directory)) for token in plan['case']['command']]
    environment = {key: value for key, value in os.environ.items() if not key.startswith('APROF_')}
    environment.update(plan['environment'], APROF_SHARED_MODE='confirmation',
                       APROF_SHARED_REPEAT=str(REPEAT), APROF_SHARED_CYCLE=str(CYCLE),
                       APROF_SHARED_TIMING='1')
    receipt = {'schema_version': 1, 'purpose': PURPOSE, 'diagnostic_only': True, 'accepted': False,
               'measurement_admission_eligible': False, 'publication_acceptance': False,
               'started_at': time.time(), 'argv': argv, 'cwd': plan['source_dir'],
               'environment': {key: environment[key] for key in (*BASE_ENVIRONMENT, 'APROF_SHARED_MODE',
                                                               'APROF_SHARED_REPEAT', 'APROF_SHARED_CYCLE',
                                                               'APROF_SHARED_TIMING')},
               'commands': [], 'status': 'failed'}
    stdout, stderr, pending = bytearray(), bytearray(), bytearray()
    deadline = time.monotonic() + NATIVE_TIMEOUT
    try:
        child = subprocess.Popen(argv, cwd=plan['source_dir'], env=environment,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except BaseException as error:
        receipt.update(status='failed', exit_status=None, finished_at=time.time(),
                       error={'type': type(error).__name__, 'message': str(error)})
        for name in ('stdout', 'stderr'):
            path = directory / f'{name}.log'
            path.write_bytes(b'')
            receipt[name] = binding(path)
        save_new(directory / 'native-receipt.json', receipt)
        raise
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ, 'stdout')
    selector.register(child.stderr, selectors.EVENT_READ, 'stderr')

    def pump(timeout):
        for key, _ in selector.select(timeout):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            target = stdout if key.data == 'stdout' else stderr
            target.extend(chunk)
            if key.data == 'stdout':
                pending.extend(chunk)
            require(len(stdout) + len(stderr) <= MAX_RAM_LOG, 'native RAM log bound exceeded')

    def ack(deadline):
        while True:
            while b'\n' in pending:
                line, _, remainder = pending.partition(b'\n')
                pending[:] = remainder
                if line.startswith(PREFIX):
                    return json.loads(line[len(PREFIX):])
            require(time.monotonic() < deadline, 'native ACK timeout')
            pump(max(0, min(1, deadline - time.monotonic())))
            require(child.poll() is None or selector.get_map(), 'native exited before ACK')

    try:
        receipt['pid'] = child.pid
        ready = ack(deadline)
        require(ready['kind'] == 'ready' and ready['pid'] == child.pid, 'native ready identity differs')
        receipt['before'] = _state(child.pid)
        messages = [ready]
        for index, command in enumerate(plan['commands']):
            if index == len(plan['commands']) - 1:
                receipt['after'] = _state(child.pid)
            request_at = time.monotonic_ns()
            child.stdin.write((command + '\n').encode())
            child.stdin.flush()
            message = ack(deadline)
            messages.append(message)
            receipt['commands'].append({'command': command, 'request_monotonic_ns': request_at,
                                        'response_monotonic_ns': time.monotonic_ns(),
                                        'kind': message['kind'], 'command_index': message.get('command_index')})
            require(message.get('command_index') == index, 'interactive ACK index differs')
        child.stdin.close()
        while selector.get_map() and time.monotonic() < deadline:
            pump(min(1, deadline - time.monotonic()))
        require(not selector.get_map(), 'native pipes did not close')
        child.wait(timeout=max(0.1, deadline - time.monotonic()))
        receipt['exit_status'] = child.returncode
        require(child.returncode == 0, 'native diagnostic process failed')
        require(_parse_stdout(stdout) == messages, 'RAM stdout differs from ACK transcript')
        receipt['samples'] = _messages(messages)
        receipt['status'] = 'complete_diagnostic_only'
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        if child.poll() is None:
            child.kill()
        child.wait(timeout=20)
        receipt['exit_status'] = child.returncode
        # Preserve bytes still buffered in both pipes after a failed native run.
        for pipe, target in ((child.stdout, stdout), (child.stderr, stderr)):
            target.extend(pipe.read())
        raise
    finally:
        selector.close()
        receipt['finished_at'] = time.time()
        # The native stdout/stderr remain in RAM until native exit, even on failure.
        with (directory / 'stdout.log').open('xb') as log:
            log.write(stdout)
        with (directory / 'stderr.log').open('xb') as log:
            log.write(stderr)
        receipt['stdout'] = binding(directory / 'stdout.log')
        receipt['stderr'] = binding(directory / 'stderr.log')
        save_new(directory / 'native-receipt.json', receipt)
    return receipt


def _summary(samples):
    phases = []
    for phase in PHASES:
        rows = [row for row in samples if row['phase'] == phase]
        phases.append({'phase': phase, 'events': len(rows),
                       'baseline_event_ms': [row['elapsed_ms'] for row in rows if row['role'] == 'baseline'],
                       'candidate_event_ms': [row['elapsed_ms'] for row in rows if row['role'] == 'candidate']})
    all_ms = [row['elapsed_ms'] for row in samples]
    return {'schema_version': 1, 'purpose': PURPOSE, 'diagnostic_only': True, 'accepted': False,
            'measurement_admission_eligible': False, 'publication_acceptance': False,
            'event_count': 30, 'repeat': REPEAT, 'checkpoint_interval': 100,
            'event_median_ms': statistics.median(all_ms), 'phases': phases, 'samples': samples,
            'interpretation': 'Per-sample four segments and 100-launch checkpoints describe this single cycle. '
                              'No timing admission, performance gain, source mechanism, or causal attribution follows.'}


def _check_anchor(output, anchor_path, frozen, latest):
    require(anchor_path.parent == ROOT / 'scaffolding/curation',
            'root preregistration anchor must be in curation')
    anchor = read(anchor_path)
    recorded = anchor.get('recorded_at_utc')
    require(isinstance(recorded, str), 'root anchor timestamp missing')
    timestamp = datetime.fromisoformat(recorded)
    require(timestamp.tzinfo is not None, 'root anchor timestamp must include timezone')
    require(anchor == {'schema_version': 1, 'purpose': PURPOSE,
                       'freeze': binding(output / 'freeze.json'),
                       'predecessor_campaign': frozen['predecessor_campaign'],
                       'max_attempts': 1, 'resampling': 'none',
                       'recorded_at_utc': recorded}, 'root anchor identity or policy differs')
    require(frozen['created_at'] <= timestamp.timestamp() <= latest,
            'root anchor was not recorded after freeze and before run')
    return anchor


def run(output, anchor_path):
    output = Path(output).resolve(strict=True)
    anchor_path = Path(anchor_path).resolve(strict=True)
    plan, frozen = read(output / 'plan.json'), read(output / 'freeze.json')
    _check_plan(output, plan)
    _check_anchor(output, anchor_path, frozen, time.time())
    require(not (output / 'started.json').exists() and not (output / 'cycle').exists(),
            'diagnostic already attempted; no resume or retry')
    verify_bindings(frozen['files'])
    require(binding(output / 'plan.json') == frozen['plan']
            and binding(output / 'build-terminal.json') == frozen['build'],
            'frozen plan or build changed')
    require(_history(Path(plan['predecessor'])) == frozen['history'],
            'failed predecessor campaign changed after freeze')
    save_new(output / 'started.json', {'at': time.time(), 'anchor': binding(anchor_path),
                                       'freeze': binding(output / 'freeze.json')})
    terminal = {'schema_version': 1, 'purpose': PURPOSE, 'diagnostic_only': True, 'accepted': False,
                'measurement_admission_eligible': False, 'publication_acceptance': False,
                'status': 'failed', 'started': binding(output / 'started.json'), 'oracles': {}}
    try:
        with locks(['host-serial.lock', *[f'device-{index}.lock' for index in range(16)]]):
            directory = output / 'cycle'
            directory.mkdir()
            save_new(directory / 'started.json', {'at': time.time(), 'cycle': CYCLE,
                                                   'plan': binding(output / 'plan.json')})
            native = _native(plan, directory)
            terminal['native'] = binding(directory / 'native-receipt.json')
            verify_bindings(plan['input_files'])
            terminal['oracles'] = _oracles(plan, directory)
            verify_bindings(plan['input_files'])
            save_new(output / 'descriptive-summary.json', _summary(native['samples']))
            terminal['summary'] = binding(output / 'descriptive-summary.json')
            terminal['status'] = 'complete_diagnostic_only'
    except BaseException as error:
        terminal['error'] = {'type': type(error).__name__, 'message': str(error)}
        if (output / 'cycle/native-receipt.json').is_file():
            terminal['native'] = binding(output / 'cycle/native-receipt.json')
        for role in ROLES:
            receipt = output / 'cycle' / f'{role}-verify-receipt.json'
            if receipt.is_file():
                terminal['oracles'][role] = read(receipt)
        raise
    finally:
        terminal['finished_at'] = time.time()
        save_new(output / 'terminal.json', terminal)
    return terminal


def replay(output, anchor_path):
    """Read-only proof of the single diagnostic attempt, never a gate verdict."""
    output = Path(output).resolve(strict=True)
    anchor_path = Path(anchor_path).resolve(strict=True)
    plan, frozen = read(output / 'plan.json'), read(output / 'freeze.json')
    _check_plan(output, plan)
    started, terminal = read(output / 'started.json'), read(output / 'terminal.json')
    _check_anchor(output, anchor_path, frozen, started['at'])
    require(started['anchor'] == binding(anchor_path) and started['freeze'] == binding(output / 'freeze.json'),
            'diagnostic anchor/start differs')
    verify_bindings(frozen['files'])
    require(frozen['history'] == _history(Path(plan['predecessor']))
            and terminal['purpose'] == PURPOSE and terminal['accepted'] is False
            and terminal['publication_acceptance'] is False
            and terminal['measurement_admission_eligible'] is False,
            'history or diagnostic-only terminal changed')
    native_path = output / 'cycle/native-receipt.json'
    require(terminal['native'] == binding(native_path), 'native receipt differs')
    native = read(native_path)
    cycle_started = read(output / 'cycle/started.json')
    require(terminal['started'] == binding(output / 'started.json')
            and cycle_started['cycle'] == CYCLE
            and cycle_started['plan'] == binding(output / 'plan.json')
            and started['at'] <= cycle_started['at'] <= native['started_at']
            <= native['finished_at'] <= terminal['finished_at'],
            'root anchor, cycle, or native lifecycle differs')
    require(native['stdout'] == binding(output / 'cycle/stdout.log')
            and native['stderr'] == binding(output / 'cycle/stderr.log')
            and native['status'] == 'complete_diagnostic_only' and native['exit_status'] == 0
            and native['diagnostic_only'] is True and native['measurement_admission_eligible'] is False
            and terminal['status'] == 'complete_diagnostic_only'
            and native['argv'] == [token.replace('{cycle_dir}', str(output / 'cycle')) for token in plan['case']['command']]
            and native['environment']['APROF_SHARED_REPEAT'] == str(REPEAT)
            and native['environment']['APROF_SHARED_CYCLE'] == str(CYCLE)
            and native['environment']['APROF_SHARED_MODE'] == 'confirmation',
            'native execution identity differs')
    messages = _parse_stdout(Path(native['stdout']['path']).read_bytes())
    samples = _messages(messages)
    require(len(native['commands']) == 19 and native['samples'] == samples
            and [row['command'] for row in native['commands']] == plan['commands']
            and [row['command_index'] for row in native['commands']] == list(range(19))
            and all(row['request_monotonic_ns'] <= row['response_monotonic_ns']
                    for row in native['commands']), 'interactive ACK transcript differs')
    require(native['pid'] == messages[0]['pid'] and native['before']['native_threads']['pid'] == native['pid']
            and native['after']['native_threads']['pid'] == native['pid']
            and native['before']['recorded_monotonic_ns'] <= native['after']['recorded_monotonic_ns']
            and all(snapshot[f'{role}_cgroup'].get('visible_mounts')
                    and snapshot[f'{role}_cgroup'].get('files')
                    and snapshot[f'{role}_threads']['threads']
                    for snapshot in (native['before'], native['after'])
                    for role in ('controller', 'native')),
            'native thread/cgroup snapshots differ')
    previous_oracle = native['finished_at']
    for role in ROLES:
        row = terminal['oracles'][role]
        require(row == read(output / 'cycle' / f'{role}-verify-receipt.json')
                and row['status'] == 'passed' and row['exit_status'] == 0
                and previous_oracle <= row['started_at'] <= row['finished_at'] <= terminal['finished_at']
                and row['argv'] == [token.replace('{cycle_dir}', str(output / 'cycle'))
                                                           for token in plan['case']['verify_commands'][role]],
                'oracle command differed')
        previous_oracle = row['finished_at']
        for key in ('output', 'log', 'result'):
            require(row[key] == binding(row[key]['path']), 'oracle artifact changed')
        require(row['output_before'] == row['output'], 'oracle changed native output')
        result = read(row['result']['path'])
        require(result.get('passed') is True and result.get('case_id') == CASE_ID,
                'oracle result did not pass')
        passed = [json.loads(line) for line in Path(row['log']['path']).read_text().splitlines()
                  if line.lstrip().startswith('{') and '"passed"' in line]
        require(passed == [result], 'oracle stdout/result differs')
    require(read(output / 'descriptive-summary.json') == _summary(samples)
            and terminal['summary'] == binding(output / 'descriptive-summary.json'),
            'descriptive summary differs from all original samples')
    return {'complete_diagnostic_only': terminal['status'] == 'complete_diagnostic_only',
            'accepted': False,
            'measurement_admission_eligible': False, 'publication_acceptance': False,
            'native': binding(native_path), 'summary': terminal['summary'],
            'event_count': len(samples)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'build', 'freeze', 'run', 'replay'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--anchor', type=Path)
    args = parser.parse_args()
    if args.action in ('run', 'replay'):
        require(args.anchor is not None, 'run/replay require the root preregistration anchor')
    result = {'prepare': lambda: prepare(args.output), 'build': lambda: build(args.output),
              'freeze': lambda: freeze(args.output), 'run': lambda: run(args.output, args.anchor),
              'replay': lambda: replay(args.output, args.anchor)}[args.action]()
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
