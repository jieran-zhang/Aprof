"""Discover once, then bind Task tools and SDK dependencies to immutable bytes."""
from __future__ import annotations

import os
import csv
import io
import posixpath
from email.parser import Parser
from pathlib import Path
import platform
import re
import shutil
import json
import subprocess
import sys

from .jsonio import file_hash
from .errors import ContractError


KIND = 'task_toolchain_v1'
ANALYSIS = 'tools/profiler/profiler_tool/analysis'
TASK_SDK_FILES = (
    'aarch64-linux/include/acl/acl_prof.h', 'aarch64-linux/lib64/libascendcl.so',
    'aarch64-linux/lib64/libmsprofiler.so', 'set_env.sh',
    *(ANALYSIS+'/'+name for name in (
        'msprof/msprof.py', 'msinterface/msprof_entrance.py', 'msinterface/msprof_export.py',
        'msinterface/msprof_output_summary.py', 'msinterface/msprof_data_storage.py',
        'framework/file_dispatch.py', 'framework/collection_engine.py', 'common_func/profiling_scene.py',
        'msinterface/msprof_c_interface.py', 'common_func/cpp_enable_scene.py', 'common_func/common.py',
        'common_func/path_manager.py', 'common_func/msprof_common.py', 'lib64/msprof_analysis.so')))
PMU_SDK_FILES = tuple(ANALYSIS+'/'+name for name in (
    'msconfig/msprof_export_data_config.py', 'msconfig/prof_header_mapping.json',
    'msconfig/filename_introduction_config.py', 'common_func/msvp_common.py',
    'common_func/platform/ai_core_metrics_manager.py', 'profiling_bean/struct_info/lpm_info_bean.py',
    'msparser/lpm_info/lpm_info_parser.py', 'msparser/data_struct_size_constant.py',
    'common_func/info_conf_reader.py', 'profiling_bean/basic_info/host_start.py',
    'mscalculate/stars/ffts_pmu_calculator.py'))
TOOL_NAMES = {'profiler', 'python', 'compiler', 'cmake', 'cxx', 'npu_smi'}


def _need(value, message):
    if not value: raise ContractError(message)


def _path(value):
    _need(isinstance(value, str), 'toolchain path must be text')
    path = Path(value)
    _need(path.is_absolute() and path.as_posix() == value and '..' not in path.parts,
          'toolchain path must be canonical absolute')
    return path


def _resolved(value):
    _need(value is not None, 'required Task tool was not found')
    path = Path(value).resolve(strict=True)
    _need(path.is_file(), 'Task dependency is not a file')
    return str(path)


def dependency_paths(binding, *, full_pmu=False):
    relative = TASK_SDK_FILES + (PMU_SDK_FILES if full_pmu else ())
    # Logical SDK names remain recorded even when an installation uses aliases.
    names = [binding['sdk_files'][name] for name in relative]
    names += [value for name,value in binding['tools'].items() if name != 'python']
    names += [binding['python_binary'], binding['install_info'], *binding['python_runtime_files']]
    names += binding['python_packages']['numpy']['files']
    return tuple(sorted(set(names)))


_PYTHON_PROBE = r"""
import importlib.metadata, json, pathlib, platform, sys
import numpy
D = importlib.metadata.distribution('numpy')
assert numpy.__version__ == D.version and D.files is not None
files = sorted({str(pathlib.Path(D.locate_file(name)).resolve(strict=True)) for name in D.files
                if str(name).rsplit('.', 1)[-1] != 'pyc'})
metadata = [name for name in files if name.endswith('.dist-info/METADATA')]
assert len(metadata) == 1
record = str(pathlib.Path(metadata[0]).with_name('RECORD'))
assert record in files
runtime = pathlib.Path(sys.prefix)/'pyvenv.cfg'
print(json.dumps(dict(python_version=platform.python_version(), host_arch=platform.machine(),
    executable=str(pathlib.Path(sys.executable).absolute()),
    runtime_files=[str(runtime.resolve(strict=True))] if runtime.is_file() else [],
    numpy=dict(version=D.version, metadata=metadata[0], record=record,
        root=str(pathlib.Path(D.locate_file('.')).resolve(strict=True)),
        module=str(pathlib.Path(numpy.__file__).resolve(strict=True)), files=files))))
"""


def _python_environment(python):
    try:
        result = subprocess.run([python, '-I', '-B', '-c', _PYTHON_PROBE], capture_output=True,
                                text=True, timeout=30, check=True)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise ContractError('Task export Python dependency preflight failed (requires importable numpy)') from error


def discover_task_toolchain(*, sdk_root=None, python=None, cmake=None, cxx=None, npu_smi=None):
    """Read paths/metadata only; never execute a compiler, profiler or device probe."""
    selected = sdk_root or os.environ.get('ASCEND_HOME_PATH')
    if selected is None:
        profiler = shutil.which('msprof')
        _need(profiler is not None, 'select sdk_root/ASCEND_HOME_PATH or put msprof on PATH')
        selected = Path(profiler).resolve(strict=True).parents[3]
    root = Path(selected).resolve(strict=True)
    _need(root.is_dir(), 'Task SDK root is not a directory')
    _need(platform.machine() == 'aarch64', 'Task toolchain supports only the existing aarch64 target')
    selected_python = str(Path(python or sys.executable).absolute())
    _path(selected_python)
    python_binary = _resolved(selected_python)
    environment = _python_environment(selected_python)
    _need(_resolved(environment['executable']) == python_binary and environment['host_arch'] == 'aarch64',
          'selected Task Python executable/architecture differs')
    tools = dict(profiler=_resolved(root/'tools/profiler/bin/msprof'), python=selected_python,
        compiler=_resolved(root/'tools/bisheng_compiler/bin/bisheng'),
        cmake=_resolved(cmake or shutil.which('cmake')), cxx=_resolved(cxx or shutil.which('c++')),
        npu_smi=_resolved(npu_smi or shutil.which('npu-smi')))
    info = root/(platform.machine()+'-linux')/'ascend_toolkit_install.info'
    metadata = dict(line.split('=', 1) for line in info.read_text().splitlines() if '=' in line)
    version = metadata.get('version') or metadata.get('Version')
    _need(version == '9.0.0' and metadata.get('arch') == 'aarch64',
          'Task toolchain supports only the existing CANN 9.0.0/aarch64 target')
    binding = dict(schema_version=1, kind=KIND, sdk_root=str(root), install_info=str(info),
        sdk_version=version.strip(), python_version=environment['python_version'], host_arch=platform.machine(),
        python_binary=python_binary, python_runtime_files=environment['runtime_files'],
        tools=tools, python_packages={'numpy': environment['numpy']}, sdk_files={name: _resolved(root/name) for name in TASK_SDK_FILES+PMU_SDK_FILES}, files={})
    binding['files'] = {name: file_hash(Path(name).resolve(strict=True))
                        for name in dependency_paths(binding, full_pmu=True)}
    validate_task_toolchain(binding, live=True)
    return binding


def validate_task_toolchain(binding, *, reader=None, live=False, digest=file_hash):
    """Replay only the registered roster; filesystem discovery never occurs here."""
    _need(isinstance(binding, dict) and set(binding) == {'schema_version', 'kind', 'sdk_root', 'install_info',
        'sdk_version', 'python_version', 'host_arch', 'tools', 'sdk_files', 'files', 'python_packages',
        'python_binary', 'python_runtime_files'}
        and binding['schema_version'] == 1 and binding['kind'] == KIND, 'Task toolchain schema differs')
    root = _path(binding['sdk_root']); tools = binding['tools']
    _need(isinstance(tools, dict) and set(tools) == TOOL_NAMES, 'Task executable roster differs')
    for name in tools.values(): _path(name)
    _path(binding['python_binary'])
    _need(isinstance(binding['python_runtime_files'], list)
          and len(binding['python_runtime_files']) <= 1, 'invalid Python runtime configuration')
    for path in binding['python_runtime_files']: _path(path)
    _need(_path(tools['profiler']).is_relative_to(root) and _path(tools['compiler']).is_relative_to(root),
          'Task compiler/profiler escaped its SDK')
    _need(isinstance(binding['sdk_files'], dict)
          and set(binding['sdk_files']) == set(TASK_SDK_FILES+PMU_SDK_FILES)
          and all(_path(path).is_relative_to(root) for path in binding['sdk_files'].values()),
          'Task SDK source roster escaped its installation')
    _need(binding['host_arch'] == 'aarch64'
          and binding['install_info'] == str(root/(binding['host_arch']+'-linux')/'ascend_toolkit_install.info')
          and binding['sdk_version'] == '9.0.0'
          and re.fullmatch(r'\d+\.\d+\.\d+', binding['python_version']), 'Task version binding differs')
    packages = binding['python_packages']
    _need(isinstance(packages, dict) and set(packages) == {'numpy'}, 'Task Python package roster differs')
    numpy = packages['numpy']
    _need(isinstance(numpy, dict) and set(numpy) == {'version', 'metadata', 'record', 'root', 'module', 'files'}
          and isinstance(numpy['version'], str) and bool(numpy['version'])
          and isinstance(numpy['files'], list) and numpy['files'] == sorted(set(numpy['files']))
          and numpy['metadata'] in numpy['files'] and numpy['module'] in numpy['files']
          and numpy['record'] in numpy['files'],
          'Task numpy identity differs')
    _path(numpy['root'])
    for path in numpy['files']: _path(path)
    files = binding['files']
    _need(isinstance(files, dict) and set(files) == set(dependency_paths(binding, full_pmu=True))
          and all(isinstance(ref, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', ref) for ref in files.values()),
          'Task dependency roster/hash differs')
    for name, ref in files.items():
        if reader is not None:
            reader.verify_artifact(ref)
        if live:
            path = _path(name)
            _need(path.is_file() and digest(path.resolve(strict=True)) == ref, 'frozen Task dependency changed')
    if reader is not None or live:
        path = reader.verify_artifact(files[binding['install_info']]) if reader else Path(binding['install_info'])
        metadata = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)
        _need(metadata.get('arch') == 'aarch64'
              and (metadata.get('version') or metadata.get('Version', '')).strip() == binding['sdk_version'],
              'SDK version differs from retained install metadata')
    if reader is not None or live:
        path = reader.verify_artifact(files[numpy['metadata']]) if reader else Path(numpy['metadata'])
        metadata = Parser().parsestr(path.read_text())
        _need(str(metadata['Name']).lower() == 'numpy' and metadata['Version'] == numpy['version'],
              'numpy version differs from retained metadata')
        path = reader.verify_artifact(files[numpy['record']]) if reader else Path(numpy['record'])
        rows = list(csv.reader(io.StringIO(path.read_text())))
        _need(rows and all(len(row) == 3 and row[0] and not row[0].startswith('/') for row in rows),
              'numpy installed file manifest differs')
        roster = sorted({posixpath.normpath(numpy['root']+'/'+row[0]) for row in rows
                         if row[0].rsplit('.', 1)[-1] != 'pyc'})
        _need(roster == numpy['files'], 'numpy dependency files differ from retained installed manifest')
    if live:
        _need(platform.machine() == binding['host_arch'], 'Task host architecture changed')
        _need(all(str((root/name).resolve(strict=True)) == path for name, path in binding['sdk_files'].items())
              and str((root/'tools/profiler/bin/msprof').resolve(strict=True)) == tools['profiler']
              and str((root/'tools/bisheng_compiler/bin/bisheng').resolve(strict=True)) == tools['compiler'],
              'frozen Task tool/SDK alias changed')
        _need(_resolved(tools['python']) == binding['python_binary'], 'frozen Task Python alias changed')
    return binding


def export_argv(binding, profile_root):
    validate_task_toolchain(binding)
    return [binding['tools']['python'], binding['sdk_files'][ANALYSIS+'/msprof/msprof.py'],
            'export', 'summary', '-dir', str(profile_root), '--format', 'csv']


def profile_tools(binding):
    validate_task_toolchain(binding)
    return dict(binding['tools'])
