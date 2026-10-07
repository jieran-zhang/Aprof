#!/usr/bin/env python3
"""Read-only verification and process-level analysis for msprof exploration.

This module never runs an oracle, profiler, gate, or native program. Collector
artifacts retain their original protocol and half-percent verdict. The new
analysis is a separate, finite JSON value for the caller to archive.
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import hashlib
import importlib
import json
import math
from pathlib import Path
import statistics as st
import sys

import msprof_exploration_provenance as engineering_provenance
import level2_evidence_storage as verification_storage

PROTOCOL = 'msprof_task_time_exploration_v1'
ANALYSIS = 'msprof_exploration_analysis_v1'
PRODUCER = 'msprof_kernel_time_study_v1'
PROTOCOL_V2 = 'msprof_task_time_exploration_v2'
ANALYSIS_V2 = 'msprof_exploration_analysis_v2'
PRODUCER_V2 = 'msprof_kernel_time_study_v2'
METRIC = 'operator_task_sum_us'
MODE = 'task_time_l1_ai_core_off'
T5 = 2.570581835636305
T2 = 4.302652729696142
TOL = math.log(1.02)
DESIGN = (
    ('AB', 'AB', 'normal,swapped'),
    ('BA', 'AB', 'swapped,normal'),
    ('AB', 'BA', 'normal,swapped'),
    ('BA', 'BA', 'swapped,normal'),
    ('AB', 'AB', 'swapped,normal'),
    ('BA', 'BA', 'normal,swapped'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return verification_storage.fingerprint(path)['sha256']


def _decode(text, opaque=False):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('nonfinite JSON constant: ' + value)

    kwargs = {'object_pairs_hook': pairs}
    if not opaque:
        kwargs['parse_constant'] = nonfinite
    value = json.loads(text, **kwargs)
    if not opaque:
        canonical(value)  # Also rejects numeric overflow such as 1e999.
    return value


def load(path, *, opaque=False):
    return _decode(verification_storage.read_bytes(path).decode(), opaque)


@contextlib.contextmanager
def _no_bytecode():
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous


def _legacy():
    with _no_bytecode():
        return (importlib.import_module('cannbench_msprof_timing'),
                importlib.import_module('shared_context_build'))


def _ids(values):
    require(isinstance(values, list) and values, 'case_ids must be a nonempty list')
    result = [str(v) for v in values]
    require(all(v.isdigit() and 1 <= int(v) <= 20 and str(int(v)) == v for v in result),
            'case IDs must be canonical integers in [1,20]')
    require(len(result) == len(set(result)), 'duplicate case ID')
    return result


def _request(request):
    require(isinstance(request, dict), 'request must be an embedded object')
    require(request.get('version') in (PRODUCER, PRODUCER_V2), 'collector protocol differs')
    require(request.get('profiler_mode') == MODE, 'explicit task-only profiler_mode required')
    require(type(request.get('device')) is int and request['device'] >= 0, 'explicit physical device required')
    require(str(request.get('cpu', '')).isdigit(), 'one explicit CPU affinity required')
    for role in 'ab':
        delay = request.get('host_delay_' + role + '_us', 0)
        require(type(delay) is int and delay == 0, 'exploration host delay must be zero')
    require(request.get('load_order') in ('AB', 'BA') and request.get('first_order') in ('AB', 'BA'),
            'explicit load/first order required')
    require(request.get('buffer_configs') in ('normal,swapped', 'swapped,normal'), 'both buffer configurations required')
    require(all(Path(request.get(key, '')).is_absolute() for key in ('role_build', 'runner_build')),
            'absolute build manifest paths required')
    from msprof_raw_storage import policy as storage_policy
    storage_policy(request)
    cases = request.get('cases')
    require(isinstance(cases, list) and cases, 'request cases missing')
    ids = _ids([row['case_id'] for row in cases])
    for row in cases:
        if request['version']==PRODUCER_V2:
            require(type(row.get('repeat')) is int and row['repeat'] in (1,10), 'v2 cases require frozen repeat 1 or 10')
        require(all(Path(row.get(key, '')).is_absolute() for key in ('metadata', 'verifier')),
                'absolute prepared metadata/verifier paths required')
    return ids


def validate_plan(plan):
    """Validate the frozen six-row additive design without touching the device.

    Required plan: protocol, analysis_version, comparison_kind (aa/ab), case_ids,
    calibration_scope (nonempty frozen JSON object), and six schedule entries
    {name, request}, where request is the complete original collector request.
    """
    canonical(plan)
    require((plan.get('protocol'),plan.get('analysis_version')) in ((PROTOCOL,ANALYSIS),(PROTOCOL_V2,ANALYSIS_V2)),
            'exploration protocol/analysis version differs')
    require(plan.get('comparison_kind') in ('aa', 'ab'), 'comparison_kind must be aa or ab')
    ids = _ids(plan.get('case_ids'))
    require(isinstance(plan.get('calibration_scope'), dict) and plan['calibration_scope'],
            'frozen calibration_scope is required')
    schedule = plan.get('schedule')
    require(isinstance(schedule, list) and len(schedule) == 6, 'exactly six planned native processes required')
    names = []
    condition = None
    for entry, design in zip(schedule, DESIGN):
        name = entry.get('name', '')
        require(name and all(c.isascii() and (c.isalnum() or c in '_-') for c in name), 'unsafe session name')
        names.append(name)
        request = entry['request']
        require(request.get('version')==(PRODUCER_V2 if plan['protocol']==PROTOCOL_V2 else PRODUCER), 'plan/producer protocol mismatch')
        require(_request(request) == ids, 'request case order differs from frozen case_ids')
        from msprof_raw_storage import policy as storage_policy
        if 'capture_storage' in request or 'capture_storage' in plan['calibration_scope']:
            require(plan['calibration_scope'].get('capture_storage')==storage_policy(request),
                    'capture storage must be frozen in calibration scope')
            if request.get('capture_storage_producer'):
                require(plan['calibration_scope'].get('capture_storage_producer_hash')==request['capture_storage_producer']['sha256'],
                        'raw transport producer must be frozen in calibration scope')
        require(tuple(request[key] for key in ('load_order', 'first_order', 'buffer_configs')) == design,
                'load/first/configuration execution design differs')
        current = {k: v for k, v in request.items() if k not in ('load_order', 'first_order', 'buffer_configs')}
        require(condition is None or current == condition, 'cohort request conditions differ')
        condition = current
    require(len(set(names)) == 6, 'duplicate planned session name')
    if 'identity_bindings' in plan:
        identities = plan['identity_bindings']
        require(isinstance(identities, dict) and set(identities) == {'role_build', 'runner_build', 'input_bindings', 'producer'},
                'frozen identity binding fields differ')
        for field in ('role_build', 'runner_build'):
            require(identities[field].get('path') == schedule[0]['request'][field], 'frozen build manifest path differs')
        require(identities['input_bindings'].get('sha256') == plan['calibration_scope'].get('inputs'),
                'frozen input identity differs from calibration scope')
        timing, _ = _legacy()
        require(identities['producer'].get('path') == str(Path(timing.__file__).resolve()), 'frozen collector producer path differs')
        _verify_pointer_tree(identities, evidence_path=schedule[0]['request']['role_build'])
    return json.loads(canonical(plan))


class ObservationBindings(dict):
    """Original logical hashes plus separately verified historical code provenance."""
    def __init__(self, value, evidence_path):
        super().__init__(value)
        self.evidence_path=evidence_path
        self.producer_bindings=[]


def _bound_file(bindings, path):
    path = str(path)
    require(path in bindings, 'unbound evidence: ' + path)
    if sha(path) != bindings[path]:
        proof = (engineering_provenance.frozen_producer(Path(path),bindings[path],
            evidence_path=bindings.evidence_path,semantic_path=('observation_binding',))
            if isinstance(bindings,ObservationBindings) else None)
        require(proof is not None, 'bound evidence changed: ' + path)
        if proof not in bindings.producer_bindings:bindings.producer_bindings.append(proof)


def _opaque_equal(a, b):
    # Legacy task metadata can contain Infinity; it never enters report JSON.
    return json.dumps(a, sort_keys=True, allow_nan=True) == json.dumps(b, sort_keys=True, allow_nan=True)


def _verify_pointer_tree(value, *, evidence_path=None, producer_bindings=None):
    """Check explicit dependency pointers, including composed build provenance."""
    return engineering_provenance.verify_pointer_tree(value, evidence_path=evidence_path,
                                                       producer_bindings=producer_bindings)


def compare_saved_report(saved, actual, *, evidence_path, provenance_out=None):
    """Allow only an attested analyzer upgrade; all observation fields must match."""
    comparable = lambda value: {key: item for key, item in value.items() if key != 'analysis_producer_hash'}
    require(canonical(comparable(saved)) == canonical(comparable(actual)),
            'saved report differs from verified observation analysis')
    old, new = saved.get('analysis_producer_hash'), actual.get('analysis_producer_hash')
    result = {'matched': True, 'comparison': 'exact', 'saved_analysis_producer_hash': old,
              'reanalysis_producer_hash': new}
    if old != new:
        require(isinstance(old, str) and new == sha(__file__), 'analysis producer identity differs')
        bindings = []
        _verify_pointer_tree({'producer': {'path': str(Path(__file__).resolve()), 'sha256': old}},
                             evidence_path=evidence_path, producer_bindings=bindings)
        require(len(bindings) == 1, 'historical analysis producer requires a frozen snapshot')
        if provenance_out is not None:
            provenance_out.extend(binding for binding in bindings if binding not in provenance_out)
        result['comparison'] = 'all_observation_fields_equal_with_attested_analyzer_update'
    return result


def _build_identity(request, bindings, *, provenance_out=None):
    timing, build_tool = _legacy()
    for key in ('role_build', 'runner_build'):
        _bound_file(bindings, request[key])
    build = load(request['role_build'])
    runner = load(request['runner_build'])
    _verify_pointer_tree(build, evidence_path=request['role_build'], producer_bindings=provenance_out)
    _verify_pointer_tree(runner, evidence_path=request['runner_build'], producer_bindings=provenance_out)
    require(runner.get('version') == request['version'], 'runner producer differs')
    per_case=request['version']==PRODUCER_V2
    require(bool(runner.get('per_case_repeat'))==per_case, 'runner case-repeat capability differs')
    require((runner.get('repeat'), runner.get('pairs'), runner.get('warmup')) == (10, 30, 10),
            'runner requires repeat=10, pairs=30, warmup=10')
    _bound_file(bindings, runner['runner'])
    require(sha(runner['runner']) == runner['runner_hash'], 'runner binary hash differs')
    runner_root = Path(request['runner_build']).parent
    for filename, field in [('runner.cpp', 'source_hash'), ('original-runner.cpp', 'original_hash'), ('abi.h', 'abi_hash')]:
        require(sha(runner_root / filename) == runner[field], 'runner source/ABI hash differs')
    original = (runner_root / 'original-runner.cpp').read_text()
    generated=timing.instrument(original,10,per_case=True) if per_case else timing.instrument(original,10)
    require((runner_root / 'runner.cpp').read_text() == generated, 'generated runner is not the attested variant')
    expected_patch = ''.join(difflib.unified_diff(original.splitlines(True), generated.splitlines(True),
                                                fromfile='original-runner.cpp', tofile='runner.cpp'))
    require((runner_root / 'harness.patch').read_text() == expected_patch, 'runner patch differs')
    require(build.get('version') == 'shared_context_build_v1' and set(build.get('roles', {})) == {'A', 'B'},
            'role build identity incomplete')
    root = Path(request['role_build']).parent
    component_roots = {}
    components = build.get('component_builds')
    if components is not None:
        require(isinstance(components, list) and len(components) == 2, 'comparison requires two component builds')
        for role, pointer in zip('AB', components):
            require(Path(pointer['path']).is_absolute() and sha(pointer['path']) == pointer['sha256'], 'component build hash differs')
            component = load(pointer['path'])
            _verify_pointer_tree(component, evidence_path=pointer['path'], producer_bindings=provenance_out)
            require(component.get('version') == 'shared_context_build_v1' and component.get('operator') == build['operator']
                    and component.get('roles', {}).get(role) == build['roles'][role]
                    and component.get('harness') == build.get('harness'), 'component role/harness identity differs')
            component_roots[role] = Path(pointer['path']).parent
    for role, identity in build['roles'].items():
        require(identity.get('role') == role and identity.get('operator_name') == build['operator'], 'role build operator/role mismatch')
        require(sha(identity['binary']) == 'sha256:' + identity['binary_sha256'], 'role binary hash differs')
        source = Path(identity['source_dir'])
        require(build_tool.source_hash(source) == identity['source_sha256'], 'role source hash differs')
        require(sha(source / 'CMakeLists.txt') == 'sha256:' + identity['cmake_sha256'], 'source CMake hash differs')
        component_root = component_roots.get(role, root)
        require(sha(component_root / role / 'op_host' / (build['operator'] + '.asc')) == 'sha256:' + identity['adapter_sha256'], 'adapter hash differs')
        require(sha(component_root / (role + '.harness.patch')) == 'sha256:' + identity['patch_sha256'], 'role patch hash differs')
    require(build.get('harness'), 'missing role harness identities')
    for name, value in build['harness'].items():
        require(Path(name).name == name and sha(build_tool.HARNESS / name) == 'sha256:' + value,
                'role harness dependency differs')
    return timing, build, runner


def _resources(rows, case_ids):
    resources = {}
    for row in rows:
        key = (row['case_id'], row['buffer_config'], row['role'])
        require(key not in resources, 'duplicate resources')
        buffers = row['buffers']
        require(buffers and [b['index'] for b in buffers] == list(range(len(buffers))), 'resource indices invalid')
        require({'input', 'output'} <= {b['kind'] for b in buffers}, 'resource input/output missing')
        require(row.get('allocation_order') == 'AB' and row.get('input_policy') == 'separate_identical_files',
                'resource preparation policy differs')
        require(all(type(b['bytes']) is int and b['bytes'] > 0 and b['address'] not in ('0', '0x0', '(nil)', '') for b in buffers),
                'invalid resource address/size')
        require(len({b['address'] for b in buffers}) == len(buffers), 'resources alias within role')
        resources[key] = buffers
    require(set(resources) == {(c, k, r) for c in case_ids for k in ('normal', 'swapped') for r in 'AB'},
            'resource coverage incomplete')
    for case in case_ids:
        for config in ('normal', 'swapped'):
            a, b = (resources[case, config, role] for role in 'AB')
            require(not {v['address'] for v in a} & {v['address'] for v in b}, 'role resources alias')
        for role in 'AB':
            normal = resources[case, 'normal', role]
            swapped = resources[case, 'swapped', role]
            other = resources[case, 'swapped', 'B' if role == 'A' else 'A']
            immutable = lambda values: [(b['kind'], b['bytes'], b['address']) for b in values if b['kind'] in ('input', 'tiling')]
            mutable = lambda values: [(b['kind'], b['bytes'], b['address']) for b in values if b['kind'] in ('output', 'workspace')]
            require(immutable(normal) == immutable(swapped), 'immutable input/tiling slots changed')
            require(mutable(normal) == mutable(other), 'normal/swapped mutable slots not exchanged')
    return resources


@verification_storage.reader_session()
def verify_observation(directory, expected_request=None, *, provenance_out=None):
    """Replay one completed native observation; never execute its verifier."""
    directory = Path(directory).resolve()
    request = load(directory / 'request.json')
    if expected_request is not None:
        require(request == expected_request, 'request differs from frozen plan')
    case_ids = _request(request)
    completion = load(directory / 'completion.json')
    require(completion.get('version') == request['version'] and completion.get('status') == 'passed'
            and completion.get('error') is None and completion.get('formal_admission') == 'not_evaluated',
            'collection failed or incomplete')
    bindings = load(directory / 'bindings.json')
    require(isinstance(bindings, dict) and bindings, 'missing evidence bindings')
    bindings=ObservationBindings(bindings,directory/'completion.json')
    for path in bindings:
        require(Path(path).is_absolute(),'bound evidence path must be absolute')
        _bound_file(bindings,path)
    timing, build, runner = _build_identity(request, bindings)
    require(any(Path(p).name == 'cannbench_msprof_timing.py' for p in bindings), 'collector producer hash missing')
    require(any(Path(p).suffix == '.json' and p not in (request['role_build'], request['runner_build'])
                and load(p, opaque=True) == request for p in bindings if Path(p).suffix == '.json'),
            'original collector request binding missing')
    from level2_adapters import OPERATORS as LEVEL2_OPERATORS, launch_contract, input_paths, verify_output_metadata, OUTPUT_KEYS, verify_build_dispatch, native_kernel_sequence, verify_oracle_relocation
    is_level2=build['operator'] in LEVEL2_OPERATORS
    if is_level2:
        for identity in build['roles'].values():
            for path in verify_build_dispatch(identity):_bound_file(bindings,path)
    case_repeats={str(row['case_id']):row.get('repeat',10) for row in request['cases']}
    cases = []
    case_bindings = {}
    expected_tsv = []
    for spec in request['cases']:
        metadata = load(spec['metadata'], opaque=True)
        case = str(spec['case_id'])
        if 'case_id' in metadata:
            require(str(metadata['case_id']) == case, 'prepared metadata case ID differs')
        inputs = input_paths(metadata) if is_level2 else [str(v) for k, v in metadata.items() if k != 'output' and isinstance(v, str) and Path(v).is_file()]
        for path in [spec['metadata'], spec['verifier'], *inputs]:
            _bound_file(bindings, path)
        require(inputs, 'prepared input/golden bindings missing')
        cases.append({'case_id': case, 'launches_per_call': {role: timing.count_launches(build['operator'], build['roles'][role]['source_dir'], metadata) for role in 'AB'}})
        argv = timing.command_from_metadata(build['roles']['A']['source_dir'], metadata, 0, directory / 'unused.bin')[1:]
        if is_level2:
            contracts={r:launch_contract(build['operator'],build['roles'][r]['source_dir'],metadata) for r in 'AB'}
            cases[-1]['kernel_sequence']={r:native_kernel_sequence(build['roles'][r],contracts[r]['kernels']) for r in 'AB'}
            cases[-1]['required_auxiliary_tasks']={r:contracts[r]['required_auxiliary_tasks'] for r in 'AB'}
            expected_dispatch={r:contracts[r]['expected_dispatch'] for r in 'AB' if 'expected_dispatch' in contracts[r]}
            if expected_dispatch:cases[-1]['expected_dispatch']=expected_dispatch
            cases[-1]['repeat']=case_repeats[case]
            if runner.get('per_case_repeat'):argv+=['--aprof-repeat',str(case_repeats[case])]
        require(all('\t' not in v and '\n' not in v for v in argv), 'invalid native argument separator')
        expected_tsv.append('\t'.join([case, *argv]))
        case_bindings[case] = {'metadata': sha(spec['metadata']), 'verifier': sha(spec['verifier']),
                               'inputs': {path: sha(path) for path in inputs}, 'launches_per_call': cases[-1]['launches_per_call']}
        if is_level2: case_bindings[case]['repeat']=case_repeats[case]
    require(load(directory / 'cases.json') == cases, 'complete-call case contract differs')
    require((directory / 'cases.tsv').read_text() == '\n'.join(expected_tsv) + '\n', 'native case arguments differ')
    records = [_decode(line) for line in (directory / 'native/journal.jsonl').read_text().splitlines()]
    configs = request['buffer_configs'].split(',')
    expected_types = ['process_start', 'session_start', 'module', 'module']
    for _ in case_ids:
        for _ in configs:
            expected_types += ['case_start', 'resources', 'resources', 'warmup_complete'] + ['sample'] * 60 + ['output', 'output']
    expected_types += ['session_end']
    require([row.get('type') for row in records] == expected_types, 'native lifecycle sequence incomplete or reordered')
    # The existing instrumenter adds timing_protocol to emit(), but the final
    # session_end is written directly by the runner and has no protocol key.
    require(all(row.get('session_id') == directory.name for row in records), 'foreign native session')
    require(all(row.get('timing_protocol') == request['version'] for row in records[:-1]), 'native timing protocol differs')
    process, start, end = records[0], records[1], records[-1]
    require(type(start.get('pid')) is int and start['pid'] > 0 and start.get('host'), 'missing native process identity')
    require(process['pid'] == start['pid'] and process['host'] == start['host']
            and process['started_at'] <= start['started_at'] <= end['ended_at'], 'native process lifecycle differs')
    require(end.get('exit_code') == 0 and end.get('context_destroyed') is True and end.get('stream_destroyed') is True,
            'native did not exit normally')
    require(start.get('load_order') == request['load_order'] and start.get('first_order') == request['first_order']
            and start.get('device') == 0 and type(start.get('vector_cores')) is int and start['vector_cores'] > 0
            and all(start.get(k) not in (None, '', '0', '0x0', '(nil)', 0) for k in ('context_id', 'stream_id')),
            'native session configuration differs')
    modules = records[2:4]
    require([row['role'] for row in modules] == list(request['load_order']), 'module loading order differs')
    for row in modules:
        identity = build['roles'][row['role']]
        require(all(row.get(k) == identity[k] for k in ('source_sha256', 'kernel_symbols', 'operator_name'))
                and Path(row['path']).resolve() == Path(identity['binary']).resolve(), 'native module identity differs')
        require(row.get('entry_address') not in (None, '', '0', '0x0', '(nil)'), 'native module entry missing')
    require(modules[0]['entry_address'] != modules[1]['entry_address'], 'native module entries alias')
    role_symbols = [row['kernel_symbols'].split(',') for row in modules]
    require(all(all(names) and len(names) == len(set(names)) for names in role_symbols)
            and not set(role_symbols[0]) & set(role_symbols[1]), 'native kernel symbols missing or alias')
    resources = _resources([row for row in records if row['type'] == 'resources'], case_ids)
    starts = [row for row in records if row['type'] == 'case_start']
    require([(row['case_id'], row['buffer_config']) for row in starts] == [(c, k) for c in case_ids for k in configs],
            'case/config execution coverage differs')
    for row in starts:
        require((row.get('case_index'), row.get('warmup_per_role'), row.get('pairs'), row.get('repeat')) ==
                (case_ids.index(row['case_id']), 10, 30, case_repeats[row['case_id']]), 'case measurement parameters differ')
    warmups = [row for row in records if row['type'] == 'warmup_complete']
    require([(row['case_id'], row['buffer_config'], row['calls_per_role']) for row in warmups] ==
            [(c, k, 10) for c in case_ids for k in configs], 'warmup coverage differs')
    samples = [row for row in records if row['type'] == 'sample']
    expected_keys = [(c, k, j, role) for c in case_ids for k in configs for j in range(30)
                     for role in (request['first_order'] if j % 2 == 0 else request['first_order'][::-1])]
    require([(row['case_id'], row['buffer_config'], row['pair_id'], row['role']) for row in samples] == expected_keys,
            'sample pairing/order/coverage differs')
    previous = start['started_at']
    for row in samples:
        order = request['first_order'] if row['pair_id'] % 2 == 0 else request['first_order'][::-1]
        require(row.get('sample_id') == f"{directory.name}/{row['case_id']}/{row['buffer_config']}/{row['pair_id']}/{row['role']}", 'sample identity differs')
        require(row.get('order') == order and row.get('position') == order.index(row['role']), 'AB/BA order differs')
        require(row.get('context_id') == start['context_id'] and row.get('stream_id') == start['stream_id'], 'sample context/stream differs')
        require(previous <= row['started_at'] <= row['ended_at'] <= end['ended_at'], 'sample times overlap/leave native session')
        previous = row['ended_at']
        require(row.get('repeat') == case_repeats[row['case_id']] and row.get('raw_unit') == 'ms' and row.get('to_ns') == 1000000
                and row['raw_duration'] > 0 and math.isclose(row['ns_per_call'], row['raw_duration'] * 1000000 / case_repeats[row['case_id']], rel_tol=1e-10),
                'event units/repeat conversion differs')
    execution = load(directory / 'msprof.execution.json')
    verify_raw_storage = verification_storage.verify_raw_storage
    actual_raw, raw_evidence, storage_environment = verify_raw_storage(request,directory,execution)
    if 'capture_storage' in request:
        import msprof_raw_storage
        _bound_file(bindings,Path(msprof_raw_storage.__file__).resolve())
    argv = ['taskset', '-c', str(request['cpu']), *timing.profiler_arguments(MODE, actual_raw), runner['runner'],
            '--role-a', build['roles']['A']['binary'], '--role-b', build['roles']['B']['binary'],
            '--cases', str(directory / 'cases.tsv'), '--output-dir', str(directory / 'native'), '--session-id', directory.name,
            '--load-order', request['load_order'], '--first-order', request['first_order'], '--buffer-configs', request['buffer_configs'], '--device', '0']
    require(execution.get('argv') == argv and execution.get('exit_code') == 0 and execution.get('error') is None,
            'profiler command did not succeed as planned')
    require(execution.get('host') == start['host'] and str(execution.get('physical_device')) == str(request['device'])
            and execution.get('logical_device') == 0 and execution['started_at'] <= process['started_at']
            and end['ended_at'] <= execution['ended_at'], 'profiler/native process binding differs')
    for name in ('msprof.stdout.log', 'msprof.stderr.log'):
        require((directory / name).is_file(), 'missing profiler log')
    for name in ('health-before.json', 'health-after.json'):
        health = load(directory / name)
        require(health.get('exit_status') == 0 and health.get('no_device_processes') is True, 'device occupancy evidence failed')
    outputs = [row for row in records if row['type'] == 'output']
    expected_outputs = [(c, k, r) for c in case_ids for k in configs for r in 'AB']
    require([(row['case_id'], row['buffer_config'], row['role']) for row in outputs] == expected_outputs, 'native output coverage differs')
    validation = load(directory / 'validation.json')
    require(validation.get('scope') == 'final_call_of_final_sample_per_case_config_role', 'oracle coverage scope differs')
    checked = validation.get('outputs', [])
    require([(row['case_id'], row['buffer_config'], row['role']) for row in checked] == expected_outputs, 'prepared validation coverage differs')
    oracle_relocation_artifacts=[]
    for native, checked_row in zip(outputs, checked):
        stem = f"{native['case_id']}_{native['buffer_config']}_{native['role']}"
        output = directory / 'native' / (stem + '.bin')
        require(Path(native['path']).resolve() == output and native.get('complete_calls_since_prepare') == 10+30*case_repeats[native['case_id']]
                and native.get('validation_scope') == 'final_call_of_final_formal_sample'
                and native.get('validation_status') == 'pending_external_oracle', 'native output identity/scope differs')
        require(checked_row.get('passed') is True and checked_row.get('output_hash') == sha(output), 'prepared output hash/verdict differs')
        spec = next(row for row in request['cases'] if str(row['case_id']) == native['case_id'])
        metadata = load(spec['metadata'], opaque=True)
        if is_level2: metadata=verify_output_metadata(build['operator'],metadata,output)
        else: metadata['output'] = str(output)
        vdir = directory / 'verification' / stem
        require(_opaque_equal(load(vdir / 'metadata.json', opaque=True), metadata), 'oracle metadata differs from prepared contract')
        oracle = load(vdir / 'execution.json')
        oracle_argv = oracle.get('argv')
        execution_metadata_path=str(vdir/'metadata.json')
        if 'oracle_relocation' in oracle:
            require(request['version']==PRODUCER_V2 and build['operator']=='unsorted_segment_sum','unexpected oracle metadata relocation')
            oracle_relocation_artifacts.extend(verify_oracle_relocation(oracle['oracle_relocation'],vdir/'metadata.json',spec['verifier']))
            execution_metadata_path=oracle['oracle_relocation']['execution_metadata_path']
        require(isinstance(oracle_argv, list) and len(oracle_argv) == 4
                and isinstance(oracle_argv[0], str) and Path(oracle_argv[0]).is_absolute()
                and Path(oracle_argv[0]).resolve() == Path(sys.executable).resolve()
                and oracle_argv[1:] == [str(Path(spec['verifier']).resolve()), '--metadata', execution_metadata_path]
                and oracle.get('exit_code') == 0 and oracle.get('mode') == 'unchanged_import_safe_main'
                and execution['ended_at'] <= oracle['started_at'] <= oracle['ended_at'], 'oracle execution evidence invalid')
        require(verification_storage.is_file(vdir / 'stdout.log'), 'oracle stdout missing')
    parsed = verification_storage.parse_profile(directory / 'raw', directory / 'native/journal.jsonl', build, cases, 10)
    require(parsed == load(directory / 'samples.json'), 'saved samples differ from CSV/journal replay')
    # Device_id is normally the physical ID. A deployment with a documented
    # profiler namespace can freeze csv_device_id explicitly in its request.
    import csv
    import io
    with verification_storage.open_binary(parsed['csv']) as binary, io.TextIOWrapper(binary, newline='', encoding='utf-8-sig') as stream:
        target_lines = {line for row in parsed['samples'] for line in row['csv_rows']}
        csv_rows = [row for i, row in enumerate(csv.DictReader(stream), 2) if i in target_lines]
    require({row['Device_id'] for row in csv_rows} == {str(request.get('csv_device_id', request['device']))}, 'CSV physical device mapping differs')
    cells = []
    for case in case_ids:
        for config in ('normal', 'swapped'):
            rows = [row for row in parsed['samples'] if (row['case_id'], row['buffer_config']) == (case, config)]
            require(len(rows) == 60, 'complete case/config sample block missing')
            pairs = {j: {row['role']: row for row in rows if row['pair_id'] == j} for j in range(30)}
            require(all(set(p) == {'A', 'B'} for p in pairs.values()), 'pair role incomplete')
            logs = [math.log(pairs[j]['A']['task_us']) - math.log(pairs[j]['B']['task_us']) for j in range(30)]
            strata = {order: st.mean(logs[j] for j in range(30) if pairs[j]['A']['order'] == order) for order in ('AB', 'BA')}
            roles = {role: _describe([p[role]['task_us'] for p in pairs.values()]) for role in 'AB'}
            cells.append({'case_id': case, 'buffer_config': config, 'mean_log': st.mean(logs), 'speedup': math.exp(st.mean(logs)),
                          'roles': roles, 'order_log_means': strata, 'order_log_contrast': strata['AB'] - strata['BA']})
        case_bindings[case]['resource_layout'] = {role: [[b['kind'], b['bytes']] for b in resources[case, 'normal', role]] for role in 'AB'}
    # Enumerate only the known evidence closure. Do not sweep profiler trees,
    # and do not absorb later reports into their own replay inputs.
    evidence = [directory / name for name in ('request.json', 'completion.json', 'bindings.json', 'cases.json', 'cases.tsv',
                'native/journal.jsonl', 'msprof.execution.json', 'msprof.stdout.log', 'msprof.stderr.log',
                'health-before.json', 'health-after.json', 'validation.json', 'samples.json')]
    evidence.extend(raw_evidence)
    for c, k, r in expected_outputs:
        stem = f'{c}_{k}_{r}'
        evidence.append(directory / 'native' / (stem + '.bin'))
        if build['operator'] in OUTPUT_KEYS:
            bundle=directory/'native'/(stem+'.bin')
            evidence.append(bundle.with_name(bundle.name+'.outputs.json'))
            evidence.extend(bundle.with_name(bundle.name+'.'+key) for key in OUTPUT_KEYS[build['operator']])
        evidence.extend(directory / 'verification' / stem / name for name in ('metadata.json', 'execution.json', 'stdout.log'))
    evidence.extend(oracle_relocation_artifacts)
    runner_root = Path(request['runner_build']).parent
    evidence.extend(runner_root / name for name in ('runner.cpp', 'original-runner.cpp', 'abi.h', 'harness.patch'))
    producer_bindings = []
    evidence.extend(_verify_pointer_tree(build, evidence_path=request['role_build'], producer_bindings=producer_bindings))
    evidence.extend(_verify_pointer_tree(runner, evidence_path=request['runner_build'], producer_bindings=producer_bindings))
    for role, identity in build['roles'].items():
        role_root = Path(request['role_build']).parent
        if build.get('component_builds'):
            pointer = build['component_builds']['AB'.index(role)]
            evidence.append(Path(pointer['path']))
            evidence.extend(_verify_pointer_tree(load(pointer['path']), evidence_path=pointer['path'],
                                                 producer_bindings=producer_bindings))
            role_root = Path(pointer['path']).parent
        evidence.extend([Path(identity['binary']), Path(identity['source_dir']) / 'CMakeLists.txt',
                         role_root / role / 'op_host' / (build['operator'] + '.asc'), role_root / (role + '.harness.patch')])
        for source_subdir in ('op_host', 'op_kernel'):
            evidence.extend(p for p in (Path(identity['source_dir']) / source_subdir).rglob('*') if p.is_file())
    _, build_tool = _legacy()
    evidence.extend(build_tool.HARNESS / name for name in build['harness'])
    resolved_paths = {Path(binding[key]['path']) for binding in producer_bindings
                      for key in ('snapshot', 'frozen_manifest')}
    artifacts = {str(p): sha(p) for p in sorted(set(evidence) - resolved_paths)}
    # Preserve the original report's logical dependency identity. Snapshot bytes
    # and their attestation are separate replay provenance, never substituted
    # into an old report or represented as the current live script's contents.
    for binding in producer_bindings:
        artifacts[binding['origin']['path']] = binding['origin']['sha256']
    if producer_bindings and provenance_out is not None:
        provenance_out.extend(binding for binding in producer_bindings if binding not in provenance_out)
    artifacts[parsed['csv']] = parsed['csv_hash']
    if 'auxiliary_csv' in parsed:artifacts[parsed['auxiliary_csv']]=parsed['auxiliary_csv_hash']
    if provenance_out is not None:
        provenance_out.extend(proof for proof in bindings.producer_bindings if proof not in provenance_out)
    dispatch_hits=[dict(case_id=row['case_id'],buffer_config=row['buffer_config'],role=row['role'],pair_id=row['pair_id'],**row['verified_dispatch']) for row in parsed['samples'] if 'verified_dispatch' in row]
    return {'session_id': directory.name, 'directory': str(directory), 'host': start['host'], 'pid': start['pid'],
            'started_at': start['started_at'], 'ended_at': end['ended_at'], 'load_order': request['load_order'],
            'first_order': request['first_order'], 'buffer_configs': configs, 'cells': cells, 'case_bindings': case_bindings,
            'environment_binding': {**storage_environment, 'device': request['device'], 'cpu': str(request['cpu']), 'profiler_mode': MODE,
                                    'runner_hash': runner['runner_hash'], 'runner_source_hash': runner['source_hash'], 'abi_hash': runner['abi_hash'],
                                    'vector_cores': start['vector_cores'], 'csv_device_id': str(request.get('csv_device_id', request['device']))},
            'source_hashes': {r: build['roles'][r]['source_sha256'] for r in 'AB'}, 'operator': build['operator'],
            'artifacts': artifacts, 'bound_artifacts': bindings,
            **({'verified_dispatch_hits':dispatch_hits} if dispatch_hits else {}),
            'provenance': {'producer_protocol': request['version'], 'native_stream_id': start['stream_id'],
                           'csv_stream_id': csv_rows[0]['Stream ID'], 'csv_device_id': csv_rows[0]['Device_id'],
                           'oracle_reexecuted': False, 'prepared_validation_scope': validation['scope']}}


def _describe(values):
    return {'mean_us': st.mean(values), 'median_us': st.median(values), 'cv': st.stdev(values) / st.mean(values),
            'minimum_us': min(values), 'maximum_us': max(values)}


def effect(logs):
    require(len(logs) == 6 and all(math.isfinite(v) for v in logs), 'effect requires six finite process values')
    mean = st.mean(logs)
    se = st.stdev(logs) / math.sqrt(6)
    bounds = [mean - T5 * se, mean + T5 * se]
    return {'n_processes': 6, 'df': 5, 'log_effects': list(logs), 'process_ratios': [math.exp(v) for v in logs],
            'mean_log': mean, 'log_ci95': bounds, 'speedup': math.exp(mean), 'ci95': [math.exp(v) for v in bounds],
            'latency_change': math.expm1(-mean), 'latency_change_ci95': [math.expm1(-bounds[1]), math.expm1(-bounds[0])]}


def equivalence(summary):
    lo, hi = summary['log_ci95']
    if lo >= -TOL and hi <= TOL:
        return 'equivalent'
    if lo > TOL or hi < -TOL:
        return 'observed_bias'
    return 'precision_insufficient'


def _inverse(matrix):
    n = len(matrix)
    rows = [[float(v) for v in row] + [float(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(rows[i][col]))
        require(abs(rows[pivot][col]) > 1e-12, 'additive design rank deficient')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [v / scale for v in rows[col]]
        for i in range(n):
            if i != col:
                factor = rows[i][col]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[col])]
    return [row[n:] for row in rows]


def additive_effects(logs):
    """Adjusted two-level contrasts; six rows, four coefficients, residual df=2."""
    require(len(logs) == 6, 'additive model requires six process values')
    x = [[1, 1 if load == 'AB' else -1, 1 if first == 'AB' else -1,
          1 if configs == 'normal,swapped' else -1] for load, first, configs in DESIGN]
    gram = [[sum(row[i] * row[j] for row in x) for j in range(4)] for i in range(4)]
    inv = _inverse(gram)
    xy = [sum(row[i] * value for row, value in zip(x, logs)) for i in range(4)]
    beta = [sum(a * b for a, b in zip(row, xy)) for row in inv]
    residuals = [value - sum(a * b for a, b in zip(row, beta)) for row, value in zip(x, logs)]
    variance = sum(r * r for r in residuals) / 2
    contrasts = {}
    for i, name in enumerate(('load_order', 'first_order', 'config_execution_order'), 1):
        center = 2 * beta[i]
        se = 2 * math.sqrt(variance * inv[i][i])
        bounds = [center - T2 * se, center + T2 * se]
        contrasts[name] = {'mean_log': center, 'log_ci95': bounds, 'ratio': math.exp(center),
                           'ci95': [math.exp(v) for v in bounds], 'standard_error': se, 'df': 2}
        contrasts[name]['equivalence_status'] = equivalence(contrasts[name])
    return {'design_matrix': x, 'rank': 4, 'residual_df': 2, 'coefficients': beta, 'residuals': residuals,
            'contrasts': contrasts, 'support': 'adjusted_main_effects_under_additive_model',
            'interaction_control': 'not_covered', 'independent_loading_control': 'not_covered'}


def _calibration_match(calibration, plan, session, case):
    if calibration is None:
        return 'not_covered', None
    require(calibration.get('protocol') == plan['protocol'] and calibration.get('analysis_version') == plan['analysis_version']
            and calibration.get('comparison_kind') == 'aa' and calibration.get('evidence_status') == 'verified_complete'
            and calibration.get('formal_admission') == 'not_evaluated', 'calibration must be a verified versioned A/A report')
    previous = calibration.get('calibration_cards', {}).get(case)
    if previous is None:
        return 'not_covered', None
    applicable = (calibration.get('calibration_scope') == plan['calibration_scope']
                  and calibration.get('environment_binding') == session['environment_binding']
                  and calibration.get('operator') == session['operator']
                  and calibration.get('source_hashes', {}).get('A') == session['source_hashes']['A']
                  and previous['case_binding'] == session['case_bindings'][case])
    return ('applicable' if applicable else 'invalidated'), previous


def _scope_evidence(scope, session):
    observed = {'host': session['host'], 'physical_device': session['environment_binding']['device'],
                'device': session['environment_binding']['device'], 'cpu': session['environment_binding']['cpu'],
                'runner_hash': session['environment_binding']['runner_hash'], 'profiler_mode': MODE}
    if 'capture_storage' in session['environment_binding']:
        observed['capture_storage']=session['environment_binding']['capture_storage']
        if 'capture_storage_producer_hash' in session['environment_binding']:
            observed['capture_storage_producer_hash']=session['environment_binding']['capture_storage_producer_hash']
    checked = []
    for key, expected in observed.items():
        if key in scope and scope[key] is not None:
            actual = str(scope[key]) if key == 'cpu' else scope[key]
            require(actual == expected, 'declared calibration scope differs from observed ' + key)
            checked.append(key)
    return {'verified_fields': checked, 'externally_declared_fields': sorted(set(scope) - set(checked)),
            'missing_environment_versions': [key for key in ('cann_version', 'driver_version') if scope.get(key) is None],
            'limitation': 'Matching the declared epoch is conditional on unchanged external environment; absent versions are not inferred.'}


@verification_storage.reader_session()
def analyze_task_cohort(directories, plan, calibration=None, *, provenance_out=None):
    """Verify six processes, then return a new report without writing artifacts."""
    plan = validate_plan(plan)
    scope_paths = _verify_pointer_tree(plan['calibration_scope'])
    if 'identity_bindings' in plan:
        scope_paths.extend(_verify_pointer_tree(plan['identity_bindings'], evidence_path=plan['schedule'][0]['request']['role_build']))
    scope_artifacts = {str(path): sha(path) for path in scope_paths}
    require(len(directories) == 6, 'exactly six observed native processes required')
    paths = [Path(path).resolve() for path in directories]
    require(len(set(paths)) == 6, 'duplicate process directory')
    resolve_continuation = engineering_provenance.resolve_continuation
    continuation = resolve_continuation(paths[0].parent, verification_storage.read_bytes)
    if continuation is not None:
        from level2_cohort_continuation import annotation as continuation_annotation
        require([str(p) for p in paths] == continuation['directories'], 'continuation session mapping differs')
        require(plan == load(paths[0].parent / 'plan.json'), 'continuation must use its exact frozen cohort plan')
    sessions = []
    identities = set()
    previous_end = None
    for path, entry in zip(paths, plan['schedule']):
        require(continuation is not None or path.name == entry['name'], 'observation order/name differs from frozen schedule')
        session = verify_observation(path, entry['request'], **({'provenance_out': provenance_out} if provenance_out is not None else {}))
        identity = (session['host'], session['pid'], session['started_at'])
        require(identity not in identities, 'duplicate native process identity')
        identities.add(identity)
        require(previous_end is None or previous_end < session['started_at'], 'native processes overlap or execution order differs')
        previous_end = session['ended_at']
        if sessions:
            for key in ('host', 'environment_binding', 'source_hashes', 'operator', 'case_bindings'):
                require(session[key] == sessions[0][key], 'cohort evidence conditions differ: ' + key)
        sessions.append(session)
    if plan['comparison_kind'] == 'aa':
        require(sessions[0]['source_hashes']['A'] == sessions[0]['source_hashes']['B'], 'A/A role source hashes differ')
    scope_evidence = _scope_evidence(plan['calibration_scope'], sessions[0])
    ids = _ids(plan['case_ids'])
    results = []
    cards = {}
    for case in ids:
        config_results = {}
        for config in ('normal', 'swapped'):
            cells = [next(c for c in s['cells'] if (c['case_id'], c['buffer_config']) == (case, config)) for s in sessions]
            result = {'case_id': case, 'buffer_config': config, 'metric': METRIC, **effect([c['mean_log'] for c in cells]),
                      'max_within_process_cv': max(c['roles'][r]['cv'] for c in cells for r in 'AB'),
                      'sessions': [{'session_id': s['session_id'], 'started_at': s['started_at'], **c} for s, c in zip(sessions, cells)],
                      'order_conditions': {order: effect([c['order_log_means'][order] for c in cells]) for order in ('AB', 'BA')},
                      'order_contrast': effect([c['order_log_contrast'] for c in cells]),
                      'additive_factors': additive_effects([c['mean_log'] for c in cells])}
            result['cv_status'] = 'within_limit' if result['max_within_process_cv'] <= .05 else 'exceeds_limit'
            result['aa_equivalence_status'] = equivalence(result) if plan['comparison_kind'] == 'aa' else 'not_applicable'
            result['aa_within_two_percent'] = (result['aa_equivalence_status'] == 'equivalent') if plan['comparison_kind'] == 'aa' else None
            config_results[config] = result
        buffer_effect = effect([a - b for a, b in zip(config_results['normal']['log_effects'], config_results['swapped']['log_effects'])])
        buffer_effect['equivalence_status'] = equivalence(buffer_effect)
        applicable, card = _calibration_match(calibration, plan, sessions[0], case) if plan['comparison_kind'] == 'ab' else ('evaluated_here', None)
        if plan['comparison_kind'] == 'aa':
            card = {'case_binding': sessions[0]['case_bindings'][case],
                    'configurations': {k: {'equivalence_status': v['aa_equivalence_status'], 'cv_status': v['cv_status'],
                                          'speedup': v['speedup'], 'ci95': v['ci95'], 'process_ratios': v['process_ratios'],
                                          'order_equivalence_status': equivalence(v['order_contrast'])} for k, v in config_results.items()},
                    'buffer_equivalence_status': buffer_effect['equivalence_status'],
                    'interaction_control': 'not_covered', 'independent_loading_control': 'not_covered'}
            cards[case] = card
        for config, result in config_results.items():
            qualified = (card is not None and applicable in ('applicable', 'evaluated_here')
                         and card['configurations'][config]['equivalence_status'] == 'equivalent'
                         and card['configurations'][config]['cv_status'] == 'within_limit'
                         and card['configurations'][config]['order_equivalence_status'] == 'equivalent'
                         and card['buffer_equivalence_status'] == 'equivalent'
                         and result['cv_status'] == 'within_limit')
            result['buffer_contrast'] = buffer_effect
            result['calibration_status'] = applicable
            result['coarse_observed_controls'] = 'within_limits' if qualified else 'limited'
            # An additive model is not independent loading/interaction control.
            result['measurement_quality'] = 'complete_with_caution'
            result['qualified_performance_eligible'] = False
            result['claim_status'] = ('needs_precision' if .01 <= abs(result['latency_change']) <= .03 else 'observation_only')
            result['limitations'] = ['Independent loading and interaction controls are not covered by this six-row additive design.']
            if not qualified:
                result['limitations'].append('A/A scope, equivalence, order/resource controls, or CV is insufficient for a qualified performance claim.')
            results.append(result)
    suites = {}
    for config in ('normal', 'swapped'):
        logs = [st.mean(c['mean_log'] for c in s['cells'] if c['buffer_config'] == config) for s in sessions]
        suites[config] = {**effect(logs), 'case_ids': ids, 'coverage': len(ids), 'expected_case_count': len(ids),
                          'description': 'equal_case_equal_process_geometric_task_time_ratio',
                          'measurement_quality': 'descriptive_complete_with_caution', 'qualified_performance_eligible': False,
                          'full_twenty_case_suite': set(ids) == {str(i) for i in range(1, 21)}}
    result = {'protocol': plan['protocol'], 'analysis_version': plan['analysis_version'], 'metric': METRIC, 'unit': 'us_per_complete_call',
              'replication_unit': 'native_process', 'comparison_kind': plan['comparison_kind'], 'case_ids': ids,
              'plan_hash': digest(plan), 'calibration_scope': plan['calibration_scope'],
              'calibration_scope_artifacts': scope_artifacts,
              'calibration_scope_evidence': scope_evidence,
              'calibration_report_hash': digest(calibration) if calibration is not None else None,
              'environment_binding': sessions[0]['environment_binding'], 'source_hashes': sessions[0]['source_hashes'],
              'operator': sessions[0]['operator'], 'results': results, 'suite': suites, 'calibration_cards': cards,
              'sessions': sessions, 'evidence_status': 'verified_complete', 'formal_admission': 'not_evaluated',
              'graph_policy_eligible': False, 'episode_ref': None,
              'limits': {'aa_ratio_band': [1 / 1.02, 1.02], 'within_process_cv': .05},
              'analysis_producer_hash': sha(__file__),
              'limitations': ['Six-process t intervals assume approximately independent process effects; new PIDs do not establish independence.',
                             'Marginal case intervals are not simultaneous coverage guarantees.',
                             'Additive factor intervals use residual df=2; unmeasured interactions remain uncovered.',
                             'Task sums exclude host submission and inter-task gaps; they are not end-to-end latency.']}
    if continuation is not None:
        # Full original request checks above still run for each actual directory.
        result['continuation'] = continuation_annotation(continuation)
        result['limitations'].extend(continuation['interruption_limitations'])
        for row in result['results']:
            row['qualified_performance_eligible'] = False
            row['measurement_quality'] = 'complete_with_caution'
            row['limitations'].extend(continuation['interruption_limitations'])
        require(resolve_continuation(paths[0].parent, verification_storage.read_bytes) == continuation,
                'continuation changed during report replay')
    canonical(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--calibration')
    parser.add_argument('directories', nargs=6)
    args = parser.parse_args()
    result = analyze_task_cohort(args.directories, load(args.plan), load(args.calibration) if args.calibration else None)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
