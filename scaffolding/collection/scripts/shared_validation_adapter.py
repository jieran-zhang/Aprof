"""Mechanically assemble one shared-buffer validation binary; no dispatch activation.

Inputs are the existing adapter's prepared baseline/candidate trees. Only the
candidate kernel and tiling file may differ. This produces source, never builds,
runs hardware, or grants measurement/publication admission.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat

import sys
from aprof_layout import skill_lib

REPO = Path(__file__).resolve().parents[3]
RELEASE = skill_lib()


def selected_runtime():
    """Bind this process to one explicitly selected release before any imports."""
    if skill_lib() != RELEASE:
        raise ValueError('selected release changed within this process')
    runtime = RELEASE / 'runtime/src/aprof_runtime'
    scripts = RELEASE / 'skills/ascendc-aprof-profiling/scripts'
    script_paths = {path.stem: path for path in scripts.glob('*.py')}

    def check_loaded():
        for name, module in tuple(sys.modules.items()):
            if name == 'aprof_runtime' or name.startswith('aprof_runtime.'):
                source = getattr(module, '__file__', None)
                if not source or not Path(source).resolve().is_relative_to(runtime):
                    raise ValueError('a different release runtime is already loaded: ' + name)
            elif name in script_paths:
                source = getattr(module, '__file__', None)
                if not source or Path(source).resolve() != script_paths[name]:
                    raise ValueError('a different release profiling script is already loaded: ' + name)

    check_loaded()
    sys.path.insert(0, str(runtime.parent))
    import aprof_runtime
    check_loaded()
    expected_version = {'0.5.1': '0.2.2', '1.0.0': '0.2.3', '1.0.1': '0.2.4'}.get(RELEASE.name)
    if expected_version is None or aprof_runtime.__version__ != expected_version:
        raise ValueError('shared local Task bridge release/runtime binding is unsupported or mismatched')
    return RELEASE


selected_runtime()
OPERATORS = ('dynamic_quant', 'gelu', 'group_norm')
ROLES = ('baseline', 'candidate')
ASSETS = RELEASE / 'skills/ascendc-aprof-profiling/assets'
HEADERS = ('device_shared_timing.h', 'device_task_profile.h')
OLD_PATH = REPO / 'scaffolding/collection/scripts/validation_operator_adapter.py'
# Import only the existing CPU preparation/command helper, not any controller.
sys.path.insert(0, str(OLD_PATH.parent))
spec = importlib.util.spec_from_file_location('validation_adapter_original', OLD_PATH)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def tree(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('source root contains a symlink')
    values = {}
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('source contains a nonregular file')
        values[path.relative_to(root).as_posix()] = path.read_bytes()
    return values


def inventory(values):
    return {name: digest(data) for name, data in values.items()}


def exact(text, before, after):
    if text.count(before) != 1:
        raise ValueError('mechanical anchor changed: ' + before[:70])
    return text.replace(before, after, 1)


def prepared_baseline(operator):
    if operator not in OPERATORS:
        raise ValueError('only dynamic_quant, gelu, group_norm are supported; GQA/WQ are multi-kernel')
    source = REPO / 'scaffolding/benchmarks/cannbench/operators' / operator
    values = {name: data for name, data in tree(source).items()
              if name == 'CMakeLists.txt' or name.split('/')[0] in ('op_host', 'op_kernel', 'scripts')}
    # The original adapter excludes Python caches; they are not source inputs.
    values = {n: b for n, b in values.items() if '__pycache__' not in Path(n).parts and not n.endswith('.pyc')}
    host = f'op_host/{operator}.asc'
    values[host] = old.instrument_text(values[host].decode(), operator).encode()
    values['op_host/aprof_device_timer.h'] = old.HEADER.read_bytes()
    return values


def checked_roles(operator, sources, expected):
    baseline = prepared_baseline(operator)
    values = {role: tree(sources[role]) for role in ROLES}
    if set(sources) != set(ROLES) or set(expected) != set(ROLES):
        raise ValueError('two independently bound source roles are required')
    for role in ROLES:
        if inventory(values[role]) != expected[role]:
            raise ValueError('role source inventory changed: ' + role)
    if values['baseline'] != baseline or set(values['candidate']) != set(baseline):
        raise ValueError('baseline or candidate source roster differs from frozen preparation')
    mutable = {f'op_kernel/{operator}_kernel.asc', f'op_kernel/{operator}_tiling.h'}
    directives = lambda text: re.findall(r'^\s*#.*$', text, re.M)
    for name, before in baseline.items():
        after = values['candidate'][name]
        if name not in mutable and before != after:
            raise ValueError('candidate changed protected host/build/oracle/input producer: ' + name)
        if name in mutable:
            a, b = before.decode(), after.decode()
            if directives(a) != directives(b):
                raise ValueError('candidate changed include/preprocessor topology')
            for token in ('<<<', 'aclrt', 'aclInit', 'aclFinalize', 'aprof::', 'extern "C"'):
                if a.count(token) != b.count(token):
                    raise ValueError('candidate introduced launch/runtime/export structure')
    return values


def role_includes(operator):
    # Include SDK/std outside role namespaces; every original custom header stays
    # at a role-local compiled copies with pragma once removed; originals remain exact.
    text = '#include <algorithm>\n#include <cstdint>\n#include <stdexcept>\n#include <vector>\n#include <type_traits>\n#include "kernel_operator.h"\n'
    for role in ROLES:
        text += (f'namespace aprof_{role} {{\n'
                 f'#define {operator}_kernel aprof_{role}_{operator}_kernel\n'
                 f'#include "../compiled/{role}/{operator}_kernel.asc"\n'
                 f'#undef {operator}_kernel\n}}\n')
    return text + 'using namespace aprof_baseline;\n'


def shared_block(operator, launch, snapshot):
    gn = operator == 'group_norm'
    stream, device, arg = ('st', 'dev', 'A(ac,av,') if gn else ('stream', 'device', 'Arg(argc, argv, ')
    if operator == 'gelu':
        inputs, outputs = [('input', 'devIn', 'bytes')], [('output', 'devOut', 'bytes')]
        tiling, pointer = 'tiling', 'devTiling'
    elif operator == 'dynamic_quant':
        inputs = [('input', 'devX', 'xBytes')]
        outputs = [('output_y', 'devY', 'yBytes'), ('output_scale', 'devScale', 'scaleBytes')]
        tiling, pointer = 'tiling', 'devTiling'
    else:
        inputs = [('x', 'dx', 'xb'), ('gamma', 'dg', 'pb'), ('beta', 'db', 'pb')]
        outputs, tiling, pointer = [('output', 'dy', 'xb')], 't', 'dt'
    shared_inputs = inputs + [('baseline_tiling', pointer, f'sizeof({tiling})'),
                              ('candidate_tiling', 'candidate_tiling_device', 'sizeof(candidate_tiling)')]
    spans = lambda items: '{' + ', '.join('{"%s", %s, %s}' % item for item in items) + '}'
    text = '''
        const char *cycle_text = std::getenv("APROF_SHARED_CYCLE");
        if (!cycle_text || std::string(cycle_text).size() != 1 || cycle_text[0] < '0' || cycle_text[0] > '5')
            throw std::invalid_argument("APROF_SHARED_CYCLE must be 0..5");
'''
    paths = []
    for role in ROLES:
        for name, _, _ in outputs:
            variable = role + '_' + name
            paths.append(variable)
            text += f'        const std::string {variable} = {arg}"--{role}-{name.replace("_", "-")}");\n'
    text += '        const std::vector<std::string> role_paths{' + ', '.join(paths) + '};\n'
    text += '''        for (size_t i = 0; i < role_paths.size(); ++i) {
            if (role_paths[i].empty()) throw std::invalid_argument("missing role output path");
            for (size_t j = 0; j < i; ++j)
                if (role_paths[i] == role_paths[j]) throw std::invalid_argument("role output paths must differ");
        }
'''
    text += f'        const aprof::SharedBuffers buffers{{{spans(shared_inputs)}, {spans(outputs)}, {{}}}};\n'
    for role in ROLES:
        body = launch
        body = re.sub(r'\b' + operator + r'_kernel\b', f'aprof_{role}::aprof_{role}_{operator}_kernel', body)
        body = re.sub(r'\b' + stream + r'\b', 'selected_stream', body)
        body = re.sub(r'\b' + tiling + r'\b', tiling if role == 'baseline' else 'candidate_tiling', body)
        for index, (_, variable, _) in enumerate(inputs):
            body = re.sub(r'\b' + variable + r'\b', f'shared.inputs[{index}].data', body)
        for index, (_, variable, _) in enumerate(outputs):
            body = re.sub(r'\b' + variable + r'\b', f'shared.outputs[{index}].data', body)
        body = re.sub(r'\b' + pointer + r'\b', f'shared.inputs[{len(inputs) + (role == "candidate")}].data', body)
        text += f'        auto launch_{role} = [&](aclrtStream selected_stream, const aprof::SharedBuffers &shared) {{\n{body}\n        }};\n'
    text += '        auto snapshot = [&](const char *role, aclrtStream, const aprof::SharedBuffers &shared) {\n'
    for name, variable, _ in outputs:
        index = next(i for i, item in enumerate(outputs) if item[0] == name)
        snapshot = re.sub(r'\b' + variable + r'\b', f'shared.outputs[{index}].data', snapshot)
        flag = {'output': 'output', 'output_y': 'y', 'output_scale': 'scale'}[name]
        snapshot = exact(snapshot, f'{arg}"--{flag}")',
                         f'(std::string(role) == "baseline" ? baseline_{name} : candidate_{name})')
    text += snapshot + '\n        };\n'
    text += f'        task_profile.Start(static_cast<uint32_t>({device}));\n'
    text += f'        aprof::RunShared({stream}, "{operator}", cycle_text[0] - \'0\', 1, 1, buffers,\n'
    text += '            {"launch_baseline", "launch_candidate"}, launch_baseline, launch_candidate, snapshot);\n'
    return text + '        task_profile.Finish();\n'


def adapt_host(operator):
    original = (REPO / 'scaffolding/benchmarks/cannbench/operators' / operator / 'op_host' / f'{operator}.asc').read_text()
    text = exact(original, f'#include "{operator}_tiling.h"', role_includes(operator))
    text = exact(text, f'#include "../op_kernel/{operator}_kernel.asc"',
                 '#include "device_shared_timing.h"\n#include "device_task_profile.h"')
    gn = operator == 'group_norm'
    tiling, pointer = ('t', 'dt') if gn else ('tiling', 'devTiling')
    declaration = '*dt=nullptr;' if gn else '*devTiling = nullptr;'
    text = exact(text, declaration, declaration[:-1] + ', *candidate_tiling_device=nullptr;')
    if gn:
        compute = 'auto t=ComputeGroupNormTiling(sh,std::stoul(A(ac,av,"--groups")),d,std::stof(A(ac,av,"--epsilon")));'
        fields = ('totalLength', 'spatial', 'groupElements', 'groupCount', 'N', 'C', 'numGroups', 'channelsPerGroup', 'dtype', 'epsilon')
        init = 'C(aclInit(nullptr),"init");ai=true;'
        allocation = 'C(aclrtMalloc(&dt,sizeof(t),ACL_MEM_MALLOC_HUGE_FIRST),"dt");'
        upload = 'C(aclrtMemcpy(dt,sizeof(t),&t,sizeof(t),ACL_MEMCPY_HOST_TO_DEVICE),"t");'
        check = 'C'
    else:
        function, args = ('ComputeGeluTiling', 'n, dtype, mode, cores') if operator == 'gelu' else ('ComputeDynamicQuantTiling', 'shape, dtype, cores')
        compute = f'const auto tiling = {function}({args});'
        fields = ('totalLength', 'dtype', 'mode') if operator == 'gelu' else ('tokenCount', 'rowLength', 'dtype')
        init = 'Check(aclInit(nullptr), "aclInit");'
        allocation = 'Check(aclrtMalloc(&devTiling, sizeof(tiling), ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc tiling");'
        upload = 'Check(aclrtMemcpy(devTiling, sizeof(tiling), &tiling, sizeof(tiling), ACL_MEMCPY_HOST_TO_DEVICE), "H2D tiling");'
        check = 'Check'
    candidate_compute = re.sub(r'\b' + tiling + r'\b', 'candidate_tiling', compute)
    candidate_compute = candidate_compute.replace('Compute', 'aprof_candidate::Compute', 1)
    guard = ' || '.join(f'{tiling}.{f} != candidate_tiling.{f}' for f in fields)
    text = exact(text, compute, compute + '\n' + candidate_compute + f'\nif ({guard}) throw std::invalid_argument("role tiling changed logical IO/attrs");\n')
    text = exact(text, init, init + '\naprof::TaskProfile task_profile;\n')
    text = exact(text, allocation, allocation + f'\n{check}(aclrtMalloc(&candidate_tiling_device,sizeof(candidate_tiling),ACL_MEM_MALLOC_HUGE_FIRST),"candidate tiling allocation");\n')
    text = exact(text, upload, upload + f'\n{check}(aclrtMemcpy(candidate_tiling_device,sizeof(candidate_tiling),&candidate_tiling,sizeof(candidate_tiling),ACL_MEMCPY_HOST_TO_DEVICE),"candidate tiling upload");\n')
    start, finish, _, _, _ = old.WRAPPERS[operator]
    first, last = text.index(start), text.index(finish)
    launch = text[first:last].strip()
    tail = text[last + len(finish):]
    # The old final sync moves to RunShared's trusted event/snapshot boundaries;
    # these single-kernel calls contain no inter-stage work or synchronization.
    snapshot_start = tail.index('C(aclrtMemcpy' if gn else '        Check(aclrtMemcpy')
    snapshot_end = tail.index('std::cout' if gn else ('        const double ms' if operator == 'dynamic_quant' else '        std::cout'))
    snapshot = tail[snapshot_start:snapshot_end]
    # DQ's original host wall-clock start/stop remain outside RunShared; only Task
    # duration from the frozen header's complete calls can become a metric.
    intervening = tail[:snapshot_start]
    text = text[:first] + shared_block(operator, launch, snapshot) + intervening + tail[snapshot_end:]
    free = f'aclrtFree({pointer});'
    if text.count(free) != 2:
        raise ValueError('unexpected tiling cleanup topology')
    return text.replace(free, free + ' if(candidate_tiling_device) aclrtFree(candidate_tiling_device);')


def adapt_oracle(text, operator):
    if operator == 'dynamic_quant':
        text = exact(text, '    parser.add_argument("--metadata", required=True)',
                     '    parser.add_argument("--metadata", required=True)\n    parser.add_argument("--output-y", required=True)\n    parser.add_argument("--output-scale", required=True)\n    parser.add_argument("--result", required=True)')
        text = exact(text, 'np.fromfile(metadata["output_y"],', 'np.fromfile(args.output_y,')
        text = exact(text, 'np.fromfile(metadata["output_scale"],', 'np.fromfile(args.output_scale,')
        return exact(text, '(metadata_path.parent / "result.json").write_text', 'Path(args.result).write_text')
    anchor = "p.add_argument('--metadata',required=True);"
    text = exact(text, anchor, anchor + "p.add_argument('--output',required=True);p.add_argument('--result',required=True);")
    text = exact(text, "open(m['output'],'rb')" if operator == 'gelu' else "l(m['output'],", "open(a.output,'rb')" if operator == 'gelu' else 'l(a.output,')
    return exact(text, "(mp.parent/'result.json').write_text", 'Path(a.result).write_text')


def generated(operator, roles, headers):
    files = dict(roles['baseline'])
    files[f'op_host/{operator}.asc'] = adapt_host(operator).encode()
    cmake = files['CMakeLists.txt'].decode()
    files['CMakeLists.txt'] = exact(cmake, 'ascendcl ascendc_runtime)', 'ascendcl ascendc_runtime msprofiler)').encode()
    oracle = 'scripts/verify_result.py'
    files[oracle] = adapt_oracle(files[oracle].decode(), operator).encode()
    for role in ROLES:
        files.update({f'roles/{role}/{name}': data for name, data in roles[role].items()})
    for role in ROLES:
        for leaf in (f'{operator}_kernel.asc', f'{operator}_tiling.h'):
            original = roles[role]['op_kernel/' + leaf].decode()
            files[f'compiled/{role}/{leaf}'] = exact(original, '#pragma once\n', '').encode()
    files.update({f'op_host/{name}': data for name, data in headers.items()})
    return files


def case_command(operator, binary, metadata, device, role_outputs):
    """Existing mathematical argv, with only output routing replaced."""
    if operator not in OPERATORS:
        raise ValueError('unsupported multi-kernel scope')
    keys = ('output_y', 'output_scale') if operator == 'dynamic_quant' else ('output',)
    if set(role_outputs) != set(ROLES) or any(set(role_outputs[r]) != set(keys) for r in ROLES):
        raise ValueError('both roles require every complete-call output')
    paths = [str(role_outputs[r][k]) for r in ROLES for k in keys]
    if len(set(paths)) != len(paths) or any(not Path(p).is_absolute() for p in paths):
        raise ValueError('distinct absolute role output paths required')
    argv = old.case_command(operator, binary, metadata, device, role_outputs['baseline'])
    output_flags = {'--y', '--scale'} if operator == 'dynamic_quant' else {'--output'}
    result = [argv[0]]
    for index in range(1, len(argv), 2):
        if argv[index] not in output_flags:
            result.extend(argv[index:index + 2])
    for role in ROLES:
        for key in keys:
            result += ['--' + role + '-' + key.replace('_', '-'), str(role_outputs[role][key])]
    return result


def oracle_command(operator, source, python, metadata, outputs, result):
    keys = ('output_y', 'output_scale') if operator == 'dynamic_quant' else ('output',)
    if operator not in OPERATORS or set(outputs) != set(keys):
        raise ValueError('oracle must verify every declared output')
    command = [str(python), str(Path(source) / 'scripts/verify_result.py'), '--metadata', str(metadata)]
    for key in keys:
        command += ['--' + key.replace('_', '-'), str(outputs[key])]
    return command + ['--result', str(result)]


def assemble(operator, sources, destination, *, expected_roles, expected_headers):
    roles = checked_roles(operator, sources, expected_roles)
    headers = {name: (ASSETS / name).read_bytes() for name in HEADERS}
    if inventory(headers) != expected_headers:
        raise ValueError('trusted timing/profile header identity mismatch')
    files = generated(operator, roles, headers)
    destination = Path(destination).absolute()
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / 'source'
    for name, data in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    proof = assembly_proof(operator, sources, destination, roles, files, expected_roles, expected_headers)
    (destination / 'source-review.json').write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    source_identity(operator, sources, destination, expected_roles=expected_roles, expected_headers=expected_headers)
    return proof


def assembly_proof(operator, sources, destination, roles, files, expected_roles, expected_headers):
    source = destination / 'source'
    patches = {name: ''.join(difflib.unified_diff(roles['baseline'][name].decode().splitlines(True), files[name].decode().splitlines(True),
                    fromfile='prepared-baseline/' + name, tofile='assembled/' + name))
               for name in ('CMakeLists.txt', f'op_host/{operator}.asc', 'scripts/verify_result.py')}
    for role in ROLES:
        for leaf in (f'{operator}_kernel.asc', f'{operator}_tiling.h'):
            name = f'compiled/{role}/{leaf}'
            patches[name] = ''.join(difflib.unified_diff(roles[role]['op_kernel/' + leaf].decode().splitlines(True),
                files[name].decode().splitlines(True), fromfile=f'original-{role}/op_kernel/{leaf}', tofile=name))
    proof = dict(schema_version=1, purpose='draft_shared_single_kernel_assembly', operator=operator,
                 eligible_for_publication=False, hardware_executed=False, build_executed=False,
                 roles={role: dict(path=str(Path(sources[role]).absolute()), files=expected_roles[role]) for role in ROLES},
                 trusted_headers=expected_headers, adapted_files=inventory(files), patches=patches,
                 producer_files={str(Path(__file__).resolve()): digest(Path(__file__).read_bytes()), str(OLD_PATH): digest(OLD_PATH.read_bytes())},
                 role_kernel_names={role: [f'aprof_{role}_{operator}_kernel'] for role in ROLES},
                 launches_per_call={role: 1 for role in ROLES},
                 output_keys=['output_y', 'output_scale'] if operator == 'dynamic_quant' else ['output'],
                 commands=dict(configure=['cmake', '-S', str(source), '-B', str(destination / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                               build=['cmake', '--build', str(destination / 'build'), '-j4']),
                 limitations=['not a kernel safety sandbox: independent source/route review remains required',
                              'one combined trusted CANN build and hardware qualification still required',
                              'no controller/runtime dispatch change; GQA and WQMM unsupported'])
    return proof


def source_identity(operator, sources, destination, *, expected_roles, expected_headers):
    roles = checked_roles(operator, sources, expected_roles)
    headers = {name: (ASSETS / name).read_bytes() for name in HEADERS}
    if inventory(headers) != expected_headers:
        raise ValueError('trusted header changed')
    expected = generated(operator, roles, headers)
    if tree(Path(destination) / 'source') != expected:
        raise ValueError('assembled source differs from exact mechanical regeneration')
    proof = json.loads((Path(destination) / 'source-review.json').read_text())
    if proof != assembly_proof(operator, sources, Path(destination).absolute(), roles, expected, expected_roles, expected_headers):
        raise ValueError('source review differs from independently regenerated proof')
    return {'valid': True, 'eligible_for_publication': False, 'adapted_files': inventory(expected)}
