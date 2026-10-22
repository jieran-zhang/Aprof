"""One trusted, original-source baseline build; no route or qualification grant.

The caller supplies its existing command runner and absolute deadline. This
module writes task-local assembly/build evidence, never generates inputs, invokes
a model, captures profiles, or archives anything. Public candidate adapters stay
unchanged; the original GQA/WQ oracle relocation is bound in a private instance.
"""
from task_budget import budget_seconds, positive, collection_policy
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import time

import shared_validation_adapter as shared
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.local_evidence import LocalEvidence
from task_baseline_pmu import PROFILE_DEPENDENCY_PATHS

HERE = Path(__file__).resolve().parent
OPERATORS = ('dynamic_quant', 'gelu', 'group_norm', 'gqa', 'weight_quant_batch_matmul')
ROLES = ('baseline', 'candidate')
PROTOCOL = 'validation_baseline_task_v1'
TASK_PROTOCOL = 'shared_buffer_msprof_task_window_v5'
CANN_HOME = '/usr/local/Ascend/cann-9.0.0'
CPU_REFERENCE_ENV = {key: '32' for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _path(value):
    path = Path(value)
    _need(path.is_absolute() and path.resolve() == path
          and not any(p.is_symlink() for p in (path, *path.parents)), 'noncanonical baseline path')
    return path


def _local(local):
    _need(isinstance(local, LocalEvidence) and shared.selected_runtime().name == '1.0.0',
          'baseline build requires selected 1.0.0 LocalEvidence')


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _bindings(local, values, required=()):
    _need(isinstance(values, dict) and set(required) <= values.keys(), 'baseline dependency roster differs')
    for name, reference in values.items():
        path = _path(name)
        local.verify_artifact(reference)
        _need(path.is_file() and file_hash(path) == reference, 'baseline dependency changed: ' + name)


def _adapter(operator, local, preparation_ref):
    _need(operator in OPERATORS, 'unsupported original validation operator')
    filename = 'shared_multikernel_adapter.py' if operator in ('gqa', 'weight_quant_batch_matmul') else 'shared_mechanism_adapter.py'
    spec = importlib.util.spec_from_file_location('baseline_private_adapter', HERE / filename)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    original = adapter.base.prepared_baseline(operator)
    manifest = _read(local, preparation_ref)
    _need(manifest.get('schema_version') == 1 and manifest.get('operator') == operator
          and manifest.get('state') == 'cpu_prepared_awaiting_baseline_qualification',
          'original preparation manifest differs')
    host = adapter.base.REPO / 'scaffolding/benchmarks/cannbench/operators' / operator / 'op_host' / (operator + '.asc')
    _need(file_hash(host) == manifest['original_host_sha256']
          and file_hash(adapter.base.old.HEADER) == manifest['timer_sha256'], 'original host/timer changed')
    relocation = manifest['oracle_relocation']
    if operator in adapter.base.old.EXTERNAL_CASES:
        _need(isinstance(relocation, dict), 'original oracle relocation missing')
        name = 'scripts/cases.py'
        _need(shared.digest(original[name]) == relocation['resolver_before_sha256'], 'original case resolver changed')
        pattern = (r"Path\(__file__\)\.resolve\(\)\.parents\[5\]\s*/\s*['\"]third_party/cann-bench/tasks/"
                   + re.escape(adapter.base.old.EXTERNAL_CASES[operator]) + r"['\"]")
        relocated, count = re.subn(pattern, 'Path(__file__).with_name("cases.yaml")', original[name].decode())
        _need(count == 1 and shared.digest(relocated.encode()) == relocation['resolver_after_sha256'],
              'original case relocation differs')
        case_spec = relocation['case_spec']
        yaml = _path(case_spec['path'])
        _need(file_hash(yaml) == case_spec['sha256'], 'original YAML case specification changed')
        original[name], original['scripts/cases.yaml'] = relocated.encode(), yaml.read_bytes()
    else:
        _need(relocation is None, 'unexpected oracle relocation')
    _need(shared.inventory(original) == manifest['source_files'], 'original preparation inventory changed')
    # Only this adapter instance sees the already verified historical relocation.
    def prepared(selected):
        _need(selected == operator, 'baseline adapter operator changed')
        return dict(original)
    adapter.base.prepared_baseline = prepared
    return adapter, manifest


def _source_proof(operator, sources, local, preparation_ref, *, register):
    _local(local)
    _need(set(sources) == set(ROLES), 'two original source roles are required')
    adapter, manifest = _adapter(operator, local, preparation_ref)
    roles, hashes = {}, {}
    for role in ROLES:
        path = _path(sources[role])
        files = shared.inventory(shared.tree(path))
        _need(files == manifest['source_files'], 'baseline-only role differs from original preparation: ' + role)
        for name, reference in files.items():
            if register:
                _need(local.register_artifact(path / name) == reference, 'source changed while registering')
            local.verify_artifact(reference)
        bundle = {'schema_version': '1.0.0', 'files': files}
        hashes[role] = local.register_json(bundle) if register else content_hash(bundle)
        local.verify_artifact(hashes[role])
        roles[role] = {'path': str(path), 'files': files}
    _need(roles['baseline']['path'] != roles['candidate']['path']
          and hashes['baseline'] == hashes['candidate'], 'baseline roles must be distinct paths with identical bytes')
    producers = (Path(__file__).resolve(), Path(adapter.__file__).resolve(), adapter.base.OLD_PATH,
                 HERE / 'shared_validation_adapter.py')
    proof = {'preparation_ref': preparation_ref, 'roles': roles, 'source_hashes': hashes,
             'original_source_files': manifest['source_files'],
             'producer_files': {str(path): file_hash(path) for path in producers}}
    return adapter, proof


def baseline_source_proof(operator, sources, *, local, preparation_ref):
    """Prepare exact same-source bundles, including the original oracle relocation."""
    return _source_proof(operator, sources, local, preparation_ref, register=True)[1]


def prepare_baseline_assembly(local, *, operator, sources, destination, preparation_ref, expected_headers):
    """Mechanical CPU assembly only; call before freezing the qualification plan."""
    adapter, source = _source_proof(operator, sources, local, preparation_ref, register=True)
    for name in adapter.base.HEADERS:
        _need(local.register_artifact(adapter.base.ASSETS / name) == expected_headers[name], 'trusted header changed')
    proof = adapter.assemble(operator, sources, _path(destination),
        expected_roles={role: source['roles'][role]['files'] for role in ROLES}, expected_headers=expected_headers)
    local.register_artifact(Path(destination) / 'source-review.json')
    return proof


def _assembly(local, plan_ref):
    _local(local)
    plan = _read(local, plan_ref)
    collection_policy(plan)
    _need(plan.get('schema_version') == 1 and plan.get('kind') == 'task_baseline_qualification_plan'
          and plan.get('protocol') == PROTOCOL and plan.get('task_protocol') == TASK_PROTOCOL
          and plan.get('budget_policy') == 'time_only_v1' and budget_seconds(plan) > 0
          and plan.get('case_ids') == list(range(1, 21)) and plan.get('device') == 0
          and type(plan.get('physical_device')) is int and plan['physical_device'] >= 0,
          'baseline build plan protocol/budget/device differs')
    adapter, source = _source_proof(plan['operator'], {r: plan['roles'][r]['path'] for r in ROLES},
                                  local, plan['preparation_ref'], register=False)
    _need(plan['roles'] == source['roles'] and plan['source_hashes'] == source['source_hashes'],
          'baseline plan differs from exact original sources')
    _bindings(local, plan['producer_refs'], source['producer_files'])
    _need(set(plan['toolchain_refs']) == set(PROFILE_DEPENDENCY_PATHS), 'original toolchain roster differs')
    _bindings(local, plan['toolchain_refs'])
    _need(positive(_read(local, plan['job_ref'])['timeout_seconds']) == budget_seconds(plan), 'baseline job deadline differs')
    assembly = _path(plan['assembly_dir'])
    source_ref = plan['source_review_ref']
    local.verify_artifact(source_ref)
    _need(file_hash(assembly / 'source-review.json') == source_ref, 'baseline assembly proof changed')
    proof = adapter.source_identity(assembly)
    _need(proof['roles'] == plan['roles'] and proof['trusted_headers'] == plan['headers'],
          'baseline assembly differs from frozen role/header plan')
    for name, reference in plan['headers'].items():
        local.verify_artifact(reference)
        _need(file_hash(adapter.base.ASSETS / name) == reference, 'baseline header changed')
    return plan, proof


def _save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'invalid baseline time')
    return value


def _remaining(commands, deadline):
    _need(commands.deadline == deadline, 'baseline runner changed the original absolute deadline')
    remaining = _number(deadline) - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('original baseline deadline expired')
    commands.remaining()
    return remaining


def _environment(plan):
    expected = {'APROF_SKILL_LIB': str(shared.RELEASE), 'ASCEND_RT_VISIBLE_DEVICES': str(plan['physical_device']),
                'ASCEND_HOME_PATH': CANN_HOME, **CPU_REFERENCE_ENV}
    _need(os.environ.get('APROF_SKILL_LIB') == expected['APROF_SKILL_LIB']
          and os.environ.get('ASCEND_RT_VISIBLE_DEVICES') == expected['ASCEND_RT_VISIBLE_DEVICES']
          and str(Path(os.environ.get('ASCEND_HOME_PATH', '/')).resolve()) == CANN_HOME
          and all(os.environ.get(key) == value for key, value in CPU_REFERENCE_ENV.items()),
          'baseline execution release/device/toolchain environment differs')
    cmake = shutil.which('cmake')
    _need(cmake is not None and str(Path(cmake).resolve()) in plan['toolchain_refs'], 'unbound CMake executable')
    return expected


def _record(local, record, execution_path, *, register):
    execution_path = _path(execution_path)
    reference = local.register_artifact(execution_path) if register else file_hash(execution_path)
    _need(_read(local, reference) == record, 'command differs from its actual execution record')
    for name in ('stdout', 'stderr'):
        value = record[name]
        path = _path(value['path'])
        actual = local.register_artifact(path) if register else file_hash(path)
        _need(actual == value['sha256'], 'baseline command log changed')
        local.verify_artifact(actual)
    return {'path': str(execution_path), 'sha256': reference}


def build_baseline_once(local, *, plan_ref, commands):
    """Return a local receipt hash after exactly one configure/compile attempt."""
    started_at, started_mono = time.time(), time.monotonic()
    deadline = commands.deadline
    _remaining(commands, deadline)
    plan, proof = _assembly(local, plan_ref)
    environment = _environment(plan)
    assembly = _path(plan['assembly_dir'])
    _need(not (assembly / 'build').exists() and not (assembly / 'build-receipt.json').exists(),
          'baseline build directory/receipt already exists; no rebuild')
    _remaining(commands, deadline)
    attempt = {'schema_version': 1, 'kind': 'original_baseline_build_attempt', 'plan_ref': plan_ref,
               'source_review_hash': plan['source_review_ref'], 'source_hashes': plan['source_hashes'],
               'commands': proof['commands'], 'environment': environment,
               'deadline_monotonic': deadline, 'started_at': started_at, 'started_monotonic': started_mono}
    attempt_path, receipt_path = assembly / 'build-attempt.json', assembly / 'build-receipt.json'
    _save(attempt_path, attempt)
    attempt_ref = {'path': str(attempt_path), 'sha256': local.register_artifact(attempt_path)}
    records, stages, status, error, binary = [], [], 'failed', None, None
    try:
        for stage in ('configure', 'build'):
            _remaining(commands, deadline)
            wall, mono = time.time(), time.monotonic()
            record = commands.run(stage, proof['commands'][stage], assembly / 'source')
            ended_at, ended_mono = time.time(), time.monotonic()
            records.append(record)
            execution_ref = _record(local, record, Path(commands.directory) / stage / 'execution.json', register=True)
            stages.append({'stage': stage, 'started_at': wall, 'finished_at': ended_at,
                           'started_monotonic': mono, 'finished_monotonic': ended_mono, 'execution_ref': execution_ref})
            _need(record['argv'] == proof['commands'][stage] and record['cwd'] == str(assembly / 'source')
                  and type(record['exit_status']) is int and record['exit_status'] == 0 and record['error'] is None,
                  'baseline ' + stage + ' failed; no retry')
            _remaining(commands, deadline)
        _assembly(local, plan_ref)
        path = _path(assembly / 'build' / plan['operator'])
        binary = {'path': str(path), 'sha256': local.register_artifact(path)}
        _remaining(commands, deadline)
        status = 'passed'
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        _save(receipt_path, {'schema_version': 1, 'kind': 'original_baseline_build',
            'admission_authority': False, 'qualification_granted': False, 'status': status, 'error': error,
            'plan_ref': plan_ref, 'attempt_ref': attempt_ref, 'source_review_hash': plan['source_review_ref'],
            'source_hashes': plan['source_hashes'], 'commands': records, 'stages': stages, 'binary': binary,
            'environment': environment, 'deadline_monotonic': deadline,
            'started_at': started_at, 'finished_at': time.time(),
            'started_monotonic': started_mono, 'finished_monotonic': time.monotonic()})
        receipt_ref = local.register_artifact(receipt_path)
    _remaining(commands, deadline)
    return receipt_ref


def checked_baseline_build(local, *, plan_ref, build_receipt_ref):
    """Read-only byte/execution replay. The outer job must join its actual exit."""
    plan, proof = _assembly(local, plan_ref)
    assembly = _path(plan['assembly_dir'])
    build = _read(local, build_receipt_ref)
    attempt_path = assembly / 'build-attempt.json'
    _need(file_hash(assembly / 'build-receipt.json') == build_receipt_ref
          and build.get('kind') == 'original_baseline_build' and build.get('schema_version') == 1
          and build.get('status') == 'passed' and build.get('error') is None
          and build.get('admission_authority') is False and build.get('qualification_granted') is False
          and build['plan_ref'] == plan_ref and build['source_review_hash'] == plan['source_review_ref']
          and build['source_hashes'] == plan['source_hashes']
          and build['attempt_ref'] == {'path': str(attempt_path), 'sha256': file_hash(attempt_path)},
          'baseline build receipt differs from the original attempt')
    attempt = _read(local, build['attempt_ref']['sha256'])
    environment = {'APROF_SKILL_LIB': str(shared.RELEASE), 'ASCEND_RT_VISIBLE_DEVICES': str(plan['physical_device']),
                   'ASCEND_HOME_PATH': CANN_HOME, **CPU_REFERENCE_ENV}
    _need(attempt == {'schema_version': 1, 'kind': 'original_baseline_build_attempt', 'plan_ref': plan_ref,
        'source_review_hash': plan['source_review_ref'], 'source_hashes': plan['source_hashes'],
        'commands': proof['commands'], 'environment': environment, 'deadline_monotonic': build['deadline_monotonic'],
        'started_at': build['started_at'], 'started_monotonic': build['started_monotonic']}
        and build['environment'] == environment, 'baseline attempt identity/environment differs')
    begin, finish, deadline = (_number(build[key]) for key in ('started_monotonic', 'finished_monotonic', 'deadline_monotonic'))
    wall_begin, wall_end = _number(build['started_at']), _number(build['finished_at'])
    _need(begin <= finish <= deadline <= begin + budget_seconds(plan) and wall_begin <= wall_end <= wall_begin + budget_seconds(plan)
          and len(build['commands']) == len(build['stages']) == 2, 'baseline build exceeded deadline or stage roster')
    last_wall, last_mono = wall_begin, begin
    for stage, record, timing in zip(('configure', 'build'), build['commands'], build['stages'], strict=True):
        start, end = _number(timing['started_at']), _number(timing['finished_at'])
        mono_start, mono_end = _number(timing['started_monotonic']), _number(timing['finished_monotonic'])
        duration = _number(record['duration_seconds'])
        _need(timing['stage'] == stage and last_wall <= start <= end <= wall_end
              and last_mono <= mono_start <= mono_end <= finish and 0 <= duration <= mono_end - mono_start + .01
              and record['argv'] == proof['commands'][stage] and record['cwd'] == str(assembly / 'source')
              and type(record['exit_status']) is int and record['exit_status'] == 0 and record['error'] is None,
              'baseline command/order/exit/time differs')
        _need(_record(local, record, timing['execution_ref']['path'], register=False) == timing['execution_ref'],
              'baseline execution pointer differs')
        last_wall, last_mono = end, mono_end
    binary = _path(assembly / 'build' / plan['operator'])
    _need(build['binary'] == {'path': str(binary), 'sha256': file_hash(binary)}, 'baseline combined binary changed')
    local.verify_artifact(build['binary']['sha256'])
    return proof, build


ENABLED_IN_1_0 = False
