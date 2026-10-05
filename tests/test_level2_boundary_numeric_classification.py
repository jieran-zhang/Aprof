"""CPU fixtures for the retained GN numeric guard proof; never invoke an NPU."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from level2_failure_classification import classify_failure
from aprof_runtime.planning import select_dispatch
from level2_adapters import workload_metadata

FIXTURES = Path(__file__).parent / 'fixtures/group_norm_numeric_guard'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')
    return path


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return path


def load(path):
    return json.loads(path.read_text())


def ref(path):
    return {'path': str(path), 'sha256': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()}


def proc(argv, cwd, code=0):
    argv = list(map(str, argv))
    task = next(p for p in (Path(cwd), *Path(cwd).parents) if p.name == 'group_norm')
    setup = ('source ' + str(task / 'sdk/set_env.sh') + ' || exit $?; '
             'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:'
             '/usr/local/Ascend/driver/lib64/driver:${LD_LIBRARY_PATH:-}; exec "$@"')
    return {'argv': argv, 'shell_argv': ['taskset', '-c', '40-43' if '-B' in argv else '8', 'bash', '-c', setup, 'feedback-hardware', *argv],
            'cwd': str(cwd), 'environment_overrides': {},
            'started_at': 1, 'finished_at': 2, 'exit_status': code,
            'status': 'passed' if code == 0 else 'failed',
            'error': f'process failed ({code}): {argv[0]}' if code else None}


def events(task, rows):
    values = []; previous = None
    for i, (kind, value) in enumerate(rows):
        row = {'sequence': i, 'recorded_at': str(i), 'kind': kind, 'previous_hash': previous, 'value': value}
        row['hash'] = 'sha256:' + hashlib.sha256((json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()).hexdigest()
        values.append(row); previous = row['hash']
    (task / 'events.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def refresh(task, parent):
    root = parent / 'boundary-validation'; request = load(root / 'request.json')
    for name in ('script', 'binary', 'dispatch_plan'):
        request[name] = ref(Path(request[name]['path']))
    save(root / 'request.json', request)
    guard = load(root / 'completion.json'); guard['request'] = ref(root / 'request.json')
    for row in guard['cases']:
        row['execution'] = ref(Path(row['execution']['path']))
    save(root / 'completion.json', guard)
    events(task, [
        ('boundary_cpu_prepared', {'count': len(guard['cases']), 'hardware_executed': False,
                                  'manifest': ref(task / 'agent/boundary_inputs/coordinator_commands.json')}),
        ('boundary_validation_started', {'candidate': parent.name, 'request': ref(root / 'request.json')}),
        ('boundary_validation_completed', {'candidate': parent.name, 'completion': ref(root / 'completion.json')})])
    return guard


def metric(actual, expected, dtype):
    a, b = actual.float().numpy().reshape(-1), expected.float().numpy().reshape(-1)
    rel = np.abs(a - b) / (np.abs(b) + 1e-7); th = .01 if dtype == 'bfloat16' else .005
    return {'passed': bool(rel.mean(dtype=np.float64) < th and rel.max(initial=0) < 10 * th),
            'special_values_match': True, 'mere': float(rel.mean(dtype=np.float64)), 'mare': float(rel.max(initial=0)), 'threshold': th}


def raw(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value.contiguous().view(torch.uint8).numpy().tobytes())


def fixture(tmp_path):
    task = tmp_path / 'run/validation/tasks/group_norm'; parent = task / 'candidates/group_norm001'
    root = parent / 'boundary-validation'; agent = task / 'agent'; source = parent / 'op'
    agent.mkdir(parents=True)
    write(task / 'sdk/set_env.sh', '# recorded SDK setup fixture; never executed\n')
    (task / 'baseline/scripts').mkdir(parents=True)
    shutil.copyfile(FIXTURES / 'verify_result.py', task / 'baseline/scripts/verify_result.py')
    shutil.copyfile(FIXTURES / 'boundary_guard.py', agent / 'boundary_guard.py')
    (agent / 'reference').mkdir(); shutil.copyfile(FIXTURES / 'golden.py', agent / 'reference/golden.py')
    producer = write(agent / 'prepare_boundary_inputs.py', '# fixture declaration producer; never executed\n')
    host = write(source / 'op_host/group_norm.asc', '#include "../op_kernel/group_norm_kernel.asc"\n')
    kernel = write(source / 'op_kernel/group_norm_kernel.asc', '// frozen numerical implementation\n')
    files = [host, kernel]; native_hash = hashlib.sha256()
    with tarfile.open(parent / 'source.tar', 'w') as tar:
        for path in files:
            relative = str(path.relative_to(source)); data = path.read_bytes()
            item = tarfile.TarInfo('source/' + relative); item.size = len(data); tar.addfile(item, io.BytesIO(data))
            native_hash.update(relative.encode() + b'\0' + data + b'\0')
    binary = write(parent / 'build/build/standalone', 'frozen standalone binary fixture')
    save(parent / 'build/build_manifest.json', {'operator': 'group_norm', 'standalone': ref(binary),
         'roles': {role: {'source_sha256': native_hash.hexdigest(), 'source_dir': str(source)} for role in ('A', 'B')}})
    save(parent / 'stages/build/result.json', {'status': 'passed', 'candidate_id': parent.name, 'kind': 'build', 'error': None})
    save(parent / 'stages/build/stage-plan.json', {'source_hash': ref(parent / 'source.tar')['sha256']})
    dispatch = {'schema_version': '1.0.0', 'operator': 'group_norm', 'dispatch_id': 'guard-numeric-fixture',
        'source_hash': ref(parent / 'source.tar')['sha256'], 'architecture_profile_ref': 'sha256:' + '1' * 64,
        'parallel_plan_ref': 'sha256:' + '2' * 64,
        'entries': [{'group_id': 'small_group', 'tiling_key': 30, 'kernel_entry': 'group_norm_small_group',
            'conditions': [{'field': 'attributes.group_elements', 'op': 'le', 'value': 4096}], 'required_capabilities': ['vector']}],
        'fallback': {'group_id': 'generic', 'tiling_key': 0, 'kernel_entry': 'group_norm_generic', 'conditions': [], 'required_capabilities': []}}
    plan = save(parent / 'dispatch_plan.json', dispatch)
    request = save(root / 'request.json', {'operator': 'group_norm', 'candidate': parent.name, 'dispatch_logs_required': True,
        'script': ref(agent / 'boundary_guard.py'), 'binary': ref(binary), 'dispatch_plan': ref(plan)})
    for name in ('health-before.json', 'health-after.json'):
        save(root / name, {'status': 'passed', 'exit_status': 0, 'error': None})
    cases = []; declarations = []; commands = []; rows = []; prepared = []; results = []
    for index, dtype in enumerate(('float32', 'float16', 'bfloat16')):
        name = f'finite_{dtype}'; shape = [2, 2, 7]; attrs = {'num_groups': 1, 'epsilon': 1e-5}
        descriptor = {'shape': shape, 'dtype': dtype, 'layout': 'ND', 'attributes': attrs}
        metadata = workload_metadata('group_norm', {**attrs, 'shape': shape, 'dtype': dtype, 'attrs': attrs})
        selected = select_dispatch(dispatch, metadata)
        case = {'name': name, 'metadata': descriptor, 'expected_key': 30}; cases.append(case)
        d = getattr(torch, dtype); x = ((torch.arange(28).float() % 11 - 5) / 8).reshape(shape).to(d)
        gamma = torch.tensor([.75, 1.25], dtype=d); beta = torch.tensor([.1, -.1], dtype=d)
        expected = torch.nn.functional.group_norm(x, 1, gamma, beta, 1e-5)
        actual = expected + .5 if index == 0 else expected
        orig = agent / 'boundary_inputs' / name; dest = root / 'inputs' / name
        for filename, value in [('x.bin', x), ('gamma.bin', gamma), ('beta.bin', beta), ('expected.bin', expected)]:
            raw(orig / filename, value); raw(dest / filename, value)
        raw(dest / 'output.bin', actual)
        def args(folder, device):
            return ['--shape', '2,2,7', '--dtype', dtype, '--groups', '1', '--epsilon', '1e-05', '--x', str(folder / 'x.bin'),
                    '--gamma', str(folder / 'gamma.bin'), '--beta', str(folder / 'beta.bin'), '--output', str(folder / 'output.bin'), '--device', device]
        declaration = {'name': name, 'operator': 'group_norm', 'hardware_executed': False, 'workload_metadata': descriptor,
            'expected_key': 30, 'producer': ref(producer), 'oracle': ref(agent / 'reference/golden.py'),
            'expected': ref(orig / 'expected.bin'), 'native_arguments': args(orig, '{device}'), 'reference_status': 'source_derived_reference'}
        save(orig / 'guard.json', declaration); declarations.append(declaration)
        command = {'name': name, 'metadata': metadata, 'expected_key': 30, 'expected_entry': 'group_norm_small_group',
                   'reference': str(dest / 'expected.bin'), 'argv': args(dest, '0')}; commands.append(command)
        execution = save(root / 'executions' / name / 'execution.json', proc([binary, *command['argv']], source))
        log = {'tiling_key': 30, 'kernel_entry': 'group_norm_small_group'}
        write(execution.parent / 'stdout.log', 'APROF_DISPATCH_JSON:' + json.dumps(log) + '\n'); write(execution.parent / 'stderr.log', '')
        rows.append({'name': name, 'execution': ref(execution), 'error': None, 'expected_process_passed': True, 'dispatch_log_passed': True, 'dispatch_logs': [log]})
        pre = {'name': name, 'dispatch': selected, 'reference_status': declaration['reference_status'], 'oracle': declaration['oracle'],
               'status': 'cpu_reference_prepared_not_hardware_verified'}; prepared.append(pre)
        metrics = metric(actual, expected, dtype)
        results.append({**pre, 'output': metrics, 'passed': metrics['passed'], 'status': 'coordinator_output_verified' if metrics['passed'] else 'coordinator_output_failed'})
    save(agent / 'boundary_cases.json', {'operator': 'group_norm', 'cases': cases})
    save(agent / 'boundary_inputs/coordinator_commands.json', {'operator': 'group_norm', 'hardware_executed': False, 'commands': declarations})
    save(root / 'inputs/coordinator_commands.json', commands)
    for name, values in [('cpu_preparation.json', prepared), ('verification.json', results)]:
        save(root / 'inputs' / name, {'operator': 'group_norm', 'hardware_executed_by_this_script': False, 'results': values})
    for name in ('prepare', 'verify'):
        argv = [sys.executable, '-B', agent / 'boundary_guard.py', '--output', root / 'inputs']
        if name == 'verify': argv += ['--verify']
        argv += ['--plan', plan]; save(root / name / 'execution.json', proc(argv, task, int(name == 'verify')))
        write(root / name / 'stderr.log', '')
        save(root / name / 'stdout.log', {'operator': 'group_norm', 'cases': len(cases), 'mode': 'verify_existing_outputs' if name == 'verify' else 'cpu_only', 'passed': name != 'verify'})
    save(root / 'completion.json', {'status': 'failed', 'error': None, 'request': ref(request), 'cases': rows,
        'verification_error': {'type': 'RuntimeError', 'message': f'process failed (1): {sys.executable}'}})
    return task, parent, root, refresh(task, parent)


def test_bound_original_numeric_guard_is_read_only_and_replayable(tmp_path):
    task, parent, root, guard = fixture(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    actual = classify_failure(task, parent, guard=guard)
    assert actual['status'] == 'source_attempt_failed', actual
    assert actual['rule'] == 'original_boundary_oracle_numeric_mismatch'
    assert actual == classify_failure(task, parent, guard=guard)
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert len(actual['event_bindings']) == 3
    assert str(task / 'events.jsonl') not in {r['path'] for r in actual['evidence']}
    assert all(ref(Path(r['path'])) == r for r in actual['evidence'])
    assert 'not individually presealed' in actual['reason']


def test_legal_public_event_suffix_does_not_change_closed_classification(tmp_path):
    task, parent, root, guard = fixture(tmp_path); before = classify_failure(task, parent, guard=guard)
    old = [json.loads(line) for line in (task / 'events.jsonl').read_text().splitlines()]
    events(task, [(row['kind'], row['value']) for row in old] + [('future_source_authored', {'candidate': 'group_norm002'})])
    assert classify_failure(task, parent, guard=guard) == before


def test_guard_failure_claim_without_any_numeric_failure_is_blocked(tmp_path):
    task, parent, root, guard = fixture(tmp_path)
    dest = root / 'inputs/finite_float32'
    shutil.copyfile(dest / 'expected.bin', dest / 'output.bin')
    value = load(root / 'inputs/verification.json'); row = value['results'][0]
    row.update(passed=True, status='coordinator_output_verified')
    row['output'].update(passed=True, mere=0., mare=0.)
    save(root / 'inputs/verification.json', value)
    result = classify_failure(task, parent, guard=guard)
    assert result['status'] == 'infrastructure_blocked'
    assert 'no original-oracle numeric mismatch' in result['reason']


def test_stricter_guard_failure_below_original_absolute_tolerance_is_blocked(tmp_path):
    task, parent, root, guard = fixture(tmp_path)
    dest = root / 'inputs/finite_float32'; orig = task / 'agent/boundary_inputs/finite_float32'
    # Gamma=beta=0 makes the reviewed golden identically zero. A tiny native
    # error fails relative-only guards but is allowed by the original checker.
    for folder in (orig, dest):
        (folder / 'gamma.bin').write_bytes(np.zeros(2, np.float32).tobytes())
        (folder / 'beta.bin').write_bytes(np.zeros(2, np.float32).tobytes())
        (folder / 'expected.bin').write_bytes(np.zeros(28, np.float32).tobytes())
    (dest / 'output.bin').write_bytes(np.full(28, 1e-5, np.float32).tobytes())
    declaration = load(orig / 'guard.json'); declaration['expected'] = ref(orig / 'expected.bin'); save(orig / 'guard.json', declaration)
    manifest_path = task / 'agent/boundary_inputs/coordinator_commands.json'; manifest = load(manifest_path)
    manifest['commands'][0] = declaration; save(manifest_path, manifest)
    verification = load(root / 'inputs/verification.json')
    verification['results'][0]['output'] = metric(torch.full((28,), 1e-5), torch.zeros(28), 'float32')
    save(root / 'inputs/verification.json', verification); guard = refresh(task, parent)
    result = classify_failure(task, parent, guard=guard)
    assert result['status'] == 'infrastructure_blocked'
    assert 'stricter-than-original tolerance' in result['reason']


@pytest.mark.parametrize('fault', ['prefix_value', 'prefix_hash', 'missing_prepare', 'prepare_after_native',
    'manifest_changed', 'missing_health', 'health_failed', 'native_signal', 'native_timeout', 'native_argv',
    'native_stderr', 'native_dispatch', 'missing_native_stdout', 'missing_verify', 'verify_import', 'verify_timeout',
    'verify_stdout_true', 'verify_exit0', 'verify_argv', 'verify_environment', 'prepare_failed', 'changed_script',
    'changed_golden', 'truncated_output', 'missing_output', 'output_nan', 'output_tamper', 'forged_metric',
    'expected_tamper', 'expected_rebound', 'inputs_changed', 'source_changed', 'source_extra', 'wrong_role_hash',
    'binary_changed', 'plan_changed', 'missing_case', 'case_reorder', 'duplicate_case', 'symlink_output',
    'verify_shell_command', 'native_shell_command', 'native_setup_override', 'baseline_verifier_changed', 'output_trailing_byte'])
def test_numeric_guard_incomplete_or_forged_evidence_is_blocked(tmp_path, fault):
    task, parent, root, guard = fixture(tmp_path); dest = root / 'inputs/finite_float32'; orig = task / 'agent/boundary_inputs/finite_float32'
    if fault in ('prefix_value', 'prefix_hash'):
        rows = (task / 'events.jsonl').read_text().splitlines(); row = json.loads(rows[0])
        if fault == 'prefix_value': row['value']['count'] = 99
        else: row['hash'] = 'sha256:' + '0' * 64
        rows[0] = json.dumps(row); (task / 'events.jsonl').write_text('\n'.join(rows) + '\n')
    elif fault in ('missing_prepare', 'prepare_after_native'):
        rows = [json.loads(line) for line in (task / 'events.jsonl').read_text().splitlines()]
        rows = rows[1:] if fault == 'missing_prepare' else [rows[1], rows[0], rows[2]]
        events(task, [(row['kind'], row['value']) for row in rows])
    elif fault == 'manifest_changed': save(task / 'agent/boundary_inputs/coordinator_commands.json', {})
    elif fault == 'missing_health': (root / 'health-after.json').unlink()
    elif fault == 'health_failed': save(root / 'health-after.json', {'status': 'failed', 'exit_status': 1})
    elif fault.startswith('native_'):
        p = root / 'executions/finite_float32/execution.json'; value = load(p)
        if fault == 'native_signal': value.update(exit_status=-11, status='failed')
        elif fault == 'native_timeout': value['timed_out'] = True
        elif fault == 'native_argv': value['argv'][-1] = '1'
        elif fault == 'native_stderr': write(p.parent / 'stderr.log', 'unclassified warning/error\n')
        elif fault == 'native_dispatch': write(p.parent / 'stdout.log', 'APROF_DISPATCH_JSON:{"tiling_key":0,"kernel_entry":"group_norm_generic"}\n')
        elif fault == 'native_shell_command': value['shell_argv'][-1] = '1'
        elif fault == 'native_setup_override': value['shell_argv'][5] += '; touch /tmp/unreviewed-command'
        save(p, value); guard = refresh(task, parent)
    elif fault == 'missing_native_stdout': (root / 'executions/finite_float32/stdout.log').unlink()
    elif fault == 'missing_verify': (root / 'inputs/verification.json').unlink()
    elif fault.startswith('verify_'):
        p = root / 'verify/execution.json'; value = load(p)
        if fault == 'verify_import': write(p.parent / 'stderr.log', 'ImportError: no torch\n')
        elif fault == 'verify_timeout': value['timed_out'] = True
        elif fault == 'verify_stdout_true': save(p.parent / 'stdout.log', {'operator': 'group_norm', 'cases': 3, 'mode': 'verify_existing_outputs', 'passed': True})
        elif fault == 'verify_exit0': value.update(exit_status=0, error=None, status='passed')
        elif fault == 'verify_argv': value['argv'][2] = '/tmp/unreviewed.py'
        elif fault == 'verify_environment': value['environment_overrides'] = {'PYTHONPATH': '/tmp/arbitrary'}
        elif fault == 'verify_shell_command': value['shell_argv'][-1] = '/tmp/unreviewed-plan'
        save(p, value)
    elif fault == 'prepare_failed': value = load(root / 'prepare/execution.json'); value['exit_status'] = 1; save(root / 'prepare/execution.json', value)
    elif fault == 'changed_script': write(task / 'agent/boundary_guard.py', '# forged guard\n'); guard = refresh(task, parent)
    elif fault == 'changed_golden': write(task / 'agent/reference/golden.py', '# forged golden\n')
    elif fault == 'truncated_output': (dest / 'output.bin').write_bytes((dest / 'output.bin').read_bytes()[:-4])
    elif fault == 'missing_output': (dest / 'output.bin').unlink()
    elif fault == 'output_nan': (dest / 'output.bin').write_bytes(np.full(28, np.nan, np.float32).tobytes())
    elif fault == 'output_tamper': (dest / 'output.bin').write_bytes(np.zeros(28, np.float32).tobytes())
    elif fault == 'output_trailing_byte': (dest / 'output.bin').write_bytes((dest / 'output.bin').read_bytes() + b'\x00')
    elif fault == 'forged_metric': value = load(root / 'inputs/verification.json'); value['results'][0]['output']['mare'] = 99.; save(root / 'inputs/verification.json', value)
    elif fault in ('expected_tamper', 'expected_rebound'):
        (dest / 'expected.bin').write_bytes(np.ones(28, np.float32).tobytes())
        if fault == 'expected_rebound':
            shutil.copyfile(dest / 'expected.bin', orig / 'expected.bin'); d = load(orig / 'guard.json'); d['expected'] = ref(orig / 'expected.bin'); save(orig / 'guard.json', d)
            m = load(task / 'agent/boundary_inputs/coordinator_commands.json'); m['commands'][0] = d; save(task / 'agent/boundary_inputs/coordinator_commands.json', m); guard = refresh(task, parent)
    elif fault == 'inputs_changed': (dest / 'x.bin').write_bytes(np.zeros(28, np.float32).tobytes())
    elif fault == 'source_changed': write(parent / 'op/op_kernel/group_norm_kernel.asc', '// changed\n')
    elif fault == 'source_extra': write(parent / 'op/op_kernel/extra.h', '// generated\n')
    elif fault == 'wrong_role_hash': value = load(parent / 'build/build_manifest.json'); value['roles']['B']['source_sha256'] = '0' * 64; save(parent / 'build/build_manifest.json', value)
    elif fault == 'binary_changed': write(parent / 'build/build/standalone', 'another binary')
    elif fault == 'plan_changed': save(parent / 'dispatch_plan.json', {})
    elif fault == 'baseline_verifier_changed': write(task / 'baseline/scripts/verify_result.py', '# different tolerances\n')
    elif fault == 'missing_case': value = load(root / 'inputs/verification.json'); value['results'].pop(); save(root / 'inputs/verification.json', value)
    elif fault == 'case_reorder': value = load(root / 'inputs/verification.json'); value['results'].reverse(); save(root / 'inputs/verification.json', value)
    elif fault == 'duplicate_case': value = load(task / 'agent/boundary_cases.json'); value['cases'][1] = value['cases'][0]; save(task / 'agent/boundary_cases.json', value)
    elif fault == 'symlink_output': p = dest / 'output.bin'; data = p.read_bytes(); p.unlink(); other = tmp_path / 'other-output.bin'; other.write_bytes(data); p.symlink_to(other)
    actual = classify_failure(task, parent, guard=guard)
    assert actual['status'] == 'infrastructure_blocked', (fault, actual)
