"""All 20 original baseline calls, both roles; no qualification or archive.

The outer controller owns device exclusivity and the original absolute deadline.
The native oracle receives unchanged IEEE metadata and every complete output.
Reports are strict JSON and retain raw metadata/results by hash, never by copying
profile data. A failed stage is retained and cannot be resumed in its directory.
"""
import json
import math
import os
from pathlib import Path
import sys
import time

import task_baseline_build as builder
import task_baseline_qualification as baseline
from aprof_runtime.jsonio import file_hash

ROLES = ('baseline', 'candidate')
KIND = 'original_baseline_correctness'
ENABLED_IN_1_0 = False


class CorrectnessFailure(RuntimeError):
    def __init__(self, message, report_ref):
        super().__init__(message)
        self.report_ref = report_ref


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _native(value):
    # Only oracle input/result identity uses native IEEE JSON. No string casts.
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()


def _file(local, path, reference=None, *, register=False):
    path = builder._path(path)
    actual = local.register_artifact(path) if register else file_hash(path)
    builder._need(reference is None or actual == reference, 'baseline correctness file changed: ' + str(path))
    local.verify_artifact(actual)
    return actual


def _output_sizes(operator, metadata):
    if operator == 'dynamic_quant':
        return {'output_y': metadata['numel'], 'output_scale': metadata['token_count'] * 4}
    if operator in ('gqa', 'weight_quant_batch_matmul'):
        return {'output': math.prod(metadata['output_shape']) * 2}
    return {'output': metadata['numel'] * (4 if metadata['dtype'] == 'float32' else 2)}


def _case_inputs(local, case):
    _file(local, case['metadata_path'], case['metadata_ref'])
    for path, reference in case['input_files'].items():
        _file(local, path, reference)
    return _read(local, case['metadata_ref'])


def _preflight(local, plan_ref, build_receipt_ref):
    plan = baseline.checked_plan(local, plan_ref)
    proof, built = builder.checked_baseline_build(local, plan_ref=plan_ref, build_receipt_ref=build_receipt_ref)
    producer = str(Path(__file__).resolve())
    builder._need(plan['producer_refs'].get(producer) == file_hash(producer),
                  'baseline correctness producer is absent from prelaunch plan')
    python = str(Path(sys.executable).resolve())
    builder._need(plan['toolchain_refs'].get(python) == file_hash(python), 'original Python oracle executable is unbound')
    oracle = Path(plan['roles']['baseline']['path']) / 'scripts/verify_result.py'
    oracle_ref = plan['roles']['baseline']['files']['scripts/verify_result.py']
    _file(local, oracle, oracle_ref)
    builder._need(proof['mechanism_entry'] == {'flag': '--aprof-mechanism-role', 'roles': list(ROLES),
        'calls': 1, 'snapshot_all_outputs': True, 'task_api_enabled': False},
        'baseline binary lacks the single complete-call role entry')
    return plan, proof, built, oracle, oracle_ref


def _paths(destination, case_id, keys):
    return {role: {key: str(destination / f'case_{case_id:02d}' / role / (key + '.bin')) for key in keys}
            for role in ROLES}


def _commands(plan, built, oracle, case, metadata, destination, role):
    sizes = _output_sizes(plan['operator'], metadata)
    outputs = _paths(destination, case['case_id'], sizes)
    adapter = baseline.multi if plan['operator'] in baseline.multi.OPERATORS else baseline.bridge.adapter.base
    kernel = adapter.case_command(plan['operator'], built['binary']['path'], metadata, plan['device'], outputs)
    kernel += ['--aprof-mechanism-role', role]
    folder = destination / f"case_{case['case_id']:02d}" / role
    verifier = [str(Path(sys.executable).resolve()), str(oracle), '--metadata', str(folder / 'metadata.json')]
    return sizes, outputs[role], folder, kernel, verifier


def _execute(local, commands, deadline, label, argv, cwd):
    builder._remaining(commands, deadline)
    wall, mono = time.time(), time.monotonic()
    record = commands.run(label, argv, cwd)
    ended_at, ended_mono = time.time(), time.monotonic()
    reference = builder._record(local, record, Path(commands.directory) / label / 'execution.json', register=True)
    return {'execution_ref': reference, 'started_at': wall, 'finished_at': ended_at,
            'started_monotonic': mono, 'finished_monotonic': ended_mono}, record


def _successful(record, expected, cwd):
    builder._need(record['argv'] == expected and record['cwd'] == str(cwd)
        and type(record['exit_status']) is int and record['exit_status'] == 0 and record['error'] is None,
        'baseline complete-call kernel/oracle process failed or changed command')


def _result(local, path, stdout_path, case_id, *, register):
    reference = _file(local, path, register=register)
    value = _read(local, reference)
    log = json.loads(Path(stdout_path).read_text().strip())
    builder._need(_native(log) == _native(value) and value.get('passed') is True
                  and type(value.get('case_id')) is int and value['case_id'] == case_id,
                  'original complete-output oracle failed or stdout/result differs')
    return reference, baseline.bridge.adapter.base.old.json_contract(value)


def collect_baseline_correctness(local, *, plan_ref, build_receipt_ref, commands, destination):
    """Return the local report hash; failure raises with a retained report_ref."""
    return _collect_complete(local, plan_ref=plan_ref, build_receipt_ref=build_receipt_ref,
        commands=commands, destination=destination, preflight=_preflight, kind=KIND)


def _collect_complete(local, *, plan_ref, build_receipt_ref, commands, destination, preflight, kind):
    started_at, started_mono = time.time(), time.monotonic()
    deadline = commands.deadline
    builder._remaining(commands, deadline)
    plan, proof, built, oracle, oracle_ref = preflight(local, plan_ref, build_receipt_ref)
    builder._need(deadline == built['deadline_monotonic'], 'correctness must retain the original build/job deadline')
    environment = builder._environment(plan)
    builder._need('APROF_TASK_PROFILE_DIR' not in os.environ, 'correctness cannot enable Task profiling')
    destination = builder._path(destination)
    forbidden = [Path(plan['assembly_dir']), *(Path(plan['roles'][r]['path']) for r in ROLES),
                 *(Path(c['metadata_path']).parent for c in plan['cases'])]
    builder._need(not any(destination.is_relative_to(path) for path in forbidden),
                  'correctness destination overlaps frozen source/build/inputs')
    destination.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'kind': kind, 'protocol': plan['protocol'],
        'admission_authority': False, 'qualification_granted': False, 'archive_performed': False,
        'plan_ref': plan_ref, 'build_receipt_ref': build_receipt_ref, 'operator': plan['operator'],
        'source_hashes': plan['source_hashes'], 'binary_hashes': {r: built['binary']['sha256'] for r in ROLES},
        'oracle': {'path': str(oracle), 'sha256': oracle_ref}, 'case_ids': list(range(1, 21)),
        'destination': str(destination), 'command_directory': str(builder._path(commands.directory)),
        'environment': environment, 'deadline_monotonic': deadline,
        'started_at': started_at, 'started_monotonic': started_mono,
        'status': 'failed', 'error': None, 'rows': []}
    failure = None
    try:
        for case in plan['cases']:
            for role in ROLES:
                builder._remaining(commands, deadline)
                metadata = _case_inputs(local, case)
                sizes, outputs, folder, kernel, verifier = _commands(plan, built, oracle, case, metadata, destination, role)
                folder.mkdir(parents=True, exist_ok=False)
                bound = folder / 'metadata.json'
                bound.write_bytes(_native(dict(metadata, **outputs)))
                row = {'case_id': case['case_id'], 'role': role, 'correct': False,
                    'source_hash': plan['source_hashes'][role], 'binary_hash': built['binary']['sha256'],
                    'original_metadata_ref': case['metadata_ref'], 'input_refs': case['input_files'],
                    'metadata_ref': local.register_artifact(bound), 'outputs': {}, 'executions': []}
                report['rows'].append(row)
                label = f"correctness-case-{case['case_id']:02d}-{role}-kernel"
                execution, record = _execute(local, commands, deadline, label, kernel, Path(plan['assembly_dir']) / 'source')
                row['executions'].append(execution)
                _successful(record, kernel, Path(plan['assembly_dir']) / 'source')
                builder._remaining(commands, deadline)
                for key, path in outputs.items():
                    builder._need(Path(path).stat().st_size == sizes[key], 'complete baseline output has the wrong byte count')
                    row['outputs'][key] = {'path': path, 'sha256': _file(local, path, register=True)}
                label = f"correctness-case-{case['case_id']:02d}-{role}-oracle"
                execution, record = _execute(local, commands, deadline, label, verifier, Path(plan['assembly_dir']) / 'source')
                row['executions'].append(execution)
                _successful(record, verifier, Path(plan['assembly_dir']) / 'source')
                row['result_ref'], row['verification'] = _result(local, folder / 'result.json',
                    record['stdout']['path'], case['case_id'], register=True)
                for value in row['outputs'].values():
                    _file(local, value['path'], value['sha256'])
                _file(local, bound, row['metadata_ref'])
                _case_inputs(local, case)
                row['correct'] = True
                builder._remaining(commands, deadline)
        preflight(local, plan_ref, build_receipt_ref)
        builder._remaining(commands, deadline)
        report['status'] = 'passed'
    except BaseException as exc:
        failure = exc
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        report.update(finished_at=time.time(), finished_monotonic=time.monotonic())
        path = destination / 'correctness.json'
        builder._save(path, report)
        report_ref = local.register_artifact(path)
    if failure is not None:
        if isinstance(failure, (KeyboardInterrupt, SystemExit)):
            raise failure
        raise CorrectnessFailure(str(failure), report_ref) from failure
    builder._remaining(commands, deadline)
    return report_ref


def verify_baseline_correctness(local, *, plan_ref, build_receipt_ref, report_ref):
    """Read-only complete scope, source, outputs and actual execution replay."""
    return _verify_complete(local, plan_ref=plan_ref, build_receipt_ref=build_receipt_ref,
        report_ref=report_ref, preflight=_preflight, kind=KIND)


def _verify_complete(local, *, plan_ref, build_receipt_ref, report_ref, preflight, kind):
    plan, proof, built, oracle, oracle_ref = preflight(local, plan_ref, build_receipt_ref)
    report = _read(local, report_ref)
    destination = builder._path(report['destination'])
    _file(local, destination / 'correctness.json', report_ref)
    expected = {'schema_version': 1, 'kind': kind, 'protocol': plan['protocol'],
        'admission_authority': False, 'qualification_granted': False, 'archive_performed': False,
        'plan_ref': plan_ref, 'build_receipt_ref': build_receipt_ref, 'operator': plan['operator'],
        'source_hashes': plan['source_hashes'], 'binary_hashes': {r: built['binary']['sha256'] for r in ROLES},
        'oracle': {'path': str(oracle), 'sha256': oracle_ref}, 'case_ids': list(range(1, 21)),
        'status': 'passed', 'error': None,
        'environment': {'APROF_SKILL_LIB': str(builder.shared.RELEASE),
            'ASCEND_RT_VISIBLE_DEVICES': str(plan['physical_device']), 'ASCEND_HOME_PATH': builder.CANN_HOME,
            **builder.CPU_REFERENCE_ENV}}
    builder._need(all(report.get(key) == value for key, value in expected.items()), 'baseline correctness identity/status differs')
    number = builder._number
    wall, wall_end = number(report['started_at']), number(report['finished_at'])
    mono, mono_end = number(report['started_monotonic']), number(report['finished_monotonic'])
    deadline = number(report['deadline_monotonic'])
    builder._need(number(built['finished_at']) <= wall <= wall_end <= wall + plan['budget_seconds']
        and deadline == built['deadline_monotonic']
        and mono <= mono_end <= deadline <= mono + plan['budget_seconds']
        and len(report['rows']) == 40, 'baseline correctness deadline/chronology/40-row scope differs')
    command_directory = builder._path(report['command_directory'])
    for index, row in enumerate(report['rows']):
        case, role = plan['cases'][index // 2], ROLES[index % 2]
        metadata = _case_inputs(local, case)
        sizes, outputs, folder, kernel, verifier = _commands(plan, built, oracle, case, metadata, destination, role)
        builder._need(row['case_id'] == case['case_id'] and row['role'] == role and row['correct'] is True
            and row['source_hash'] == plan['source_hashes'][role] and row['binary_hash'] == built['binary']['sha256']
            and row['original_metadata_ref'] == case['metadata_ref'] and row['input_refs'] == case['input_files']
            and set(row['outputs']) == set(outputs) and len(row['executions']) == 2,
            'baseline correctness row order/source/input/output roster differs')
        bound = folder / 'metadata.json'
        _file(local, bound, row['metadata_ref'])
        builder._need(bound.read_bytes() == _native(dict(metadata, **outputs)), 'original native oracle metadata changed')
        for key, path in outputs.items():
            builder._need(row['outputs'][key]['path'] == path and Path(path).stat().st_size == sizes[key],
                          'complete output path/size differs')
            _file(local, path, row['outputs'][key]['sha256'])
        for name, argv, operation in zip(('kernel', 'oracle'), (kernel, verifier), row['executions'], strict=True):
            begin, end = number(operation['started_at']), number(operation['finished_at'])
            begin_mono, end_mono = number(operation['started_monotonic']), number(operation['finished_monotonic'])
            builder._need(wall <= begin <= end <= wall_end and mono <= begin_mono <= end_mono <= mono_end,
                          'baseline actual execution order/time differs')
            execution = operation['execution_ref']
            label = f"correctness-case-{case['case_id']:02d}-{role}-{name}"
            builder._need(execution['path'] == str(command_directory / label / 'execution.json'),
                          'baseline actual execution slot differs')
            record = _read(local, execution['sha256'])
            builder._need(builder._record(local, record, execution['path'], register=False) == execution
                and 0 <= number(record['duration_seconds']) <= end_mono - begin_mono + .01,
                'baseline execution/raw duration differs')
            _successful(record, argv, Path(plan['assembly_dir']) / 'source')
            wall, mono = end, end_mono
        result_ref, verification = _result(local, folder / 'result.json', record['stdout']['path'], case['case_id'], register=False)
        builder._need(row['result_ref'] == result_ref and row['verification'] == verification,
                      'baseline original oracle result differs')
    return {'valid': True, 'scope': 'all_original_20_cases_both_roles_complete_outputs', 'report_ref': report_ref,
            'admission_authority': False, 'qualification_granted': False, 'archive_performed': False}
