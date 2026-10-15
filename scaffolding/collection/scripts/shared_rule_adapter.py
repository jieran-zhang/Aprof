"""Frozen exp/sigmoid mechanical assembly; no automatic build or admission."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = REPO.parent
ROUND = ROOT / 'validation-graph-base-1.0.0-round2-20261014'
OPERATORS = ('exp', 'sigmoid')
ROLES = ('baseline', 'candidate')
FROZEN = {'exp': 'dea6e4e4cb095c10dd396bccd11713b6c8877673183c078ce92a9e7c4cea53f9',
          'sigmoid': 'a87d2492882e9a4c4626ef599c145859cfaf97b288ff79ac1cab62d54897735f'}
HEADERS = {'device_shared_timing.h': 'sha256:86ff5f27ebc52a4be4798a4ee271305f873f3da994471634096ca9b1c88815ed',
           'device_task_profile.h': 'sha256:6a01558694758bfce2d7bb41274ee2c51e810dcd5d39df980d4278d97057b47c'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# These are private module instances. Existing drafts and canonical imports are
# not mutated; their source/identity machinery is reused with two fixed branches.
base = load('rule_base', HERE / 'shared_validation_adapter.py')
mechanism = load('rule_mechanism', HERE / 'shared_mechanism_adapter.py')
qualification = load('rule_output_routing', REPO / 'scaffolding/collection/scripts/qualify_shared_timing_v051.py')
original_includes, original_check, original_proof = base.role_includes, base.checked_roles, base.assembly_proof
original_identity = mechanism.source_identity


def source_tree(root):
    """Same source exclusions as historical bundles; no build/profile copying."""
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('source root contains a symlink')
    files = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(n for n in dirs if n not in {'.git', '.aprof', 'build', '__pycache__', '.pytest_cache'})
        for name in dirs + names:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError('source contains a symlink')
        for name in sorted(names):
            path = Path(directory) / name
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('source contains a nonregular file')
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def frozen_binding(operator):
    if operator not in OPERATORS:
        raise ValueError('only the frozen exp/sigmoid rules are supported')
    freeze = ROUND / operator / 'frozen-round.json'
    if base.digest(freeze.read_bytes()) != 'sha256:' + FROZEN[operator]:
        raise ValueError('historical source freeze changed')
    value = json.loads(freeze.read_text())
    bindings = {}
    for role in ROLES:
        bundle = ROUND / operator / 'source-bundles' / role / 'source-bundle.json'
        reference = base.digest(bundle.read_bytes())
        if reference != value['source_hashes'][role]:
            raise ValueError('historical source bundle changed')
        bindings[role] = {'path': str(bundle), 'sha256': reference,
                          'files': json.loads(bundle.read_text())['files']}
    return {'freeze': {'path': str(freeze), 'sha256': 'sha256:' + FROZEN[operator]}, 'roles': bindings}


def prepared_baseline(operator):
    values = source_tree(ROUND / operator / 'baseline')
    if base.inventory(values) != frozen_binding(operator)['roles']['baseline']['files']:
        raise ValueError('frozen baseline bytes changed')
    return values


def checked_roles(operator, sources, expected):
    values = original_check(operator, sources, expected)
    binding = frozen_binding(operator)
    for role in ROLES:
        if base.inventory(values[role]) != binding['roles'][role]['files']:
            raise ValueError('source differs from the frozen rule: ' + role)
    return values


def role_includes(operator):
    return '#include <cmath>\n#include <cstring>\n' + original_includes(operator)


def adapt_host(operator):
    text = qualification.adapt_host(prepared_baseline(operator)[f'op_host/{operator}.asc'].decode(), operator)
    text = base.exact(text, '// A/A method qualification: both named callbacks invoke the unchanged baseline kernel.',
                      '// Frozen baseline and candidate share IO with independent kernels and tiling.')
    text = base.exact(text, f'#include "{operator}_tiling.h"', role_includes(operator))
    text = base.exact(text, f'#include "../op_kernel/{operator}_kernel.asc"', '#include "device_task_profile.h"')
    text = base.exact(text, '*devTiling = nullptr;', '*devTiling = nullptr, *candidate_tiling_device = nullptr;')
    function, args = ('ComputeExpTiling', 'n, dtype, cores, base, scale, shift') if operator == 'exp' else ('ComputeSigmoidTiling', 'n, dtype, cores')
    compute = f'const auto tiling = {function}({args});'
    guard = 'tiling.totalLength != candidate_tiling.totalLength || tiling.dtype != candidate_tiling.dtype'
    if operator == 'exp':
        guard += ' || std::memcmp(&tiling.multiplier, &candidate_tiling.multiplier, sizeof(float)) != 0 || std::memcmp(&tiling.shift, &candidate_tiling.shift, sizeof(float)) != 0'
    text = base.exact(text, compute, compute + f'\n        const auto candidate_tiling = aprof_candidate::{function}({args});\n        if ({guard}) throw std::invalid_argument("role tiling changed logical IO/attrs");')
    init = 'Check(aclInit(nullptr), "aclInit");'
    text = base.exact(text, init, init + '\n        aprof::TaskProfile task_profile;')
    allocation = 'Check(aclrtMalloc(&devTiling, sizeof(tiling), ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc tiling");'
    text = base.exact(text, allocation, allocation + '\n        Check(aclrtMalloc(&candidate_tiling_device, sizeof(candidate_tiling), ACL_MEM_MALLOC_HUGE_FIRST), "candidate tiling allocation");')
    upload = 'Check(aclrtMemcpy(devTiling, sizeof(tiling), &tiling, sizeof(tiling), ACL_MEMCPY_HOST_TO_DEVICE), "H2D tiling");'
    text = base.exact(text, upload, upload + '\n        Check(aclrtMemcpy(candidate_tiling_device, sizeof(candidate_tiling), &candidate_tiling, sizeof(candidate_tiling), ACL_MEMCPY_HOST_TO_DEVICE), "candidate tiling upload");')
    text = base.exact(text, '{"tiling", devTiling, sizeof(tiling)}', '{"baseline_tiling", devTiling, sizeof(tiling)}, {"candidate_tiling", candidate_tiling_device, sizeof(candidate_tiling)}')
    for role in ROLES:
        begin = text.index(f'        auto launch_{role} =')
        end = text.index('        };', begin) + len('        };')
        body = text[begin:end].replace(f'{operator}_kernel<<<', f'aprof_{role}::aprof_{role}_{operator}_kernel<<<')
        if role == 'candidate':
            body = body.replace('tiling.blockNum', 'candidate_tiling.blockNum').replace('shared.inputs[1]', 'shared.inputs[2]')
        text = text[:begin] + body + text[end:]
    run = f'        aprof::RunShared(stream, "{operator}", cycle_text[0] - \'0\', 1, 1, buffers,\n                         {{"launch_baseline", "launch_candidate"}}, launch_baseline, launch_candidate, snapshot);'
    text = base.exact(text, run, '        task_profile.Start(static_cast<uint32_t>(device));\n' + run + '\n        task_profile.Finish();')
    # The independent callback snapshot already synchronized and wrote each role.
    tail = '''        Check(aclrtSynchronizeStream(stream), "kernel synchronize");
        Check(aclrtMemcpy(hostOut, bytes, devOut, bytes, ACL_MEMCPY_DEVICE_TO_HOST), "D2H output");
        if (!WriteFile(Arg(argc, argv, "--output"), hostOut, bytes)) throw std::runtime_error("write output failed");
'''
    text = base.exact(text, tail, '')
    if text.count('aclrtFree(devTiling);') != 2:
        raise ValueError('unexpected cleanup topology')
    return text.replace('aclrtFree(devTiling);', 'aclrtFree(devTiling); if (candidate_tiling_device) aclrtFree(candidate_tiling_device);')


def assembly_proof(operator, sources, destination, roles, files, expected_roles, expected_headers):
    proof = original_proof(operator, sources, destination, roles, files, expected_roles, expected_headers)
    proof['purpose'] = 'draft_frozen_rule_shared_assembly'
    proof['historical_source_binding'] = frozen_binding(operator)
    proof['producer_files'].update({str(Path(__file__).resolve()): base.digest(Path(__file__).read_bytes()),
                                    str(Path(qualification.__file__)): base.digest(Path(qualification.__file__).read_bytes())})
    proof['limitations'] = ['CPU assembly proof only; independent review and new hardware admission still required',
                            'exact frozen exp/sigmoid rules only; one combined trusted build',
                            'historical failures remain failures; no controller/runtime/default activation']
    return proof


base.OPERATORS = OPERATORS
base.tree = source_tree
base.prepared_baseline = prepared_baseline
base.checked_roles = checked_roles
base.role_includes = role_includes
base.adapt_host = adapt_host
base.adapt_oracle = qualification.adapt_oracle
base.assembly_proof = assembly_proof
mechanism.base = base
mechanism.OPERATORS = OPERATORS


def assemble(operator, sources, destination, *, expected_roles, expected_headers):
    if expected_headers != HEADERS:
        raise ValueError('frozen 0.5.1 header identity differs')
    proof = mechanism.assemble(operator, sources, destination, expected_roles=expected_roles, expected_headers=expected_headers)
    source_identity(destination)
    return proof


def source_identity(destination):
    proof = original_identity(destination)
    if proof['trusted_headers'] != HEADERS:
        raise ValueError('frozen 0.5.1 header identity differs')
    return proof


# Reuse the existing source-bound, review-gated exclusive build implementation.
# Loading this module does not run configure/build or invoke a model.
bridge = load('rule_controller_bridge', HERE / 'local_controller_bridge.py')
mechanism.source_identity = source_identity
bridge.adapter = mechanism
build_once, checked_build = bridge.build_once, bridge.checked_build
task_config = bridge.task_config
ENABLED_IN_1_0 = False
