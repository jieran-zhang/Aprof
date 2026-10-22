"""CPU derivation fixtures; qualification/probe samples never claim hardware success."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import task_baseline_context as context
import probe_architecture
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.jsonio import canonical_json
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.planning import MEMORIES


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    local = LocalEvidence(tmp_path / 'records')
    source = context.baseline.bridge.adapter.base.REPO.parent / (
        'validation-graph-base-1.0.0-round2-20261014/evaluation-source-preparation/group_norm/baseline')
    files = {name: local.register_artifact(source / name) for name in context.GN_FILES}
    source_ref = local.register_json({'schema_version': '1.0.0', 'files': files})
    assembly = tmp_path / 'assembly'; assembly.mkdir()
    cases = []
    for cid in range(1, 21):
        # Descriptors only: no tensor allocation or original input generation.
        workload = dict(case_id=cid, shape=[1, 8, 8193], dtype='float16', num_groups=2, epsilon=0.00001)
        cases.append(dict(case_id=cid, workload=workload, metadata_ref=local.register_json(workload)))
    metric = dict(unit='us', file='op_summary*.csv', format='csv', field='aicore_time(us)',
                  row_aggregation='median', aggregation='median')
    plan = dict(operator='group_norm', device=0, physical_device=2, assembly_dir=str(assembly), cases=cases,
        budget_seconds=7200,
        source_hashes={role: source_ref for role in ('baseline', 'candidate')},
        roles={'baseline': {'files': files}}, profile={'case_id': 1, 'metrics': {'aic': metric}},
        pmu_scope={'case_id': 1, 'CPU_fixture_only': True})
    plan_ref = local.register_json(plan)
    def checked(reader, ref):
        assert reader is local and ref == plan_ref
        return json.loads(reader.verify_artifact(ref).read_text())
    monkeypatch.setattr(context.baseline, 'checked_plan', checked)
    platform = dict(npu_arch=2201, core_counts={'aic': 24, 'aiv': 48},
                    memory_bytes={name: 196608 for name in MEMORIES})
    platform_log = tmp_path / 'platform.log'; platform_log.write_text(json.dumps(platform))
    compile_log = tmp_path / 'compile.log'; compile_log.write_text('CPU synthetic probe fixture; no compiler run')
    raw = dict(soc_name='Ascend910_9392', probe_kind='device', device_id=0, errors=[], platform=platform,
        visible_core_counts={'aic': 24, 'aiv': 48}, CPU_fixture_only=True,
        compile={'exit_status': 0, 'log_ref': local.register_artifact(compile_log)},
        platform_execution={'exit_status': 0, 'log_ref': local.register_artifact(platform_log)})
    raw_ref = local.register_json(raw)
    profile = probe_architecture.build_profile(raw, '9.0.0',
        {'probe_source_ref': local.register_artifact(context.PROBE), 'raw_probe_ref': raw_ref, 'sdk_header_ref': None})
    profile_path = tmp_path / 'architecture.json'; profile_path.write_text(canonical_json(profile))
    profile_ref = local.register_artifact(profile_path)
    probe_stdout = tmp_path / 'probe.stdout'; probe_stderr = tmp_path / 'probe.stderr'
    probe_stdout.write_text(json.dumps({'profile_ref': profile_ref, 'profile': str(profile_path), 'errors': []}))
    probe_stderr.write_text('CPU synthetic supervisor fixture; never executed a probe')
    probe_execution = dict(schema_version='1.0.0', kind='aprof_execution_report', status='passed',
        exit_code=0, error=None, duration_seconds=1.0,
        started_at='2020-01-01T00:00:00+00:00', finished_at='2020-01-01T00:00:01+00:00',
        job={'argv': [str(context.baseline.bridge.timing.SUMMARY_PYTHON), str(context.PROBE), '--device', '0',
                      '--output', str(profile_path)], 'timeout_seconds': 60,
             'environment': {'ASCEND_RT_VISIBLE_DEVICES': '2', 'APROF_SKILL_LIB': str(context.baseline.bridge.RELEASE)}},
        stdout={'path': str(probe_stdout), 'sha256': local.register_artifact(probe_stdout)},
        stderr={'path': str(probe_stderr), 'sha256': local.register_artifact(probe_stderr)})
    execution_ref = local.register_json(probe_execution)
    group = dict(group_id='original', algorithm='original GroupNorm', task_partition='original contiguous groups',
        ownership='original one writer', reduction='original two passes', synchronization='original dependency barriers',
        workspace_bytes=0, workspace_formula='0', required_capabilities=['vector'], memory_requirements={'UB': 1024},
        alternatives=['unchanged original'], selection_evidence=[source_ref])
    parallel = dict(schema_version='1.0.0', plan_id='original', operator='group_norm', source_hash=source_ref,
        architecture_profile_ref=profile_ref, semantic_invariants=['original output'],
        precision_invariants=['original precision'], groups=[group])
    parallel_ref = local.register_json(parallel)
    dispatch = dict(schema_version='1.0.0', dispatch_id='original', operator='group_norm', source_hash=source_ref,
        architecture_profile_ref=profile_ref, parallel_plan_ref=parallel_ref, entries=[],
        fallback=dict(group_id='original', tiling_key=0, kernel_entry='group_norm', conditions=[], required_capabilities=[]))
    dispatch_ref = local.register_json(dispatch)
    kwargs = dict(plan_ref=plan_ref, architecture_profile_ref=profile_ref, architecture_execution_ref=execution_ref,
                  parallel_plan_ref=parallel_ref, dispatch_plan_ref=dispatch_ref)
    derivation_ref = context.prepare_context_derivation(local, **kwargs)
    config = json.loads(local.verify_artifact(derivation_ref).read_text())
    build_ref = local.register_json({'started_at': config['created_at'] + 1})
    pmu_ref = local.register_json({'CPU_fixture_only': 'full PMU boundary mocked'})
    qualification = dict(valid=True, status='passed', qualification_passed=True, plan_ref=plan_ref,
        attempt_ref=local.register_json({'CPU_fixture_only': 'actual dispatcher boundary mocked'}),
        result_ref=local.register_json({'CPU_fixture_only': 'full qualification boundary mocked'}),
        components={'references': {'build_receipt_ref': build_ref, 'pmu_ref': pmu_ref},
            'pmu': {'valid': True, 'pmu_complete': True, 'metrics': {'baseline': {
                'aprof_baseline_group_norm_kernel': {'aic': {'status': 'known', 'stable': True,
                    'median': 1.0, 'cv': 0.0, 'capture_values': [1.0]*5}}}}}})
    qualification_ref = local.register_json(qualification)
    calls = []
    def replay(reader, *, attempt_ref, result_ref):
        calls.append((attempt_ref, result_ref))
        assert reader is local and (attempt_ref, result_ref) == (qualification['attempt_ref'], qualification['result_ref'])
        return deepcopy(qualification)
    original_replay = context.verify_baseline_qualification
    monkeypatch.setattr(context, 'verify_baseline_qualification', replay)
    return locals()


def build(f):
    return context.build_baseline_contexts(f['local'], derivation_ref=f['derivation_ref'],
        qualification_ref=f['qualification_ref'], destination=f['tmp_path'] / 'contexts')


def test_original_gn_exact_predicate_and_existing_graph_route_replay(fixture):
    f = fixture; ref = build(f); local = f['local']; sequence = local._sequence
    result = context.replay_baseline_contexts(local, derivation_ref=f['derivation_ref'],
        qualification_ref=f['qualification_ref'], registry_ref=ref)
    assert len(result['contexts']) == 20 and len(f['calls']) == 2 and local._sequence == sequence
    assert result['valid'] and not result['admission_authority'] and not result['archive_performed']
    for name, value in result['contexts'].items():
        assert value['budget']['wall_time_limit_seconds'] == f['plan']['budget_seconds']
        evidence = value['evidence']; states = evidence['predicate_states']
        assert len(states) == 19 and states[context.SYNC] is True
        assert all(state == 'unknown' for key, state in states.items() if key != context.SYNC)
        assert evidence['predicate_proofs'][context.SYNC]['tile_iterations'] == 9
        route = result['routes'][name]
        assert next(c for c in route['candidates'] if c['edge_id'] == route['selected_edge_id'])['target_id'] == 'transformation.narrow_sync_scope'
    first = result['contexts']['group_norm-case-1']['evidence']['profile_observations']
    assert first['status'] == 'verified_baseline_PMU'
    assert result['contexts']['group_norm-case-2']['evidence']['profile_observations']['status'] == 'unknown'
    assert not list(f['tmp_path'].rglob('*.sqlite'))


@pytest.mark.parametrize('defect', ['predicate', 'omitted_case', 'workload', 'pmu'])
def test_saved_context_cannot_inject_facts_or_omit_cases(fixture, defect):
    f = fixture; local = f['local']; registry = json.loads(local.verify_artifact(build(f)).read_text())
    if defect == 'omitted_case': registry['contexts'].pop('group_norm-case-20')
    else:
        entry = registry['contexts']['group_norm-case-1']; value = context._read(local, entry['context']['sha256'])
        if defect == 'predicate': value['evidence']['predicate_states']['predicate.profile.overlap_low'] = True
        elif defect == 'workload': value['workload']['metadata']['shape'] = [1]
        else: value['evidence']['profile_observations']['metrics'] = {'invented': 1}
        entry['context'] = context._pointer(local, local.register_json(value))
    with pytest.raises(ValueError, match='Context'):
        context.replay_baseline_contexts(local, derivation_ref=f['derivation_ref'],
            qualification_ref=f['qualification_ref'], registry_ref=local.register_json(registry))


@pytest.mark.parametrize('defect', ['raw_probe', 'source', 'capacity', 'late', 'missing'])
def test_missing_changed_or_postbuild_derivation_rejected(fixture, defect):
    f = fixture; local = f['local']; kwargs = dict(f['kwargs'])
    if defect == 'raw_probe':
        value = deepcopy(f['profile']); value['core_counts']['aiv'] += 1
        kwargs['architecture_profile_ref'] = local.register_json(value)
    elif defect == 'source':
        value = deepcopy(f['parallel']); value['source_hash'] = local.register_json({'foreign': True})
        kwargs['parallel_plan_ref'] = local.register_json(value)
    elif defect == 'capacity':
        value = deepcopy(f['parallel']); value['groups'][0]['memory_requirements']['UB'] = 999999999
        kwargs['parallel_plan_ref'] = local.register_json(value)
        dispatch = deepcopy(f['dispatch']); dispatch['parallel_plan_ref'] = kwargs['parallel_plan_ref']
        kwargs['dispatch_plan_ref'] = local.register_json(dispatch)
    elif defect == 'late': (f['assembly'] / 'build-attempt.json').write_text('{}')
    else: kwargs['dispatch_plan_ref'] = 'sha256:' + '0'*64
    with pytest.raises(StoreError if defect == 'missing' else (ValueError, ContractError)):
        context.prepare_context_derivation(local, **kwargs)


def test_passed_summary_cannot_replace_real_qualification(fixture, monkeypatch):
    f = fixture
    monkeypatch.setattr(context, 'verify_baseline_qualification', f['original_replay'])
    with pytest.raises((KeyError, ValueError, ContractError)):
        build(f)
    assert not (f['tmp_path']/'contexts').exists()


@pytest.mark.parametrize('defect', ['exit', 'physical_device', 'argv', 'stdout'])
def test_architecture_claim_requires_original_successful_probe_execution(fixture, defect):
    f = fixture; local = f['local']; value = deepcopy(f['probe_execution'])
    if defect == 'exit': value['exit_code'] = 2
    elif defect == 'physical_device': value['job']['environment']['ASCEND_RT_VISIBLE_DEVICES'] = '3'
    elif defect == 'argv': value['job']['argv'][1] = '/untrusted/probe.py'
    else:
        reference = local.register_json({'profile_ref': f['plan_ref'], 'profile': str(f['profile_path']), 'errors': []})
        value['stdout'] = context._pointer(local, reference)
    with pytest.raises(ValueError, match='architecture probe'):
        context.prepare_context_derivation(local, **{**f['kwargs'],
            'architecture_execution_ref': local.register_json(value)})


def test_gn_unknown_for_nonrepeating_or_unreviewed_source(fixture):
    f = fixture; case = deepcopy(f['cases'][0]); case['workload']['shape'] = [1, 8, 1]
    assert context._gn_sync(f['local'], f['plan'], case) == ('unknown', None)
    plan = deepcopy(f['plan']); plan['roles']['baseline']['files'].pop('op_kernel/group_norm_tiling.h')
    assert context._gn_sync(f['local'], plan, f['cases'][0]) == ('unknown', None)


@pytest.mark.parametrize('operator,value,shape,dtype', [
    ('dynamic_quant', {'shape': [2, 8], 'dtype': 'bfloat16'}, [2, 8], 'bfloat16'),
    ('gelu', {'shape': [3, 7], 'dtype': 'float32', 'approximate': 'tanh'}, [3, 7], 'float32'),
    ('group_norm', {'shape': [1, 8, 9], 'dtype': 'float16', 'num_groups': 2}, [1, 8, 9], 'float16'),
    ('gqa', {'query_shape': [1, 2, 4, 8], 'key_shape': [1, 3, 2, 8], 'value_shape': [1, 3, 2, 8],
             'dtype': 'bfloat16', 'is_causal': False}, [1, 2, 4, 8], 'bfloat16'),
    ('weight_quant_batch_matmul', {'input_shape': [[2, 4], [4, 8], [8], None, [8]],
        'dtype': ['float16', 'int8', 'float16', None, 'float32']}, [2, 4], 'float16')])
def test_original_workload_projection_preserves_multikernel_dimensions(operator, value, shape, dtype):
    result = context.workload_metadata(operator, value)
    assert result['shape'] == shape and result['dtype'] == dtype
    if operator == 'gqa': assert result['attributes']['key_shape_2'] == 2
    if operator == 'weight_quant_batch_matmul':
        assert result['attributes']['input_present_3'] is False
        assert result['attributes']['input_dtype_4'] == 'float32'
