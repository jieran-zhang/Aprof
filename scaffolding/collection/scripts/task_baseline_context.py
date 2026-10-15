"""Unactivated, replayable baseline Context derivation; no collection or archive.

Planning documents are explicit inputs, never inferred from PMU counters. This
module proves the reviewed GroupNorm and GQA row/tile-loop sync predicate. Every other
predicate stays unknown, including profile predicates without an extractor.
"""
import json
import math
from datetime import datetime
from pathlib import Path
import time

import task_baseline_qualification as baseline
from task_baseline_controller import verify_baseline_qualification
from aprof_runtime.contracts import Context
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.jsonio import content_hash, file_hash, to_primitive
from aprof_runtime.planning import (select_dispatch, validate_planning_context,
    validate_planning_contract, verify_profile_probe, workload_metadata, UNKEYED_MODE)
from timing_admission import require, number

PROTOCOL = 'baseline_context_derivation_v1'
ENABLED_IN_1_0 = False
SYNC = 'predicate.source.sync_inside_tile_loop'
GN_FILES = {
    'op_kernel/group_norm_kernel.asc': 'sha256:e3f8d5d28d47282dfe15053ebbdcc3c30347f9bafd5eb40c2cc831d4f0f5f7dd',
    'op_kernel/group_norm_tiling.h': 'sha256:3c39fc6564c9a8e96dbf1733b4584dc750f12e1cab9b566788c3e640c02a2549',
}
GQA_FILES = {
    'op_kernel/gqa_kernel.asc': 'sha256:03885ce18cc73d88d9f9c12b60d2d02f943401edf216c3507f4653cb96b418f8',
    'op_host/gqa.asc': 'sha256:eade580c0d7f9bef0f473287ea720e0c74fdaacdd43fda1ddf34f04a59628df5',
}
SYNC_RULE = ('SyncAll, PIPE_ALL barrier, or equivalently broad synchronization '
             'executes inside a repeated tile loop')
GRAPH = baseline.bridge.RELEASE / 'skillgraph/versions/v0002/graph.json'
PROBE = Path(__file__).with_name('probe_architecture.py')


def _read(local, reference, *, canonical=False):
    value = json.loads(local.verify_artifact(reference).read_text())
    require(not canonical or content_hash(value) == reference, 'noncanonical context input')
    return value


def _pointer(local, reference):
    return {'path': str(local.verify_artifact(reference)), 'sha256': reference}


def _references(local, value):
    if isinstance(value, dict):
        for child in value.values(): _references(local, child)
    elif isinstance(value, list):
        for child in value: _references(local, child)
    elif isinstance(value, str) and value.startswith('sha256:'):
        local.verify_artifact(value)



def _planning_context(plan, case, profile, parallel, dispatch, profile_ref, parallel_ref, dispatch_ref):
    metadata = workload_metadata(plan['operator'], case['workload'])
    selected = select_dispatch(dispatch, metadata)
    value = dict(schema_version='1.0.0', task_id=plan['operator'] + '-case-' + str(case['case_id']),
        operator=plan['operator'], hardware_fingerprint=profile['hardware_fingerprint'],
        workload=dict(source_hash=plan['source_hashes']['baseline'], metadata=metadata,
            original_metadata_ref=case['metadata_ref'], original_workload=case['workload'],
            case_id=case['case_id'], tiling_key=selected.get('tiling_key'), workload_group=selected['group_id']),
        budget=dict(candidate_limit=1, build_limit=1, timing_limit=1, full_profile_limit=1,
            wall_time_limit_seconds=plan['budget_seconds'], budget_policy='time_only_v1'),
        evidence=dict(optimization_stage='execution', architecture_profile=profile,
            architecture_profile_ref=profile_ref, parallel_plan=parallel, parallel_plan_ref=parallel_ref,
            dispatch_plan=dispatch, dispatch_plan_ref=dispatch_ref))
    if dispatch.get('mode') == UNKEYED_MODE:
        value['workload'].pop('tiling_key', None)
        value['workload']['complete_call_ref'] = content_hash(selected)
    validate_planning_context(Context.from_dict(value), execution=True)
    return value


def _probe_execution(local, reference, profile_ref, plan):
    execution = _read(local, reference)
    job = execution['job']
    require(execution.get('schema_version') == '1.0.0' and execution.get('kind') == 'aprof_execution_report'
            and execution['status'] == 'passed' and type(execution['exit_code']) is int
            and execution['exit_code'] == 0 and not execution.get('error')
            and job['argv'] == [str(baseline.bridge.timing.SUMMARY_PYTHON), str(PROBE),
                '--device', str(plan['device']), '--output', str(local.verify_artifact(profile_ref))]
            and job['environment']['ASCEND_RT_VISIBLE_DEVICES'] == str(plan['physical_device'])
            and job['environment']['APROF_SKILL_LIB'] == str(baseline.bridge.RELEASE),
            'architecture probe execution/device/producer differs')
    start, finish = [datetime.fromisoformat(execution[key].replace('Z', '+00:00'))
                     for key in ('started_at', 'finished_at')]
    require(start.tzinfo is not None and finish.tzinfo is not None and start < finish
            and 0 < number(execution['duration_seconds']) <= number(job['timeout_seconds']),
            'architecture probe execution window differs')
    for key in ('stdout', 'stderr'):
        pointer = execution[key]
        require(_pointer(local, pointer['sha256']) == pointer, 'architecture probe log pointer differs')
    summary = _read(local, execution['stdout']['sha256'])
    require(summary['profile_ref'] == profile_ref and summary['profile'] == str(local.verify_artifact(profile_ref))
            and not summary['errors'], 'architecture probe stdout differs from profile')
    return finish.timestamp()


def unkeyed_dispatch_value(plan, parallel, parallel_ref, *, dispatch_id):
    """Called only after the existing mechanical/source/input plan verifier."""
    require(len(parallel['groups']) == 1, 'complete-call scope requires one declared whole-call algorithm group')
    require([case['case_id'] for case in plan['cases']] == list(range(1,21)), 'complete-call scope needs all original cases')
    return dict(schema_version='1.0.0', dispatch_id=dispatch_id, mode=UNKEYED_MODE,
        scope='declared_workloads_only', operator=plan['operator'],
        source_hash=plan['source_hashes']['candidate'],
        plan_basis_source_hash=plan['source_hashes']['baseline'],
        implementation_source_hash=plan['source_hashes']['candidate'],
        architecture_profile_ref=parallel['architecture_profile_ref'], parallel_plan_ref=parallel_ref,
        source_review_ref=plan['source_review_ref'], declared_workloads=[dict(
            metadata_ref=case['metadata_ref'], workload=workload_metadata(plan['operator'],case['workload']),
            group_id=parallel['groups'][0]['group_id'], role_kernel_names=case['role_kernel_names'])
            for case in plan['cases']])


def _unkeyed_baseline(local, plan_ref, parallel_plan_ref, dispatch_id):
    import task_baseline_build as builder
    plan = baseline.checked_plan(local, plan_ref)
    builder._assembly(local, plan_ref)  # Existing exact source_identity, no build dependency.
    parallel = _read(local, parallel_plan_ref, canonical=True)
    return validate_planning_contract('dispatch_plan', unkeyed_dispatch_value(
        plan, parallel, parallel_plan_ref, dispatch_id=dispatch_id))


def prepare_unkeyed_dispatch(local, *, plan_ref, parallel_plan_ref, dispatch_id):
    return local.register_json(_unkeyed_baseline(local,plan_ref,parallel_plan_ref,dispatch_id))


def _inputs(local, plan_ref, architecture_profile_ref, architecture_execution_ref, parallel_plan_ref, dispatch_plan_ref):
    plan = baseline.checked_plan(local, plan_ref)
    profile = _read(local, architecture_profile_ref, canonical=True)
    raw = _read(local, profile['provenance']['raw_probe_ref'], canonical=True)
    verify_profile_probe(profile, raw)
    require(profile['probe_kind'] == raw['probe_kind'] == 'device'
            and profile['device_id'] == plan['device'] and profile['architecture_id'] == '910c'
            and profile['sdk_version'] == '9.0.0' and not raw.get('errors')
            and profile['hardware_fingerprint'] == content_hash(raw)
            and profile['provenance']['probe_source_ref'] == file_hash(PROBE),
            'baseline Context requires the bound actual A3 architecture probe')
    _references(local, profile)
    for name in ('compile', 'platform_execution'):
        require(type(raw[name]['exit_status']) is int and raw[name]['exit_status'] == 0,
                'architecture probe did not complete')
        local.verify_artifact(raw[name]['log_ref'])
    require(json.loads(local.verify_artifact(raw['platform_execution']['log_ref']).read_text()) == raw['platform'],
            'architecture platform facts differ from original probe stdout')
    _probe_execution(local, architecture_execution_ref, architecture_profile_ref, plan)
    parallel = _read(local, parallel_plan_ref, canonical=True)
    dispatch = _read(local, dispatch_plan_ref, canonical=True)
    for kind, value in (('parallel_plan', parallel), ('dispatch_plan', dispatch)):
        validate_planning_contract(kind, value)
        _references(local, value)
        require(value['operator'] == plan['operator'] and value['source_hash'] == plan['source_hashes']['baseline'],
                'planning evidence differs from original baseline')
    require(parallel['architecture_profile_ref'] == dispatch['architecture_profile_ref'] == architecture_profile_ref
            and dispatch['parallel_plan_ref'] == parallel_plan_ref, 'planning architecture/parent differs')
    if dispatch.get('mode') == UNKEYED_MODE:
        require(dispatch == _unkeyed_baseline(local, plan_ref, parallel_plan_ref, dispatch['dispatch_id']),
                'unkeyed scope differs from mechanical source proof/original metadata')
    for case in plan['cases']:
        _planning_context(plan, case, profile, parallel, dispatch, architecture_profile_ref,
                          parallel_plan_ref, dispatch_plan_ref)
    graph, _ = load_snapshot(GRAPH)
    require(len(graph['predicates']) == 19 and graph['planning_contract'] == 'architecture_parallel_dispatch_v1',
            'unexpected fixed graph contract')
    predicate = next(p for p in graph['predicates'] if p['id'] == SYNC)
    require(predicate['rule'] == SYNC_RULE and predicate['evaluation']['extractor_id'] == 'sync_inside_tile_loop'
            and predicate['evaluation']['mode'] == 'source_match', 'GN predicate semantics changed')
    return plan, profile, parallel, dispatch, graph


def prepare_context_derivation(local, *, plan_ref, architecture_profile_ref, architecture_execution_ref,
                               parallel_plan_ref, dispatch_plan_ref):
    """Freeze derivation inputs before the baseline build; never launch a probe."""
    baseline._local(local)
    plan, *_ = _inputs(local, plan_ref, architecture_profile_ref, architecture_execution_ref,
                      parallel_plan_ref, dispatch_plan_ref)
    require(not (Path(plan['assembly_dir']) / 'build-attempt.json').exists(),
            'Context derivation must precede the baseline build attempt')
    return local.register_json(dict(schema_version=1, protocol=PROTOCOL, plan_ref=plan_ref,
        architecture_profile_ref=architecture_profile_ref, architecture_execution_ref=architecture_execution_ref,
        parallel_plan_ref=parallel_plan_ref,
        dispatch_plan_ref=dispatch_plan_ref, graph_ref=local.register_artifact(GRAPH),
        producer_ref=local.register_artifact(__file__), created_at=time.time()))


def _checked(local, derivation_ref):
    baseline._local(local)
    config = _read(local, derivation_ref, canonical=True)
    require(set(config) == {'schema_version', 'protocol', 'plan_ref', 'architecture_profile_ref', 'architecture_execution_ref',
        'parallel_plan_ref', 'dispatch_plan_ref', 'graph_ref', 'producer_ref', 'created_at'}
        and config['schema_version'] == 1 and config['protocol'] == PROTOCOL
        and config['producer_ref'] == file_hash(__file__) and config['graph_ref'] == file_hash(GRAPH),
        'Context derivation source/graph changed')
    _references(local, config)
    number(config['created_at'])
    return config, _inputs(local, **{key: config[key] for key in (
        'plan_ref', 'architecture_profile_ref', 'architecture_execution_ref', 'parallel_plan_ref', 'dispatch_plan_ref')})


def _gn_sync(local, plan, case):
    if plan['operator'] != 'group_norm' or any(plan['roles']['baseline']['files'].get(name) != digest
                                               for name, digest in GN_FILES.items()):
        return 'unknown', None
    for reference in GN_FILES.values(): local.verify_artifact(reference)
    shape, groups = case['workload']['shape'], case['workload']['num_groups']
    require(len(shape) >= 2 and type(groups) is int and groups > 0 and shape[1] % groups == 0,
            'invalid original GroupNorm grouping')
    elements = shape[1] // groups * math.prod(shape[2:])
    if elements <= 4096: return 'unknown', None
    return True, dict(extractor='exact_original_gn_tile_loop_v1', source_files=GN_FILES,
        metadata_ref=case['metadata_ref'], group_elements=elements, tile_elements=4096,
        tile_iterations=(elements + 4095) // 4096, kernel_line=15, tiling_line=8)


def _gqa_sync(local, plan, case):
    """One Skv row is one disjoint GM/local/GM tile; no barrier-removal claim."""
    if plan['operator'] != 'gqa' or any(plan['roles']['baseline']['files'].get(name) != digest
                                      for name, digest in GQA_FILES.items()):
        return 'unknown', None
    require(plan['case_ids'] == list(range(1, 21))
            and [row['case_id'] for row in plan['cases']] == plan['case_ids']
            and case in plan['cases'], 'GQA diagnosis requires the complete original case roster')
    sources = {name: local.verify_artifact(reference).read_text().splitlines()
               for name, reference in GQA_FILES.items()}
    kernel, host = sources['op_kernel/gqa_kernel.asc'], sources['op_host/gqa.asc']
    # Tiling is defined inline: kernel line 8 and host line 20, not a separate header.
    loop = kernel[20]
    require('struct GqaTiling {' in kernel[7]
            and 'p_.InitBuffer(raw_,t->Skv*sizeof(T))' in kernel[18]
            and 'for(uint64_t r=bid;r<t_->rows;r+=stride)' in loop
            and 'if(GetBlockIdx()!=0)return;uint64_t bid=0,stride=1;' in loop
            and 'DataCopyPad(raw,x_[r*t_->Skv],cp,pad)' in loop
            and 'DataCopyPad(x_[r*t_->Skv],raw,cp)' in loop
            and loop.count('PipeBarrier<PIPE_ALL>()') == 8
            and 't.rows=t.B*t.Nkv*t.G*t.S;' in host[19]
            and 't.G=t.Nq/t.Nkv;' in host[19]
            and 'gqa_softmax<<<t.blocks,nullptr,st>>>' in host[22]
            and 'GqaSoftmax<half>' in kernel[23] and 'GqaSoftmax<bfloat16_t>' in kernel[23],
            'reviewed GQA row-tile source anchors differ')
    metadata = _read(local, case['metadata_ref'])
    workload = baseline.bridge.adapter.base.old.json_contract(
        {key: value for key, value in metadata.items() if key != 'output'})
    require(workload == case['workload'] and metadata['case_id'] == case['case_id'],
            'GQA diagnosis metadata differs from the frozen workload')
    q, k, v = (metadata[name] for name in ('query_shape', 'key_shape', 'value_shape'))
    require(all(isinstance(shape, list) and len(shape) == 4
                and all(type(n) is int and n > 0 for n in shape) for shape in (q, k, v))
            and k == v and q[0] == k[0] and q[3] == k[3]
            and q[2] % k[2] == 0 and q[1] <= k[1]
            and metadata['dtype'] in ('float16', 'bfloat16'), 'invalid original GQA row tiling')
    rows = q[0] * k[2] * (q[2] // k[2]) * q[1]
    if rows <= 1:
        return 'unknown', None
    return True, dict(extractor='exact_original_gqa_row_tile_loop_v1', source_files=GQA_FILES,
        metadata_ref=case['metadata_ref'], tile_elements=k[1], tile_iterations=rows,
        tile_bytes=k[1] * 2, dtype=metadata['dtype'], row_count_formula='B*Nkv*(Nq/Nkv)*S',
        broad_barriers_per_tile=8, kernel_line=21, buffer_line=19, tiling_line=8,
        host_tiling_line=20, host_launch_line=23, dtype_dispatch_line=24,
        scope='source_sync_structure_only', barrier_removal_authorized=False)


def _derive(local, derivation_ref, qualification_ref):
    config, (plan, profile, parallel, dispatch, graph) = _checked(local, derivation_ref)
    saved = _read(local, qualification_ref)
    qualified = verify_baseline_qualification(local, attempt_ref=saved['attempt_ref'], result_ref=saved['result_ref'])
    require(saved == qualified and qualified['valid'] is True and qualified['qualification_passed'] is True
            and qualified['plan_ref'] == config['plan_ref'] and qualified['status'] == 'passed',
            'Context requires independently replayed complete baseline qualification')
    components = qualified['components']
    build = _read(local, components['references']['build_receipt_ref'])
    probe_finished = _probe_execution(local, config['architecture_execution_ref'], config['architecture_profile_ref'], plan)
    require(probe_finished <= config['created_at'] <= number(build['started_at']),
            'Context inputs were chosen after baseline build or before architecture probe completion')
    pmu = components['pmu']
    require(pmu['valid'] is True and pmu['pmu_complete'] is True, 'baseline PMU is not complete')
    contexts, routes = {}, {}
    for case in plan['cases']:
        value = _planning_context(plan, case, profile, parallel, dispatch, config['architecture_profile_ref'],
                                  config['parallel_plan_ref'], config['dispatch_plan_ref'])
        states = {p['id']: 'unknown' for p in graph['predicates']}
        states[SYNC], proof = (_gqa_sync(local, plan, case) if plan['operator'] == 'gqa'
                               else _gn_sync(local, plan, case))
        evidence = value['evidence']
        evidence.update(predicate_states=states,
            baseline_qualification_ref=qualification_ref, context_derivation_ref=derivation_ref,
            predicate_proofs={} if proof is None else {SYNC: proof},
            profile_observations={'status': 'unknown', 'reason': 'case_not_profiled'})
        if case['case_id'] == plan['profile']['case_id']:
            evidence['profile_observations'] = dict(status='verified_baseline_PMU',
                report_ref=components['references']['pmu_ref'], scope=plan['pmu_scope'],
                metric_specs=plan['profile']['metrics'], metrics=pmu['metrics']['baseline'],
                semantics='median across every named-kernel occurrence, then five captures; not whole-call busy time')
        context = Context.from_dict(value)
        contexts[value['task_id']] = value
        routes[value['task_id']] = to_primitive(route_graph(graph, context, selection_mode='argmax'))
    return config, contexts, routes


def _registry(local, derivation_ref, qualification_ref, config, pointers):
    refs = [derivation_ref, qualification_ref, config['plan_ref'], config['architecture_profile_ref'],
            config['architecture_execution_ref'],
            config['parallel_plan_ref'], config['dispatch_plan_ref']]
    return dict(schema_version=1, derivation_ref=derivation_ref,
        graph={'path': str(GRAPH.resolve()), 'sha256': config['graph_ref']},
        contexts={name: dict(context=pointer, baseline_qualification=_pointer(local, qualification_ref),
            evidence=[_pointer(local, reference) for reference in refs]) for name, pointer in pointers.items()})


def build_baseline_contexts(local, *, derivation_ref, qualification_ref, destination):
    config, contexts, _ = _derive(local, derivation_ref, qualification_ref)
    directory = Path(destination)
    require(directory.is_absolute() and directory.resolve() == directory
            and directory.is_relative_to(local.directory.parent), 'Context output escaped task-local workspace')
    directory.mkdir(parents=True, exist_ok=False)
    pointers = {}
    for name, value in contexts.items():
        path = directory / (name + '.json')
        baseline.bridge.save(path, value)
        pointers[name] = _pointer(local, local.register_artifact(path))
    registry = _registry(local, derivation_ref, qualification_ref, config, pointers)
    path = directory / 'route-registry.json'
    baseline.bridge.save(path, registry)
    return local.register_artifact(path)


def replay_baseline_contexts(local, *, derivation_ref, qualification_ref, registry_ref):
    """Recompute every Context/predicate/route; no saved status grants authority."""
    config, contexts, routes = _derive(local, derivation_ref, qualification_ref)
    registry = _read(local, registry_ref)
    require(set(registry.get('contexts', {})) == set(contexts), 'Context case roster differs')
    pointers = {}
    for name, expected in contexts.items():
        pointer = registry['contexts'][name]['context']
        require(set(pointer) == {'path', 'sha256'} and _pointer(local, pointer['sha256']) == pointer
                and _read(local, pointer['sha256']) == expected, 'Context facts/predicates differ from evidence')
        pointers[name] = pointer
    require(registry == _registry(local, derivation_ref, qualification_ref, config, pointers),
            'Context registry qualification/evidence differs')
    return dict(valid=True, contexts=contexts, routes=routes, registry_ref=registry_ref,
                admission_authority=False, archive_performed=False)
