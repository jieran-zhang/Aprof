"""Real original-source assembly; synthetic command records, no CANN/NPU/input generation."""
import json
from pathlib import Path

import pytest

from aprof_runtime import __version__
if __version__ != '0.2.3':
    pytest.skip('select graph-base/1.0.0 runtime 0.2.3', allow_module_level=True)

from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.errors import StoreError
import task_baseline_build as build


class Clock:
    def __init__(self):
        self.elapsed = 0

    def monotonic(self):
        return 10000.0 + self.elapsed

    def time(self):
        return 1800000000.0 + self.elapsed


class Commands:
    """Fixture process outputs only; never invokes any compiler or executable."""
    def __init__(self, directory, assembly, operator, clock, *, failure=None):
        self.directory, self.assembly, self.operator, self.clock = directory, assembly, operator, clock
        self.deadline = clock.monotonic() + 3600
        self.calls, self.failure = [], failure

    def remaining(self):
        value = self.deadline - self.clock.monotonic()
        if value <= 0:
            raise TimeoutError('fixture shared deadline expired')
        return value

    def run(self, label, argv, cwd):
        self.calls.append(label)
        output = self.directory / label
        output.mkdir(parents=True)
        for name in ('stdout', 'stderr'):
            (output / (name + '.log')).write_text('CPU fixture ' + name + '\n')
        self.clock.elapsed += 2
        error = {'type': 'TimeoutError', 'message': 'CPU fixture timeout'} if label == self.failure else None
        record = {'argv': list(argv), 'cwd': str(cwd), 'duration_seconds': 2,
                  'exit_status': -15 if error else 0, 'error': error,
                  **{name: {'path': str(output / (name + '.log')), 'sha256': file_hash(output / (name + '.log'))}
                     for name in ('stdout', 'stderr')}}
        (output / 'execution.json').write_text(json.dumps(record))
        if label == 'configure':
            (self.assembly / 'build').mkdir()
        if label == 'build' and not error:
            (self.assembly / 'build' / self.operator).write_bytes(b'CPU fixture, not executable or hardware evidence')
        return record


def write(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def setup(tmp_path, monkeypatch, operator='gelu'):
    clock = Clock()
    monkeypatch.setattr(build, 'time', clock)
    local = LocalEvidence(tmp_path / 'records')
    prep_root = (build.shared.REPO.parent / 'validation-graph-base-1.0.0-round2-20261014'
                 / 'evaluation-source-preparation' / operator)
    preparation_ref = local.register_artifact(prep_root / 'preparation.json')
    # Read the exact frozen source tree; this is source copying for a CPU test,
    # not a production profiler/trace archive or input generator.
    manifest = json.loads((prep_root / 'preparation.json').read_text())
    files = {name: (prep_root / 'baseline' / name).read_bytes() for name in manifest['source_files']}
    sources = {role: tmp_path / role for role in build.ROLES}
    for source in sources.values():
        write(source, files)
    original = build.baseline_source_proof(operator, sources, local=local, preparation_ref=preparation_ref)
    headers = {name: local.register_artifact(build.shared.ASSETS / name) for name in build.shared.HEADERS}
    assembly = tmp_path / 'assembly'
    proof = build.prepare_baseline_assembly(local, operator=operator, sources=sources, destination=assembly,
        preparation_ref=preparation_ref, expected_headers=headers)
    cmake = tmp_path / 'cpu-cmake-placeholder'
    cmake.write_text('CPU fixture; never execute')
    monkeypatch.setattr(build, 'PROFILE_DEPENDENCY_PATHS', (str(cmake),))
    monkeypatch.setattr(build.shutil, 'which', lambda name: str(cmake) if name == 'cmake' else None)
    monkeypatch.setenv('ASCEND_HOME_PATH', build.CANN_HOME)
    monkeypatch.setenv('ASCEND_RT_VISIBLE_DEVICES', '2')
    for key, value in build.CPU_REFERENCE_ENV.items():
        monkeypatch.setenv(key, value)
    producer_refs = {name: local.register_artifact(name) for name in original['producer_files']}
    plan = {'schema_version': 1, 'kind': 'task_baseline_qualification_plan', 'protocol': build.PROTOCOL,
        'task_protocol': build.TASK_PROTOCOL, 'budget_policy': 'time_only_v1', 'budget_seconds': 3600,
        'case_ids': list(range(1, 21)), 'device': 0, 'physical_device': 2, 'operator': operator,
        'assembly_dir': str(assembly), 'preparation_ref': preparation_ref, 'roles': original['roles'],
        'source_hashes': original['source_hashes'], 'headers': headers,
        'source_review_ref': local.register_artifact(assembly / 'source-review.json'),
        'producer_refs': producer_refs, 'toolchain_refs': {str(cmake): local.register_artifact(cmake)},
        'job_ref': local.register_json({'timeout_seconds': 3600, 'fixture': 'CPU binding only'})}
    plan_ref = local.register_json(plan)
    commands = Commands(tmp_path / 'commands', assembly, operator, clock)
    return local, plan, plan_ref, commands, proof, clock


@pytest.mark.parametrize('operator', build.OPERATORS)
def test_original_roles_one_combined_build_and_readonly_replay(tmp_path, monkeypatch, operator):
    local, plan, plan_ref, commands, proof, clock = setup(tmp_path, monkeypatch, operator)
    receipt_ref = build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    count = local._sequence
    actual_proof, receipt = build.checked_baseline_build(local, plan_ref=plan_ref, build_receipt_ref=receipt_ref)
    assert count == local._sequence  # replay emits no new local records
    assert actual_proof == proof
    assert commands.calls == ['configure', 'build']
    assert receipt['binary']['path'] == str(commands.assembly / 'build' / operator)
    assert plan['source_hashes']['baseline'] == plan['source_hashes']['candidate']
    assert receipt['admission_authority'] is receipt['qualification_granted'] is False
    assert receipt['finished_at'] - receipt['started_at'] == 4
    attempt = json.loads((commands.assembly / 'build-attempt.json').read_text())
    assert not {'independent_review', 'route'} & attempt.keys()
    assert '--aprof-mechanism-role' in (commands.assembly / f'source/op_host/{operator}.asc').read_text()
    with pytest.raises(ValueError, match='no rebuild'):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    assert commands.calls == ['configure', 'build']


@pytest.mark.parametrize('changed', ['candidate', 'baseline', 'assembled', 'header'])
def test_changed_source_rejected_before_any_command(tmp_path, monkeypatch, changed):
    local, plan, plan_ref, commands, _, _ = setup(tmp_path, monkeypatch)
    if changed in build.ROLES:
        path = Path(plan['roles'][changed]['path']) / 'op_kernel/gelu_kernel.asc'
        path.write_bytes(path.read_bytes() + b'\n// changed original\n')
    elif changed == 'assembled':
        path = commands.assembly / 'source/op_host/gelu.asc'
        path.write_bytes(path.read_bytes() + b'\n// changed callback\n')
    else:
        plan['headers']['device_task_profile.h'] = plan['headers']['device_shared_timing.h']
        plan_ref = local.register_json(plan)
    with pytest.raises(ValueError):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    assert commands.calls == []


@pytest.mark.parametrize('stage', ['configure', 'build'])
def test_real_runner_failure_is_retained_and_not_retried(tmp_path, monkeypatch, stage):
    local, plan, plan_ref, commands, _, _ = setup(tmp_path, monkeypatch)
    commands.failure = stage
    with pytest.raises(ValueError, match='failed; no retry'):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    receipt = json.loads((commands.assembly / 'build-receipt.json').read_text())
    assert receipt['status'] == 'failed' and receipt['error']
    assert receipt['commands'][-1]['exit_status'] == -15
    assert receipt['commands'][-1]['error']['type'] == 'TimeoutError'
    previous = list(commands.calls)
    with pytest.raises(ValueError, match='no rebuild'):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    assert commands.calls == previous


def test_preparation_time_uses_original_shared_deadline(tmp_path, monkeypatch):
    local, plan, plan_ref, commands, _, clock = setup(tmp_path, monkeypatch)
    commands.deadline = clock.monotonic() + 10
    original = build._assembly
    def delayed(*args):
        result = original(*args)
        clock.elapsed += 11
        return result
    monkeypatch.setattr(build, '_assembly', delayed)
    with pytest.raises(TimeoutError):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    assert not commands.calls
    assert commands.deadline == 10010


def test_expired_after_build_does_not_produce_passed_receipt(tmp_path, monkeypatch):
    local, plan, plan_ref, commands, _, clock = setup(tmp_path, monkeypatch)
    commands.deadline = clock.monotonic() + 3
    with pytest.raises(TimeoutError):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    receipt = json.loads((commands.assembly / 'build-receipt.json').read_text())
    assert commands.calls == ['configure', 'build'] and receipt['status'] == 'failed'


@pytest.mark.parametrize('mutation', ['binary', 'stdout', 'execution', 'reorder', 'timeout', 'device'])
def test_replay_rejects_actual_evidence_or_receipt_tamper(tmp_path, monkeypatch, mutation):
    local, plan, plan_ref, commands, _, _ = setup(tmp_path, monkeypatch)
    reference = build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    path = commands.assembly / 'build-receipt.json'
    receipt = json.loads(path.read_text())
    if mutation == 'binary':
        Path(receipt['binary']['path']).write_bytes(b'changed executable')
    elif mutation == 'stdout':
        Path(receipt['commands'][0]['stdout']['path']).write_text('changed log')
    elif mutation == 'execution':
        Path(receipt['stages'][0]['execution_ref']['path']).write_text('{}')
    else:
        if mutation == 'reorder':
            receipt['stages'].reverse()
        elif mutation == 'timeout':
            receipt['finished_monotonic'] = receipt['deadline_monotonic'] + 1
        else:
            receipt['environment']['ASCEND_RT_VISIBLE_DEVICES'] = '3'
        path.write_text(json.dumps(receipt))
        reference = local.register_artifact(path)
    with pytest.raises((ValueError, StoreError)):
        build.checked_baseline_build(local, plan_ref=plan_ref, build_receipt_ref=reference)


@pytest.mark.parametrize('mutation', ['toolchain', 'producer', 'device', *build.CPU_REFERENCE_ENV])
def test_frozen_execution_identity_checked_before_build(tmp_path, monkeypatch, mutation):
    local, plan, plan_ref, commands, _, _ = setup(tmp_path, monkeypatch)
    if mutation == 'toolchain':
        Path(next(iter(plan['toolchain_refs']))).write_text('changed toolchain')
    elif mutation == 'producer':
        plan['producer_refs'].pop(str(Path(build.__file__).resolve()))
        plan_ref = local.register_json(plan)
    elif mutation == 'device':
        monkeypatch.setenv('ASCEND_RT_VISIBLE_DEVICES', '3')
    else:
        monkeypatch.setenv(mutation, '1')
    with pytest.raises((ValueError, StoreError)):
        build.build_baseline_once(local, plan_ref=plan_ref, commands=commands)
    assert not commands.calls
