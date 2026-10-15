"""GQA/WQMM complete callbacks for explicitly selected 1.0 Task v5; no dispatch."""
import difflib
import importlib.util
import json
import re
from pathlib import Path
import sys
from types import SimpleNamespace

from aprof_layout import skill_lib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RELEASE = REPO / 'skill-libs/graph-base/1.0.0'
if skill_lib() != RELEASE:
    raise ValueError('multi-kernel Task v5 requires explicitly selected graph-base/1.0.0')
BASE = HERE / 'shared_validation_adapter.py'
spec = importlib.util.spec_from_file_location('multikernel_private_base', BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
if base.selected_runtime() != RELEASE:
    raise ValueError('multi-kernel adapter loaded a different release')

OPERATORS = ('gqa', 'weight_quant_batch_matmul')
ROLES = base.ROLES
EXPORTS = {
    'gqa': ('gqa_reorder', 'gqa_softmax', 'gqa_qk_fp16', 'gqa_qk_bf16',
            'gqa_pv_fp16', 'gqa_pv_bf16', 'gqa_scatter'),
    'weight_quant_batch_matmul': ('wq_dequant_fp16', 'wq_dequant_bf16',
                                'wq_matmul_fp16', 'wq_matmul_bf16', 'wq_post_fp16', 'wq_post_bf16'),
}
EXTERNAL_INCLUDES = ('#include <cstdint>', '#include <type_traits>',
                     '#include "kernel_operator.h"', '#include "lib/matmul_intf.h"')
original_check = base.checked_roles


def kernel_file(operator):
    if operator not in OPERATORS:
        raise ValueError('only GQA and weight_quant_batch_matmul are supported')
    return f'op_kernel/{operator}_kernel.asc'


def checked_roles(operator, sources, expected):
    kernel = kernel_file(operator)
    values = original_check(operator, sources, expected)
    for role in ROLES:
        text = values[role][kernel].decode()
        exports = tuple(re.findall(r'extern "C"[^\n]*?\bvoid\s+(\w+)\(', text))
        if exports != EXPORTS[operator]:
            raise ValueError('role exported kernel names/order changed')
    if operator == 'gqa':
        # The protected host fills this fixed ABI; only device algorithm edits
        # are supported here, not a new host/tiling interface.
        layout = lambda data: re.findall(r'struct GqaTiling \{[^}]*\};', data.decode())
        if len(layout(values['baseline'][kernel])) != 1 or layout(values['baseline'][kernel]) != layout(values['candidate'][kernel]):
            raise ValueError('candidate changed the protected GQA tiling layout')
    return values


def compiled_kernel(data):
    text = base.exact(data.decode(), '#pragma once\n', '')
    for include in EXTERNAL_INCLUDES:
        if include in text:
            text = base.exact(text, include + '\n', '')
    return text.encode()


def role_includes(operator):
    text = '\n'.join(EXTERNAL_INCLUDES) + '\n'
    for role in ROLES:
        text += f'namespace aprof_{role} {{\n'
        for name in EXPORTS[operator]:
            text += f'#define {name} aprof_{role}_{name}\n'
        text += f'#include "../compiled/{role}/{operator}_kernel.asc"\n'
        for name in EXPORTS[operator]:
            text += f'#undef {name}\n'
        text += '}\n'
    return text + 'using namespace aprof_baseline;\n'


def buffer_layout(operator):
    if operator == 'gqa':
        return {
            'inputs': [('query', 'dq', 'qb'), ('key', 'dk', 'kvb'), ('value', 'dv', 'kvb'),
                       ('baseline_tiling', 'dt', 'sizeof(t)'), ('candidate_tiling', 'candidate_dt', 'sizeof(t)')],
            'outputs': [('output', 'dy', 'qb')],
            'workspaces': [('reordered_query', 'rQ', 'qb'), ('reordered_key', 'rK', 'kvb'),
                           ('reordered_value', 'rV', 'kvb'), ('scores', 'score', 'sb'),
                           ('temporary_output', 'tmp', 'qb'), ('matmul_tiling', 'tile', 'sizeof(AscendC::tiling::TCubeTiling)')],
        }
    kernel_file(operator)
    return {
        'inputs': [(name, f'bufs[{index}].d', f'bufs[{index}].n') for name, index in
                   [('x', 'ix'), ('weight', 'iw'), ('scale', 'is'), ('offset', 'io'), ('bias', 'ib'),
                    ('baseline_tiling', 'it'), ('candidate_tiling', 'candidate_it')]],
        'outputs': [('output', 'bufs[iy].d', 'bufs[iy].n')],
        'workspaces': [('dequantized_weight', 'bufs[idq].d', 'bufs[idq].n'),
                       ('matmul_result_fp32', 'bufs[imat].d', 'bufs[imat].n')],
    }


def callback_body(operator, launch, role):
    stream = base.old.WRAPPERS[operator][2]
    body = re.sub(r'\b' + stream + r'\b', 'selected_stream', launch)
    for name in EXPORTS[operator]:
        body = re.sub(r'\b' + name + r'\b', f'aprof_{role}::aprof_{role}_{name}', body)
    layout = buffer_layout(operator)
    substitutions = {}
    for group, items in layout.items():
        for index, (name, pointer, _) in enumerate(items):
            if name == 'candidate_tiling':
                continue
            if name == 'baseline_tiling' and role == 'candidate':
                index += 1
            substitutions[pointer] = f'shared.{group}[{index}].data'
    # One pass avoids interpreting inserted shared.inputs[] as source tokens.
    pattern = '|'.join(re.escape(key) for key in sorted(substitutions, key=len, reverse=True))
    return re.sub(r'(?<![\w])(?:' + pattern + r')(?![\w])', lambda match: substitutions[match[0]], body)


def shared_block(operator, launch, snapshot):
    _, _, stream, device, count = base.old.WRAPPERS[operator]
    arg = 'A(argc,argv,' if operator == 'gqa' else 'Arg(argc,argv,'
    layout = buffer_layout(operator)
    spans = lambda items: '{' + ', '.join('{"%s", %s, %s}' % item for item in items) + '}'
    text = '''
        const char *cycle_text = std::getenv("APROF_SHARED_CYCLE");
        if (!cycle_text || std::string(cycle_text).size() != 1 || cycle_text[0] < '0' || cycle_text[0] > '5')
            throw std::invalid_argument("APROF_SHARED_CYCLE must be 0..5");
'''
    for role in ROLES:
        text += f'        const std::string {role}_output = {arg}"--{role}-output");\n'
    text += '''        if (baseline_output.empty() || candidate_output.empty() || baseline_output == candidate_output)
            throw std::invalid_argument("distinct complete role output paths required");
'''
    text += '        const aprof::SharedBuffers buffers{' + ', '.join(spans(layout[g]) for g in ('inputs', 'outputs', 'workspaces')) + '};\n'
    for role in ROLES:
        text += f'        auto launch_{role} = [&](aclrtStream selected_stream, const aprof::SharedBuffers &shared) {{\n'
        text += callback_body(operator, launch, role) + '\n        };\n'
    pointer = layout['outputs'][0][1]
    snapshot = base.exact(snapshot, pointer, 'shared.outputs[0].data')
    snapshot = base.exact(snapshot, arg + '"--output")', '(std::string(role) == "baseline" ? baseline_output : candidate_output)')
    text += '        auto snapshot = [&](const char *role, aclrtStream, const aprof::SharedBuffers &shared) {\n' + snapshot + '\n        };\n'
    text += f'        task_profile.Start(static_cast<uint32_t>({device}));\n'
    text += f'        aprof::RunShared({stream}, "{operator}", cycle_text[0] - \'0\', {count}, {count}, buffers,\n'
    text += '            {"launch_baseline", "launch_candidate"}, launch_baseline, launch_candidate, snapshot);\n'
    return text + '        task_profile.Finish();\n'


def adapt_host(operator):
    kernel_file(operator)
    original = (base.REPO / 'scaffolding/benchmarks/cannbench/operators' / operator / 'op_host' / f'{operator}.asc').read_text()
    text = base.exact(original, f'#include "../op_kernel/{operator}_kernel.asc"',
                      role_includes(operator) + '#include "device_shared_timing.h"\n#include "device_task_profile.h"')
    if operator == 'gqa':
        text = base.exact(text, 'C(aclInit(nullptr),"aclInit");', 'C(aclInit(nullptr),"aclInit");aprof::TaskProfile task_profile;')
        text = base.exact(text, '*dt,*tile;', '*dt,*candidate_dt,*tile;')
        text = base.exact(text, '{&dt,sizeof(t)},', '{&dt,sizeof(t)},{&candidate_dt,sizeof(t)},')
        upload = 'C(aclrtMemcpy(dt,sizeof(t),&t,sizeof(t),ACL_MEMCPY_HOST_TO_DEVICE),"tiling H2D");'
        text = base.exact(text, upload, upload + 'C(aclrtMemcpy(candidate_dt,sizeof(t),&t,sizeof(t),ACL_MEMCPY_HOST_TO_DEVICE),"candidate tiling H2D");')
    else:
        text = base.exact(text, 'Check(aclInit(nullptr),"aclInit");', 'Check(aclInit(nullptr),"aclInit");aprof::TaskProfile task_profile;')
        anchor = 'it=add(sizeof(AscendC::tiling::TCubeTiling),"",false);'
        text = base.exact(text, anchor, anchor[:-1] + ',candidate_it=add(sizeof(AscendC::tiling::TCubeTiling),"",false);')
        upload = 'Check(aclrtMemcpy(bufs[it].d,bufs[it].n,&tile,sizeof(tile),ACL_MEMCPY_HOST_TO_DEVICE),"tiling H2D");'
        text = base.exact(text, upload, upload + 'Check(aclrtMemcpy(bufs[candidate_it].d,bufs[candidate_it].n,&tile,sizeof(tile),ACL_MEMCPY_HOST_TO_DEVICE),"candidate tiling H2D");')
    start, finish, _, _, _ = base.old.WRAPPERS[operator]
    if text.count(start) != 1 or text.count(finish) != 1:
        raise ValueError('complete callback anchors changed')
    first, last = text.index(start), text.index(finish) + len(finish)
    if '<<<' in text[:first] + text[last:]:
        raise ValueError('launch escaped the complete callback')
    end = text.index('std::cout', last)
    # Include every original internal and final sync. GQA Tile()/uploads and
    # both QK/PV loops remain inside each callback without changing their order.
    return text[:first] + shared_block(operator, text[first:last], text[last:end]) + text[end:]


def adapt_oracle(text, operator):
    kernel_file(operator)
    quote = "'" if operator == 'gqa' else '"'
    anchor = f'p.add_argument({quote}--metadata{quote},required=True);'
    text = base.exact(text, anchor, anchor + 'p.add_argument("--output",required=True);p.add_argument("--result",required=True);')
    if operator == 'gqa':
        text = base.exact(text, 'np.memmap(m[n],', 'np.memmap(a.output if n=="output" else m[n],')
        return base.exact(text, "(mp.parent/'result.json').write_text", 'Path(a.result).write_text')
    text = base.exact(text, 'np.memmap(m["output"],', 'np.memmap(a.output,')
    return base.exact(text, '(mp.parent/"result.json").write_text', 'Path(a.result).write_text')


def generated(operator, roles, headers):
    files = dict(roles['baseline'])
    host = adapt_host(operator)
    arg, stream, check = ('A(argc,argv,', 'st', 'C') if operator == 'gqa' else ('Arg(argc,argv,', 'stream', 'Check')
    host = base.exact(host, '        const char *cycle_text = std::getenv("APROF_SHARED_CYCLE");',
        f'''        const std::string mechanism_role = {arg}"--aprof-mechanism-role");
        if (!mechanism_role.empty() && mechanism_role != "baseline" && mechanism_role != "candidate")
            throw std::invalid_argument("unknown mechanism role");
        const char *cycle_text = mechanism_role.empty() ? std::getenv("APROF_SHARED_CYCLE") : "0";''')
    begin = host.index('        task_profile.Start(')
    end = host.index('        task_profile.Finish();', begin) + len('        task_profile.Finish();')
    branch = f'''        if (!mechanism_role.empty()) {{
            if (std::getenv("APROF_TASK_PROFILE_DIR"))
                throw std::invalid_argument("mechanism capture cannot enable Task API profiling");
            if (mechanism_role == "baseline") launch_baseline({stream}, buffers);
            else launch_candidate({stream}, buffers);
            {check}(aclrtSynchronizeStream({stream}), "mechanism complete call");
            snapshot(mechanism_role.c_str(), {stream}, buffers);
        }} else {{
'''
    host = host[:begin] + branch + host[begin:end] + '\n        }' + host[end:]
    files[f'op_host/{operator}.asc'] = host.encode()
    cmake = files['CMakeLists.txt'].decode()
    anchor = 'ascendcl ascendc_runtime)' if operator == 'gqa' else 'tiling_api m dl)'
    files['CMakeLists.txt'] = base.exact(cmake, anchor, anchor[:-1] + ' msprofiler)').encode()
    files['scripts/verify_result.py'] = adapt_oracle(files['scripts/verify_result.py'].decode(), operator).encode()
    for role in ROLES:
        files.update({f'roles/{role}/{name}': data for name, data in roles[role].items()})
        files[f'compiled/{role}/{operator}_kernel.asc'] = compiled_kernel(roles[role][kernel_file(operator)])
    files.update({f'op_host/{name}': data for name, data in headers.items()})
    return files


def case_binding(operator, metadata):
    """Derive this complete call's sequence; never emit a legacy Task config."""
    kernel_file(operator)
    if operator == 'gqa':
        q, k = metadata['query_shape'], metadata['key_shape']
        if (len(q) != 4 or len(k) != 4 or any(type(n) is not int or n <= 0 for n in [*q, *k])
                or k[0] != q[0] or k[3] != q[3] or q[2] % k[2] or q[1] > k[1]):
            raise ValueError('GQA metadata differs from the protected host shape contract')
        dtype = metadata['dtype']
    else:
        if not isinstance(metadata['dtype'], (tuple, list)) or not metadata['dtype']:
            raise ValueError('WQMM dtype must be the original dtype list')
        dtype = metadata['dtype'][0]
    if dtype not in ('float16', 'bfloat16'):
        raise ValueError('unsupported multi-kernel dtype')
    suffix = 'fp16' if dtype == 'float16' else 'bf16'
    count = base.old.launches_per_call(operator, metadata)
    if operator == 'gqa':
        groups = (count - 3) // 2
        names = ['gqa_reorder', *([f'gqa_qk_{suffix}'] * groups), 'gqa_softmax',
                 *([f'gqa_pv_{suffix}'] * groups), 'gqa_scatter']
    else:
        names = [f'wq_{stage}_{suffix}' for stage in ('dequant', 'matmul', 'post')]
    if len(names) != count:
        raise ValueError('original launch-count helper disagrees with complete sequence')
    return {'launches_per_call': {role: count for role in ROLES},
            'role_kernel_names': {role: [f'aprof_{role}_{name}' for name in names] for role in ROLES}}


def assembly_proof(operator, sources, destination, roles, files, expected_roles, expected_headers):
    source = destination / 'source'
    changed = ['CMakeLists.txt', f'op_host/{operator}.asc', 'scripts/verify_result.py']
    patches = {}
    for name in changed + [f'compiled/{role}/{operator}_kernel.asc' for role in ROLES]:
        before = roles[name.split('/')[1]][kernel_file(operator)] if name.startswith('compiled/') else roles['baseline'][name]
        patches[name] = ''.join(difflib.unified_diff(before.decode().splitlines(True), files[name].decode().splitlines(True),
                                                   fromfile='original/' + name, tofile='assembled/' + name))
    return dict(schema_version=1, purpose='shared_multikernel_assembly', operator=operator,
        eligible_for_publication=False, hardware_executed=False, build_executed=False,
        release=str(RELEASE), runtime_build='aprof-runtime/0.2.3', task_protocol='shared_buffer_msprof_task_window_v5',
        roles={role: {'path': str(Path(sources[role]).absolute()), 'files': expected_roles[role]} for role in ROLES},
        trusted_headers=expected_headers, adapted_files=base.inventory(files), patches=patches,
        producer_files={str(path): base.digest(path.read_bytes()) for path in (Path(__file__).resolve(), BASE, base.OLD_PATH)},
        role_exports={role: [f'aprof_{role}_{name}' for name in EXPORTS[operator]] for role in ROLES},
        task_binding={'requires_case_metadata': True, 'helper': 'shared_multikernel_adapter.case_binding',
                      'launch_count_expression': base.old.WRAPPERS[operator][4]},
        mechanism_entry={'flag': '--aprof-mechanism-role', 'roles': list(ROLES),
                         'calls': 1, 'snapshot_all_outputs': True, 'task_api_enabled': False},
        buffer_roles={group: [name for name, _, _ in entries] for group, entries in buffer_layout(operator).items()},
        output_keys=['output'],
        commands={'configure': ['cmake', '-S', str(source), '-B', str(destination / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                  'build': ['cmake', '--build', str(destination / 'build'), '-j4']},
        limitations=['mechanical source assembly only; independent source/route review remains required',
                     'one trusted CANN build and complete hardware qualification remain required',
                     'no automatic controller activation or mechanism admission',
                     'complete multi-kernel Task capture cost is unqualified; repeat rules are unchanged',
                     'original host tiling ABI and scheduling are fixed; candidate edits are confined to the kernel'])


# Private wiring leaves existing adapter and bridge module instances intact.
base.OPERATORS = OPERATORS
base.checked_roles = checked_roles
base.adapt_host = adapt_host
base.adapt_oracle = adapt_oracle
base.generated = generated
base.assembly_proof = assembly_proof
prepared_baseline, assemble = base.prepared_baseline, base.assemble
case_command, oracle_command = base.case_command, base.oracle_command


def source_identity(destination):
    destination = Path(destination).absolute()
    proof = json.loads((destination / 'source-review.json').read_text())
    sources = {role: Path(proof['roles'][role]['path']) for role in ROLES}
    base.source_identity(proof['operator'], sources, destination,
        expected_roles={role: proof['roles'][role]['files'] for role in ROLES},
        expected_headers=proof['trusted_headers'])
    return proof


_bridge_spec = importlib.util.spec_from_file_location('multikernel_private_bridge', HERE / 'local_controller_bridge.py')
bridge = importlib.util.module_from_spec(_bridge_spec)
_bridge_spec.loader.exec_module(bridge)
bridge.adapter = SimpleNamespace(base=base, source_identity=source_identity)
build_once, checked_build = bridge.build_once, bridge.checked_build


def task_config(assembly, build_receipt, prepared, scratch, *, run_id, session_id, candidate_id,
                physical_device, profiler):
    """Bind all 20 complete mathematical workloads to their exact v5 role sequences."""
    proof, build = checked_build(assembly, build_receipt)
    op, binary = proof['operator'], build['binary']['path']
    source = Path(assembly) / 'source'
    config = {'schema_version': '1.0.0', 'operator': op, 'run_id': run_id, 'session_id': session_id,
        'candidate_id': candidate_id, 'device': 0, 'physical_device': physical_device,
        'expected_case_ids': list(range(1, 21)),
        'roles': {role: {'source_dir': proof['roles'][role]['path'], 'symbol': 'launch_' + role,
                        'launches_per_operator': {}} for role in ROLES},
        'build': {'source_dir': str(source), 'binary': binary,
                  'receipt_files': [str(build_receipt), str(Path(assembly) / 'source-review.json'),
                                    build['attempt_ref']['path']]},
        'task_profile': {'profiler': str(profiler), 'scratch_root': str(scratch),
                         'role_kernel_names': {role: {} for role in ROLES}}, 'cases': []}
    for case_id in config['expected_case_ids']:
        metadata_path = Path(prepared) / f'case_{case_id:02d}/metadata.json'
        metadata = json.loads(metadata_path.read_text())
        if type(metadata.get('case_id')) is not int or metadata['case_id'] != case_id:
            raise ValueError('prepared metadata case identity differs')
        binding = case_binding(op, metadata)
        for role in ROLES:
            config['roles'][role]['launches_per_operator'][str(case_id)] = binding['launches_per_call'][role]
            config['task_profile']['role_kernel_names'][role][str(case_id)] = binding['role_kernel_names'][role]
        outputs = {role: {'output': '{cycle_dir}/' + role + '-output.bin'} for role in ROLES}
        absolute = {role: {key: value.replace('{cycle_dir}', '/APROF_CYCLE') for key, value in paths.items()}
                    for role, paths in outputs.items()}
        command = case_command(op, binary, metadata, 0, absolute)
        routing = {absolute[role]['output']: outputs[role]['output'] for role in ROLES}
        inputs = []
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key != 'output': visit(child)
            elif isinstance(value, list):
                for child in value: visit(child)
            elif isinstance(value, str) and Path(value).is_absolute() and Path(value).is_file():
                inputs.append(value)
        visit(metadata)
        config['cases'].append({'case_id': case_id,
            'workload': base.old.json_contract({key: value for key, value in metadata.items() if key != 'output'}),
            'prepared_files': [str(metadata_path), *sorted(set(inputs))],
            'command': [routing.get(value, value) for value in command],
            'verify_commands': {role: oracle_command(op, source, Path(sys.executable).resolve(), metadata_path,
                outputs[role], '{cycle_dir}/' + role + '-result.json') for role in ROLES},
            'output_files': {role: list(outputs[role].values()) for role in ROLES}})
    return bridge.timing.config_value(config)


ENABLED_IN_1_0 = False
