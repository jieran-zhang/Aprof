"""CPU path/identity tests; tiny SDK files do not establish device qualification."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil
import sys
import platform
import venv
from types import SimpleNamespace

import pytest

from aprof_runtime import task_toolchain as tools
from aprof_runtime import full_call_pmu as pmu
from aprof_runtime.errors import ContractError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence

PACKAGE = Path(__file__).resolve().parents[2]
_REAL_PROBE = tools._python_environment
SCRIPTS = PACKAGE / 'skills/ascendc-aprof-profiling/scripts'


def put(path, data=b'tiny test file'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def installed(tmp_path, monkeypatch):
    sdk = tmp_path / 'another SDK 9.0.0'
    for name in tools.TASK_SDK_FILES + tools.PMU_SDK_FILES:
        put(sdk/name, name.encode())
    for name in ('tools/profiler/bin/msprof', 'tools/bisheng_compiler/bin/bisheng'):
        put(sdk/name, name.encode())
    put(sdk/'aarch64-linux/ascend_toolkit_install.info', b'version=9.0.0\narch=aarch64\n')
    # A tiny installed Python distribution exercises the real file/RECORD checks.
    site = tmp_path/'another site-packages'
    files = ['numpy/__init__.py', 'numpy/core.so', 'numpy-2.0.dist-info/METADATA', 'numpy-2.0.dist-info/RECORD']
    for name in files: put(site/name)
    put(site/files[2], b'Name: numpy\nVersion: 2.0\n')
    put(site/files[3], ''.join(name+',,\n' for name in files).encode())
    package = dict(version='2.0', files=sorted(str(site/name) for name in files),
        metadata=str(site/files[2]), record=str(site/files[3]), module=str(site/files[0]), root=str(site))
    monkeypatch.setattr(tools, '_python_environment', lambda python: dict(
        python_version=platform.python_version(), host_arch='aarch64', executable=python,
        runtime_files=[], numpy=package))
    monkeypatch.setattr(tools.platform, 'machine', lambda: 'aarch64')
    executables = {name: str(put(tmp_path/'bin'/name, name.encode())) for name in ('cmake', 'cxx', 'npu_smi')}
    return sdk, executables


def discover(installed):
    sdk, executable = installed
    return tools.discover_task_toolchain(sdk_root=sdk, **executable)


def collector():
    spec = importlib.util.spec_from_file_location('portable_task_window_collector', SCRIPTS/'device_task_window_timing.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def config(tmp_path, binding, module):
    roles = {}
    for role in ('baseline', 'candidate'):
        source = put(tmp_path/role/'kernel.cpp', role.encode()).parent
        roles[role] = dict(source_dir=str(source), symbol=role, launches_per_operator={'1': 1})
    native = tmp_path/'native'
    put(native/'op_host/device_task_profile.h', module.HEADER_ASSET.read_bytes())
    binary = put(tmp_path/'binary'); build_receipt = put(tmp_path/'build.json', b'{}')
    data = put(tmp_path/'input.bin', b'00')
    return dict(schema_version='1.0.0', operator='tiny', run_id='task', session_id='session', candidate_id='candidate',
        device=0, physical_device=0, expected_case_ids=[1], roles=roles,
        build=dict(source_dir=str(native), binary=str(binary), receipt_files=[str(build_receipt)]),
        cases=[dict(case_id=1, workload={'N':1}, prepared_files=[str(data)], command=[str(binary)],
            verify_commands={r:[str(Path(sys.executable).resolve()), '-c', 'pass'] for r in roles},
            output_files={r:['{cycle_dir}/'+r+'.bin'] for r in roles})],
        task_profile=dict(profiler=binding['tools']['profiler'], scratch_root=str(tmp_path/'scratch'),
            role_kernel_names={r:{'1':[r]} for r in roles}, toolchain=binding))


def test_actual_alternate_paths_config_export_and_pmu(tmp_path, installed):
    binding = discover(installed); module = collector()
    original = config(tmp_path, binding, module); frozen = deepcopy(original)
    accepted = module.config_value(original)
    assert original == frozen and accepted == original
    assert module.profile_dependencies(accepted) == binding['files']
    expected = [binding['tools']['python'], binding['sdk_files'][tools.ANALYSIS+'/msprof/msprof.py'],
                'export', 'summary', '-dir', str(tmp_path/'PROF_test'), '--format', 'csv']
    assert module.export_argv(accepted, tmp_path/'PROF_test') == expected
    command = [str(tmp_path/'binary'), 'argument with spaces']
    argv = pmu.capture_argv(command, tmp_path/'profile', toolchain=binding)
    assert argv[0] == binding['tools']['profiler']
    assert '--python-path='+binding['tools']['python'] in argv
    assert argv[2:-2] == list(pmu.FLAGS[:-1])
    assert pmu.capture_argv(command, '/old/profile')[0] == pmu.TOOL
    metric = {'vec':dict(unit='us',file='op_summary*.csv',format='csv',field='vec_time(us)',
                        row_aggregation='median',aggregation='median')}
    scope = pmu._scope(accepted, 1, metric)
    assert scope['warmups'] == 10 and scope['captures'] == 5
    assert scope['flags'] == list(pmu.profile_flags(binding))


def test_environment_discovery_resolves_sdk_alias(installed, tmp_path, monkeypatch):
    sdk, executable = installed
    alias = tmp_path/'sdk-current'; alias.symlink_to(sdk, target_is_directory=True)
    monkeypatch.setenv('ASCEND_HOME_PATH', str(alias))
    binding = tools.discover_task_toolchain(**executable)
    assert binding['sdk_root'] == str(sdk)
    assert binding['sdk_version'] == '9.0.0' and binding['python_packages']['numpy']['version'] == '2.0'


def test_replay_uses_retained_dependencies_after_sdk_removed(installed, tmp_path):
    binding = discover(installed); local = LocalEvidence(tmp_path/'retained')
    for original, ref in binding['files'].items():
        copy = put(tmp_path/'copies'/ref.removeprefix('sha256:'), Path(original).read_bytes())
        assert local.register_artifact(copy) == ref
    shutil.rmtree(installed[0])
    assert tools.validate_task_toolchain(binding, reader=local) == binding


@pytest.mark.parametrize('mutation', ['sdk_version','sdk_arch','python','missing_file','hash','numpy_version','numpy_roster'])
def test_changed_frozen_dependency_rejected(installed, tmp_path, mutation):
    binding = discover(installed)
    if mutation == 'sdk_version': binding['sdk_version'] = '9.1.0'
    if mutation == 'sdk_arch': binding['host_arch'] = 'x86_64'
    if mutation == 'python': binding['tools']['python'] = str(put(tmp_path/'other-python'))
    if mutation == 'missing_file': binding['files'].pop(next(iter(binding['files'])))
    if mutation == 'hash': Path(binding['tools']['profiler']).write_bytes(b'changed')
    if mutation == 'numpy_version': binding['python_packages']['numpy']['version'] = '99.0'
    if mutation == 'numpy_roster':
        package = binding['python_packages']['numpy']
        omitted = next(path for path in package['files'] if path.endswith('core.so'))
        package['files'].remove(omitted); binding['files'].pop(omitted)
    with pytest.raises((ContractError, OSError)):
        tools.validate_task_toolchain(binding, live=True)


def test_alias_retarget_rejected_even_when_bytes_match(installed):
    binding = discover(installed); original = Path(binding['tools']['profiler'])
    other = put(original.with_name('msprof-other'), original.read_bytes())
    original.unlink(); original.symlink_to(other)
    with pytest.raises(ContractError, match='alias changed'):
        tools.validate_task_toolchain(binding, live=True)


@pytest.mark.parametrize('failure', ['missing_numpy','unsupported_host','unsupported_sdk'])
def test_preparation_rejects_unavailable_or_unqualified_environment(installed, monkeypatch, failure):
    if failure == 'missing_numpy':
        def missing(name): raise ContractError('numpy not installed')
        monkeypatch.setattr(tools, '_python_environment', missing)
    elif failure == 'unsupported_host': monkeypatch.setattr(tools.platform, 'machine', lambda:'x86_64')
    else: put(installed[0]/'aarch64-linux/ascend_toolkit_install.info', b'version=8.5.0\narch=aarch64\n')
    with pytest.raises(ContractError): discover(installed)


def test_explicit_separate_python_is_preflighted_and_frozen(installed, tmp_path, monkeypatch):
    environment = tmp_path/'export-python'
    venv.EnvBuilder(system_site_packages=True, symlinks=False, with_pip=False).create(environment)
    python = environment/'bin/python'
    monkeypatch.setattr(tools, '_python_environment', _REAL_PROBE)
    binding = tools.discover_task_toolchain(sdk_root=installed[0], python=str(python), **installed[1])
    assert binding['tools']['python'] == str(python)
    assert binding['python_binary'] == str(python.resolve())
    assert str(environment/'pyvenv.cfg') in binding['files']
    assert binding['python_packages']['numpy']['version']
    assert tools.export_argv(binding, tmp_path/'profile')[0] == str(python)
    assert tools.validate_task_toolchain(binding, live=True) == binding


def test_ordinary_collection_requires_frozen_toolchain():
    module = collector()
    with pytest.raises(ValueError, match='frozen portable toolchain'):
        module.collect_local({'task_profile':{}}, '/unused', budget_binding={'kind':'task','launch_ref':'unused'})


@pytest.fixture
def budget_launch(tmp_path,monkeypatch):
    import time
    from aprof_runtime.task_budget import prepare_budget_plan,prepare_task_launch
    for suffix in ('LAUNCH_REF','LOCAL_INDEX','DEADLINE_MONOTONIC'):
        monkeypatch.delenv('APROF_TASK_'+suffix,raising=False)
    local=LocalEvidence(tmp_path/'budget-records')
    value={'run_id':'tiny-task','operator':'tiny','task_profile':{'toolchain':{'test_only_wiring':True}}}
    config_ref=local.register_json(value)
    scope=local.register_json({'stages':[{'inputs':{'command_config':config_ref}}]})
    budget=local.register_json(prepare_budget_plan(task_id='tiny-task',scope_ref=scope,budget_seconds=100))
    job=local.register_json({'timeout_seconds':100})
    mono=time.monotonic(); wall=time.time()
    launch=prepare_task_launch(local,budget_ref=budget,job_ref=job,started_at=wall-2,
        started_monotonic=mono-2,issued_monotonic=mono-1)
    reference=local.register_json(launch);index=local.write_index(tmp_path/'launch-index.json')
    return value,reference,index,launch['deadline_monotonic']


def test_collector_inherits_original_budget_and_main_passes_it(tmp_path,budget_launch,monkeypatch):
    import json
    value,reference,index,deadline=budget_launch
    module=collector()
    monkeypatch.setenv('APROF_TASK_LAUNCH_REF',reference)
    monkeypatch.setenv('APROF_TASK_LOCAL_INDEX',str(index))
    monkeypatch.setenv('APROF_TASK_DEADLINE_MONOTONIC',str(deadline))
    options=module._launch_arguments(value)
    assert options['deadline_monotonic']==deadline and 0<options['timeout_seconds']<100
    assert options['budget_binding']=={'kind':'task','launch_ref':reference}
    module._collection_budget(value,**options,started_at=module.time.time(),started_monotonic=module.time.monotonic())
    config_path=put(tmp_path/'config.json',json.dumps(value).encode())
    calls=[]
    def no_capture(config,output,**kwargs):
        calls.append((config,output,kwargs))
        return {'status':'passed'}  # Test only argument wiring; no measurement qualification.
    monkeypatch.setattr(module,'collect_local',no_capture)
    assert module.main(['--config',str(config_path),'--output',str(tmp_path/'work')])==0
    assert calls[0][0]==value and calls[0][2]['deadline_monotonic']==deadline
    assert calls[0][2]['budget_reader'].verify_artifact(reference).is_file()
    assert module.main(['--config',str(config_path)])==0
    assert calls[-1][1].is_relative_to(options['budget_reader'].directory.parent)


@pytest.mark.parametrize('conflict',['launch','index','deadline','partial_env','timeout','config'])
def test_collector_rejects_budget_override(tmp_path,budget_launch,monkeypatch,conflict):
    value,reference,index,deadline=budget_launch
    module=collector()
    for suffix,text in [('LAUNCH_REF',reference),('LOCAL_INDEX',str(index)),('DEADLINE_MONOTONIC',str(deadline))]:
        monkeypatch.setenv('APROF_TASK_'+suffix,text)
    kwargs={}
    if conflict=='launch':kwargs['budget_launch_ref']='sha256:'+'0'*64
    if conflict=='index':kwargs['local_index']=tmp_path/'other-index.json'
    if conflict=='deadline':kwargs['deadline_monotonic']=deadline+1
    if conflict=='partial_env':monkeypatch.delenv('APROF_TASK_LOCAL_INDEX')
    if conflict=='timeout':kwargs['timeout_seconds']=1
    if conflict=='config':value={**value,'operator':'changed'}
    with pytest.raises(ValueError):module._launch_arguments(value,**kwargs)


def test_collector_explicit_budget_uses_frozen_deadline(budget_launch):
    value,reference,index,deadline=budget_launch
    options=collector()._launch_arguments(value,local_index=index,budget_launch_ref=reference)
    assert options['deadline_monotonic']==deadline


def test_live_toolchain_rejects_different_host(installed,monkeypatch):
    binding=discover(installed)
    monkeypatch.setattr(tools.platform,'machine',lambda:'x86_64')
    with pytest.raises(ContractError,match='host architecture changed'):
        tools.validate_task_toolchain(binding,live=True)


def test_new_cli_does_not_silently_use_fixed_machine_paths(tmp_path,monkeypatch):
    import json
    module=collector()
    for suffix in ('LAUNCH_REF','LOCAL_INDEX','DEADLINE_MONOTONIC'):
        monkeypatch.delenv('APROF_TASK_'+suffix,raising=False)
    path=put(tmp_path/'legacy-config.json',json.dumps({'task_profile':{}}).encode())
    monkeypatch.setattr(module,'collect_local',lambda *a,**k: pytest.fail('capture must not start'))
    assert module.main(['--config',str(path),'--output',str(tmp_path/'work')])==2
    assert not (tmp_path/'work').exists()
