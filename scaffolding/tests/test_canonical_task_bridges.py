"""Canonical imports and mechanical source proofs only; no CANN or hardware."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / 'scaffolding/collection/scripts'
RELEASE = REPO / 'skill-libs/graph-base/0.5.1'


def child(code, *args, release=RELEASE):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('APROF_SKILL_LIB', None)
    if release is not None:
        env['APROF_SKILL_LIB'] = str(release)
    program = 'import sys\nfrom pathlib import Path\nsys.path.insert(0, ' + repr(str(SCRIPTS)) + ')\n'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', program + textwrap.dedent(code), *map(str, args)],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_release_required():
    child('''
        try:
            import task_screen_bridge
        except ValueError as error:
            assert 'select a release' in str(error)
        else:
            raise AssertionError('implicit release selected')
    ''', release=None)


@pytest.mark.parametrize('version', ['0.5.0'])
def test_unmigrated_runtime_rejected(version):
    child('''
        try:
            import task_screen_bridge
        except ValueError as error:
            assert 'runtime 0.2.2' in str(error)
        else:
            raise AssertionError('old runtime accepted')
    ''', release=REPO / 'skill-libs/graph-base' / version)


@pytest.mark.parametrize('kind', ['runtime', 'submodule', 'profiler'])
def test_loaded_foreign_runtime_or_script_rejected(kind):
    child('''
        import types
        other = Path(sys.argv[1])
        kind = sys.argv[2]
        if kind == 'runtime':
            sys.path.insert(0, str(other / 'runtime/src'))
            import aprof_runtime
        elif kind == 'submodule':
            # This mixed submodule must be rejected before runtime imports consume it.
            module = types.ModuleType('aprof_runtime.jsonio')
            module.__file__ = str(other / 'runtime/src/aprof_runtime/jsonio.py')
            sys.modules[module.__name__] = module
        else:
            module = types.ModuleType('profile_capture')
            module.__file__ = str(other / 'skills/ascendc-aprof-profiling/scripts/profile_capture.py')
            sys.modules[module.__name__] = module
        try:
            import task_screen_bridge
        except ValueError as error:
            assert 'different release' in str(error)
        else:
            raise AssertionError('cross-release import accepted')
    ''', REPO / 'skill-libs/graph-base/0.5.0', kind)


@pytest.mark.parametrize('version', ['0.5.1', '1.0.0'])
def test_fresh_screen_entry_selects_canonical_modules_and_runtime(version):
    selected = REPO / 'skill-libs/graph-base' / version
    child(''' 
        import task_screen_bridge as screen
        import aprof_runtime
        assert screen.bridge.RELEASE == Path(sys.argv[1])
        assert Path(aprof_runtime.__file__).resolve().parent == Path(sys.argv[1]) / 'runtime/src/aprof_runtime'
        version = Path(sys.argv[1]).name
        assert aprof_runtime.__version__ == {'0.5.1': '0.2.2', '1.0.0': '0.2.3'}[version]
        assert screen.bridge.timing.PROTOCOL == 'shared_buffer_msprof_task_window_' + {'0.5.1': 'v4', '1.0.0': 'v5'}[version]
        assert Path(screen.rule.__file__).parent == Path(screen.__file__).parent
        assert screen.SCREEN_HEADER.is_file()
        assert screen.ENABLED_IN_1_0 is False
    ''', selected, release=selected)


def test_selected_release_cannot_switch_after_import():
    child('''
        import os
        import shared_validation_adapter as base
        os.environ['APROF_SKILL_LIB'] = sys.argv[1]
        try:
            base.selected_runtime()
        except ValueError as error:
            assert 'changed within' in str(error)
        else:
            raise AssertionError('release switched after binding')
    ''', REPO / 'skill-libs/graph-base/1.0.0')


@pytest.mark.parametrize('operator', ['dynamic_quant', 'gelu', 'group_norm'])
def test_shared_validation_source_and_complete_output_proof(tmp_path, operator):
    child('''
        import shared_mechanism_adapter as mechanism
        import local_controller_bridge as bridge
        base = mechanism.base
        op, root = sys.argv[1], Path(sys.argv[2])
        values = base.prepared_baseline(op)
        sources = {role: root / role for role in base.ROLES}
        for directory in sources.values():
            for name, data in values.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        expected = {role: base.inventory(values) for role in base.ROLES}
        headers = {name: (base.ASSETS / name).read_bytes() for name in base.HEADERS}
        trusted = base.inventory(headers)
        assembly = root / 'assembly'
        proof = mechanism.assemble(op, sources, assembly, expected_roles=expected, expected_headers=trusted)
        assert mechanism.source_identity(assembly) == proof
        original = base.generated(op, {role: values for role in base.ROLES}, headers)[f'op_host/{op}.asc'].decode()
        host = (assembly / 'source/op_host' / (op + '.asc')).read_text()
        begin = original.index('        task_profile.Start(')
        end = original.index('        task_profile.Finish();', begin) + len('        task_profile.Finish();')
        assert original[begin:end] in host
        assert proof['mechanism_entry']['calls'] == 1 and proof['mechanism_entry']['snapshot_all_outputs']
        assert bridge.ENABLED_IN_1_0 is False
        assert bridge.adapter is not mechanism
        if op == 'dynamic_quant':
            assert proof['output_keys'] == ['output_y', 'output_scale']
            for role in base.ROLES:
                assert role + '_output_y' in host and role + '_output_scale' in host
            assert '--output-scale' in (assembly / 'source/scripts/verify_result.py').read_text()
        (assembly / 'source/op_host' / (op + '.asc')).write_text(host + '\\n// unauthorized change\\n')
        try:
            mechanism.source_identity(assembly)
        except ValueError:
            pass
        else:
            raise AssertionError('changed generated source accepted')
    ''', operator, tmp_path)


@pytest.mark.parametrize('operator', ['exp', 'sigmoid'])
def test_frozen_rule_screen_is_private_and_formal_branch_unchanged(tmp_path, operator):
    child('''
        import shared_mechanism_adapter as validation
        import shared_rule_adapter as formal
        import task_screen_bridge as screen
        op, destination = sys.argv[1], Path(sys.argv[2]) / 'assembly'
        assert validation.OPERATORS == ('dynamic_quant', 'gelu', 'group_norm')
        assert formal.mechanism is not screen.rule.mechanism
        assert formal.bridge is not screen.bridge
        sources = {role: formal.ROUND / op / role for role in formal.ROLES}
        roles = {role: formal.source_tree(path) for role, path in sources.items()}
        expected = {role: formal.base.inventory(files) for role, files in roles.items()}
        headers = {name: (formal.base.ASSETS / name).read_bytes() for name in formal.HEADERS}
        original = formal.mechanism.generated(op, roles, headers)[f'op_host/{op}.asc'].decode()
        proof = screen.assemble(op, sources, destination, expected_roles=expected, expected_headers=formal.HEADERS)
        assert screen.source_identity(destination) == proof
        host = (destination / 'source/op_host' / (op + '.asc')).read_text()
        begin = original.index('        task_profile.Start(')
        end = original.index('        task_profile.Finish();', begin) + len('        task_profile.Finish();')
        assert original[begin:end] in host
        assert 'RunTaskScreen' not in original and 'RunTaskScreen' in host
        assert proof['screen_entry']['tasks_per_case'] == 1622
        assert proof['screen_entry']['formal_admission'] is False
        assert str(screen.SCREEN_HEADER) in proof['producer_files']
        assert screen.file_hash(destination / 'source/op_host/device_task_screen.h') == screen.file_hash(screen.SCREEN_HEADER)
        assert proof['historical_source_binding'] == formal.frozen_binding(op)
        assert screen.ENABLED_IN_1_0 is False
        assert screen.bridge.timing.PROTOCOL == 'shared_buffer_msprof_task_window_' + {'0.5.1': 'v4', '1.0.0': 'v5'}[screen.bridge.RELEASE.name]
        assert screen.bridge.RELEASE == formal.base.RELEASE
        for path in proof['producer_files']:
            assert '-design-' not in path
        (destination / 'source/op_host/device_task_screen.h').write_text('changed')
        try:
            screen.source_identity(destination)
        except ValueError:
            pass
        else:
            raise AssertionError('screen header tampering accepted')
    ''', operator, tmp_path)


def test_multikernel_scope_rejected():
    child('''
        import shared_validation_adapter as base
        for op in ('gqa', 'weight_quant_batch_matmul'):
            try:
                base.prepared_baseline(op)
            except ValueError as error:
                assert 'multi-kernel' in str(error)
            else:
                raise AssertionError('unsupported complete-call scope accepted')
    ''')


@pytest.mark.parametrize('corrupt', [False, True])
def test_real_screen_preregistration_indexes_package_producers_without_copy(tmp_path, corrupt):
    child('''
        import contextlib, json, time
        import task_screen_bridge as screen
        root, corrupt = Path(sys.argv[1]), sys.argv[2] == 'True'
        assembly = root / 'assembly'; assembly.mkdir()
        source = assembly / 'source'; source.mkdir()
        (source / 'host.py').write_text('fixture source')
        (assembly / 'source-review.json').write_text('{}')
        receipt = assembly / 'build-receipt.json'; receipt.write_text('{}')
        binary = assembly / 'binary'; binary.write_bytes(b'not executed')
        prepared = root / 'input.bin'; prepared.write_bytes(b'input')
        roles = {}
        for role in screen.ROLES:
            folder = root / role; folder.mkdir()
            (folder / 'kernel.py').write_text(role)
            roles[role] = {'source_dir': str(folder)}
        python = str(Path(sys.executable).resolve())
        config = {'operator': 'exp', 'roles': roles,
            'build': {'source_dir': str(source), 'binary': str(binary), 'receipt_files': [str(receipt)]},
            'cases': [{'case_id': cid, 'workload': {'fixture': cid}, 'prepared_files': [str(prepared)],
                       'verify_commands': {r: [python] for r in screen.ROLES}} for cid in screen.CASES['exp']]}
        paths = [str(receipt), str(binary), str(prepared), python]
        producer_name = 'runtime/src/aprof_runtime/local_evidence.py'
        producer = screen.timing.RELEASE / producer_name
        actual = screen.file_hash(producer)
        frozen = {'files': {p: screen.file_hash(p) for p in paths},
                  'producer_files': {producer_name: 'sha256:' + '0' * 64 if corrupt else actual}}
        proof = {'operator': 'exp', 'producer_files': {}}
        screen.checked_build = lambda *a: (proof, {'binary': {'path': str(binary)}})
        screen.rule.task_config = lambda *a, **kw: config
        screen.timing.inventory = lambda *a, **kw: frozen
        screen.timing.create_profile_storage = lambda scratch, output, local, **kw: local.register_json({'fixture': True})
        entered = []
        @contextlib.contextmanager
        def stop_before_hardware(*args):
            entered.append(True)
            raise RuntimeError('CPU test stops before hardware')
            yield
        screen.timing.shared.device_lock = stop_before_hardware
        result = screen.collect_screen(assembly, receipt, root, root / 'output',
            physical_device=0, deadline=time.monotonic() + 30)
        assert result['status'] == 'failed' and result['gate_projection'] == {}
        local = screen.LocalEvidence.from_index(result['local_index'])
        report = json.loads(local.verify_artifact(result['report_ref']).read_text())
        if corrupt:
            assert not entered and report['registration_ref'] is None
            assert report['error']['message'] == 'screen package producer changed'
        else:
            assert entered and report['registration_ref']
            registration = json.loads(local.verify_artifact(report['registration_ref']).read_text())
            assert registration['inventory']['producer_files'] == {producer_name: actual}
            assert local.verify_artifact(actual) == producer.resolve()
            index = json.loads(Path(result['local_index']).read_text())
            assert index['artifacts'][actual] == str(producer.resolve())
            assert report['error']['message'] == 'CPU test stops before hardware'
    ''', tmp_path, corrupt)
