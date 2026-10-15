"""Task-rule correctness/boundary driver; no build or archive operation.

The trusted outer controller supplies a frozen protocol and ONE absolute
monotonic deadline, retains the full stage roster, and enforces process-tree
cancellation. This module writes only task-local evidence and original outputs.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import sys
import time

import task_screen_bridge as screen
adapter = screen.rule
from validation_host_evaluator import verify_correctness_report
from timing_admission import (BOUNDARY_SIZES, THRESHOLDS, identity, read,
                              verify_boundary_report)

bridge = adapter.bridge
ROLES = adapter.ROLES
ENABLED_IN_1_0 = False


def _write_native_metadata(path, metadata, output):
    # Original oracle metadata permits IEEE specials; evidence reports do not.
    with Path(path).open('x') as stream:
        json.dump(dict(metadata, output=str(output)), stream,
                  sort_keys=True, indent=2, allow_nan=True)
        stream.write('\n')


def _same_native_metadata(left, right):
    """Compare parsed native JSON, treating paired NaNs as the same value."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_native_metadata(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_native_metadata(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and math.isnan(left):
        return math.isnan(right)
    return left == right


class StageFailure(RuntimeError):
    """Failed execution has a retained partial result, never a second attempt."""
    def __init__(self, message, result):
        super().__init__(message)
        self.result = result


def path_ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': bridge.file_hash(path)}


def checked_file(store, path, reference):
    path = Path(path)
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or bridge.file_hash(path) != reference):
        raise ValueError('frozen file changed: ' + str(path))
    if store.register_artifact(path) != reference:
        raise ValueError('local input registration differs')
    return path


def execute(argv, cwd, prefix, store, deadline):
    """Project the existing real process receipt without inventing timestamps."""
    timeout = bridge.remaining(deadline)
    original = Path(str(prefix) + '.execution.json')
    try:
        bridge.profile_capture.run(argv, cwd, prefix, timeout, store,
            environment={'APROF_SHARED_CYCLE': '0'})
    except RuntimeError:
        if not original.is_file():
            raise
    raw = json.loads(original.read_text())
    result = {key: raw[key] for key in ('argv', 'cwd', 'started_at', 'error')}
    result.update(finished_at=raw['ended_at'], exit_status=raw['exit_code'],
        environment=raw['environment'], timeout_seconds=raw['timeout_seconds'], pid=raw['pid'],
        stdout=path_ref(store.verify_artifact(raw['stdout_hash'])),
        stderr=path_ref(store.verify_artifact(raw['stderr_hash'])),
        log_ref=raw['stdout_hash'], original_execution_ref=store.register_artifact(original))
    target = Path(str(prefix) + '.admission-execution.json')
    bridge.save(target, result)
    store.register_artifact(target)
    return path_ref(target), result


def _check_execution(record, deadline):
    if record['exit_status'] != 0 or record['error'] is not None:
        raise RuntimeError('kernel/verifier process failed; no retry')
    bridge.remaining(deadline)


def preflight_boundary_plan(store, *, operator, source_hashes, boundary_plan_ref, oracle_files):
    """Check the complete fixed boundary contract before review/build/device work."""
    plan=read(store,boundary_plan_ref)
    if plan.get('schema_version')!=1 or plan.get('operator')!=operator or operator not in BOUNDARY_SIZES:
        raise ValueError('boundary plan has no frozen operator scope')
    for key in ('generator_ref','verifier_ref'):
        if plan[key] not in oracle_files.values():
            raise ValueError('boundary oracle differs from frozen protocol: '+key)
        store.verify_artifact(plan[key])
    for path,reference in oracle_files.items():
        checked_file(store,path,reference)
    if plan['verifier_ref']!=read(store,source_hashes['baseline'])['files'].get('scripts/verify_result.py'):
        raise ValueError('boundary verifier differs from original source')
    cases=plan['cases'];wanted=[(dtype,size) for dtype in THRESHOLDS for size in BOUNDARY_SIZES[operator]]
    if ([(c['dtype'],c['numel']) for c in cases]!=wanted
            or [c['case_id'] for c in cases]!=list(range(101,101+len(wanted)))):
        raise ValueError('boundary inventory differs from frozen 42/57 cases')
    for case in cases:
        special=['-inf','inf','nan','-0','0'] if case['numel']==65 else []
        if case['shape']!=[case['numel']] or not case.get('input_files') or case.get('special_values',[])!=special:
            raise ValueError('boundary shape/input/special-value scope differs')
        paths=[checked_file(store,path,reference) for path,reference in case['input_files'].items()]
        if special:
            size=4 if case['dtype']=='float32' else 2
            if len(paths)!=1 or paths[0].stat().st_size!=65*size:
                raise ValueError('boundary special input byte count differs')
            with paths[0].open('rb') as stream:data=stream.read(5*size)
            values=(struct.unpack('<5f',data) if size==4 else struct.unpack('<5e',data)
                if case['dtype']=='float16' else [struct.unpack('<f',b'\x00\x00'+data[i:i+2])[0] for i in range(0,10,2)])
            if not (values[0]==-math.inf and values[1]==math.inf and math.isnan(values[2])
                    and values[3]==values[4]==0 and math.copysign(1,values[3])==-1 and math.copysign(1,values[4])==1):
                raise ValueError('boundary special input coverage differs')
    return plan


def _preflight(assembly, build_receipt, prepared, store, expected, protocol_ref, stage):
    proof, build = adapter.checked_build(assembly, build_receipt)
    op = proof['operator']
    if stage not in ('correctness', 'boundary') or op not in adapter.OPERATORS:
        raise ValueError('unsupported correctness stage/operator')
    protocol = read(store, protocol_ref)
    identity(protocol, expected)
    if expected['operator'] != op:
        raise ValueError('assembly operator differs')
    binary = Path(build['binary']['path'])
    if protocol['binary_hashes'] != {r: build['binary']['sha256'] for r in ROLES}:
        raise ValueError('protocol must bind both roles to the checked combined binary')
    for role in ROLES:
        binding = proof['historical_source_binding']['roles'][role]
        if expected['source_hashes'][role] != binding['sha256']:
            raise ValueError('original source role differs')
        checked_file(store, binding['path'], binding['sha256'])
    oracle = Path(proof['roles']['baseline']['path']) / 'scripts/verify_result.py'
    oracle_hash = proof['roles']['baseline']['files']['scripts/verify_result.py']
    if protocol['oracle_files'].get(str(oracle)) != oracle_hash:
        raise ValueError('protocol must bind the original native oracle')
    checked_file(store, oracle, oracle_hash)
    inputs = read(store, protocol['input_inventory_ref'])
    cases = None
    if stage == 'boundary':
        plan = preflight_boundary_plan(store,operator=op,source_hashes=expected['source_hashes'],
            boundary_plan_ref=protocol['boundary_plan_ref'],oracle_files=protocol['oracle_files'])
        wanted = [(dtype, size) for dtype in THRESHOLDS for size in BOUNDARY_SIZES[op]]
        cases = plan['cases']
        if (plan.get('schema_version') != 1 or plan.get('operator') != op
                or plan.get('verifier_ref') != oracle_hash
                or [(c['dtype'], c['numel']) for c in cases] != wanted
                or [c['case_id'] for c in cases] != list(range(101, 101 + len(wanted)))):
            raise ValueError('boundary inventory differs from frozen 42/57 cases')
    ids = list(range(1, 21)) if cases is None else [c['case_id'] for c in cases]
    metadata = []
    for index, case_id in enumerate(ids):
        path = Path(prepared) / f'case_{case_id:02d}/metadata.json'
        checked_file(store, path, inputs[str(path)])
        value = json.loads(path.read_text())
        checked_file(store, value['input'], inputs[value['input']])
        size = 4 if value['dtype'] == 'float32' else 2
        if (value['case_id'] != case_id or value['dtype'] not in THRESHOLDS
                or Path(value['input']).stat().st_size != value['numel'] * size):
            raise ValueError('prepared case identity or input byte count differs')
        if cases is not None:
            case = cases[index]
            attrs = value.get('attrs', {k: value[k] for k in ('base', 'scale', 'shift') if k in value})
            if (any(value[k] != case[k] for k in ('case_id', 'shape', 'dtype', 'numel'))
                    or attrs != case.get('attrs', {})
                    or case['input_files'] != {value['input']: inputs[value['input']]}):
                raise ValueError('boundary metadata differs from frozen plan')
        metadata.append((path, value))
    return proof, build, protocol, oracle, inputs, metadata


def verify_rule_correctness(store, report_ref, *, protocol_ref, expected, window, device=0):
    """Read-only join above the two existing verifiers; no stage/exit authority."""
    report = read(store, report_ref)
    identity(report, expected)
    stage = report['kind'].removeprefix('task_rule_')
    if (report['status'] != 'passed' or report['error'] is not None
            or report['protocol_ref'] != protocol_ref or report['device'] != device
            or not window[0] <= report['started_at'] <= report['finished_at'] <= window[1]):
        raise ValueError('correctness identity/status/window differs')
    build_path = store.verify_artifact(report['build_receipt_ref'])
    build = read(store, report['build_receipt_ref'])
    binary = Path(build['binary']['path'])
    original = store.verify_artifact(report['rows'][0]['original_metadata_ref'])
    proof, _, protocol, oracle, inputs, metadata = _preflight(
        binary.parent.parent, build_path, original.parent.parent, store, expected, protocol_ref, stage)
    if (report['source_review_ref'] != bridge.file_hash(binary.parent.parent / 'source-review.json')
            or report['binary_hashes'] != protocol['binary_hashes']
            or report['input_inventory_ref'] != protocol['input_inventory_ref']
            or report['oracle_ref'] != bridge.file_hash(oracle)):
        raise ValueError('correctness source/build/oracle binding differs')
    ids = [m['case_id'] for _, m in metadata]
    if (report['case_ids'] != ids or report['passed_case_ids'] != ids
            or [(r['case_id'], r['role']) for r in report['rows']] != [(c, r) for c in ids for r in ROLES]):
        raise ValueError('correctness role/case inventory differs')
    role_reports = {}
    if stage == 'correctness':
        role_reports = {r: verify_correctness_report(report['role_reports'][r]) for r in ROLES}
    else:
        verify_boundary_report(store, report_ref, protocol_ref=protocol_ref,
                               expected={**expected, 'boundary_window': window})
    previous = report['started_at']
    for index, row in enumerate(report['rows']):
        original_path, m = metadata[index // 2]
        role = row['role']
        bound = read(store, row['metadata_ref'])
        if (row['passed'] is not True or row['source_hash'] != expected['source_hashes'][role]
                or row['binary_hash'] != protocol['binary_hashes'][role]
                or row['original_metadata_ref'] != inputs[str(original_path)]
                or row['input_refs'] != {m['input']: inputs[m['input']]}
                or not _same_native_metadata(bound, dict(m, output=bound['output']))
                or len(row['output_refs']) != 1):
            raise ValueError('correctness row source/input/output binding differs')
        output = checked_file(store, bound['output'], row['output_refs'][0])
        checked_file(store, output.parent / 'metadata.json', row['metadata_ref'])
        checked_file(store, output.parent / 'result.json', row['result_ref'])
        if output.stat().st_size != m['numel'] * (4 if m['dtype'] == 'float32' else 2):
            raise ValueError('correctness full output byte count differs')
        outputs = {r: {'output': str(output.parent / (r + '-output.bin'))} for r in ROLES}
        argv = adapter.base.case_command(proof['operator'], binary, m, device, outputs)
        expected_commands = [argv + ['--aprof-mechanism-role', role],
            [sys.executable, str(oracle), '--metadata', str(output.parent / 'metadata.json')]]
        for key, command in zip(('kernel', 'verifier'), expected_commands):
            record = read(store, row[key + '_execution_ref'])
            raw = read(store, record['original_execution_ref'])
            projection = dict(argv=raw['argv'], cwd=raw['cwd'], started_at=raw['started_at'],
                finished_at=raw['ended_at'], exit_status=raw['exit_code'], error=raw['error'],
                environment=raw['environment'], timeout_seconds=raw['timeout_seconds'], pid=raw['pid'],
                stdout=path_ref(store.verify_artifact(raw['stdout_hash'])),
                stderr=path_ref(store.verify_artifact(raw['stderr_hash'])), log_ref=raw['stdout_hash'],
                original_execution_ref=record['original_execution_ref'])
            if (record != projection or record['argv'] != command
                    or record['exit_status'] != 0 or record['error'] is not None
                    or record['environment'] != {'APROF_SHARED_CYCLE': '0'}
                    or not previous <= record['started_at'] <= record['finished_at'] <= report['finished_at']):
                raise ValueError('correctness actual execution/role/order differs')
            previous = record['finished_at']
        if stage == 'correctness':
            legacy = role_reports[role]['rows'][index // 2]
            for key, reference in (('metadata', row['metadata_ref']), ('verification', row['result_ref']),
                    ('kernel_execution', row['kernel_execution_ref']), ('verifier_execution', row['verifier_execution_ref'])):
                if legacy[key]['sha256'] != reference:
                    raise ValueError('role report differs from complete execution aggregate')
            if [v['sha256'] for v in legacy['outputs']] != row['output_refs']:
                raise ValueError('role report output differs')
    return {'passed': True, 'stage': stage, 'case_count': len(ids), 'report_ref': report_ref,
            'protocol_ref': protocol_ref, 'admission_authority': False}


def collect_correctness(assembly, build_receipt, prepared, destination, store, *, expected,
                        deadline, protocol_ref, stage='correctness', device=0):
    """Run complete original oracle checks for both roles; fail closed, without retries.

    ``prepared`` contains case_01..20 or case_101..142/157 metadata. The frozen
    protocol's input_inventory_ref maps their absolute metadata/input paths to
    hashes. Boundary's original plan and new combined binary are both mandatory.
    Failure raises StageFailure whose result holds the partial report references.
    """
    bridge.remaining(deadline)
    assembly, destination = Path(assembly).absolute(), Path(destination).absolute()
    destination.mkdir(parents=True, exist_ok=False)
    started = time.time()
    rows, role_rows = [], {r: [] for r in ROLES}
    report = dict(schema_version=1, kind='task_rule_' + stage, **{
        k: expected[k] for k in ('operator', 'run_id', 'candidate_id', 'source_hashes')},
        protocol_ref=protocol_ref, device=device, started_at=started, status='failed', case_ids=[],
        passed_case_ids=[], rows=rows, error=None)
    result = None
    try:
        proof, build, protocol, oracle, inputs, metadata = _preflight(
            assembly, build_receipt, Path(prepared).absolute(), store, expected, protocol_ref, stage)
        binary = Path(build['binary']['path'])
        binary_ref = store.register_artifact(binary)
        report.update(case_ids=[m['case_id'] for _, m in metadata],
            binary_hashes={r: binary_ref for r in ROLES},
            source_review_ref=store.register_artifact(assembly / 'source-review.json'),
            build_receipt_ref=store.register_artifact(build_receipt),
            input_inventory_ref=protocol['input_inventory_ref'], oracle_ref=store.register_artifact(oracle))
        for original, m in metadata:
            for role in ROLES:
                bridge.remaining(deadline)
                folder = destination / f"case_{m['case_id']:03d}" / role
                folder.mkdir(parents=True)
                outputs = {r: {'output': str(folder / (r + '-output.bin'))} for r in ROLES}
                output = Path(outputs[role]['output'])
                bound = folder / 'metadata.json'
                _write_native_metadata(bound, m, output)
                row = dict(case_id=m['case_id'], role=role, source_hash=expected['source_hashes'][role],
                    binary_hash=binary_ref, original_metadata_ref=inputs[str(original)],
                    input_refs={m['input']: inputs[m['input']]}, metadata_ref=store.register_artifact(bound),
                    result_ref=None, kernel_execution_ref=None, verifier_execution_ref=None,
                    output_refs=[], passed=False)
                rows.append(row)
                argv = adapter.base.case_command(proof['operator'], binary, m, device, outputs)
                argv += ['--aprof-mechanism-role', role]
                for path, ref in ((binary, binary_ref), (original, inputs[str(original)]),
                                  (m['input'], inputs[m['input']]), (oracle, report['oracle_ref'])):
                    checked_file(store, path, ref)
                kernel_path, kernel = execute(argv, assembly / 'source', folder / 'kernel', store, deadline)
                row['kernel_execution_ref'] = kernel_path['sha256']
                if output.is_file():
                    row['output_refs'] = [store.register_artifact(output)]
                _check_execution(kernel, deadline)
                if (not output.is_file() or output.stat().st_size != m['numel'] * (4 if m['dtype'] == 'float32' else 2)
                        or any(Path(outputs[r]['output']).exists() for r in ROLES if r != role)):
                    raise ValueError('single role callback output scope/byte count differs')
                output_ref = row['output_refs'][0]
                verifier_path, verifier = execute([sys.executable, str(oracle), '--metadata', str(bound)],
                    oracle.parent.parent, folder / 'verifier', store, deadline)
                row['verifier_execution_ref'] = verifier_path['sha256']
                result_path = folder / 'result.json'
                if result_path.is_file():
                    row['result_ref'] = store.register_artifact(result_path)
                for path, ref in ((binary, binary_ref), (original, inputs[str(original)]),
                                  (m['input'], inputs[m['input']]), (oracle, report['oracle_ref']),
                                  (bound, row['metadata_ref']), (output, output_ref)):
                    checked_file(store, path, ref)
                _check_execution(verifier, deadline)
                native = json.loads(result_path.read_text())
                if native.get('passed') is not True:
                    raise ValueError('original mathematical oracle rejected output')
                row['passed'] = True
                role_rows[role].append(dict(case_id=m['case_id'], correct=True, metadata=path_ref(bound),
                    verification=path_ref(result_path), outputs=[path_ref(output)],
                    kernel_execution=kernel_path, verifier_execution=verifier_path))
            report['passed_case_ids'].append(m['case_id'])
        adapter.checked_build(assembly, build_receipt)
        bridge.remaining(deadline)
        report['status'] = 'passed'
        report['finished_at'] = time.time()
        if stage == 'boundary':
            verify_boundary_report(store, store.register_json(report), protocol_ref=protocol_ref,
                expected={**expected, 'boundary_window': [started, report['finished_at']]})
        else:
            for role in ROLES:
                role_path = destination / (role + '-report.json')
                bridge.save(role_path, dict(case_ids=report['case_ids'], rows=role_rows[role], complete=True))
                verify_correctness_report(path_ref(role_path))
        bridge.remaining(deadline)
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if report['status'] == 'passed' and time.monotonic() >= deadline:
            report['status'] = 'failed'
            report['error'] = {'type': 'TimeoutError', 'message': 'original controller deadline expired'}
        report['finished_at'] = time.time()
        report['duration_seconds'] = report['finished_at'] - started
        role_reports = {}
        if stage == 'correctness':
            for role in ROLES:
                path = destination / (role + '-report.json')
                if not path.exists():
                    bridge.save(path, dict(case_ids=list(range(1, 21)), rows=role_rows[role], complete=False))
                role_reports[role] = path_ref(path)
                store.register_artifact(path)
        report['role_reports'] = role_reports
        path = destination / 'report.json'
        bridge.save(path, report)
        result = dict(report_ref=store.register_artifact(path), report=path_ref(path), role_reports=role_reports,
                      status=report['status'], started_at=started, finished_at=report['finished_at'])
    if report['status'] != 'passed':
        raise StageFailure(report['error']['message'], result)
    return result
