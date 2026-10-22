"""Original GQA source and 20 workload descriptors; no inputs or device run."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

import task_baseline_context as context
from aprof_runtime.errors import StoreError
from aprof_runtime.local_evidence import LocalEvidence


# Frozen original case geometry/attributes; no tensor files or temporary assembly.
# Each tuple is (case_id, query_shape, key/value_shape, dtype, causal, scale).
ORIGINAL_CASES = (
    (1, [2, 128, 32, 128], [2, 128, 8, 128], 'float16', True, -1.0),
    (2, [2, 128, 48, 128], [2, 128, 4, 128], 'float16', False, -1.0),
    (3, [2, 128, 128, 128], [2, 128, 8, 128], 'float16', True, -1.0),
    (4, [4, 256, 64, 128], [4, 256, 8, 128], 'bfloat16', False, -1.0),
    (5, [2, 128, 32, 256], [2, 128, 8, 256], 'float16', True, -1.0),
    (6, [2, 256, 128, 256], [2, 256, 8, 256], 'bfloat16', True, -1.0),
    (7, [2, 128, 32, 128], [2, 256, 8, 128], 'bfloat16', False, -1.0),
    (8, [4, 1024, 32, 128], [4, 1024, 8, 128], 'float16', True, -1.0),
    (9, [4, 512, 64, 128], [4, 512, 8, 128], 'bfloat16', False, -1.0),
    (10, [4, 512, 128, 128], [4, 512, 8, 128], 'bfloat16', True, -1.0),
    (11, [16, 1, 32, 128], [16, 2048, 8, 128], 'float16', False, -1.0),
    (12, [16, 1, 96, 128], [16, 2048, 8, 128], 'bfloat16', False, -1.0),
    (13, [60, 1, 32, 128], [60, 2048, 8, 128], 'float16', False, -1.0),
    (14, [128, 1, 128, 128], [128, 512, 8, 128], 'float16', False, -1.0),
    (15, [60, 1, 32, 256], [60, 1024, 8, 256], 'float16', False, -1.0),
    (16, [60, 2, 32, 128], [60, 2048, 8, 128], 'float16', True, -1.0),
    (17, [128, 4, 128, 128], [128, 512, 8, 128], 'float16', True, -1.0),
    (18, [2, 128, 32, 128], [2, 128, 1, 128], 'float16', False, -1.0),
    (19, [2, 128, 32, 128], [2, 128, 32, 128], 'bfloat16', True, -1.0),
    (20, [2, 128, 32, 128], [2, 128, 8, 128], 'bfloat16', True, 0.08838),
)


@pytest.fixture
def fixture(tmp_path):
    local = LocalEvidence(tmp_path / 'records')
    source = Path(__file__).resolve().parents[1] / 'benchmarks/cannbench/operators/gqa'
    # Reproduce the existing protected timer instrumentation; no compilation.
    old = context.baseline.bridge.adapter.base.old
    host = tmp_path / 'gqa.asc'
    host.write_text(old.instrument_text((source / 'op_host/gqa.asc').read_text(), 'gqa'))
    files = {name: local.register_artifact(host if name.startswith('op_host/') else source / name)
             for name in context.GQA_FILES}
    assert files == context.GQA_FILES
    cases = []
    for cid, query, key, dtype, causal, scale in deepcopy(ORIGINAL_CASES):
        metadata = dict(case_id=cid, query_shape=query, key_shape=key, value_shape=list(key),
                        dtype=dtype, is_causal=causal, scaleValue=scale, output_shape=list(query))
        workload = old.json_contract(metadata)
        cases.append(dict(case_id=cid, metadata_ref=local.register_json(metadata), workload=workload))
    plan = dict(operator='gqa', case_ids=list(range(1, 21)), cases=cases,
                roles={'baseline': {'files': files}})
    return local, plan


def test_all_twenty_original_row_tiles_bind_actual_source_and_metadata(fixture):
    local, plan = fixture
    sequence = local._sequence
    rows = []
    dtypes = set()
    for case in plan['cases']:
        state, proof = context._gqa_sync(local, plan, case)
        assert state is True
        metadata = context._read(local, case['metadata_ref'])
        b, s, nq, _ = metadata['query_shape']
        assert proof['tile_iterations'] == b * s * nq > 1
        assert proof['tile_elements'] == metadata['key_shape'][1]
        assert proof['tile_bytes'] == 2 * proof['tile_elements']
        assert proof['source_files'] == context.GQA_FILES
        assert proof['metadata_ref'] == case['metadata_ref']
        assert proof['broad_barriers_per_tile'] == 8
        assert proof['scope'] == 'source_sync_structure_only'
        assert proof['barrier_removal_authorized'] is False
        rows.append(proof['tile_iterations']); dtypes.add(proof['dtype'])
    assert min(rows) == 512 and max(rows) == 262144
    assert dtypes == {'float16', 'bfloat16'}
    assert local._sequence == sequence  # Derivation is read-only.


@pytest.mark.parametrize('name', list(context.GQA_FILES))
def test_different_or_missing_source_stays_unknown(fixture, tmp_path, name):
    local, plan = fixture
    changed = tmp_path / Path(name).name
    changed.write_bytes(local.verify_artifact(context.GQA_FILES[name]).read_bytes() + b'\n// changed\n')
    plan['roles']['baseline']['files'][name] = local.register_artifact(changed)
    assert context._gqa_sync(local, plan, plan['cases'][0]) == ('unknown', None)
    plan['roles']['baseline']['files'].pop(name)
    assert context._gqa_sync(local, plan, plan['cases'][0]) == ('unknown', None)


@pytest.mark.parametrize('mutation', ['loop', 'barrier', 'tiling'])
def test_actual_bytes_cannot_change_under_original_hash(fixture, tmp_path, mutation):
    local, plan = fixture
    name = 'op_host/gqa.asc' if mutation == 'tiling' else 'op_kernel/gqa_kernel.asc'
    ref = context.GQA_FILES[name]
    raw = local.verify_artifact(ref).read_text()
    before, after = {'loop': ('r<t_->rows', 'r<1'), 'barrier': ('PIPE_ALL', 'PIPE_V'),
                     'tiling': ('t.rows=t.B*t.Nkv*t.G*t.S;', 't.rows=1;')}[mutation]
    assert before in raw
    changed = tmp_path / 'tampered.asc'; changed.write_text(raw.replace(before, after))
    local._paths[ref] = changed  # Malicious index claim; actual reader must hash-reject it.
    with pytest.raises(StoreError):
        context._gqa_sync(local, plan, plan['cases'][0])


@pytest.mark.parametrize('mutation', ['workload_rows', 'metadata_bytes', 'case_omitted', 'case_repeated'])
def test_changed_case_binding_or_incomplete_roster_rejected(fixture, tmp_path, mutation):
    local, plan = fixture
    if mutation == 'workload_rows': plan['cases'][0]['workload']['query_shape'][1] += 1
    elif mutation == 'metadata_bytes':
        ref = plan['cases'][0]['metadata_ref']
        raw = context._read(local, ref); raw['query_shape'][1] += 1
        changed = tmp_path / 'metadata.json'; changed.write_text(json.dumps(raw)); local._paths[ref] = changed
    elif mutation == 'case_omitted': plan['cases'].pop()
    else: plan['cases'][-1] = deepcopy(plan['cases'][0])
    with pytest.raises((ValueError, StoreError)):
        context._gqa_sync(local, plan, plan['cases'][0])


def test_one_row_is_unknown_even_when_profile_claims_overlap(fixture):
    local, plan = fixture
    case = plan['cases'][0]
    metadata = context._read(local, case['metadata_ref'])
    metadata['query_shape'] = [1, 1, 1, 128]
    metadata['key_shape'] = metadata['value_shape'] = [1, 1, 1, 128]
    case['metadata_ref'] = local.register_json(metadata)
    case['workload'] = context.baseline.bridge.adapter.base.old.json_contract(
        {key: value for key, value in metadata.items() if key != 'output'})
    plan['profile'] = {'predicate.profile.overlap_low': True, 'claimed_gain': 100}
    assert context._gqa_sync(local, plan, case) == ('unknown', None)


def test_profile_claim_does_not_change_the_source_proof(fixture):
    local, plan = fixture
    actual = context._gqa_sync(local, plan, plan['cases'][0])
    plan['profile'] = {'predicate.profile.overlap_low': True, 'claimed_gain': 100}
    assert context._gqa_sync(local, plan, plan['cases'][0]) == actual
    assert 'overlap_low' not in json.dumps(actual)


@pytest.mark.parametrize('shape', [[1, 0, 4, 128], [1, 32, 3, 128], [1, 100000, 4, 128]])
def test_inconsistent_original_shape_cannot_prove_a_row_loop(fixture, shape):
    local, plan = fixture
    case = plan['cases'][0]; metadata = context._read(local, case['metadata_ref'])
    metadata['query_shape'] = shape
    case['metadata_ref'] = local.register_json(metadata)
    case['workload'] = context.baseline.bridge.adapter.base.old.json_contract(
        {key: value for key, value in metadata.items() if key != 'output'})
    with pytest.raises(ValueError, match='row tiling'):
        context._gqa_sync(local, plan, case)
